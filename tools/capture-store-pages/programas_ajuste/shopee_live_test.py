"""Login + captura Shopee na MESMA janela (uma so).

Abre UMA janela do perfil de automacao, espera voce logar NELA e, assim que a
sessao acessar produtos, captura os itens de origem/subset_shopee.csv sem abrir
nenhuma outra janela. Serve para testar a Shopee sem a confusao de multiplas
janelas / conflito de lock.

    .venv/Scripts/python.exe -u shopee_live_test.py
"""
import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import time

from playwright.sync_api import sync_playwright

from core.browser import launch_persistent
from core import csv_io, registry

SUBSET = 'origem/subset_shopee.csv'
TIMEOUT_S = 600      # ate 10 min esperando o login NESTA janela
INTERVALO_S = 15


def main():
    fields, rows = csv_io.read_origem(SUBSET)
    store = registry.get_store('shopee')

    with sync_playwright() as p:
        ctx = launch_persistent(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto('https://shopee.com.br/buyer/login', wait_until='domcontentloaded')

        print('=' * 68, flush=True)
        print('>> FACA LOGIN NESTA JANELA QUE ACABOU DE ABRIR (a janela VAZIA,', flush=True)
        print('   sem seus favoritos/abas). NAO use seu Chrome normal.', flush=True)
        print(f'   Vou checar a cada {INTERVALO_S}s se a sessao ja acessa produtos.', flush=True)
        print('=' * 68, flush=True)

        # Poll de login numa aba SEPARADA (nao atrapalha o form de login da aba 1).
        test_page = ctx.new_page()
        test_url = (rows[0].get('url') or '').strip()
        inicio = time.time()
        ready = False
        while time.time() - inicio < TIMEOUT_S:
            time.sleep(INTERVALO_S)
            try:
                test_page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
                test_page.wait_for_timeout(4000)
                if 'verify/' not in test_page.url and test_page.locator(store.ready_selector).count() > 0:
                    ready = True
                    break
                print(f'  ainda nao logado/bloqueado ({int(time.time() - inicio)}s)...', flush=True)
            except Exception as e:
                print(f'  aguardando login ({int(time.time() - inicio)}s)... [{type(e).__name__}]', flush=True)
        test_page.close()

        if not ready:
            print('Tempo esgotado sem sessao valida. Encerrando.', flush=True)
            ctx.close()
            return

        print('SESSAO OK! Capturando os', len(rows), 'produtos na mesma janela...', flush=True)
        for r in rows:
            url = (r.get('url') or '').strip()
            cap = (r.get('numero_da_captura') or '').strip()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                store.prepare(page)
                if store.ready_selector:
                    try:
                        page.wait_for_selector(store.ready_selector, timeout=25000)
                    except Exception:
                        pass
                page.wait_for_timeout(store.post_load_wait)
                bloqueado = ('verify/' in page.url or
                             (store.ready_selector and page.locator(store.ready_selector).count() == 0))
                if bloqueado:
                    print(f'  cap {cap:>3}: BLOQUEADO/sem-produto -> {page.url[:60]}', flush=True)
                    continue
                data = store.capture(page)
                print(f'  cap {cap:>3}: OK | titulo={str(data.get("produto_titulo",""))[:45]!r} '
                      f'| preco_1={data.get("preco_1")!r} | nota={data.get("avaliacao_nota")!r} '
                      f'| detalhes={len(data.get("lst_Product_Detalhes_tecnicos") or [])}', flush=True)
            except Exception as e:
                print(f'  cap {cap:>3}: ERRO {type(e).__name__}: {e}', flush=True)

        print('Fim do teste. Deixando a janela aberta 5s...', flush=True)
        page.wait_for_timeout(5000)
        ctx.close()


if __name__ == '__main__':
    main()
