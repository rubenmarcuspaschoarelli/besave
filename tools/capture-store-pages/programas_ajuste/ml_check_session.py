"""Verifica, sem abrir janela visivel de espera, se o perfil persistente
(.chrome_perfil) ja consegue abrir uma pagina de produto do ML sem cair no
wall "Para continuar, acesse sua conta". Rodar DEPOIS de fechar o
ml_login_wait.py (o perfil nao pode estar em uso por 2 processos ao mesmo
tempo).

    .venv/Scripts/python.exe -u ml_check_session.py
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
from playwright.sync_api import sync_playwright

from core.browser import launch_persistent

TEST_URL = 'https://www.mercadolivre.com.br/kit-wella-professionals-invigo-nutri-enrich-shampoo-mascara/p/MLB48188116'


def main():
    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(2500)
        wall = 'account-verification' in page.url or page.locator('text=Para continuar, acesse sua conta').count() > 0
        tem_titulo = page.locator('h1.ui-pdp-title').count() > 0
        print(f'url={page.url}')
        print(f'wall={wall} titulo_produto_ok={tem_titulo}')
        page.wait_for_timeout(3000)
        ctx.close()


if __name__ == '__main__':
    main()
