"""
Dump da GALERIA de imagens da Amazon -- mesmo papel do shopee_dump.py e do
ml_dump_barra.py: quando a loja muda a marcacao, olhar o HTML de verdade em vez
de chutar seletor.

Motivo (11/09): o download de imagens da Amazon parou de funcionar. O
teste_tempos.py mostrou que cada <li> de #altImages tem input=0 -- ou seja, o
<input> que core/base_store.get_images clica nao existe mais, e cada clique
espera o timeout inteiro (15s x 7 miniaturas = ~105s por oferta, zero imagem).

Grava destino/log/amazon_galeria_dump.html e imprime um resumo do que achou.

Uso:
    python amazon_dump_galeria.py <url de um produto amazon>
    python amazon_dump_galeria.py --da-fila         # pega a ultima oferta Amazon capturada
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys

from playwright.sync_api import sync_playwright

from core import registry
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB
from core.caminhos import em_log

from main import _gate_fechar_navegadores, _goto_robusto, _nova_page

SAIDA = em_log('amazon_galeria_dump.html')

# O que o codigo de hoje usa (AmazonStore) -- e o que se quer conferir.
THUMBS = '#altImages ul'
CONTAINER = '#main-image-container > ul:visible'


def _url_da_fila():
    db = OracleDB()
    if not db.conectar():
        return None
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM (SELECT DS_URL_FINAL FROM OFERTA_FILA_CAPTURA "
            " WHERE ST_CAPTURA = '1' AND DS_URL_FINAL LIKE '%amazon.com.br%' "
            " ORDER BY ID_OFERTA DESC) WHERE ROWNUM <= 1")
        linha = cur.fetchone()
        return linha[0] if linha else None
    finally:
        cur.close()
        db.desconectar()


def _bloco(page, seletor, rotulo):
    """HTML de um bloco da pagina (vazio se o seletor nao casar)."""
    try:
        el = page.locator(seletor).first
        if el.count() == 0:
            print(f'  {rotulo}: NAO EXISTE ({seletor})')
            return f'<!-- {rotulo}: ausente ({seletor}) -->'
        html = el.evaluate('el => el.outerHTML') or ''
        print(f'  {rotulo}: {len(html)} chars ({seletor})')
        return f'<!-- ===== {rotulo} ({seletor}) ===== -->\n{html}'
    except Exception as e:  # noqa: BLE001
        print(f'  {rotulo}: erro {e}')
        return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url', nargs='?')
    ap.add_argument('--da-fila', action='store_true')
    args = ap.parse_args()

    url = args.url or (_url_da_fila() if args.da_fila else None)
    if not url:
        print('Informe a URL de um produto Amazon (ou use --da-fila).')
        sys.exit(1)

    _gate_fechar_navegadores()
    with sync_playwright() as p:
        context = launch_persistent(p, headless=False)
        page = _nova_page(context)
        store = registry.get_store('amazon')
        _goto_robusto(page, url, timeout=60000)
        page.wait_for_timeout(store.post_load_wait)
        print(f'\nURL final: {page.url[:100]}')

        print('\nblocos:')
        partes = [_bloco(page, THUMBS, 'miniaturas (#altImages ul)'),
                  _bloco(page, '#altImages', 'altImages inteiro'),
                  _bloco(page, '#main-image-container', 'container da imagem grande'),
                  _bloco(page, '#imageBlock', 'imageBlock (bloco todo)')]

        # O que existe DENTRO de cada miniatura: o codigo de hoje clica num
        # <input>; se ele sumiu, o que ficou no lugar?
        print('\nminiaturas, uma a uma:')
        itens = page.locator(THUMBS).locator('li')
        for i in range(itens.count()):
            li = itens.nth(i)
            info = li.evaluate("""el => ({
                classe: el.className,
                temInput: el.querySelectorAll('input').length,
                temBotao: el.querySelectorAll('button').length,
                temImg: el.querySelectorAll('img').length,
                img: (el.querySelector('img') || {}).src || '',
                clicavel: [...el.querySelectorAll('[class*=button],[role=button],span.a-button-inner')]
                          .map(e => e.tagName + '.' + e.className).slice(0, 3),
            })""")
            print(f"  li[{i}] class={info['classe'][:40]!r} input={info['temInput']} "
                  f"button={info['temBotao']} img={info['temImg']}")
            print(f"        img  = {info['img'][:110]}")
            if info['clicavel']:
                print(f"        clicaveis = {info['clicavel']}")

        # A fonte "sem clique": a Amazon costuma publicar as resolucoes de cada
        # foto num JSON no atributo data-a-dynamic-image.
        print('\ndata-a-dynamic-image encontrados:')
        dyn = page.evaluate("""() => [...document.querySelectorAll('[data-a-dynamic-image]')]
            .map(e => ({ id: e.id, alt: (e.alt || '').slice(0, 30),
                         json: e.getAttribute('data-a-dynamic-image').slice(0, 300) }))""")
        for d in dyn[:10]:
            print(f"  id={d['id']!r} alt={d['alt']!r}")
            print(f"    {d['json']}")
        if not dyn:
            print('  (nenhum)')

        with open(SAIDA, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(partes))
        print(f'\nGravado: {SAIDA}')
        context.close()


if __name__ == '__main__':
    main()
