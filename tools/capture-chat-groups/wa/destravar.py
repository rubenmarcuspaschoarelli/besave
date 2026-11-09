"""
Destrava a lista de conversas quando um aviso/dialogo do WhatsApp Web cobre a tela.

Medido em 22/10/2026: um aviso dentro de #wa-popovers-bucket interceptou o clique
no grupo e o robo girou 5h30 sem capturar (antes, 03/08, foi um modal por 48 min).

Ordem, por clique: 1) clica; 2) se interceptado, Escape e clica de novo; 3) se
ainda interceptado, fecha um aviso da LISTA FECHADA abaixo e clica de novo; 4)
senao, erro tratado da volta (nunca um laco no mesmo clique).

So stdlib: o teste roda no CI sem Playwright. Nada aqui toca contador ou marcadores.
"""

import re
import unicodedata

# Por tentativa. Ordem de segundos: o padrao do Playwright (30 s) mais o retry
# interno do clique segurava o robo por minutos em cada volta.
CLIQUE_TIMEOUT_MS = 5_000

# Onde avisos e dialogos vivem. Botao fora destes containers nunca e clicado.
CONTAINERS_AVISO = ("#wa-popovers-bucket", '[role="dialog"]')

# LISTA FECHADA de botoes que o robo pode clicar (texto ou aria-label inteiro,
# sem acento e sem caixa). Nunca entra aqui nada que mude conta, grupo ou
# mensagem (sair do grupo, apagar, responder, cancelar, denunciar...).
TEXTOS_FECHAR = ("fechar", "ok", "agora nao", "close", "not now")

# Voltas cegas seguidas ate recarregar a pagina (~10 min; repete a cada N).
RECARREGAR_VOLTAS_PADRAO = 8

_INTERCEPTADO = "intercepts pointer events"

_JS_FECHAR = r"""
(arg) => {
  const norm = s => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
                      .replace(/\s+/g, ' ').trim().toLowerCase();
  for (const seletor of arg.containers) {
    for (const caixa of document.querySelectorAll(seletor)) {
      for (const el of caixa.querySelectorAll('button, [role="button"]')) {
        const rotulos = [el.innerText, el.getAttribute('aria-label')];
        const achou = rotulos.map(norm).find(r => r && arg.textos.includes(r));
        if (achou) {
          const aviso = (caixa.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120);
          el.click();
          return {botao: achou, aviso: aviso};
        }
      }
    }
  }
  return null;
}
"""


class CliqueBloqueado(RuntimeError):
    """Clique interceptado e nada da lista fechada o destravou."""


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def texto_permitido(texto: str) -> bool:
    """True se o texto/aria-label e' exatamente um dos botoes de fechar permitidos."""
    return _norm(texto) in TEXTOS_FECHAR


def foi_interceptado(erro) -> bool:
    return _INTERCEPTADO in str(erro)


def fechar_aviso(page):
    """Clica UM botao permitido de aviso/dialogo. Devolve {botao, aviso} ou None."""
    try:
        return page.evaluate(
            _JS_FECHAR, {"containers": list(CONTAINERS_AVISO), "textos": list(TEXTOS_FECHAR)}
        )
    except Exception as e:  # noqa: BLE001
        print(f"[destravar] Nao consegui procurar botao de fechar: {e}")
        return None


def clicar(page, alvo, antes_de_repetir=None, timeout_ms: int = CLIQUE_TIMEOUT_MS) -> None:
    """
    Clica em `alvo` (locator ou handle). Sem interceptacao e' um clique so, como
    sempre foi. `antes_de_repetir()` roda antes de cada novo clique (ex.: conferir
    que a busca continua na tela depois do Escape); pode levantar para abortar.
    """
    try:
        alvo.click(timeout=timeout_ms)
        return
    except Exception as e:
        if not foi_interceptado(e):
            raise
        print("[destravar] Clique interceptado por outro elemento; tentando Escape.")

    page.keyboard.press("Escape")
    if antes_de_repetir:
        antes_de_repetir()
    try:
        alvo.click(timeout=timeout_ms)
        print("[destravar] Escape destravou o clique.")
        return
    except Exception as e:
        if not foi_interceptado(e):
            raise

    fechado = fechar_aviso(page)
    if fechado is None:
        raise CliqueBloqueado("clique interceptado; Escape nao resolveu e nao ha aviso conhecido para fechar")
    print(f"[destravar] Fechei {fechado.get('botao')!r} do aviso: {fechado.get('aviso', '')!r}")
    if antes_de_repetir:
        antes_de_repetir()
    try:
        alvo.click(timeout=timeout_ms)
    except Exception as e:
        if foi_interceptado(e):
            raise CliqueBloqueado("clique ainda interceptado depois de fechar o aviso") from e
        raise


def recarregar(page, espera_ms: int = 120_000) -> bool:
    """Ultimo recurso: recarrega o WhatsApp Web e espera a lista. True se voltou."""
    print("[destravar] Recarregando o WhatsApp Web (grupos sem abrir ha varias voltas).")
    try:
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#pane-side", timeout=espera_ms)
    except Exception as e:  # noqa: BLE001
        print(f"[destravar] Recarregamento nao concluiu: {e}")
        return False
    print("[destravar] Recarregado; lista de conversas de volta.")
    return True


def recarregar_voltas(cfg) -> int:
    """`destravar.recarregar_voltas` do config.json; ausente ou invalido = padrao."""
    bloco = (cfg or {}).get("destravar")
    try:
        n = int((bloco if isinstance(bloco, dict) else {}).get("recarregar_voltas"))
    except (TypeError, ValueError):
        return RECARREGAR_VOLTAS_PADRAO
    return n if n > 0 else RECARREGAR_VOLTAS_PADRAO
