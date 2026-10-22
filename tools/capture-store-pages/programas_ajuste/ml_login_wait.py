"""Abre o Chrome persistente do projeto (.chrome_perfil) na tela de login do
ML e so espera (SEM checar nada, SEM abas extras) -- login fica no seu ritmo,
sem nenhuma atividade em segundo plano competindo com a pagina.

Rode UMA vez:
    .venv/Scripts/python.exe -u ml_login_wait.py

Quando terminar de logar, avise no chat. O script e' encerrado (fecha a
janela, mas o login/cookies ja ficam salvos no perfil em disco) e depois a
sessao e' verificada com um script separado (ml_check_session.py).
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import time

from playwright.sync_api import sync_playwright

from core.browser import launch_persistent


def main():
    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto('https://www.mercadolivre.com.br/hub/login', wait_until='domcontentloaded')

        print('=' * 64, flush=True)
        print('Janela aberta. Faca login no seu ritmo -- nenhuma checagem', flush=True)
        print('automatica vai rodar. Quando terminar, avise no chat.', flush=True)
        print('=' * 64, flush=True)

        # Espera indefinidamente (ate ser interrompido externamente).
        while True:
            time.sleep(3600)


if __name__ == '__main__':
    main()
