"""Login no Mercado Livre usando o perfil persistente do projeto (.chrome_perfil).

Rode UMA vez (a sessao fica salva no perfil dedicado .chrome_perfil):

    .venv/Scripts/python.exe -u ml_login.py

Uma janela do Chrome abre na tela de login do ML. Faca login normalmente
(email/senha, 2FA se pedir). O script detecta sozinho quando uma pagina de
PRODUTO passa a carregar sem o wall de "Para continuar, acesse sua conta"
(ver captureamazon-backfill-qt-opinioes-pendente na memoria) e ai encerra,
deixando o login persistido no perfil. Nao precisa de ENTER.
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import time

from playwright.sync_api import sync_playwright

from core.browser import launch_persistent

# Produto usado so para TESTAR se a sessao ja acessa PDP sem cair no wall.
TEST_URL = 'https://www.mercadolivre.com.br/kit-wella-professionals-invigo-nutri-enrich-shampoo-mascara/p/MLB48188116'
TIMEOUT_S = 1800     # ate 30 min esperando voce logar
INTERVALO_S = 30     # testa a cada 30s (gentil com o anti-bot)
PAUSA_INICIAL_S = 180  # nao testa nada nos primeiros 3 min -- tempo p/ logar sem qualquer aba extra abrindo


def sessao_ok(test_page):
    try:
        test_page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
        test_page.wait_for_timeout(2500)
        return ('account-verification' not in test_page.url
                and test_page.locator('h1.ui-pdp-title').count() > 0)
    except Exception:
        return False


def main():
    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto('https://www.mercadolivre.com.br/hub/login', wait_until='domcontentloaded')

        print('=' * 64, flush=True)
        print('Faca login na janela do Chrome (email/senha, 2FA se pedir).', flush=True)
        print(f'Sem nenhuma checagem nos primeiros {PAUSA_INICIAL_S // 60} min -- login com calma.', flush=True)
        print('Depois disso, o script detecta sozinho quando a sessao passa a', flush=True)
        print(f'acessar produtos sem o wall (checa a cada {INTERVALO_S}s, ate {TIMEOUT_S // 60} min no total).', flush=True)
        print('=' * 64, flush=True)

        time.sleep(PAUSA_INICIAL_S)

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
            print('SESSAO OK! Produto carregou sem wall. Login persistido no perfil.', flush=True)
        else:
            print('Tempo esgotado. O que estiver logado fica salvo no perfil mesmo assim.', flush=True)
        ctx.close()


if __name__ == '__main__':
    main()
