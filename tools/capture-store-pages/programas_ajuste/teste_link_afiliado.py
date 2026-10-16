"""
Teste AO VIVO da captura do link oficial de afiliado (core/link_afiliado.py),
sem tocar no banco e sem mexer na fila.

Serve p/ validar os seletores de cada loja antes de soltar o main.py: abre o
Chrome da automacao (mesmo perfil, mesmos gates de login), navega ate a URL
informada, capta o link e imprime o que veio. Nada e gravado -- nem Oracle,
nem CSV.

Uso:
    python teste_link_afiliado.py <url> [<url> ...]
    python teste_link_afiliado.py --da-fila 3      # 1 URL por loja, vinda do
                                                   # banco (ofertas ja capturadas)

Exemplos:
    python teste_link_afiliado.py https://www.amazon.com.br/dp/B0XXXXXXX
    python teste_link_afiliado.py --da-fila 1

Se uma loja vier vazia, o proprio core/link_afiliado.py imprime o motivo
provavel (widget ausente = sessao de afiliado deslogada; dialogo que nao abriu
= layout mudou).
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from playwright.sync_api import sync_playwright

from core import registry, link_afiliado
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB

from main import (_gate_fechar_navegadores, _gate_login_manual, _assentar_pos_login,
                  _gates_login_afiliados, _goto_robusto, _nova_page)


def _urls_da_fila(por_loja):
    """Pega ate `por_loja` URLs ja capturadas de cada loja com fluxo de link de
    afiliado. Usa a DS_URL_FINAL -- sao paginas de produto
    reais, ja validadas, entao um teste que falhe ai e problema do FLUXO DO
    LINK, nao da URL."""
    db = OracleDB()
    if not db.conectar():
        return []
    urls = []
    cur = db._conn.cursor()
    try:
        for loja in link_afiliado.LOJAS:
            nome = registry.nome_loja(loja)
            cur.execute(
                "SELECT * FROM (SELECT DS_URL_FINAL AS URL "
                "  FROM OFERTA_FILA_CAPTURA "
                " WHERE ST_CAPTURA = '1' AND DS_URL_FINAL IS NOT NULL "
                "   AND EXISTS (SELECT 1 FROM OFERTA o WHERE o.ID_OFERTA = "
                "               OFERTA_FILA_CAPTURA.ID_OFERTA AND o.DS_LOJA = :loja) "
                " ORDER BY ID_OFERTA DESC) WHERE ROWNUM <= :n",
                {'loja': nome, 'n': int(por_loja)})
            for (url,) in cur:
                if url:
                    urls.append(url)
    finally:
        cur.close()
        db.desconectar()
    return urls


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('urls', nargs='*', help='URLs de produto para testar.')
    ap.add_argument('--da-fila', type=int, default=0, metavar='N',
                    help='Em vez de URLs na linha de comando, usa N ofertas ja '
                         'capturadas de CADA loja (Amazon, Mercado Livre, Shopee).')
    args = ap.parse_args()

    urls = list(args.urls)
    if args.da_fila:
        urls += _urls_da_fila(args.da_fila)
    if not urls:
        print('Informe pelo menos uma URL (ou use --da-fila N).')
        sys.exit(1)

    link_afiliado.configurar(True)
    _gate_fechar_navegadores()

    with sync_playwright() as p:
        try:
            context = launch_persistent(p, headless=False)
        except Exception as e:  # noqa: BLE001
            print(f'Nao consegui abrir o Chrome com o perfil {PERFIL_DIR}: {e}')
            sys.exit(1)
        link_afiliado.preparar_contexto(context)
        page = _nova_page(context)

        # Mesmos gates do main.py: Shopee (loja) e depois os 3 de afiliado.
        if any(registry.resolver_loja(u) == 'shopee' for u in urls):
            _gate_login_manual(page)
            _assentar_pos_login(page)
        _gates_login_afiliados(page)

        for url in urls:
            loja = registry.resolver_loja(url)
            print('\n' + '-' * 64)
            print(f'{loja or "loja desconhecida"} | {url[:90]}')
            if loja not in link_afiliado.LOJAS:
                print('  (sem fluxo de link de afiliado nesta loja)')
                continue
            store = registry.get_store(loja)
            try:
                _goto_robusto(page, url, timeout=60000)
                if store:
                    try:
                        store.prepare(page)       # ML: sai da previa p/ o produto
                    except Exception:  # noqa: BLE001
                        pass
                    if store.ready_selector:
                        try:
                            page.wait_for_selector(store.ready_selector, timeout=25000)
                        except Exception:  # noqa: BLE001
                            pass
                    page.wait_for_timeout(store.post_load_wait)
            except Exception as e:  # noqa: BLE001
                print(f'  falhou ao abrir a pagina: {e}')
                continue
            # Mesmo descarte do main.py: anuncio fora do ar nao chega a ter
            # link de afiliado (nem deveria mesmo).
            descarte = store.status_descarte(page) if store else None
            if descarte:
                print(f'  DESCARTE = {descarte} (no main.py vira ST_CAPTURA=9 '
                      'com esse motivo em DS_CAPTURA e pula p/ a proxima)')
                continue
            url_final = page.url
            resultado = link_afiliado.capturar(page, loja, url_final)
            for campo in link_afiliado.CAMPOS:
                print(f'  {campo:<24} = {resultado.get(campo) or "-"}')

        print('\n' + '-' * 64)
        print('Fim do teste (nada foi gravado).')
        context.close()


if __name__ == '__main__':
    main()
