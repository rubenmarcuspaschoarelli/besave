"""Valida os seletores de stores/shopee.py contra os HTMLs salvos (offline).
Carrega cada dump com JS desligado (mantem o DOM estatico) e roda a captura."""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
from playwright.sync_api import sync_playwright
from stores.shopee import ShopeeStore

ARQUIVOS = [(635, 'destino/shopee_dump_635.html'),
            (643, 'destino/shopee_dump_643.html')]
CAMPOS = ['produto_titulo', 'preco_1', 'avaliacao_nota', 'avaliacao_quantidade',
          'quantidade_vendida', 'pais_origem', 'produto_descricao']

store = ShopeeStore()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(java_script_enabled=False)
    page = ctx.new_page()
    for idv, arq in ARQUIVOS:
        html = open(arq, encoding='utf-8').read()
        page.set_content(html, wait_until='domcontentloaded')
        out = store.capture(page)
        print(f'\n===== {idv} =====')
        for c in CAMPOS:
            v = out.get(c, '')
            if c == 'produto_descricao' and v:
                v = v[:60] + '...'
            print(f'  {c:22} = {v!r}')
        cats = out.get('lst_categorias') or []
        print(f'  lst_categorias         = {len(cats)} itens: {cats[:4]}')
        det = out.get('lst_Product_Detalhes_tecnicos') or []
        print(f'  lst_Detalhes_tecnicos  = {len(det)} pares')
        for d in det[:6]:
            print(f'       - {d.get("key")}: {str(d.get("value"))[:40]}')
    browser.close()
