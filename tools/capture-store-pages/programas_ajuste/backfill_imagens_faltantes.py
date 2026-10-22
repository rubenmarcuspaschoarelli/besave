"""
Backfill das ofertas SEM imagem no site (2026-10-08): BESAVE.OFERTA cujo
s3/ofertas/img/<ID>/<ID>.webp nao existe -- o site mostra o placeholder.

Diagnostico (08/10, 499 ofertas levantadas pelo usuario): TODAS chegaram do
WhatsApp SEM foto (OFERTA_FILA_CAPTURA.DS_IMAGEM_OFERTA nulo), e quase todas
sao de grupos NAO marcados com "usa_imagem_loja" (Promos da Ly, diaenoite) --
nesses grupos a imagem do site vinha so do WhatsApp, entao ninguem a gerava.
Amazon/ML ate tinham as fotos capturadas em destino/img/<ID>/; a Shopee nem
isso (a ShopeeStore nao baixava galeria ate hoje). O main.py agora preenche
esse buraco ao vivo (core/imagens_oferta.tem_imagem_publicada); este script
cuida do historico.

Por oferta (ID DECRESCENTE), mesma sessao/perfil do main.py:
  1. reabre a pagina do produto e RECAPTURA tudo (preco e demais campos ->
     STP_OFERTA_FILA_CAPTURA_UPDATE -> PRODUTO -> CUPOM -> BESAVE.OFERTA,
     mesmo _gravar_completo do backfill_url_afiliado.py). Datas (DT_OFERTA/
     DT_CAPTACAO) NAO mudam -- sao da mensagem original. Se o preco da
     pagina (menor entre preco/recorrencia/espere-e-economize) ficou MENOR
     que OFERTA.VL_PRECO_POR, grava esse preco em OFERTA.VL_PRECO_POR,
     recalcula o min/max do PRODUTO e zera OFERTA.DT_PUBLICACAO_SITE (o site
     republica a oferta ja com o preco novo);
  2. baixa a galeria de novo p/ destino/img/<ID>/ (troca a pasta inteira so
     se veio pelo menos 1 foto; senao a antiga fica);
  3. publica a 1a FOTO (pula video/GIF animado) em s3/ofertas/img/<ID>/ e as
     fotos na pasta do produto (core/imagens_produto).
Se a pagina nao abre mais (anuncio pausado, link morto), ainda tenta publicar
a partir das fotos que ja estavam em destino/img/<ID>/.

Nunca sobrescreve uma imagem do site que ja existe, exceto nos grupos
"usa_imagem_loja" (mesma regra do main.py).

Parede de bloqueio/captcha (Shopee 'verify/', ML 'account-verification'): o
script PARA e pede para resolver na janela aberta, depois tenta de novo.

NAO rodar junto com o main.py (perfil .chrome_perfil compartilhado).

Uso:
    .venv/Scripts/python.exe backfill_imagens_faltantes.py --dry-run
    .venv/Scripts/python.exe backfill_imagens_faltantes.py --so-local          # sem navegador: so publica o que ja esta em disco
    .venv/Scripts/python.exe backfill_imagens_faltantes.py --lote 20           # recaptura completa, 20 ofertas
    .venv/Scripts/python.exe backfill_imagens_faltantes.py --lojas shopee --lote 30
    .venv/Scripts/python.exe backfill_imagens_faltantes.py --ids lista.txt     # so esses IDs (sem imagem no site)
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import json
import os
import random
import shutil
import sys
import time
from collections import Counter
from datetime import datetime

from core import registry, estado, imagens_oferta, imagens_produto, afiliados
from core.oracle_db import OracleDB, _num, _recorrencia
from core.caminhos import IMG_DIR

DESTINO_IMG = IMG_DIR
TENTATIVAS_PATH = os.path.join('conf', 'backfill_imagens_faltantes_tentativas.json')
# Ofertas ja RECAPTURADAS com dados ok: com --ids a lista nao filtra por
# imagem no site, entao sem isto cada lote repetiria os mesmos IDs do topo.
FEITAS_PATH = os.path.join('conf', 'backfill_imagens_faltantes_feitas.json')
PAUSA = {'shopee': (15, 25)}          # Shopee: anti-bot mais sensivel
PAUSA_PADRAO = (4, 8)
PAUSA_A_CADA = 15
PAUSA_LONGA = (60, 90)


def _ler_tentativas():
    try:
        with open(TENTATIVAS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _ler_feitas():
    try:
        with open(FEITAS_PATH, encoding='utf-8') as f:
            return set(json.load(f))
    except Exception:  # noqa: BLE001
        return set()


def _gravar_feitas(feitas):
    with open(FEITAS_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted(feitas), f)


def _gravar_tentativas(t):
    with open(TENTATIVAS_PATH, 'w', encoding='utf-8') as f:
        json.dump(t, f, ensure_ascii=False, indent=1)


def _ler_alvos(db, ids_filtro):
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT o.ID_OFERTA, o.ID_PRODUTO, f.DS_ORIGEM, "
            "       NVL(f.DS_URL_FINAL, f.DS_URL_ORIGEM) "
            "  FROM OFERTA o JOIN OFERTA_FILA_CAPTURA f ON f.ID_OFERTA = o.ID_OFERTA "
            " WHERE o.ST_ATIVO = 1 "
            " ORDER BY o.ID_OFERTA DESC")
        linhas = cur.fetchall()
    finally:
        cur.close()
    out = []
    for id_oferta, id_produto, origem, url in linhas:
        id_oferta = int(id_oferta)
        if ids_filtro is not None and id_oferta not in ids_filtro:
            continue
        # Sem --ids: so quem nao tem imagem no site. Com --ids: a lista manda
        # (permite recapturar os dados de quem ja ganhou a imagem do disco).
        if ids_filtro is None and imagens_oferta.tem_imagem_publicada(id_oferta):
            continue
        out.append({'id': id_oferta, 'id_produto': id_produto, 'origem': origem,
                    'url': url or '', 'loja': registry.resolver_loja(url or '')})
    return out


def _publicar(id_oferta, origem, pasta):
    """Imagem do site a partir da 1a foto de `pasta`. Respeita a regra do
    main.py: so sobrescreve imagem existente nos grupos usa_imagem_loja."""
    if imagens_oferta.tem_imagem_publicada(id_oferta) and not estado.usa_imagem_loja(origem):
        return 'img_site=ja_tinha'
    foto = imagens_oferta.primeira_imagem(pasta)
    if not foto:
        return 'img_site=SEM_FOTO'
    return ('img_site=ok' if imagens_oferta.publicar_imagem_oferta(id_oferta, foto)
            else 'img_site=FALHOU')


def _baixar_galeria(store, page, id_oferta):
    """Baixa p/ uma pasta nova e so troca a antiga se veio alguma foto."""
    final = os.path.join(DESTINO_IMG, str(id_oferta))
    nova = final + '.novo'
    shutil.rmtree(nova, ignore_errors=True)
    n = store.get_images(page, nova)
    if n:
        # Troca ARQUIVO a arquivo, nao a pasta: renomear a pasta falha
        # (WinError 5) se ela estiver aberta no Explorer, por exemplo.
        os.makedirs(final, exist_ok=True)
        for f in os.listdir(final):
            try:
                os.remove(os.path.join(final, f))
            except OSError:
                pass
        for f in os.listdir(nova):
            os.replace(os.path.join(nova, f), os.path.join(final, f))
    shutil.rmtree(nova, ignore_errors=True)
    return n


def _esperar_usuario(motivo):
    print('\n' + '=' * 64)
    print(f'BLOQUEIO: {motivo}')
    print('Resolva o captcha / faca o login NA JANELA DO CHROME aberta.')
    print('=' * 64)
    while True:
        r = input('[S = resolvi, tentar de novo / P = pular esta oferta / Q = sair]: ').strip().lower()
        if r in ('s', 'p', 'q'):
            return r


def _recapturar(db, page, alvo):
    from backfill_url_afiliado import _abrir_produto, _gravar_completo
    loja, url, id_oferta = alvo['loja'], alvo['url'], alvo['id']
    store = registry.get_store(loja)
    while True:
        motivo, bloqueado = _abrir_produto(page, loja, url)
        if not bloqueado:
            break
        r = _esperar_usuario(page.url[:90])
        if r == 'q':
            raise KeyboardInterrupt
        if r == 'p':
            return None, 'bloqueado (pulado)'
    if motivo:
        return None, motivo

    url_final = page.url
    dados = store.capture(page)
    n = _baixar_galeria(store, page, id_oferta) if store.baixar_imagens else 0
    # Pagina abriu mas a captura veio oca (sem titulo): visto na Shopee em
    # 08/10, instantes antes do captcha. Gravar apagaria preco/campos bons
    # com NULL -- entao so as fotos valem desta vez.
    if not (dados.get('produto_titulo') or '').strip():
        return n, 'dados=VAZIOS (nao gravados)'
    preco_banco = _preco_banco(db, id_oferta)
    resumo = _gravar_completo(db, id_oferta, alvo['id_produto'], loja, url_final, dados, {})
    return n, resumo + ' | ' + _republicar_se_baixou(db, id_oferta, preco_banco, dados)


def _preco_pagina(dados):
    """Menor preco positivo da pagina: preco principal, 'Assine e economize'
    e 'Espere e economize' (mesmos campos da cascata de core/precos.py)."""
    valores = [_num(dados.get('preco_1')), _recorrencia(dados)[0],
               _num(dados.get('espere_economize'))]
    valores = [v for v in valores if v and v > 0]
    return min(valores) if valores else None


def _preco_banco(db, id_oferta):
    cur = db._conn.cursor()
    try:
        cur.execute("SELECT VL_PRECO_POR FROM OFERTA WHERE ID_OFERTA = :i", i=id_oferta)
        r = cur.fetchone()
        return float(r[0]) if r and r[0] is not None else None
    finally:
        cur.close()


def _republicar_se_baixou(db, id_oferta, preco_banco, dados):
    """Pedido do usuario (2026-10-08): preco da pagina MENOR que o do banco
    (OFERTA.VL_PRECO_POR antes da recaptura) -> OFERTA.VL_PRECO_POR = preco
    da pagina e DT_PUBLICACAO_SITE = NULL (o site republica ja com o preco
    novo), e PRODUTO.VR_PRECO_MINIMO/MAXIMO recalculados do zero sobre as
    ofertas (como no backfill_recorrencia.py). Opcao "A" do usuario: aqui o
    preco da pagina vence o da mensagem, diferente da cascata ao vivo
    (core/precos.py). OFERTA_FILA_CAPTURA (origem) e as datas nao mudam."""
    preco_pag = _preco_pagina(dados)
    if preco_pag is None or preco_banco is None:
        return f'preco banco={preco_banco} pagina={preco_pag}'
    if preco_pag >= preco_banco - 0.005:
        return f'preco {preco_banco:.2f} -> {preco_pag:.2f}'
    cur = db._conn.cursor()
    try:
        cur.execute("UPDATE OFERTA SET VL_PRECO_POR = :p, DT_PUBLICACAO_SITE = NULL "
                    "WHERE ID_OFERTA = :i", p=round(preco_pag, 2), i=id_oferta)
        cur.execute("SELECT ID_PRODUTO FROM OFERTA WHERE ID_OFERTA = :i", i=id_oferta)
        id_produto = (cur.fetchone() or [None])[0]
        if id_produto is not None:
            cur.execute("SELECT MIN(VL_PRECO_POR), MAX(VL_PRECO_POR) FROM OFERTA "
                        "WHERE ID_PRODUTO = :id AND VL_PRECO_POR IS NOT NULL", id=id_produto)
            minimo, maximo = cur.fetchone()
            cur.execute("UPDATE PRODUTO SET VR_PRECO_MINIMO = :mi, VR_PRECO_MAXIMO = :ma "
                        "WHERE ID_PRODUTO = :id", mi=minimo, ma=maximo, id=id_produto)
        db._conn.commit()
    except Exception:
        db._conn.rollback()
        raise
    finally:
        cur.close()
    return (f'preco {preco_banco:.2f} -> {preco_pag:.2f} BAIXOU: VL_PRECO_POR atualizado, '
            f'DT_PUBLICACAO_SITE=NULL')


def _id_produto_atual(db, id_oferta):
    cur = db._conn.cursor()
    try:
        cur.execute("SELECT ID_PRODUTO FROM OFERTA_FILA_CAPTURA WHERE ID_OFERTA = :i", i=id_oferta)
        r = cur.fetchone()
        return r[0] if r else None
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ids', help='arquivo com IDs (separados por espaco/linha)')
    ap.add_argument('--lojas', nargs='+', choices=['amazon', 'mercadolivre', 'shopee'])
    ap.add_argument('--lote', type=int, default=0, help='maximo de ofertas (0 = todas)')
    ap.add_argument('--so-local', action='store_true', dest='so_local',
                    help='sem navegador: publica so a partir de destino/img/<ID>')
    ap.add_argument('--retentar', action='store_true',
                    help='inclui ofertas que ja falharam (conf/backfill_imagens_faltantes_tentativas.json)')
    ap.add_argument('--refazer', action='store_true',
                    help='inclui ofertas ja recapturadas (conf/backfill_imagens_faltantes_feitas.json)')
    ap.add_argument('--dry-run', action='store_true', dest='dry_run')
    args = ap.parse_args()

    ids_filtro = None
    if args.ids:
        with open(args.ids, encoding='utf-8') as f:
            ids_filtro = {int(x) for x in f.read().split() if x.strip().isdigit()}

    db = OracleDB()
    db.conectar()
    afiliados.carregar(db)
    alvos = _ler_alvos(db, ids_filtro)
    if args.lojas:
        alvos = [a for a in alvos if a['loja'] in args.lojas]
    tentativas = _ler_tentativas()
    if not args.retentar:
        alvos = [a for a in alvos if str(a['id']) not in tentativas]
    feitas = _ler_feitas()
    if not args.refazer and not args.so_local:
        alvos = [a for a in alvos if a['id'] not in feitas]
    if args.lote:
        alvos = alvos[:args.lote]

    tem_local = lambda a: bool(imagens_oferta.primeira_imagem(os.path.join(DESTINO_IMG, str(a['id']))))  # noqa: E731
    cont = Counter((a['loja'] or 'desconhecida', 'foto_local' if tem_local(a) else 'sem_foto_local')
                   for a in alvos)
    print(f'{len(alvos)} oferta(s) alvo'
          f'{" (ignorando " + str(len(tentativas)) + " ja tentadas)" if tentativas and not args.retentar else ""}:')
    for k, v in sorted(cont.items()):
        print(f'  {v:5}  {k[0]:13} {k[1]}')
    if args.dry_run or not alvos:
        db.desconectar()
        return

    if args.so_local:
        res = Counter()
        for a in alvos:
            r = _publicar(a['id'], a['origem'], os.path.join(DESTINO_IMG, str(a['id'])))
            res[r] += 1
            print(f"  {a['id']} {a['loja']}: {r}")
        print(f'\nResumo: {dict(res)}')
        db.desconectar()
        return

    from playwright.sync_api import sync_playwright
    from core.browser import launch_persistent
    from main import _gate_fechar_navegadores, _nova_page

    _gate_fechar_navegadores()
    resultado = Counter()
    abertas = 0
    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = _nova_page(ctx)
        try:
            for i, a in enumerate(alvos, 1):
                t0 = time.time()
                ini = datetime.now().strftime('%d/%m %H:%M:%S')
                id_oferta, pasta = a['id'], os.path.join(DESTINO_IMG, str(a['id']))
                partes = []
                if a['loja'] is None or registry.get_store(a['loja']) is None:
                    partes.append('loja sem captura -> so disco')
                else:
                    abertas += 1
                    try:
                        n, resumo = _recapturar(db, page, a)
                        partes.append(f'fotos={n}' if n is not None else f'pagina: {resumo}')
                        if n is not None:
                            partes.append(resumo)
                        if 'dados=ok' in (resumo or ''):
                            feitas.add(id_oferta)
                            _gravar_feitas(feitas)
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:  # noqa: BLE001
                        partes.append(f'ERRO recaptura: {str(e).splitlines()[0][:120]}')
                r = _publicar(id_oferta, a['origem'], pasta)
                partes.append(r)
                id_produto = _id_produto_atual(db, id_oferta)
                if id_produto is not None and r == 'img_site=ok':
                    try:
                        n_p = imagens_produto.publicar_imagens_produto(id_produto, pasta)
                        if n_p:
                            partes.append(f'imgs_produto={n_p}')
                    except Exception as e:  # noqa: BLE001
                        partes.append(f'imgs_produto ERRO: {e}')
                resultado[r] += 1
                if r not in ('img_site=ok', 'img_site=ja_tinha'):
                    tentativas[str(id_oferta)] = {'motivo': ' | '.join(partes)[:300],
                                                  'quando': ini}
                    _gravar_tentativas(tentativas)
                elif str(id_oferta) in tentativas:
                    del tentativas[str(id_oferta)]
                    _gravar_tentativas(tentativas)
                print(f'[{ini}] {i}/{len(alvos)} {id_oferta} {a["loja"]}: '
                      f'{" | ".join(partes)} ({time.time() - t0:.0f}s)', flush=True)

                if i < len(alvos) and a['loja']:
                    if abertas and abertas % PAUSA_A_CADA == 0:
                        time.sleep(random.uniform(*PAUSA_LONGA))
                    else:
                        time.sleep(random.uniform(*PAUSA.get(a['loja'], PAUSA_PADRAO)))
        except KeyboardInterrupt:
            print('\nInterrompido.')
        finally:
            ctx.close()
            db.desconectar()
    print('\nResumo:', dict(resultado))


if __name__ == '__main__':
    main()
