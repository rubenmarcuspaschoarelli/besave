"""WhatsApp Web: abrir o canal, anexar a foto, escrever a legenda, enviar e confirmar (BSV-63).

So ancoras estaveis (id, data-icon, aria-label, role, span[title]); nunca as classes ofuscadas, que a Meta
troca a cada deploy. Cada lista e tentada em ordem; o primeiro seletor visivel vence.

ORIGEM DOS SELETORES (ver README, "Seletores"):
  - `#side`, `#pane-side`, `#main`, `#main header`, caixa de busca, `list-item`: as mesmas ancoras do robo da
    captura (capture-chat-groups/wa/browser.py), em uso diario desde 07/2026;
  - aba de canais, anexo, legenda, enviar, relogio de pendente e QR: `data-icon`/`aria-label` do WhatsApp Web
    conhecidos, AINDA NAO CONFERIDOS no numero de publicacao. A conferencia e no teste real da inst2, com
    `python main.py --gravar-dom` (DOM redigido) — ate la a fixture dos testes e sintetica.
"""

import re
import time
import unicodedata
from functools import wraps
from pathlib import Path

from .publicador import OK, QR, BrowserMorto

WHATSAPP_URL = "https://web.whatsapp.com/"

SEL_LOGADO = ["#pane-side", "#side"]
SEL_QR = ['canvas[aria-label*="QR" i]', 'canvas[aria-label*="Scan" i]', "div[data-ref] canvas",
          '[data-testid="qrcode"]']
SEL_ABA_CANAIS = ['[aria-label="Canais"]', '[aria-label="Channels"]', '[data-icon="newsletter-outline"]',
                  '[data-icon="newsletter"]', '[aria-label="Atualizações"]', '[aria-label="Updates"]']
SEL_BUSCA = ['#side input[role="textbox"]', 'input[aria-label^="Pesquisar"]', 'input[aria-label*="Search"]',
             '#side div[contenteditable="true"][data-tab="3"]', 'div[contenteditable="true"][role="textbox"][data-tab="3"]']
SEL_CABECALHO = "#main header"
SEL_CAIXA_CANAL = ['#main footer div[contenteditable="true"]']
SEL_ANEXAR = ['#main footer [data-icon="plus-rounded"]', '#main footer [data-icon="plus"]',
              '#main footer [data-icon="attach-menu-plus"]', '#main footer [data-icon="clip"]',
              '#main footer [aria-label="Anexar"]', '#main footer [aria-label="Attach"]',
              '#main footer [title="Anexar"]']
SEL_INPUT_FOTO = ['input[type="file"][accept*="image"]']
SEL_LEGENDA = ['div[contenteditable="true"][aria-label*="legenda" i]', 'div[contenteditable="true"][aria-label*="caption" i]',
               'div[contenteditable="true"][aria-placeholder*="legenda" i]',
               'div[contenteditable="true"][aria-placeholder*="caption" i]']
SEL_ENVIAR = ['[aria-label="Enviar"]', '[aria-label="Send"]', '[data-icon="send"]', '[data-icon="wds-ic-send-filled"]']
SEL_BALAO = '#main [role="row"]'
SEL_PENDENTE = '[data-icon="msg-time"], [data-icon*="msg-time"]'
SEL_MODAL = '[role="dialog"]'

ESPERA_SESSAO_S = 60
ESPERA_PASSO_MS = 15_000
SONDA_MS = 500

_FECHADO = re.compile(r"Target page, context or browser has been closed|Target closed|Browser has been closed|"
                      r"Connection closed|browser has disconnected", re.IGNORECASE)

# Texto do editor como o WhatsApp vai enviar: <p> = linha, <br> = quebra, <img alt> = emoji.
_JS_TEXTO = """(el) => {
  const txt = (n) => { let s = '';
    n.childNodes.forEach(c => {
      if (c.nodeType === 3) s += c.data;
      else if (c.nodeName === 'IMG') s += c.getAttribute('alt') || '';
      else if (c.nodeName === 'BR') s += '\\n';
      else s += txt(c);
    });
    return s; };
  const bloco = (n) => { const s = txt(n); return s.endsWith('\\n') ? s.slice(0, -1) : s; };
  const ps = Array.from(el.children).filter(c => c.nodeName === 'P' || c.nodeName === 'DIV');
  return ps.length ? ps.map(bloco).join('\\n') : bloco(el);
}"""

_JS_COLAR = """(el, texto) => {
  el.focus();
  const dt = new DataTransfer();
  dt.setData('text/plain', texto);
  el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
}"""


class ErroPagina(RuntimeError):
    """Passo da pagina que nao deu (canal nao abriu, anexo falhou, legenda diferente...)."""


def _morto(f):
    """Erro do Playwright com o navegador fechado vira BrowserMorto (o processo sai e o systemd reinicia)."""
    @wraps(f)
    def g(*a, **k):
        try:
            return f(*a, **k)
        except (BrowserMorto, ErroPagina):
            raise
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise BrowserMorto(str(e)[:200]) from e
            raise
    return g


def normalizar(texto: str) -> str:
    """Chave de comparacao: sem acento, minusculo, so [a-z0-9] (emoji e marcacao somem)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def chave_confirmacao(legenda: str, n: int = 40) -> str:
    """Comeco da 1a linha da legenda (o titulo), normalizado: e o que o balao mostra primeiro."""
    for linha in legenda.splitlines():
        k = normalizar(linha)
        if k:
            return k[:n]
    return normalizar(legenda)[:n]


_NBSP = chr(0xA0)
_INVISIVEIS = re.compile("[" + "".join(map(chr, (0xFE0F, 0x200B, 0x200C, 0xFEFF))) + "]")


def igual_ao_editor(esperado: str, lido: str) -> bool:
    """Compara o texto do editor com DS_LEGENDA. Tolera so o que o DOM troca sem mudar o post:
    NBSP por espaco, U+FE0F (seletor de emoji) e caracteres de largura zero."""
    def limpo(s):
        s = unicodedata.normalize("NFC", s or "").replace(_NBSP, " ")
        return _INVISIVEIS.sub("", s)
    return limpo(esperado) == limpo(lido)


def digitar(teclado, texto: str) -> None:
    """Digita linha a linha. No WhatsApp `Enter` ENVIA: a quebra de linha e `Shift+Enter`."""
    linhas = texto.split("\n")
    for i, linha in enumerate(linhas):
        if linha:
            teclado.insert_text(linha)
        if i < len(linhas) - 1:
            teclado.press("Shift+Enter")


class CanalWeb:
    def __init__(self, page, log=print):
        self.page = page
        self.log = log
        self._baloes_antes = 0

    # ------------------------------------------------------------------------------------ auxiliares

    def _visivel(self, seletores, timeout_ms=0):
        """Primeiro seletor visivel (locator) ou None. Com timeout, sonda ate achar."""
        fim = time.monotonic() + timeout_ms / 1000
        while True:
            for sel in seletores:
                loc = self.page.locator(sel)
                try:
                    n = loc.count()
                except Exception as e:
                    if _FECHADO.search(str(e)):
                        raise
                    n = 0
                for i in range(n):
                    item = loc.nth(i)
                    if item.is_visible():
                        return item
            if time.monotonic() >= fim:
                return None
            self.page.wait_for_timeout(SONDA_MS)

    def _cabecalho_tem(self, nome: str) -> bool:
        cab = self.page.locator(SEL_CABECALHO)
        if cab.count() == 0:
            return False
        try:
            return normalizar(nome) in normalizar(cab.first.inner_text(timeout=2_000))
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise
            return False

    # ----------------------------------------------------------------------------------------- sessao

    @_morto
    def sessao(self) -> str:
        """ok (logado), qr (deslogado) ou carregando (nem um nem outro em 60 s)."""
        fim = time.monotonic() + ESPERA_SESSAO_S
        while True:
            if self._visivel(SEL_QR) is not None:
                return QR
            if self._visivel(SEL_LOGADO) is not None:
                return OK
            if time.monotonic() >= fim:
                return "carregando"
            self.page.wait_for_timeout(SONDA_MS)

    # ------------------------------------------------------------------------------------------ passos

    @_morto
    def abrir_canal(self, nome: str) -> None:
        if self._cabecalho_tem(nome) and self._visivel(SEL_CAIXA_CANAL) is not None:
            return
        aba = self._visivel(SEL_ABA_CANAIS)
        if aba is not None:
            aba.click()
        alvo = self._visivel([f'#app span[title="{_aspas(nome)}"]'], timeout_ms=3_000)
        if alvo is None:
            busca = self._visivel(SEL_BUSCA, timeout_ms=5_000)
            if busca is None:
                raise ErroPagina("nao achei o canal na lista nem a caixa de pesquisa")
            busca.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            self.page.keyboard.type(nome, delay=30)
            alvo = self._visivel([f'#app span[title="{_aspas(nome)}"]'], timeout_ms=ESPERA_PASSO_MS)
            if alvo is None:
                raise ErroPagina("o canal nao apareceu na pesquisa")
        alvo.click()
        fim = time.monotonic() + ESPERA_PASSO_MS / 1000
        while not self._cabecalho_tem(nome):
            if time.monotonic() >= fim:
                raise ErroPagina("o cabecalho aberto nao e o do canal")
            self.page.wait_for_timeout(SONDA_MS)
        if self._visivel(SEL_CAIXA_CANAL, timeout_ms=5_000) is None:
            raise ErroPagina("canal aberto sem caixa de mensagem (o numero e admin do canal?)")

    @_morto
    def anexar(self, foto: Path) -> None:
        botao = self._visivel(SEL_ANEXAR, timeout_ms=5_000)
        if botao is None:
            raise ErroPagina("nao achei o botao de anexar")
        botao.click()
        fim = time.monotonic() + 5
        entrada = None
        while entrada is None:
            for sel in SEL_INPUT_FOTO:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    entrada = loc.first
                    break
            if entrada is None:
                if time.monotonic() >= fim:
                    raise ErroPagina("nao achei a entrada de foto do anexo")
                self.page.wait_for_timeout(SONDA_MS)
        entrada.set_input_files(str(foto))
        if self._visivel(SEL_LEGENDA, timeout_ms=ESPERA_PASSO_MS) is None:
            raise ErroPagina("a previa da foto nao abriu (sem caixa de legenda)")

    def texto_do_editor(self, caixa) -> str:
        return caixa.evaluate(_JS_TEXTO)

    @_morto
    def escrever_legenda(self, texto: str, modo: str = "colar") -> None:
        caixa = self._visivel(SEL_LEGENDA, timeout_ms=5_000)
        if caixa is None:
            raise ErroPagina("sem caixa de legenda")
        modos = ["colar", "digitar"] if modo == "colar" else ["digitar"]
        for m in modos:
            caixa.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            if m == "colar":
                caixa.evaluate(_JS_COLAR, texto)
            else:
                digitar(self.page.keyboard, texto)
            self.page.wait_for_timeout(300)
            lido = self.texto_do_editor(caixa)
            if igual_ao_editor(texto, lido):
                return
            self.log(f"[pagina] WARN legenda pelo modo {m} chegou diferente ({len(lido)} de {len(texto)} caracteres)")
        raise ErroPagina("a legenda no editor nao ficou identica a DS_LEGENDA")

    @_morto
    def enviar(self) -> None:
        self._baloes_antes = self.page.locator(SEL_BALAO).count()
        botao = self._visivel(SEL_ENVIAR, timeout_ms=5_000)
        if botao is None:
            raise ErroPagina("nao achei o botao de enviar")
        botao.click()

    @_morto
    def confirmar(self, legenda: str, timeout_s: float) -> bool:
        """Balao novo com o comeco da legenda e sem o relogio de pendente (rede caida mostra o balao local
        com relogio: so o balao daria confirmacao falsa)."""
        chave = chave_confirmacao(legenda)
        fim = time.monotonic() + timeout_s
        while True:
            baloes = self.page.locator(SEL_BALAO)
            n = baloes.count()
            for i in range(max(self._baloes_antes, n - 5), n):
                b = baloes.nth(i)
                try:
                    if chave in normalizar(b.inner_text(timeout=2_000)) and b.locator(SEL_PENDENTE).count() == 0:
                        return True
                except Exception as e:
                    if _FECHADO.search(str(e)):
                        raise
            if time.monotonic() >= fim:
                return False
            self.page.wait_for_timeout(1_000)

    @_morto
    def limpar(self) -> None:
        """Escape ate fechar previa e modais (no maximo 4)."""
        for _ in range(4):
            if self._visivel(SEL_LEGENDA) is None and self._visivel([SEL_MODAL]) is None:
                return
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)

    @_morto
    def recarregar(self) -> None:
        self.page.reload(wait_until="domcontentloaded")
        self.sessao()


def _aspas(nome: str) -> str:
    return nome.replace("\\", "\\\\").replace('"', '\\"')


# --- DOM gravado (para conferir seletores no teste real) ----------------------------------------------

_RE_TELEFONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_RE_URL = re.compile(r"(?:https?|blob|data):[^\s\"'<>)]+", re.IGNORECASE)


def redigir_dom(html: str) -> str:
    """Tira numeros de telefone (8+ digitos), URLs (https, blob, data) e srcset. Nomes de contatos e grupos
    que aparecerem na lista NAO sao reconhecidos: o dono revisa o arquivo antes de versionar (regra 11)."""
    html = _RE_URL.sub("REDACTED", html)
    html = re.sub(r'\ssrcset="[^"]*"', "", html)
    return _RE_TELEFONE.sub("REDACTED", html)
