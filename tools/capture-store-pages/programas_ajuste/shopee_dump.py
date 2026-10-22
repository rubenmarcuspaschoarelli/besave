"""
Dump do HTML atual de paginas de produto Shopee, para remapear os seletores com
hash que quebram a cada deploy. Reusa o perfil logado (.chrome_perfil) e NAO tem
input() -> roda direto no terminal:

    $env:PYTHONIOENCODING="utf-8"; .venv\\Scripts\\python.exe -u shopee_dump.py

Salva destino/shopee_dump_<id>.html para cada URL. Depois o HTML e inspecionado
para achar preco/nota/avaliacoes/vendas/detalhes.
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import os
from playwright.sync_api import sync_playwright
from core.browser import launch_persistent

# (id, url de origem) — os dois produtos Shopee do lote 635..643
ALVOS = [
    (635, 'https://s.shopee.com.br/70IcItns1B'),
    (643, 'https://s.shopee.com.br/6AjVLSe7wT'),
]
READY = '#sll2-normal-pdp-main'

from core.caminhos import em_log

with sync_playwright() as p:
    ctx = launch_persistent(p)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for idv, url in ALVOS:
        print(f'\n=== {idv} {url} ===')
        try:
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print('  goto:', e)
        try:
            page.wait_for_selector(READY, timeout=25000)
        except Exception:
            print('  READY ausente')
        page.wait_for_timeout(5000)
        print('  url_final:', page.url)
        print('  ready presente:', page.locator(READY).count() > 0)
        # sondas rapidas: texto de candidatos plausiveis
        for rot, sel in [
            ('h1', f'{READY} h1'),
            ('preco atual', ':is([class]):text-matches("^R\\\\$\\\\s?\\\\d")'),
        ]:
            try:
                loc = page.locator(sel).first
                print(f'  [{rot}] "{(loc.inner_text(timeout=1500) or "").strip()[:60]}"')
            except Exception:
                print(f'  [{rot}] (nao achou)')
        out = em_log(f'shopee_dump_{idv}.html')
        with open(out, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print('  HTML salvo em', out, f'({os.path.getsize(out)} bytes)')
    ctx.close()
print('\nDONE')
