"""
Backfill SO das imagens de ofertas ja capturadas.

Existe por causa da quebra da galeria da Amazon (10/09 18h28 -> 11/09 10h): as
ofertas foram capturadas com dados corretos, mas `destino/img/<ID_OFERTA>`
ficou VAZIA porque o clique na miniatura tinha deixado de funcionar (ver o
resumo.md, secao "Tempo por oferta no log + a galeria da Amazon").

Por que nao devolver a oferta para a fila (ST_CAPTURA='0')? Porque a recaptura
reescreveria preco, titulo e o link de afiliado -- campos que hoje estao certos
-- so para buscar foto. Aqui o banco NAO e tocado: le a lista de ofertas, abre
cada pagina e baixa as imagens que faltam. Nada de UPDATE, nada de CSV.

Uso:
    python backfill_imagens.py --loja amazon            # so as pastas vazias da Amazon
    python backfill_imagens.py --loja amazon --limite 5 # ensaio curto
    python backfill_imagens.py --loja amazon --desde 25190
    python backfill_imagens.py --listar                 # so mostra o que faria

Retomavel: quem ja tem foto na pasta fica de fora da proxima rodada.

ATENCAO: usa o Chrome do perfil unico (.chrome_perfil) -- nao rode junto com o
main.py capturando.
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys
import time

from playwright.sync_api import sync_playwright

from core import registry
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB

from core.caminhos import IMG_DIR
from main import (_gate_fechar_navegadores, _gate_login_manual,
                  _assentar_pos_login, _goto_robusto, _nova_page)

# Pausa entre ofertas: abrir pagina atras de pagina em rajada foi o que acionou
# o bloqueio do Mercado Livre no backfill de QT_OPINIOES (ver resumo.md).
PAUSA_PADRAO = 2.0

# De-para loja -> pedaco de dominio que aparece na DS_URL_FINAL.
MARCA_URL = {
    'amazon': '%amazon.com%',
    'mercadolivre': '%mercadolivre.com%',
    'shopee': '%shopee.com%',
}


def _pasta(id_oferta):
    return os.path.join(IMG_DIR, str(id_oferta))


def _sem_imagem(id_oferta):
    p = _pasta(id_oferta)
    return (not os.path.isdir(p)) or (not os.listdir(p))


def _pendentes(loja, desde, limite):
    """IDs + URL das ofertas ja capturadas (ST_CAPTURA='1') da loja cuja pasta
    de imagens esta vazia. A fonte da verdade e o DISCO: quem tem foto sai."""
    db = OracleDB()
    if not db.conectar():
        return []
    cur = db._conn.cursor()
    try:
        sql = ("SELECT ID_OFERTA, DS_URL_FINAL FROM OFERTA_FILA_CAPTURA "
               " WHERE ST_CAPTURA = '1' AND DS_URL_FINAL LIKE :marca "
               "   AND ID_OFERTA >= :desde ORDER BY ID_OFERTA")
        cur.execute(sql, {'marca': MARCA_URL[loja], 'desde': int(desde or 0)})
        alvos = [(i, u) for (i, u) in cur if u and _sem_imagem(i)]
    finally:
        cur.close()
        db.desconectar()
    return alvos[:limite] if limite else alvos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--loja', default='amazon', choices=sorted(MARCA_URL),
                    help='Loja a recuperar (padrao: amazon).')
    ap.add_argument('--desde', type=int, default=0,
                    help='So ofertas com ID_OFERTA >= este valor. A quebra da '
                         'galeria da Amazon comeca em 25190.')
    ap.add_argument('--limite', type=int, default=0, help='Maximo de ofertas (0 = todas).')
    ap.add_argument('--pausa', type=float, default=PAUSA_PADRAO,
                    help=f'Segundos entre ofertas (padrao {PAUSA_PADRAO:g}).')
    ap.add_argument('--listar', action='store_true',
                    help='So lista o que seria feito, sem abrir o navegador.')
    args = ap.parse_args()

    alvos = _pendentes(args.loja, args.desde, args.limite)
    print(f'{len(alvos)} oferta(s) {args.loja} sem imagem no disco.')
    if not alvos:
        return
    if args.listar:
        for id_oferta, url in alvos:
            print(f'  {id_oferta} | {url[:90]}')
        return

    store = registry.get_store(args.loja)
    if store is None or not store.baixar_imagens:
        print(f'A loja {args.loja} nao baixa imagens.')
        sys.exit(1)

    _gate_fechar_navegadores()
    with sync_playwright() as p:
        try:
            context = launch_persistent(p, headless=False)
        except Exception as e:  # noqa: BLE001
            print(f'Nao consegui abrir o Chrome com o perfil {PERFIL_DIR}: {e}')
            sys.exit(1)
        page = _nova_page(context)
        # A Shopee exige sessao de comprador ate p/ ver a pagina do produto; as
        # outras lojas nao pedem login nenhum para as fotos (o login de
        # AFILIADO nao entra aqui -- este backfill nao mexe em link).
        if args.loja == 'shopee':
            _gate_login_manual(page)
            _assentar_pos_login(page)

        ok = vazias = falhas = 0
        for n, (id_oferta, url) in enumerate(alvos, 1):
            t0 = time.perf_counter()
            try:
                _goto_robusto(page, url, timeout=60000)
                try:
                    store.prepare(page)
                except Exception:  # noqa: BLE001
                    pass
                if store.ready_selector:
                    try:
                        page.wait_for_selector(store.ready_selector, timeout=25000)
                    except Exception:  # noqa: BLE001
                        pass
                page.wait_for_timeout(store.post_load_wait)
                baixadas = store.get_images(page, _pasta(id_oferta))
            except Exception as e:  # noqa: BLE001
                baixadas, erro = 0, str(e).splitlines()[0][:70]
                falhas += 1
                print(f'[{n}/{len(alvos)}] {id_oferta} | ERRO: {erro}')
                continue
            gasto = time.perf_counter() - t0
            if baixadas:
                ok += 1
            else:
                # Pagina fora do ar, produto removido ou galeria mudou de novo.
                vazias += 1
            print(f'[{n}/{len(alvos)}] {id_oferta} | {baixadas} imagem(ns) | '
                  f'{gasto:.1f}s' + ('' if baixadas else '  <- continua sem foto'))
            if args.pausa and n < len(alvos):
                time.sleep(args.pausa)

        print(f'\nFim: {ok} com imagem, {vazias} sem foto na pagina, {falhas} com erro. '
              'Nada foi gravado no banco.')
        context.close()


if __name__ == '__main__':
    main()
