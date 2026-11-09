"""
Abertura do WhatsApp Web com contexto persistente (QR lido apenas 1x)
e navegacao ate o grupo alvo.

Estrategia de seletores: usamos SEMPRE ancoras estaveis (data-testid,
contenteditable, #main) e nunca as classes ofuscadas (x1lliihq, xnpuxes...),
pois a Meta rotaciona essas classes entre deploys.
"""

import re
import unicodedata
from pathlib import Path

from . import destravar

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


class ConversaErrada(RuntimeError):
    """A conversa aberta nao e o grupo pedido (nada foi lido dela)."""


def normalizar_nome(texto: str) -> str:
    """
    Chave de comparacao de nome de conversa: sem acento, minusculo, so [a-z0-9].
    Emoji some (e no DOM vira <img alt>, ausente do innerText), entao
    '@achadinhoscomcarol 🛍️ 9' -> 'achadinhoscomcarol9'.
    """
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _texto(page, seletor: str):
    """innerText do 1o elemento do seletor, ou None se nao existir/nao der p/ ler."""
    try:
        loc = page.locator(seletor).first
        if loc.count() == 0:
            return None
        return loc.inner_text(timeout=2_000)
    except Exception:  # noqa: BLE001
        return None


def abrir_grupo(page, nome_grupo: str, timeout: int = 30_000):
    """
    Pesquisa o grupo pelo nome, seleciona o primeiro resultado
    (data-testid="list-item-1") e espera o painel de mensagens (#main).

    Confere o NOME duas vezes, porque o rodizio le como "nova" toda mensagem
    nao vista da conversa aberta: em 31/08/2026 a busca ainda nao tinha
    filtrado, o list-item-1 era a conversa mais recente da lista normal e 67
    mensagens PESSOAIS (familia, grupo de trabalho) viraram ofertas dos grupos.
      1) antes do clique, espera o 1o resultado conter o nome do grupo;
      2) depois de abrir, o cabecalho da conversa tem que conter o nome.
    Divergencia levanta ConversaErrada (o rodizio trata como falha e tenta de
    novo na volta seguinte). Se o texto nao der para LER (seletor mudou numa
    versao nova do WhatsApp), so avisa e segue — nao trava a captura.
    """
    print(f"[browser] Abrindo grupo: {nome_grupo!r}")

    # 1) Foca a caixa de pesquisa (varios fallbacks por robustez).
    page.wait_for_selector("#side", timeout=timeout)
    busca = _achar_caixa_busca(page)
    if busca is None:
        raise RuntimeError("Nao encontrei a caixa de pesquisa do WhatsApp.")

    destravar.clicar(page, busca)
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

    # 2b) So clica quando o 1o resultado for o grupo (a busca pode ainda nao
    # ter filtrado). Ate ~6s; o texto do item traz nome + ultima msg + hora.
    chave = normalizar_nome(nome_grupo)
    texto_item = None
    for _ in range(12):
        texto_item = _texto(page, '[data-testid="list-item-1"]') \
            or _texto(page, '#pane-side [role="listitem"]')
        if texto_item is None or chave in normalizar_nome(texto_item):
            break
        page.wait_for_timeout(500)
    if texto_item is None:
        print("[browser] AVISO: nao consegui ler o 1o resultado da busca; clicando sem conferir.")
    elif chave not in normalizar_nome(texto_item):
        raise ConversaErrada(
            f"1o resultado da busca nao e {nome_grupo!r}: {texto_item[:80]!r}")

    def conferir_item():
        # Escape pode limpar a busca: antes de repetir, o 1o resultado ainda tem de ser o grupo.
        texto = _texto(page, '[data-testid="list-item-1"]')             or _texto(page, '#pane-side [role="listitem"]')
        if texto is not None and chave not in normalizar_nome(texto):
            raise ConversaErrada(
                f"depois de destravar, o 1o resultado nao e {nome_grupo!r}: {texto[:80]!r}")

    destravar.clicar(page, item, antes_de_repetir=conferir_item)

    # 3) Espera o painel de conversa carregar.
    page.wait_for_selector("#main", timeout=timeout)
    page.wait_for_selector(
        '#main [data-testid="conversation-panel-messages"]', timeout=timeout
    )

    # 4) Confere o cabecalho da conversa aberta.
    cabecalho = _texto(page, "#main header")
    if cabecalho is None:
        print("[browser] AVISO: nao consegui ler o cabecalho da conversa; seguindo sem conferir.")
    elif chave not in normalizar_nome(cabecalho):
        raise ConversaErrada(
            f"conversa aberta nao e {nome_grupo!r}: cabecalho {cabecalho[:80]!r}")
    print("[browser] Grupo aberto, painel de mensagens pronto.")
