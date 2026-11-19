"""WhatsApp Web: abrir o canal, anexar a foto, escrever a legenda, enviar e confirmar (BSV-63).

Seletores do mapeamento do dono no WhatsApp Web real (16/11/2026; README, "Seletores"; recorte redigido em
tools/tests/fixtures/whatsapp_canal_real.html). So data-testid, aria-label, role e title (e os ids #side/#pane-side);
nunca as classes x..., XPath ou os ids dinamicos _r_..._. Os icones do WhatsApp sao <svg><title>, nao data-icon.
"""

import re
import time
import unicodedata
from datetime import datetime
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
# Camada a fechar com Escape: qualquer [role="dialog"] MENOS o aviso fixo do canal ("Os canais no seu pais...",
# conversation-subheader), que tambem e role=dialog e nunca some. Escape sem camada aberta fecha a conversa.
SEL_DIALOGO = '[role="dialog"]:not(:has([data-testid="conversation-subheader"]))'
TEXTO_MENU_FOTOS = "Fotos e vídeos"
SEL_LEGENDA = '[data-testid="media-caption-input-container"][contenteditable="true"][role="textbox"]'
SEL_ENVIAR = 'div[role="button"][aria-label="Enviar 1 item selecionado"]'
SEL_BALAO = '[data-testid^="conv-msg-"]'
SEL_LEGENDA_BALAO = '[data-testid~="image-caption"]'
SEL_STATUS_BALAO = '[data-testid="msg-meta"] [aria-label]'
STATUS_CONFIRMADO = frozenset({"enviada", "entregue", "lida"})     # real: " Enviada " (wds-ic-delivered)

ESPERA_SESSAO_S = 60
ESPERA_PASSO_S = 15
ESPERA_MENU_S = 5             # o item "Fotos e vídeos" aparece depois do clique no Anexar
LEITURA_MS = 2_000            # leitura de DOM fora do evaluate da lista: nunca o padrao de 30 s
CLIQUE_MS = 5_000             # clique curto: o padrao de 30 s travou o Anexar na inst2 (17/11)
ESPERA_PREVIA_S = 30          # inst2 (ARM, 4 GB): a previa levou mais de 15 s no teste real de 17/11
MAX_EVIDENCIAS = 20           # arquivos falha_* guardados em log/ (os mais antigos saem)
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

# Leitura ATOMICA dos baloes (17/11: com count() + nth(i), a lista virtualizada re-renderizava quando o post novo
# entrava, nth(i) sumia e o get_attribute esperava 30 s). Um evaluate so, sem auto-wait.
_JS_BALOES = """els => els.map(e => {
  const cap = e.querySelector('[data-testid~="image-caption"]');
  const st = e.querySelector('[data-testid="msg-meta"] [aria-label]');
  return {tid: e.getAttribute('data-testid'), legenda: cap ? cap.innerText : null,
          status: st ? st.getAttribute('aria-label') : null};
})"""

_JS_COLAR = """(el, texto) => {
  el.focus();
  const dt = new DataTransfer();
  dt.setData('text/plain', texto);
  el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
}"""


class ErroPagina(FalhaPasso):
    """Passo da pagina que nao deu: falha antes do clique (a linha continua P)."""


class FooterPerdido(ErroPagina):
    """O footer do canal nao voltou depois do Escape: grava a evidencia e recarrega a pagina."""


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


def balao_confirmado(baloes, antes: set[str], chave: str) -> bool:
    """Ha balao NOVO (tid fora de `antes`) com `chave` na legenda e status enviada/entregue/lida."""
    return any(b.get("tid") not in antes and tem_chave(b.get("legenda") or "", chave)
               and status_confirmado(b.get("status")) for b in baloes)


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
    def __init__(self, page, log=print, pasta_log: Path | None = None, agora=datetime.now):
        self.page = page
        self.log = log
        self.pasta_log = Path(pasta_log) if pasta_log is not None else None
        self.agora = agora
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
        return titulo is not None and normalizar(titulo.inner_text(timeout=LEITURA_MS)) == normalizar(nome)

    def _ler_baloes(self) -> list[dict]:
        return self.page.locator(SEL_BALAO).evaluate_all(_JS_BALOES)

    def _ids_baloes(self) -> set[str]:
        return {b["tid"] for b in self._ler_baloes()}

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
        self._clicar(aba, "Canais")
        busca = self._visivel(SEL_BUSCA_CANAIS, ESPERA_PASSO_S)
        if busca is None:
            raise ErroPagina("nao achei a busca do painel de canais")
        self._clicar(busca, "busca de canais")
        busca.fill("")
        busca.press_sequentially(nome, delay=30)
        celula = self._visivel(SEL_CELULA.format(nome=_aspas(nome)), ESPERA_PASSO_S)
        if celula is None:
            raise ErroPagina("o canal nao apareceu na busca")
        self._clicar(celula, "celula do canal")
        fim = time.monotonic() + ESPERA_PASSO_S
        while not self._canal_aberto(nome):
            if time.monotonic() >= fim:
                raise ErroPagina("o cabecalho aberto nao e o do canal; nada enviado")
            self.page.wait_for_timeout(SONDA_MS)
        if self._visivel(SEL_CAIXA_CANAL, 5) is None:
            raise ErroPagina("canal aberto sem caixa de mensagem (o numero e admin do canal?)")

    def _clicar(self, alvo, oque: str) -> None:
        """Clique com timeout curto (CLIQUE_MS). Nao passou -> falha prevista com o motivo do call log."""
        try:
            alvo.click(timeout=CLIQUE_MS)
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise
            raise ErroPagina(f"clique em {oque} nao passou: {motivo_playwright(e)}") from None

    # ------------------------------------------------------------------------------------------- anexo

    @_morto
    def anexar(self, foto: Path) -> None:
        """Caminho do usuario: Anexar -> "Fotos e vídeos" dentro de expect_file_chooser -> set_files -> previa.
        O input oculto do footer (junto do microfone) NAO e usado: no teste real de 17/11 ele nao abria a
        previa com legenda. Antes: camadas fechadas e footer do canal visivel. Toda falha (prevista ou nao)
        grava evidencia em log/ e fecha as camadas; a linha continua P (sem D)."""
        try:
            self._garantir_footer()
            self._clicar(self._botao_anexar(), "Anexar")
            item = self._item_fotos()
            with self.page.expect_file_chooser(timeout=CLIQUE_MS) as escolha:
                self._clicar(item, TEXTO_MENU_FOTOS)
            escolha.value.set_files(str(foto))
            inicio = time.monotonic()
            if self._visivel(SEL_LEGENDA, ESPERA_PREVIA_S) is None:
                self.log("[anexo] caminho=menu previa=nao")
                raise ErroPagina("a previa da foto nao abriu (sem a legenda da previa)")
            self.log(f"[anexo] caminho=menu previa_s={time.monotonic() - inicio:.1f}")
        except BrowserMorto:
            raise
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise
            self.log(f"[anexo] falha: {_resumo(e)}")
            self._evidencia()
            if isinstance(e, FooterPerdido):
                self._recarregar_pagina()
            else:
                self._depois_da_falha()
            raise

    def _botao_anexar(self):
        botao = self._visivel(SEL_ANEXAR, 5)
        if botao is None:
            raise ErroPagina("nao achei o botao Anexar")
        return botao

    def _item_fotos(self):
        item = self.page.get_by_text(TEXTO_MENU_FOTOS, exact=True)
        fim = time.monotonic() + ESPERA_MENU_S
        while True:
            for i in range(item.count()):
                if item.nth(i).is_visible():
                    return item.nth(i)
            if time.monotonic() >= fim:
                raise ErroPagina(f"o item {TEXTO_MENU_FOTOS} nao apareceu em {ESPERA_MENU_S} s depois do Anexar")
            self.page.wait_for_timeout(SONDA_MS)

    def _fechar_camadas(self) -> None:
        """Escape ate sumir [role="dialog"] e a previa visiveis (no maximo 3)."""
        for _ in range(3):
            if self._visivel(SEL_DIALOGO) is None and self._visivel(SEL_LEGENDA) is None:
                return
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)

    def _garantir_footer(self) -> None:
        """Camadas fechadas e caixa do canal visivel; senao FooterPerdido (quem pega recarrega a pagina)."""
        self._fechar_camadas()
        if self._visivel(SEL_CAIXA_CANAL, 3) is None:
            raise FooterPerdido("o footer do canal nao voltou depois do Escape; recarregando a pagina")

    def _depois_da_falha(self) -> None:
        try:
            self._garantir_footer()
        except FooterPerdido as e:
            self.log(f"[anexo] {e}")
            self._recarregar_pagina()

    def _recarregar_pagina(self) -> None:
        try:
            self.page.reload(wait_until="domcontentloaded")
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise BrowserMorto(str(e)[:200]) from e
            self.log(f"[anexo] WARN recarregar falhou: {_resumo(e)}")

    def _evidencia(self) -> None:
        """log/falha_<DDMM_HHMMSS>.png e .html (recorte redigido do --gravar-dom). Guarda os MAX_EVIDENCIAS
        arquivos mais recentes. Falha aqui so vai ao log: nao muda o resultado da tentativa."""
        if self.pasta_log is None:
            return
        try:
            self.pasta_log.mkdir(parents=True, exist_ok=True)
            base = f"falha_{self.agora():%d%m_%H%M%S}"
            n, nome = 2, base
            while (self.pasta_log / f"{nome}.png").exists() or (self.pasta_log / f"{nome}.html").exists():
                nome, n = f"{base}_{n}", n + 1
            self.page.screenshot(path=str(self.pasta_log / f"{nome}.png"), timeout=10_000)
            (self.pasta_log / f"{nome}.html").write_text(redigir_dom(self.page.content()), encoding="utf-8")
            self.log(f"[anexo] evidencia em log/{nome}.png e .html")
        except Exception as e:
            if _FECHADO.search(str(e)):
                raise
            self.log(f"[anexo] WARN evidencia nao gravada ({type(e).__name__})")
        rodar_evidencias(self.pasta_log, MAX_EVIDENCIAS, self.log)

    def texto_do_editor(self, caixa) -> str:
        return caixa.evaluate(_JS_TEXTO, timeout=LEITURA_MS)

    @_morto
    def escrever_legenda(self, texto: str, modo: str = "colar") -> None:
        """Cola (ou digita) e confere cru com cru. Divergiu: limpa e tenta 1 vez (digitando). Divergiu de novo:
        fecha a previa e falha, sem D."""
        caixa = self._visivel(SEL_LEGENDA, 5)
        if caixa is None:
            raise ErroPagina("sem a legenda da previa")
        for m in (["colar", "digitar"] if modo == "colar" else ["digitar", "digitar"]):
            self._clicar(caixa, "legenda da previa")
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            if m == "colar":
                caixa.evaluate(_JS_COLAR, texto, timeout=LEITURA_MS)
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
        self._clicar(botao, "Enviar da previa")

    @_morto
    def confirmar(self, chave: str, timeout_s: float) -> bool:
        """Positiva: a previa fechou, ha balao NOVO (fora dos de antes do clique) cuja legenda tem `chave`
        (besave.io/{id}) e cujo msg-meta diz enviada/entregue/lida. Qualquer outro estado = nao confirmado.
        Erro de uma sondagem (pagina re-renderizando etc.) vai ao log uma vez e a sondagem segue ate o prazo; so
        o prazo esgotado devolve False (D). Navegador morto sobe como BrowserMorto."""
        fim = time.monotonic() + timeout_s
        avisou = False
        while True:
            try:
                if self._visivel(SEL_LEGENDA) is None and self._balao_confirmado(chave):
                    return True
            except BrowserMorto:
                raise
            except Exception as e:
                if _FECHADO.search(str(e)):
                    raise
                if not avisou:
                    self.log(f"[confirmar] WARN sondagem falhou, seguindo ate o prazo ({_resumo(e)})")
                    avisou = True
            if time.monotonic() >= fim:
                return False
            self.page.wait_for_timeout(1_000)

    def _balao_confirmado(self, chave: str) -> bool:
        return balao_confirmado(self._ler_baloes(), self._baloes_antes, chave)

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


_MOTIVOS = re.compile(r"intercepts pointer events|outside of the viewport|not visible|not enabled|not stable|"
                      r"detached|not attached|is not an? ", re.IGNORECASE)


def motivo_playwright(e) -> str:
    """Motivo de um erro do Playwright: a ultima linha do call log que diz POR QUE (intercepts pointer events,
    outside of the viewport...); sem ela, a ultima linha util do call log; sem call log, a 1a linha da mensagem."""
    texto = str(e)
    linhas = [x.strip(" -\t") for x in texto.split("Call log:", 1)[1].splitlines()] if "Call log:" in texto else []
    linhas = [x for x in linhas if x]
    for linha in reversed(linhas):
        if _MOTIVOS.search(linha):
            return linha[:300]
    if linhas:
        return linhas[-1][:300]
    return (texto.strip().splitlines() or [type(e).__name__])[0][:300]


def _resumo(e) -> str:
    if isinstance(e, ErroPagina):
        return str(e).splitlines()[0][:300]
    return f"{type(e).__name__}: {motivo_playwright(e)}"


def rodar_evidencias(pasta: Path, manter: int = MAX_EVIDENCIAS, log=print) -> None:
    """Deixa em `pasta` so os `manter` arquivos falha_* mais recentes (mtime; empate pelo nome)."""
    try:
        arquivos = sorted((p for p in Path(pasta).glob("falha_*") if p.is_file()),
                          key=lambda p: (p.stat().st_mtime, p.name))
        for velho in arquivos[:max(0, len(arquivos) - manter)]:
            velho.unlink()
    except OSError as e:
        log(f"[anexo] WARN rotacao das evidencias falhou ({type(e).__name__})")


# --- DOM gravado (para conferir seletores no teste real) ----------------------------------------------

_RE_TELEFONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_RE_NUMERO_LONGO = re.compile(r"\d{10,}")
_RE_URL = re.compile(r"(?:https?|blob|data):[^\s\"'<>)]+", re.IGNORECASE)


def redigir_dom(html: str) -> str:
    """Tira numeros de telefone (8+ digitos), URLs (https, blob, data) e srcset. Nomes de contatos e grupos
    que aparecerem na lista NAO sao reconhecidos: o dono revisa o arquivo antes de versionar (regra 11)."""
    html = _RE_URL.sub("REDACTED", html)
    html = re.sub(r'\ssrcset="[^"]*"', "", html)
    html = _RE_NUMERO_LONGO.sub("REDACTED", html)
    return _RE_TELEFONE.sub("REDACTED", html)
