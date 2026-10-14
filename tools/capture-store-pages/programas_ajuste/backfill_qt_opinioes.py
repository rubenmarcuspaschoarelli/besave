"""
Backfill de QT_OPINIOES/DS_AVALIACAO_GERAL para ofertas do Mercado Livre
capturadas ANTES desses 2 campos existirem (main.py so passou a captura-los
ao vivo em 2026-09-02, ver stores/mercadolivre.py). Ao contrario do
DS_URL_BESAVE (derivavel da DS_URL_FINAL ja gravada), esses 2 campos exigem
REABRIR A PAGINA DE VERDADE -- nao tem como recuperar do que ja esta no
banco. Por isso e MUITO mais lento que os outros backfills (Playwright real,
~1 pagina por vez, nao e so banco).

So atualiza as 2 colunas (UPDATE direto na tabela, sem passar pela SP) -- nao
toca em mais nada da linha, evita o risco do incidente do dict parcial (ver
resumo.md / memoria).

Alvo (revisto 2026-10-13): so ofertas ATIVAS em BESAVE.OFERTA cujo PRODUTO
tambem nao tem nenhum dos 2 campos (se outra oferta ja preencheu o produto,
nao precisa), mais recentes primeiro, 1 pagina por produto. Achou: grava na
fila E no PRODUTO (NVL -- nunca apaga o que ja existe, mesmo criterio da
STP_PRODUTO_UPSERT).

Retomavel: toda oferta tentada (achou, nao tinha opinioes, pagina fora) vai
para conf/backfill_qt_opinioes_tentativas.json e nao e repetida (--retentar
ignora). Parede de login do ML (account-verification) ou captcha: o script
PARA na hora (sem marcar a oferta) -- logar na janela e rodar de novo.
Rodar em lotes com --limite e recomendado (site real, evita rajada).
NAO rodar junto com o main.py --monitorar (perfil .chrome_perfil compartilhado).

Uso:
    .venv/Scripts/python.exe backfill_qt_opinioes.py --limite 50
    .venv/Scripts/python.exe backfill_qt_opinioes.py            # todas (LENTO -- milhares de paginas)
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import json
import os
import random
import sys
import time

from playwright.sync_api import sync_playwright

from core.oracle_db import OracleDB, _num_contador
from core.browser import launch_persistent
from stores.mercadolivre import MercadoLivreStore

LOTE_COMMIT = 20
PAUSA_ENTRE_OFERTAS = (4, 8)   # segundos, aleatorio -- evita rajada anti-bot (ver memoria)
PAUSA_A_CADA = 15              # ofertas
PAUSA_LONGA = (60, 90)         # segundos, a cada PAUSA_A_CADA ofertas
TENTATIVAS_PATH = os.path.join('conf', 'backfill_qt_opinioes_tentativas.json')
MARCAS_BLOQUEIO = ('verify/', 'account-verification', 'captcha')


def _ler_tentativas():
    try:
        with open(TENTATIVAS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _gravar_tentativas(t):
    tmp = TENTATIVAS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    os.replace(tmp, TENTATIVAS_PATH)


def _ler_pendentes(db, limite, tentativas, retentar=False):
    cur = db._conn.cursor()
    sql = ("SELECT f.ID_OFERTA, f.DS_URL_FINAL, o.ID_PRODUTO "
           "  FROM OFERTA_FILA_CAPTURA f JOIN OFERTA o ON o.ID_OFERTA = f.ID_OFERTA "
           "  LEFT JOIN PRODUTO p ON p.ID_PRODUTO = o.ID_PRODUTO "
           " WHERE o.ST_ATIVO = 1 AND f.ST_CAPTURA = '1' "
           "   AND LOWER(f.DS_URL_FINAL) LIKE '%mercadolivre.com.br%' "
           "   AND f.QT_OPINIOES IS NULL AND f.DS_AVALIACAO_GERAL IS NULL "
           "   AND p.QT_OPINIOES IS NULL AND p.DS_AVALIACAO_GERAL IS NULL "
           " ORDER BY f.ID_OFERTA DESC")
    try:
        cur.execute(sql)
        linhas = cur.fetchall()
    finally:
        cur.close()
    if not retentar:
        linhas = [r for r in linhas if str(r[0]) not in tentativas]
    # Mesmo produto em 2 ofertas: 1 pagina so.
    vistos, out = set(), []
    for r in linhas:
        if r[2] is None or r[2] not in vistos:
            out.append(r)
            vistos.add(r[2])
    return out[:limite] if limite and limite > 0 else out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--limite', type=int, default=0,
                     help='Processa no maximo N ofertas (0 = todas -- LENTO).')
    ap.add_argument('--retentar', action='store_true',
                    help='Inclui as ja tentadas (conf/backfill_qt_opinioes_tentativas.json).')
    ap.add_argument('--dry-run', action='store_true', dest='dry_run')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    tentativas = _ler_tentativas()
    linhas = _ler_pendentes(db, args.limite, tentativas, args.retentar)
    print(f'{len(linhas)} oferta(s) ML p/ rescanear QT_OPINIOES/DS_AVALIACAO_GERAL'
          f' ({len(tentativas)} ja tentada(s) no arquivo).')
    if args.dry_run or not linhas:
        db.desconectar()
        return

    store = MercadoLivreStore()
    atualiza = db._conn.cursor()
    encontrados = 0
    processados = 0
    erros_pagina = 0

    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        bloqueado = False
        for id_oferta, url, id_produto in linhas:
            processados += 1
            quando = time.strftime('%d/%m %H:%M:%S')
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                page.wait_for_selector(store.ready_selector, timeout=15000)
                page.wait_for_timeout(1500)
            except Exception as e:
                if any(m in page.url for m in MARCAS_BLOQUEIO):
                    bloqueado = True
                    print(f'[oferta {id_oferta}] PAREDE DE LOGIN/CAPTCHA: {page.url[:80]}')
                    print('  >> Faca login na janela do Chrome e rode o script de novo.')
                    break
                erros_pagina += 1
                tentativas[str(id_oferta)] = {'resultado': f'pagina fora: {type(e).__name__}',
                                              'quando': quando}
                _gravar_tentativas(tentativas)
                print(f'[oferta {id_oferta}] pagina indisponivel/expirada: {type(e).__name__}')
                continue

            qt_raw = av_raw = ''
            try:
                loc = page.locator('.total-opinion')
                if loc.count():
                    qt_raw = loc.first.inner_text()
            except Exception:
                pass
            try:
                loc = page.locator('.ui-review-capability__summary__plain_text__summary_container')
                if loc.count():
                    av_raw = loc.first.inner_text()
            except Exception:
                pass

            qt = _num_contador(qt_raw) if qt_raw else None
            av = av_raw.strip() or None

            if qt is not None or av is not None:
                atualiza.execute(
                    "UPDATE OFERTA_FILA_CAPTURA SET QT_OPINIOES=:qt, DS_AVALIACAO_GERAL=:av "
                    "WHERE ID_OFERTA=:id",
                    {'qt': qt, 'av': av, 'id': int(id_oferta)},
                )
                if id_produto is not None:
                    atualiza.execute(
                        "UPDATE PRODUTO SET QT_OPINIOES = NVL(:qt, QT_OPINIOES), "
                        "       DS_AVALIACAO_GERAL = NVL(:av, DS_AVALIACAO_GERAL) "
                        " WHERE ID_PRODUTO = :prod",
                        {'qt': qt, 'av': av, 'prod': int(id_produto)})
                encontrados += 1
                resultado = f'ok qt={qt} resumo={"sim" if av else "nao"}'
                print(f'[oferta {id_oferta}] qt_opinioes={qt} avaliacao_geral={"sim" if av else "nao"}')
            else:
                resultado = 'sem opinioes/resumo'
                print(f'[oferta {id_oferta}] sem opinioes/resumo (produto com poucas avaliacoes)')
            db._conn.commit()
            tentativas[str(id_oferta)] = {'resultado': resultado, 'quando': quando}
            _gravar_tentativas(tentativas)

            if processados % LOTE_COMMIT == 0:
                db._conn.commit()
                print(f'  ...{processados}/{len(linhas)} processada(s), commit.')

            if processados % PAUSA_A_CADA == 0 and processados < len(linhas):
                pausa = random.uniform(*PAUSA_LONGA)
                print(f'  ...pausa longa de {pausa:.0f}s (anti-bot).')
                time.sleep(pausa)
            else:
                time.sleep(random.uniform(*PAUSA_ENTRE_OFERTAS))

        ctx.close()

    db._conn.commit()
    if bloqueado:
        print('\nINTERROMPIDO na parede de login/captcha do ML.')
    print(f'\n{encontrados}/{processados} tinham QT_OPINIOES ou DS_AVALIACAO_GERAL '
          f'({erros_pagina} pagina(s) indisponivel/expirada).')
    atualiza.close()
    db.desconectar()


if __name__ == '__main__':
    main()
