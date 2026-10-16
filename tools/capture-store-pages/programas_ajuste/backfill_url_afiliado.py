"""
Backfill de DS_URL_AFILIADO (link OFICIAL de afiliado, clicado no widget de
cada loja -- core/link_afiliado.py) p/ as ofertas de BESAVE.OFERTA capturadas
ANTES de o main.py passar a pega-lo ao vivo (2026-09-10), ou que ficaram sem
ele (sessao de afiliado deslogada na hora da captura).

Decisao do usuario (2026-09-24): o link de afiliado confiavel e SO o que a
loja gera (DS_URL_AFILIADO); a DS_URL_BESAVE (troca de parametros por regex,
core/afiliados.py) nao serve de fonte. Por isso este backfill reabre a pagina
de verdade -- nao da p/ derivar do que ja esta no banco.

Ordem: ID_OFERTA DECRESCENTE (ofertas mais recentes primeiro), em lotes de
--lote (padrao 300). Por loja:
  * Amazon / Mercado Livre: abre a DS_URL_FINAL e clica no widget
    (SiteStripe / barra de afiliado). Mesmas esperas e hooks do main.py.
  * Shopee: NAO abre a pagina do produto -- cola a DS_URL_FINAL no gerador
    affiliate.shopee.com.br (numa aba separada), como o main.py.

Modo so-link (--so-link, e sempre p/ Shopee -- ver recaptura completa abaixo):
grava so o link (UPDATE direto, 4 colunas de afiliado -- nunca via
STP_OFERTA_FILA_CAPTURA_UPDATE com dict parcial, ver o incidente):
  * OFERTA_FILA_CAPTURA e BESAVE.OFERTA: DS_URL_AFILIADO + categoria/taxa/
    codigo (esses 3 com NVL: o que ja existia nao e apagado);
  * PRODUTO.DS_ULT_URL: o link desta oferta, SO se nenhuma oferta MAIS NOVA do
    mesmo produto ja tiver link oficial (a mais recente vence).
Commit a cada oferta: pode interromper (Ctrl+C) a qualquer momento.

Ofertas que nao deram link ficam registradas em
conf/backfill_url_afiliado_tentativas.json e sao PULADAS nos lotes seguintes
(senao os mesmos anuncios pausados/sem link voltariam sempre ao topo da fila
por serem os IDs mais altos). --retentar ignora esse registro. Falhas que sao
da SESSAO e nao da oferta (login do ML, corta-circuito de 5 falhas seguidas do
link_afiliado, 5 paginas seguidas sem produto) NAO sao registradas -- essas
ofertas voltam no proximo lote. "sem link" e pagina_sem_produto/erro de
navegacao so viram registro quando a loja volta a dar link depois delas.

Antes do lote, --sincronizar-produtos (roda sozinho, so banco) acerta
PRODUTO.DS_ULT_URL com o link oficial mais recente ja existente em OFERTA.

Recaptura completa (2026-09-24, decisao do usuario): como Amazon/ML ja tem a
pagina do produto aberta so para o link de afiliado, o lote tambem recaptura
TODOS os campos de oferta (preco de/para e o resto -- store.capture(), o
mesmo metodo do main.py) e grava via STP_OFERTA_FILA_CAPTURA_UPDATE (seguro
aqui porque o dict e COMPLETO, nao parcial -- ver o incidente na memoria).
Por tabela: OFERTA_FILA_CAPTURA/OFERTA (preco e demais campos), PRODUTO
(core/produtos.cadastrar_produto) e BESAVE.OFERTA (core/ofertas.publicar_oferta,
feed publico). Imagens NAO sao recapturadas (nao pedido). A Shopee CONTINUA
so no link (nao abre a pagina do produto nesta rotina) -- use --so-link para
desligar a recaptura tambem em Amazon/ML e voltar ao backfill so de link.

NAO rodar junto com o main.py (perfil .chrome_perfil compartilhado).

Uso:
    .venv/Scripts/python.exe backfill_url_afiliado.py --dry-run          # so conta
    .venv/Scripts/python.exe backfill_url_afiliado.py --sincronizar-produtos
    .venv/Scripts/python.exe backfill_url_afiliado.py                    # lote de 300, com recaptura completa (Amazon/ML)
    .venv/Scripts/python.exe backfill_url_afiliado.py --so-link          # lote de 300, so o link (comportamento antigo)
    .venv/Scripts/python.exe backfill_url_afiliado.py --lote 50 --lojas mercadolivre
    .venv/Scripts/python.exe backfill_url_afiliado.py --retentar sem_link --ate-vezes 1 --lote 400
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from core import registry, link_afiliado, produtos, ofertas, cupons, afiliados, estado
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB

from main import (MARCAS_BLOQUEIO, _gate_fechar_navegadores, _gates_login_afiliados,
                  _goto_robusto, _nova_page)

LOTE_PADRAO = 300
TENTATIVAS_PATH = os.path.join('conf', 'backfill_url_afiliado_tentativas.json')
PAUSA_ENTRE_OFERTAS = (4, 8)   # segundos, aleatorio -- evita rajada anti-bot
PAUSA_A_CADA = 15              # ofertas que abriram pagina
PAUSA_LONGA = (60, 90)         # segundos, a cada PAUSA_A_CADA ofertas
# Motivos de _abrir_produto que podem ser pagina lenta/tela intermediaria (nao
# culpa da oferta): entram na sequencia pendente, como o "sem link". Os demais
# (anuncio_pausado etc.) sao definitivos e registrados na hora.
MOTIVOS_DUVIDOSOS = {'pagina_sem_produto'}

# Tamanhos das colunas (ver sql/ALTER_OFERTA_FILA_CAPTURA_AFILIADO.sql).
_TAMANHOS = {'url_afiliado': 600, 'categoria_afiliado': 100,
             'taxa_comissao_afiliado': 20, 'id_produto_afiliado': 50}

_SET_AFILIADO = (
    "DS_URL_AFILIADO = :url, "
    "DS_CATEGORIA_PROD_AFILIADO = NVL(:cat, DS_CATEGORIA_PROD_AFILIADO), "
    "DS_TAXA_COMISSAO_PROD_AFILIADO = NVL(:taxa, DS_TAXA_COMISSAO_PROD_AFILIADO), "
    "DS_ID_PRODUTO_AFILIADO = NVL(:cod, DS_ID_PRODUTO_AFILIADO)")

# PRODUTO: grava o link so se nenhuma oferta MAIS NOVA do produto ja tem link
# oficial -- como o lote anda do ID maior p/ o menor, a 1a que acha vence.
_SQL_PRODUTO = (
    "UPDATE PRODUTO SET DS_ULT_URL = SUBSTR(:url, 1, 500) "
    "WHERE ID_PRODUTO = :prod AND NOT EXISTS ("
    "  SELECT 1 FROM OFERTA o WHERE o.ID_PRODUTO = :prod "
    "  AND o.ID_OFERTA > :id AND o.DS_URL_AFILIADO IS NOT NULL)")

# Sincroniza PRODUTO.DS_ULT_URL com o link oficial da oferta MAIS RECENTE que
# tem um (so banco, idempotente).
_SQL_SINCRONIZAR = """
MERGE INTO PRODUTO p
USING (
  SELECT ID_PRODUTO, DS_URL_AFILIADO FROM (
    SELECT ID_PRODUTO, DS_URL_AFILIADO,
           ROW_NUMBER() OVER (PARTITION BY ID_PRODUTO ORDER BY ID_OFERTA DESC) rn
      FROM OFERTA
     WHERE DS_URL_AFILIADO IS NOT NULL AND ID_PRODUTO IS NOT NULL)
   WHERE rn = 1
) u ON (p.ID_PRODUTO = u.ID_PRODUTO)
WHEN MATCHED THEN UPDATE SET p.DS_ULT_URL = SUBSTR(u.DS_URL_AFILIADO, 1, 500)
  WHERE p.DS_ULT_URL IS NULL OR p.DS_ULT_URL <> SUBSTR(u.DS_URL_AFILIADO, 1, 500)
"""


# --- registro de tentativas sem link -------------------------------------------
def _ler_tentativas():
    try:
        with open(TENTATIVAS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:  # noqa: BLE001
        print(f'[tentativas] nao consegui ler {TENTATIVAS_PATH}: {e}')
        return {}


def _gravar_tentativas(tentativas):
    tmp = TENTATIVAS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(tentativas, f, ensure_ascii=False, indent=1)
    os.replace(tmp, TENTATIVAS_PATH)


def _registrar(tentativas, id_oferta, motivo):
    atual = tentativas.get(str(id_oferta)) or {}
    tentativas[str(id_oferta)] = {
        'motivo': motivo,
        'vezes': int(atual.get('vezes') or 0) + 1,
        'quando': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    _gravar_tentativas(tentativas)


def _entra_no_lote(registro, args):
    """Oferta sem registro de falha sempre entra. Com registro, so com
    --retentar, filtrada por motivo (se informado) e por --ate-vezes."""
    if registro is None:
        return True
    if args.retentar is None:
        return False
    if args.retentar and registro.get('motivo') not in args.retentar:
        return False
    if args.ate_vezes is not None and int(registro.get('vezes') or 0) > args.ate_vezes:
        return False
    return True


# --- banco -----------------------------------------------------------------------
def _ler_pendentes(db, lojas):
    """Todas as ofertas sem link oficial, do ID maior p/ o menor, ja com a loja
    resolvida pela DS_URL_FINAL (so as lojas com fluxo de link)."""
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT ID_OFERTA, ID_PRODUTO, DS_URL_FINAL FROM OFERTA "
            "WHERE DS_URL_AFILIADO IS NULL AND DS_URL_FINAL IS NOT NULL "
            "ORDER BY ID_OFERTA DESC")
        linhas = cur.fetchall()
    finally:
        cur.close()
    out = []
    for id_oferta, id_produto, url in linhas:
        loja = registry.resolver_loja(url)
        if loja in lojas:
            out.append((int(id_oferta), id_produto, loja, url))
    return out


def _gravar(db, id_oferta, id_produto, dados):
    binds = {
        'url': dados['url_afiliado'][:_TAMANHOS['url_afiliado']],
        'cat': (dados.get('categoria_afiliado') or '')[:_TAMANHOS['categoria_afiliado']] or None,
        'taxa': (dados.get('taxa_comissao_afiliado') or '')[:_TAMANHOS['taxa_comissao_afiliado']] or None,
        'cod': (dados.get('id_produto_afiliado') or '')[:_TAMANHOS['id_produto_afiliado']] or None,
        'id': id_oferta,
    }
    cur = db._conn.cursor()
    try:
        cur.execute(f"UPDATE OFERTA_FILA_CAPTURA SET {_SET_AFILIADO} WHERE ID_OFERTA = :id", binds)
        # Toda oferta que este programa altera volta a ficar ativa (mesma regra
        # da STP_OFERTA_PUBLICAR; quem desativa e um processo separado) --
        # EXCETO a duplicada (core/duplicidade.py, fila 'duplicada de N') e a
        # vencida (core/validade.py, DT_OFERTA alem de ofertas.validade_dias).
        cur.execute(f"UPDATE OFERTA SET {_SET_AFILIADO} WHERE ID_OFERTA = :id", binds)
        dias = estado.ler_validade_ofertas()
        cur.execute("UPDATE OFERTA SET ST_ATIVO = 1, DT_DESATIVACAO = NULL "
                    "WHERE ID_OFERTA = :id AND NOT EXISTS (SELECT 1 FROM OFERTA_FILA_CAPTURA f "
                    "  WHERE f.ID_OFERTA = :id AND f.DS_CAPTURA LIKE 'duplicada de %') "
                    "  AND (:dias = 0 OR DT_OFERTA >= SYSDATE - :dias)",
                    {'id': id_oferta, 'dias': int(dias)})
        produto = 0
        if id_produto is not None:
            cur.execute(_SQL_PRODUTO, {'url': binds['url'], 'prod': int(id_produto),
                                       'id': id_oferta})
            produto = cur.rowcount
        db._conn.commit()
        return produto
    except Exception:
        db._conn.rollback()
        raise
    finally:
        cur.close()


def _gravar_completo(db, id_oferta, id_produto, loja, url_final, dados_produto, dados_afiliado):
    """Recaptura COMPLETA (preco de/para + demais campos de oferta, produto e
    feed publico) para uma oferta ja existente -- mesmo pipeline do main.py
    ao vivo (store.capture -> STP_OFERTA_FILA_CAPTURA_UPDATE -> cadastro do
    produto -> cupom -> BESAVE.OFERTA), so que sem imagens. Seguro chamar a SP
    aqui porque `dados_produto` e um dict COMPLETO de store.capture() (todo
    campo nao encontrado desta vez vira NULL de verdade, igual a uma captura
    ao vivo) -- diferente do incidente do dict parcial que os outros backfills
    evitam. `ativo=None` preserva ST_ATIVO; DS_URL_BESAVE nao e informada e a
    SP tem NVL nela, entao o valor atual fica intacto. Best-effort em cada
    etapa (como main.py); devolve um resumo curto para o log."""
    pacote = dict(dados_produto)
    pacote['url_final'] = url_final
    pacote.update(dados_afiliado)

    # A gravacao PRINCIPAL (que inclui o link de afiliado, junto com o resto)
    # precisa propagar excecao em falha -- e o mesmo caminho de erro do
    # _gravar antigo (chamador faz rollback via db, no conta como sucesso e
    # NAO limpa a sequencia de falhas do corta-circuito). So as etapas
    # seguintes (produto/cupom/oferta) sao best-effort de verdade.
    ok, erro = db.atualizar_captura(id_oferta, pacote, descricao='backfill_dados_completos', ativo=None)
    if not ok:
        raise RuntimeError(f'atualizar_captura: {erro}')

    resumo = ['dados=ok']
    try:
        linha_gravada = db.buscar_para_produto(id_oferta)
        novo_id_produto, classificacao, erro_produto = (
            produtos.cadastrar_produto(db, id_oferta, linha_gravada)
            if linha_gravada else (None, None, 'linha nao encontrada apos gravar'))
    except Exception as e:  # noqa: BLE001
        novo_id_produto, classificacao, erro_produto = None, None, str(e)
    if novo_id_produto is not None:
        resumo.append(f'produto={novo_id_produto}')
        id_produto = novo_id_produto
    else:
        resumo.append('produto=FALHOU')
        if erro_produto:
            resumo.append(f'({erro_produto})')

    try:
        linha_cupom = db.buscar_para_cupom(id_oferta)
        id_cupom, erro_cupom = (
            cupons.publicar_cupom(db, linha_cupom, registry.nome_loja(loja, url_final))
            if linha_cupom else (None, 'linha nao encontrada apos gravar'))
    except Exception as e:  # noqa: BLE001
        id_cupom, erro_cupom = None, str(e)
    if id_cupom is not None:
        resumo.append(f'cupom={id_cupom}')
    elif erro_cupom:
        resumo.append('cupom=FALHOU')

    if id_produto is not None and afiliados.loja_ativa(loja):
        try:
            linha_oferta = db.buscar_para_oferta(id_oferta)
            ok_oferta, erro_oferta = (
                ofertas.publicar_oferta(db, id_oferta, id_produto,
                                        registry.nome_loja(loja, url_final),
                                        linha_oferta, classificacao)
                if linha_oferta else (False, 'linha nao encontrada apos gravar'))
        except Exception as e:  # noqa: BLE001
            ok_oferta, erro_oferta = False, str(e)
        if ok_oferta:
            resumo.append('oferta=publicada')
        elif (erro_oferta or '').startswith('duplicada de '):
            resumo.append(f'oferta={erro_oferta}')
        else:
            resumo.append('oferta=FALHOU')

    return ' | '.join(resumo)


def _sincronizar_produtos(db):
    cur = db._conn.cursor()
    try:
        cur.execute(_SQL_SINCRONIZAR)
        n = cur.rowcount
        db._conn.commit()
        return n
    finally:
        cur.close()


# --- pagina ----------------------------------------------------------------------
def _abrir_produto(page, loja, url):
    """Abre a pagina do produto com os mesmos hooks do main.py. Devolve
    (motivo_definitivo, bloqueado): motivo_definitivo != None quando a OFERTA
    nao tem como dar link (anuncio pausado, nao e pagina de produto);
    bloqueado=True quando a SESSAO/IP caiu num muro de login (culpa nao e da
    oferta)."""
    store = registry.get_store(loja)
    _goto_robusto(page, url, timeout=60000)
    try:
        store.prepare(page)
    except Exception as e:  # noqa: BLE001
        print(f'  prepare: {e}')
    if store.ready_selector:
        try:
            page.wait_for_selector(store.ready_selector, timeout=25000)
        except Exception:  # noqa: BLE001
            pass
    page.wait_for_timeout(store.post_load_wait)
    if any(m in page.url for m in MARCAS_BLOQUEIO):
        return None, True
    try:
        descarte = store.status_descarte(page)
    except Exception:  # noqa: BLE001
        descarte = None
    if descarte:
        return descarte, False
    sem_produto = ((store.ready_selector and page.locator(store.ready_selector).count() == 0)
                   or store.pagina_sem_produto(page))
    if sem_produto:
        return 'pagina_sem_produto', False
    return None, False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lote', type=int, default=LOTE_PADRAO,
                    help=f'Quantas ofertas processar nesta execucao (padrao {LOTE_PADRAO}).')
    ap.add_argument('--lojas', nargs='+', choices=link_afiliado.LOJAS,
                    default=list(link_afiliado.LOJAS),
                    help='Restringe a estas lojas (padrao: as 3).')
    ap.add_argument('--retentar', nargs='*', metavar='MOTIVO', default=None,
                    help='Inclui ofertas que ja falharam em lotes anteriores. Sem '
                         'valor: todos os motivos; com valor: so esses (ex. '
                         '--retentar sem_link).')
    ap.add_argument('--ate-vezes', type=int, default=None, dest='ate_vezes',
                    help='Com --retentar: so retenta quem falhou ate N vezes (ex. 1 = '
                         'so quem ainda nao foi retentado; assim lotes seguidos '
                         'avancam em vez de repetir as mesmas ofertas).')
    ap.add_argument('--so-link', action='store_true', dest='so_link',
                    help='Desliga a recaptura completa de dados (preco/demais campos) '
                         'em Amazon/ML; grava so o link de afiliado, como antes.')
    ap.add_argument('--dry-run', action='store_true',
                    help='So mostra quantas faltam, sem abrir navegador nem gravar.')
    ap.add_argument('--sincronizar-produtos', action='store_true',
                    help='So acerta PRODUTO.DS_ULT_URL com os links oficiais ja '
                         'existentes em OFERTA (sem navegador) e sai.')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    if args.sincronizar_produtos:
        n = _sincronizar_produtos(db)
        print(f'PRODUTO.DS_ULT_URL atualizado em {n} produto(s) a partir de OFERTA.DS_URL_AFILIADO.')
        db.desconectar()
        return

    tentativas = _ler_tentativas()
    pendentes = _ler_pendentes(db, set(args.lojas))
    total = len(pendentes)
    pendentes = [p for p in pendentes if _entra_no_lote(tentativas.get(str(p[0])), args)]
    lote = pendentes[:args.lote] if args.lote > 0 else pendentes

    por_loja = {}
    for _, _, loja, _ in pendentes:
        por_loja[loja] = por_loja.get(loja, 0) + 1
    print(f'{total} oferta(s) em OFERTA sem DS_URL_AFILIADO ({", ".join(args.lojas)}); '
          f'{total - len(pendentes)} pulada(s) por ja terem falhado antes; '
          f'{len(pendentes)} na fila: '
          + ', '.join(f'{k}={v}' for k, v in sorted(por_loja.items())))
    if lote:
        print(f'Este lote: {len(lote)} oferta(s), ID {lote[0][0]} ate {lote[-1][0]}.')
    if args.dry_run or not lote:
        db.desconectar()
        return

    link_afiliado.configurar(True)
    if not args.so_link:
        afiliados.carregar(db)  # precisa estar carregado p/ afiliados.loja_ativa() (BESAVE.OFERTA)
    _gate_fechar_navegadores()

    ok = sem_link = pulados = 0
    lojas_paradas = set()
    # Falhas "duvidosas" da sequencia atual de cada loja, como (id, motivo):
    # "sem link", e tambem pagina_sem_produto/erro de navegacao (25/09: uma
    # rajada de 39 pagina_sem_produto no ML era pagina lenta, nao oferta ruim
    # -- reabertas depois, todas carregaram). So viram registro definitivo
    # quando a loja volta a dar link (prova que a sessao esta boa). Se um
    # corta-circuito disparar, a sequencia era sessao caida -> descarta.
    sequencia = {loja: [] for loja in link_afiliado.LOJAS}
    # Paginas seguidas que nao abriram como produto, por loja: em
    # LIMITE_FALHAS a loja para neste lote (mesmo limite do link_afiliado).
    paginas_falhas_seguidas = {loja: 0 for loja in link_afiliado.LOJAS}
    paginas_abertas = 0
    inicio = time.time()

    with sync_playwright() as p:
        try:
            context = launch_persistent(p, headless=False)
        except Exception as e:  # noqa: BLE001
            print(f'Nao consegui abrir o Chrome com o perfil {PERFIL_DIR}: {e}')
            sys.exit(1)
        link_afiliado.preparar_contexto(context)
        page = _nova_page(context)
        _gates_login_afiliados(page)

        try:
            for n, (id_oferta, id_produto, loja, url) in enumerate(lote, 1):
                if loja in lojas_paradas or loja in link_afiliado._desistidas:
                    pulados += 1
                    continue
                inicio_dt = datetime.now()
                t0 = time.perf_counter()
                dur = lambda: f'{time.perf_counter() - t0:.1f}s'  # noqa: E731
                prefixo = f'[{inicio_dt:%d/%m %H:%M:%S}] [{n}/{len(lote)}] oferta {id_oferta} | {loja:<12}'

                dados_produto = None
                if loja != 'shopee':      # Shopee: so o gerador, sem abrir o produto
                    paginas_abertas += 1
                    try:
                        motivo, bloqueado = _abrir_produto(page, loja, url)
                    except Exception as e:  # noqa: BLE001
                        motivo, bloqueado = f'erro: {type(e).__name__}', False
                    if bloqueado:
                        lojas_paradas.add(loja)
                        print(f'{prefixo} | MURO DE LOGIN ({page.url[:60]}) -- parando '
                              f'{loja} neste lote (oferta nao registrada como falha). | {dur()}')
                        continue
                    if motivo in MOTIVOS_DUVIDOSOS or (motivo or '').startswith('erro'):
                        sem_link += 1
                        sequencia[loja].append((id_oferta, motivo))
                        paginas_falhas_seguidas[loja] += 1
                        if paginas_falhas_seguidas[loja] >= link_afiliado.LIMITE_FALHAS:
                            lojas_paradas.add(loja)
                            print(f'{prefixo} | {motivo} -- {link_afiliado.LIMITE_FALHAS} '
                                  f'paginas seguidas sem produto: parando {loja} neste lote; '
                                  f'as {len(sequencia[loja])} ultima(s) falha(s) NAO serao '
                                  f'registradas (sessao/site, nao a oferta). | {dur()}')
                            sequencia[loja] = []
                        else:
                            print(f'{prefixo} | {motivo} (pendente) | {dur()}')
                        continue
                    paginas_falhas_seguidas[loja] = 0
                    if motivo:            # definitivo (ex.: anuncio_pausado)
                        sem_link += 1
                        _registrar(tentativas, id_oferta, motivo)
                        print(f'{prefixo} | {motivo} | {dur()}')
                        continue
                    if not args.so_link:
                        store = registry.get_store(loja)
                        try:
                            dados_produto = store.capture(page)
                        except Exception as e:  # noqa: BLE001
                            print(f'{prefixo} | recaptura de dados falhou: '
                                  f'{type(e).__name__}: {e}')

                # Fixado ANTES do link_afiliado.capturar(): o clique no widget de
                # afiliado pode navegar a pagina (nova aba/redirect), entao ler
                # page.url DEPOIS pegaria a URL errada (mesmo cuidado do main.py).
                url_final = url if loja == 'shopee' else page.url
                dados = link_afiliado.capturar(page, loja, url_final)
                if dados.get('url_afiliado'):
                    try:
                        if dados_produto is not None:
                            resumo_dados = _gravar_completo(
                                db, id_oferta, id_produto, loja, url_final, dados_produto, dados)
                        else:
                            produto = _gravar(db, id_oferta, id_produto, dados)
                            resumo_dados = 'produto atualizado' if produto else None
                    except Exception as e:  # noqa: BLE001
                        print(f'{prefixo} | link ok, mas FALHOU ao gravar: {e} | {dur()}')
                        continue
                    ok += 1
                    for pendente_id, pendente_motivo in sequencia[loja]:  # sessao boa -> eram da oferta
                        _registrar(tentativas, pendente_id, pendente_motivo)
                    sequencia[loja] = []
                    print(f'{prefixo} | {dados["url_afiliado"]}'
                          f'{" | " + resumo_dados if resumo_dados else ""} | {dur()}')
                else:
                    sequencia[loja].append((id_oferta, 'sem_link'))
                    if loja in link_afiliado._desistidas:
                        print(f'{prefixo} | sem link -- corta-circuito disparou; as '
                              f'{len(sequencia[loja])} ultima(s) falha(s) de {loja} NAO '
                              f'serao registradas (sessao caida, nao a oferta). | {dur()}')
                        sequencia[loja] = []
                    else:
                        sem_link += 1
                        print(f'{prefixo} | sem link | {dur()}')

                if loja != 'shopee':
                    if paginas_abertas % PAUSA_A_CADA == 0:
                        pausa = random.uniform(*PAUSA_LONGA)
                        print(f'  ...pausa longa de {pausa:.0f}s (anti-bot).')
                        time.sleep(pausa)
                    else:
                        time.sleep(random.uniform(*PAUSA_ENTRE_OFERTAS))
        except KeyboardInterrupt:
            print('\nInterrompido (Ctrl+C) -- o que ja foi gravado esta commitado.')
        finally:
            # Sequencia final sem corta-circuito: < LIMITE_FALHAS seguidas, trata
            # como falha da oferta (mesma regra do main.py).
            # Loja parada (muro de login / paginas seguidas sem produto) tambem
            # descarta: a sequencia que antecedeu a parada era da sessao.
            for loja, pendentes_loja in sequencia.items():
                if loja not in link_afiliado._desistidas and loja not in lojas_paradas:
                    for pendente_id, pendente_motivo in pendentes_loja:
                        _registrar(tentativas, pendente_id, pendente_motivo)
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass

    minutos = (time.time() - inicio) / 60
    print('\n' + '-' * 64)
    print(f'{ok} link(s) gravado(s), {sem_link} sem link, {pulados} pulada(s) '
          f'(loja parada: {", ".join(sorted(lojas_paradas | link_afiliado._desistidas)) or "-"}) '
          f'em {minutos:.0f} min.')
    db.desconectar()


if __name__ == '__main__':
    main()
