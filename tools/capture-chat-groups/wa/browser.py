"""
Abertura do WhatsApp Web com contexto persistente (QR lido apenas 1x)
e navegacao ate o grupo alvo.

Estrategia de seletores: usamos SEMPRE ancoras estaveis (data-testid,
contenteditable, #main) e nunca as classes ofuscadas (x1lliihq, xnpuxes...),
pois a Meta rotaciona essas classes entre deploys.
"""

from pathlib import Path

WHATSAPP_URL = "https://web.whatsapp.com/"

# Diretorio onde a sessao (cookies/login) fica persistida.
USER_DATA_DIR = str(Path(__file__).resolve().parent.parent / "user_data")


def abrir_whatsapp(playwright, headless: bool = False):
    """
    Inicia o Chromium com contexto persistente e retorna (context, page).

    Na primeira execucao sera necessario ler o QR Code. Nas proximas o login
    ja estara salvo em USER_DATA_DIR e a sessao abre direto.
    """
    context = playwright.chromium.launch_persistent_context(
        USER_DATA_DIR,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--start-maximized"],
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto(WHATSAPP_URL, wait_until="domcontentloaded")

    print("[browser] Aguardando o WhatsApp Web carregar...")
    print("[browser] Se aparecer o QR Code, escaneie com o celular (so na 1a vez).")

    # Espera ate a interface principal estar disponivel (login concluido).
    # '#pane-side' e o painel de conversas: ancora estavel e independente de
    # idioma, que so aparece depois de autenticar.
    page.wait_for_selector("#pane-side", timeout=300_000)  # ate 5 min p/ o QR
    print("[browser] Sessao autenticada.")
    return context, page


def _achar_caixa_busca(page):
    """Localiza a caixa de pesquisa do painel esquerdo (varios fallbacks).

    No WhatsApp atual e um <input> com aria-label 'Pesquisar...'. Mantemos
    tambem os fallbacks de contenteditable para outras versoes/idiomas.
    """
    seletores = [
        '[data-testid="chat-list-search-container"] input',
        '#side input[role="textbox"]',
        'input[aria-label^="Pesquisar"]',
        'input[aria-label*="Search"]',
        '#side div[contenteditable="true"][data-tab="3"]',
        '#side div[contenteditable="true"]',
    ]
    for sel in seletores:
        el = page.query_selector(sel)
        if el is not None:
            return el
    return None


def abrir_grupo(page, nome_grupo: str, timeout: int = 30_000):
    """
    Pesquisa o grupo pelo nome, seleciona o primeiro resultado
    (data-testid="list-item-1") e espera o painel de mensagens (#main).
    """
    print(f"[browser] Abrindo grupo: {nome_grupo!r}")

    # 1) Foca a caixa de pesquisa (varios fallbacks por robustez).
    page.wait_for_selector("#side", timeout=timeout)
    busca = _achar_caixa_busca(page)
    if busca is None:
        raise RuntimeError("Nao encontrei a caixa de pesquisa do WhatsApp.")

    busca.click()
    # Limpa qualquer texto residual e digita o nome do grupo.
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.keyboard.type(nome_grupo, delay=40)

    # 2) Espera o primeiro item da lista de resultados e clica.
    # Usamos locator (nao ElementHandle): ele re-resolve e re-tenta o clique,
    # evitando o erro "Element is not attached to the DOM" quando o WhatsApp
    # re-renderiza a lista virtualizada.
    item = page.locator('[data-testid="list-item-1"]').first
    try:
        item.wait_for(state="visible", timeout=timeout)
    except Exception:
        item = page.locator('#pane-side [role="listitem"]').first
        item.wait_for(state="visible", timeout=timeout)

    page.wait_for_timeout(1200)  # deixa a lista de resultados estabilizar
    item.click()

    # 3) Espera o painel de conversa carregar.
    page.wait_for_selector("#main", timeout=timeout)
    page.wait_for_selector(
        '#main [data-testid="conversation-panel-messages"]', timeout=timeout
    )
    print("[browser] Grupo aberto, painel de mensagens pronto.")
