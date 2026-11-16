"""BSV-63 LEG-01..02, QR-01: pagina do WhatsApp Web.

Parte 1 (roda no CI, sem navegador): digitacao contra um teclado falso em que `Enter` ENVIA, comparacao do
editor, chave de confirmacao e redacao do DOM.
Parte 2 (Chromium real com a fixture SINTETICA tests/fixtures/whatsapp_canal.html): pula sem Playwright.
"""
from pathlib import Path

import pytest
from pub import canal_web
from pub.canal_web import CanalWeb, ErroPagina

LEGENDA = (
    "*Fone Bluetooth XYZ com ANC*\n"
    "\n"
    "Menor preço do ano\n"
    "🔥 *-33%*  ~R$ 299,90~  *R$ 199,90*  🔁 _(Recorrência)_\n"
    "📉 *Caiu mais o preço!!!*\n"
    "🎟️ Cupom: `BE_SAVE`\n"
    "Promoção Amazon: https://besave.io/5412?utm_source=whatsapp\n"
    "\n"
    "🏃‍♂️ _Corre que acaba rapido_"
)
CANAL = "BeSave - Preços Baixos e Ofertas incríveis"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "whatsapp_canal.html"


class TecladoWhatsApp:
    """Como o editor do WhatsApp: Enter envia o que esta escrito; Shift+Enter quebra a linha."""

    def __init__(self):
        self.buffer = ""
        self.enviadas = []

    def insert_text(self, s):
        self.buffer += s

    def type(self, s, delay=0):
        for c in s:
            self.press("Enter") if c == "\n" else self.insert_text(c)

    def press(self, tecla):
        if tecla == "Enter":
            self.enviadas.append(self.buffer)
            self.buffer = ""
        elif tecla == "Shift+Enter":
            self.buffer += "\n"
        else:
            raise AssertionError(f"tecla inesperada {tecla}")


def test_leg01_digitar_nao_envia_nada_e_o_editor_fica_identico():
    t = TecladoWhatsApp()
    canal_web.digitar(t, LEGENDA)
    assert t.enviadas == []                      # nenhuma mensagem saiu no meio
    assert t.buffer == LEGENDA                   # com as duas linhas em branco
    t.press("Enter")                             # o clique em enviar
    assert t.enviadas == [LEGENDA]


def test_leg01_linhas_em_branco_seguidas_e_finais():
    t = TecladoWhatsApp()
    canal_web.digitar(t, "a\n\n\nb\n")
    assert t.buffer == "a\n\n\nb\n" and t.enviadas == []


def test_leg02_comparacao_do_editor_so_tolera_o_invisivel():
    assert canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("🎟️", "🎟").replace("  ", "  "))
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("\n\n", "\n"))       # perdeu linha em branco
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("*", ""))            # perdeu a marcacao
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA + "\n")


def test_chave_de_confirmacao_e_o_titulo_sem_marcacao():
    assert canal_web.chave_confirmacao(LEGENDA) == "fonebluetoothxyzcomanc"
    assert canal_web.chave_confirmacao("*" + "Título " * 20 + "*").startswith("titulotitulo")
    assert len(canal_web.chave_confirmacao("*" + "x" * 99 + "*")) == 40


def test_dom_gravado_e_redigido():
    html = ('<div title="+55 11 98765-4321">5511987654321@c.us</div><img src="https://pps.whatsapp.net/v/x.jpg" '
            'srcset="a 1x"><img src="blob:https://web.whatsapp.com/abc">')
    r = canal_web.redigir_dom(html)
    assert "98765" not in r and "5511987654321" not in r and "whatsapp.net" not in r and "blob:" not in r
    assert "srcset" not in r


def test_seletores_nao_usam_classe_ofuscada():
    todos = [s for nome, v in vars(canal_web).items() if nome.startswith("SEL_")
             for s in (v if isinstance(v, list) else [v])]
    assert todos and not any("." in s.split("[")[0] for s in todos)


# --- Chromium real com a fixture sintetica ----------------------------------------------------------


@pytest.fixture(scope="module")
def navegador():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chromium do Playwright indisponivel ({type(e).__name__})")
        yield b
        b.close()


@pytest.fixture
def pagina(navegador, tmp_path):
    ctx = navegador.new_context()
    page = ctx.new_page()
    page.goto(FIXTURE.as_uri())
    yield page
    ctx.close()


@pytest.fixture
def foto(tmp_path):
    from PIL import Image
    caminho = tmp_path / "5412.jpg"
    Image.new("RGB", (800, 800), (255, 255, 255)).save(caminho, format="JPEG")
    return caminho


def _postar(c, foto, modo, legenda=LEGENDA, timeout=5):
    c.abrir_canal(CANAL)
    c.anexar(foto)
    c.escrever_legenda(legenda, modo)
    c.enviar()
    return c.confirmar(legenda, timeout)


def test_dom_sessao_logada_e_qr(pagina):
    assert CanalWeb(pagina).sessao() == "ok"
    pagina.goto(canal_web.Path(FIXTURE).as_uri() + "#qr")
    pagina.reload()
    assert CanalWeb(pagina).sessao() == "qr"


@pytest.mark.parametrize("modo", ["colar", "digitar"])
def test_dom_leg01_um_envio_identico_a_legenda(pagina, foto, modo):
    c = CanalWeb(pagina, log=lambda s: None)
    assert _postar(c, foto, modo) is True
    assert pagina.evaluate("window.__envios") == [LEGENDA]
    assert pagina.evaluate("window.__enters") == 0
    c.limpar()
    assert pagina.locator("#previa").is_visible() is False


def test_dom_rede_caida_balao_com_relogio_nao_confirma(pagina, foto):
    pagina.evaluate("window.__redeCaida = true")
    c = CanalWeb(pagina, log=lambda s: None)
    assert _postar(c, foto, "colar", timeout=2) is False
    assert pagina.evaluate("window.__envios") == [LEGENDA]          # saiu localmente; fica D, sem reenvio


def test_dom_leg02_colar_que_perde_linhas_cai_para_digitar(pagina, foto):
    # editor que ignora o paste (como se o WhatsApp nao aceitasse): o publicador tem de digitar
    pagina.evaluate("document.querySelector('#legenda').addEventListener('paste', e => e.stopImmediatePropagation(), true)")
    avisos = []
    c = CanalWeb(pagina, log=avisos.append)
    assert _postar(c, foto, "colar") is True
    assert pagina.evaluate("window.__envios") == [LEGENDA]
    assert any("modo colar chegou diferente" in a for a in avisos)


def test_dom_leg02_editor_que_nao_aceita_texto_e_falha_antes_do_clique(pagina, foto):
    pagina.evaluate("""const el = document.querySelector('#legenda');
        el.addEventListener('paste', e => e.stopImmediatePropagation(), true);
        el.addEventListener('beforeinput', e => e.preventDefault(), true);""")
    c = CanalWeb(pagina, log=lambda s: None)
    c.abrir_canal(CANAL)
    c.anexar(foto)
    with pytest.raises(ErroPagina):
        c.escrever_legenda(LEGENDA, "colar")
    assert pagina.evaluate("window.__envios") == []


def test_dom_canal_inexistente_e_erro_de_pagina(pagina):
    with pytest.raises(ErroPagina):
        CanalWeb(pagina, log=lambda s: None).abrir_canal("Outro canal")
