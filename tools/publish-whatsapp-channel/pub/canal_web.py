"""WhatsApp Web: abrir o canal, anexar a foto, escrever a legenda, enviar e confirmar (BSV-63).

Seletores do mapeamento do dono no WhatsApp Web real (16/11/2026; README, "Seletores"; recorte redigido em
tools/tests/fixtures/whatsapp_canal_real.html). So data-testid, aria-label, role e title (e os ids #side/#pane-side);
nunca as classes x..., XPath ou os ids dinamicos _r_..._. Os icones do WhatsApp sao <svg><title>, nao data-icon.
"""

import re
import time
import unicodedata
from functools import wraps
from pathlib import Path

from .publicador import OK, QR, BrowserMorto, FalhaPasso

WHATSAPP_URL = "https://web.whatsapp.com/"

SEL_LOGADO = ["#side", "#pane-side"]
# QR: fora do mapeamento de 16/11 (a sessao estava logada); aria-label do canvas, a conferir no primeiro QR.
SEL_QR = ['canvas[aria-label*="QR" i]', 'canvas[aria-label*="Scan" i]', 'canvas[aria-label*="Escaneie" i]']
SEL_ABA_CANAIS = 'button[aria-label="Canais"]'
SEL_BUSCA_CANAIS = '[data-testid="newsletter-tab-drawer"] input[type="text"]'
SEL_CELULA = '[data-testid="newsletter-tab-newsletter-cell"][aria-label="Canal {nome}"]'
SEL_TITULO = '[data-testid="conversation-info-header-chat-title"]'
SEL_CAIXA_CANAL = '[data-testid="conversation-compose-box-input"][contenteditable="true"]'
SEL_ANEXAR = '#main footer button[aria-label="Anexar"]'
SEL_INPUT_FOTO = '#main footer input[type="file"][accept="image/*"]'
TEXTO_MENU_FOTOS = "Fotos e vídeos"
SEL_LEGENDA = '[data-testid="media-caption-input-container"][contenteditable="true"][role="textbox"]'
SEL_ENVIAR = 'div[role="button"][aria-label="Enviar 1 item selecionado"]'
SEL_BALAO = '[data-testid^="conv-msg-"]'
SEL_LEGENDA_BALAO = '[data-testid~="image-caption"]'
SEL_STATUS_BALAO = '[data-testid="msg-meta"] [aria-label]'
STATUS_CONFIRMADO = frozenset({"enviada", "entregue", "lida"})     # real: " Enviada " (wds-ic-delivered)

ESPERA_SESSAO_S = 60
ESPERA_PASSO_S = 15
ESPERA_INPUT_S = 5
SONDA_MS = 500

_FECHADO = re.compile(r"Target page, context or browser has been closed|Target closed|Browser has been closed|"
                      r"Connection closed|browser has disconnected", re.IGNORECASE)

# Texto da caixa de legenda como o WhatsApp vai enviar: <p> = linha, <br> = quebra, <img alt> = emoji.
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


class ErroPagina(FalhaPasso):
    """Passo da pagina que nao deu: falha antes do clique (a linha continua P)."""


def _morto(f):
    """Erro do Playwright com o navegador fechado vira BrowserMorto (o processo sai e o systemd reinicia)."""
    @wraps(f)
    def g(*a, **k):
        try:
            return f(*a, **k)
        except (BrowserMorto, FalhaPasso):
            raise
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise BrowserMorto(str(e)[:200]) from e
            raise
    return g


def normalizar(texto: str) -> str:
    """Chave de comparacao de nome: sem acento, minusculo, so [a-z0-9] (emoji e marcacao somem)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


_NBSP = chr(0xA0)
_INVISIVEIS = re.compile("[" + "".join(map(chr, (0xFE0F, 0x200B, 0x200C, 0xFEFF))) + "]")


def _texto_normalizado(s: str) -> str:
    """NFC, quebras de linha unificadas, NBSP vira espaco, sem seletor de emoji nem largura zero.
    A marcacao (*, _, ~, `) fica: na caixa ela aparece crua, e DS_LEGENDA tambem e crua."""
    s = unicodedata.normalize("NFC", s or "").replace("\r\n", "\n").replace("\r", "\n").replace(_NBSP, " ")
    return _INVISIVEIS.sub("", s)


def igual_ao_editor(esperado: str, lido: str) -> bool:
    return _texto_normalizado(esperado) == _texto_normalizado(lido)


def tem_chave(texto: str, chave: str) -> bool:
    """`besave.io/5412` no texto, sem casar `besave.io/54120`."""
    return re.search(re.escape(chave) + r"(?!\d)", texto or "") is not None


def status_confirmado(rotulo: str | None) -> bool:
    return rotulo is not None and rotulo.strip().casefold() in STATUS_CONFIRMADO


def digitar(teclado, texto: str) -> None:
    """Digita linha a linha. No WhatsApp `Enter` ENVIA: a quebra de linha e `Shift+Enter`."""
    linhas = texto.split("\n")
    for i, linha in enumerate(linhas):
        if linha:
            teclado.insert_text(linha)
        if i < len(linhas) - 1:
            teclado.press("Shift+Enter")


def _aspas(nome: str) -> str:
    return nome.replace("\\", "\\\\").replace('"', '\\"')


class CanalWeb:
    def __init__(self, page, log=print):
        self.page = page
        self.log = log
        self._baloes_antes: set[str] = set()

    # ------------------------------------------------------------------------------------ auxiliares

    def _visivel(self, seletor: str, espera_s: float = 0):
        """Primeiro elemento visivel do seletor (locator) ou None; com espera, sonda ate achar."""
        fim = time.monotonic() + espera_s
        while True:
            loc = self.page.locator(seletor)
            for i in range(loc.count()):
                if loc.nth(i).is_visible():
                    return loc.nth(i)
            if time.monotonic() >= fim:
                return None
            self.page.wait_for_timeout(SONDA_MS)

    def _existe(self, seletor: str) -> bool:
        return self.page.locator(seletor).count() > 0

    def _canal_aberto(self, nome: str) -> bool:
        """Cabecalho com o titulo do canal: texto normalizado IGUAL ao nome (nao basta conter)."""
        titulo = self._visivel(SEL_TITULO)
        return titulo is not None and normalizar(titulo.inner_text(timeout=2_000)) == normalizar(nome)

    def _ids_baloes(self) -> set[str]:
        return set(self.page.locator(SEL_BALAO).evaluate_all("els => els.map(e => e.getAttribute('data-testid'))"))

    # ----------------------------------------------------------------------------------------- sessao

    @_morto
    def sessao(self) -> str:
        """ok (logado), qr (deslogado) ou carregando (nem um nem outro em 60 s)."""
        fim = time.monotonic() + ESPERA_SESSAO_S
        while True:
            if any(self._visivel(s) is not None for s in SEL_QR):
                return QR
            if any(self._existe(s) for s in SEL_LOGADO):
                return OK
            if time.monotonic() >= fim:
                return "carregando"
            self.page.wait_for_timeout(SONDA_MS)

    # ------------------------------------------------------------------------------------------ passos

    @_morto
    def abrir_canal(self, nome: str) -> None:
        """Cabecalho ja no canal e caixa visivel: nada a fazer. Senao: Canais -> busca -> celula -> confere."""
        if self._canal_aberto(nome) and self._visivel(SEL_CAIXA_CANAL) is not None:
            return
        aba = self._visivel(SEL_ABA_CANAIS, ESPERA_PASSO_S)
        if aba is None:
            raise ErroPagina("nao achei o botao Canais")
        aba.click()
        busca = self._visivel(SEL_BUSCA_CANAIS, ESPERA_PASSO_S)
        if busca is None:
            raise ErroPagina("nao achei a busca do painel de canais")
        busca.click()
        busca.fill("")
        busca.press_sequentially(nome, delay=30)
        celula = self._visivel(SEL_CELULA.format(nome=_aspas(nome)), ESPERA_PASSO_S)
        if celula is None:
            raise ErroPagina("o canal nao apareceu na busca")
        celula.click()
        fim = time.monotonic() + ESPERA_PASSO_S
        while not self._canal_aberto(nome):
            if time.monotonic() >= fim:
                raise ErroPagina("o cabecalho aberto nao e o do canal; nada enviado")
            self.page.wait_for_timeout(SONDA_MS)
        if self._visivel(SEL_CAIXA_CANAL, 5) is None:
            raise ErroPagina("canal aberto sem caixa de mensagem (o numero e admin do canal?)")

    @_morto
    def anexar(self, foto: Path) -> None:
        """set_input_files no input oculto do footer; sem ele, Anexar e espera o input; sem ele ainda, o item
        "Fotos e vídeos" dentro de expect_file_chooser. O dialogo do sistema nunca abre solto."""
        foto = str(foto)
        if not self._existe(SEL_INPUT_FOTO):
            botao = self._visivel(SEL_ANEXAR, 5)
            if botao is None:
                raise ErroPagina("nao achei o botao Anexar")
            botao.click()
            fim = time.monotonic() + ESPERA_INPUT_S
            while not self._existe(SEL_INPUT_FOTO) and time.monotonic() < fim:
                self.page.wait_for_timeout(SONDA_MS)
        if self._existe(SEL_INPUT_FOTO):
            self.page.locator(SEL_INPUT_FOTO).first.set_input_files(foto)
        else:
            item = self.page.get_by_text(TEXTO_MENU_FOTOS, exact=True)
            if item.count() == 0:
                raise ErroPagina("sem input de foto e sem o item Fotos e vídeos")
            with self.page.expect_file_chooser(timeout=ESPERA_INPUT_S * 1000) as escolha:
                item.first.click()
            escolha.value.set_files(foto)
        if self._visivel(SEL_LEGENDA, ESPERA_PASSO_S) is None:
            raise ErroPagina("a previa da foto nao abriu (sem a legenda da previa)")

    def texto_do_editor(self, caixa) -> str:
        return caixa.evaluate(_JS_TEXTO)

    @_morto
    def escrever_legenda(self, texto: str, modo: str = "colar") -> None:
        """Cola (ou digita) e confere cru com cru. Divergiu: limpa e tenta 1 vez (digitando). Divergiu de novo:
        fecha a previa e falha, sem D."""
        caixa = self._visivel(SEL_LEGENDA, 5)
        if caixa is None:
            raise ErroPagina("sem a legenda da previa")
        for m in (["colar", "digitar"] if modo == "colar" else ["digitar", "digitar"]):
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
        self.page.keyboard.press("Escape")
        raise ErroPagina("a legenda da previa nao ficou identica a DS_LEGENDA")

    @_morto
    def enviar(self) -> None:
        self._baloes_antes = self._ids_baloes()
        botao = self._visivel(SEL_ENVIAR, 5)
        if botao is None:
            raise ErroPagina("nao achei o Enviar da previa")
        botao.click()

    @_morto
    def confirmar(self, chave: str, timeout_s: float) -> bool:
        """Positiva: a previa fechou, ha balao NOVO (fora dos de antes do clique) cuja legenda tem `chave`
        (besave.io/{id}) e cujo msg-meta diz enviada/entregue/lida. Qualquer outro estado = nao confirmado."""
        fim = time.monotonic() + timeout_s
        while True:
            if self._visivel(SEL_LEGENDA) is None and self._balao_confirmado(chave):
                return True
            if time.monotonic() >= fim:
                return False
            self.page.wait_for_timeout(1_000)

    def _balao_confirmado(self, chave: str) -> bool:
        baloes = self.page.locator(SEL_BALAO)
        for i in range(baloes.count()):
            b = baloes.nth(i)
            if b.get_attribute("data-testid") in self._baloes_antes:
                continue
            legenda = b.locator(SEL_LEGENDA_BALAO)
            if legenda.count() == 0 or not tem_chave(legenda.first.inner_text(timeout=2_000), chave):
                continue
            status = b.locator(SEL_STATUS_BALAO)
            if status.count() > 0 and status_confirmado(status.first.get_attribute("aria-label")):
                return True
        return False

    @_morto
    def limpar(self) -> None:
        """Escape ate fechar a previa e o menu do Anexar (no maximo 4)."""
        for _ in range(4):
            menu = self.page.locator(f'{SEL_ANEXAR}[aria-expanded="true"]')
            if self._visivel(SEL_LEGENDA) is None and menu.count() == 0:
                return
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)

    @_morto
    def recarregar(self) -> None:
        self.page.reload(wait_until="domcontentloaded")
        self.sessao()


# --- DOM gravado (para conferir seletores no teste real) ----------------------------------------------

_RE_TELEFONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_RE_URL = re.compile(r"(?:https?|blob|data):[^\s\"'<>)]+", re.IGNORECASE)


def redigir_dom(html: str) -> str:
    """Tira numeros de telefone (8+ digitos), URLs (https, blob, data) e srcset. Nomes de contatos e grupos
    que aparecerem na lista NAO sao reconhecidos: o dono revisa o arquivo antes de versionar (regra 11)."""
    html = _RE_URL.sub("REDACTED", html)
    html = re.sub(r'\ssrcset="[^"]*"', "", html)
    return _RE_TELEFONE.sub("REDACTED", html)
