"""Login na Shopee usando o perfil persistente do Chrome real.

Rode UMA vez (a sessao fica salva no perfil dedicado .chrome_perfil):

    .venv/Scripts/python.exe -u shopee_login.py

Uma janela do Chrome real abre na tela de login. Faca login normalmente
(email/senha, OTP e resolva o captcha se aparecer). O script detecta sozinho
quando uma pagina de PRODUTO passa a carregar (prova de que a sessao funciona)
e ai encerra, deixando o login persistido no perfil. Nao precisa de ENTER.
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import time

from playwright.sync_api import sync_playwright

from core.browser import launch_persistent

# Produto usado so para TESTAR se a sessao ja acessa PDP sem cair no anti-bot.
TEST_URL = 'https://shopee.com.br/product/407776125/22497335924'
TIMEOUT_S = 600     # ate 10 min esperando voce logar/resolver captcha
INTERVALO_S = 20    # testa a cada 20s (gentil com o anti-bot)


def sessao_ok(test_page):
    try:
        test_page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
        test_page.wait_for_timeout(4000)
        return 'verify/' not in test_page.url and test_page.locator('#sll2-normal-pdp-main').count() > 0
    except Exception:
        return False


def main():
    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto('https://shopee.com.br/buyer/login', wait_until='domcontentloaded')

        print('=' * 64, flush=True)
        print('Faca login na janela do Chrome (email/senha, OTP) e RESOLVA o', flush=True)
        print('captcha se aparecer. O script detecta sozinho quando a sessao', flush=True)
        print(f'passa a acessar produtos (checa a cada {INTERVALO_S}s, ate {TIMEOUT_S // 60} min).', flush=True)
        print('=' * 64, flush=True)

        test_page = ctx.new_page()
        inicio = time.time()
        ok = False
        while time.time() - inicio < TIMEOUT_S:
            time.sleep(INTERVALO_S)
            if sessao_ok(test_page):
                ok = True
                break
            print(f'  ainda bloqueado/nao logado ({int(time.time() - inicio)}s)...', flush=True)

        test_page.close()
        if ok:
            print('SESSAO OK! Produto carregou. Login persistido no perfil.', flush=True)
        else:
            print('Tempo esgotado. O que estiver logado fica salvo no perfil mesmo assim.', flush=True)
        ctx.close()


if __name__ == '__main__':
    main()
