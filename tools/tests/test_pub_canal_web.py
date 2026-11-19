"""BSV-63: pagina do WhatsApp Web sobre a fixture REAL (recorte redigido do mapeamento do dono, 16/11/2026).

Parte 1 (sem navegador, roda no CI): digitacao contra um teclado em que `Enter` ENVIA, comparacao cru com cru,
chave besave.io/{id}, status do balao e a propria fixture (redacao e seletores presentes).
Parte 2 (Chromium real, fixtures/whatsapp_canal_real.html + fixtures/whatsapp_simulador.js): cada seletor da
tabela e o fluxo por postagem. Pula sem Playwright (CI); roda no WSL e no PC. Nada toca o WhatsApp de verdade.
"""
import re
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
CHAVE = "besave.io/5412"
CANAL = "BeSave - Preços Baixos e Ofertas incríveis"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "whatsapp_canal_real.html"
SIMULADOR = FIXTURES / "whatsapp_simulador.js"


class TecladoWhatsApp:
    """Como o editor do WhatsApp: Enter envia o que esta escrito; Shift+Enter quebra a linha."""

    def __init__(self):
        self.buffer = ""
        self.enviadas = []

    def insert_text(self, s):
        self.buffer += s

    def press(self, tecla):
        if tecla == "Enter":
            self.enviadas.append(self.buffer)
            self.buffer = ""
        elif tecla == "Shift+Enter":
            self.buffer += "\n"
        else:
            raise AssertionError(f"tecla inesperada {tecla}")


# --- parte 1: sem navegador --------------------------------------------------------------------------


def test_leg01_digitar_nao_envia_nada_e_o_editor_fica_identico():
    t = TecladoWhatsApp()
    canal_web.digitar(t, LEGENDA)
    assert t.enviadas == [] and t.buffer == LEGENDA
    t.press("Enter")
    assert t.enviadas == [LEGENDA]


def test_leg01_linhas_em_branco_seguidas_e_finais():
    t = TecladoWhatsApp()
    canal_web.digitar(t, "a\n\n\nb\n")
    assert t.buffer == "a\n\n\nb\n" and t.enviadas == []


def test_leg02_cru_com_cru_normalizando_so_quebras_espacos_e_nfc():
    assert canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("\n", "\r\n").replace("  ", "  "))
    assert canal_web.igual_ao_editor("café", "café")                               # NFC
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("\n\n", "\n"))         # perdeu linha em branco
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA.replace("*", ""))              # caixa mostra * cru
    assert not canal_web.igual_ao_editor(LEGENDA, LEGENDA + "\n")


def test_chave_besave_io_com_fronteira():
    assert canal_web.tem_chave("Promoção Amazon: https://besave.io/5412?utm_source=whatsapp", CHAVE)
    assert canal_web.tem_chave("besave.io/5412", CHAVE)
    assert not canal_web.tem_chave("https://besave.io/54120?utm_source=whatsapp", CHAVE)
    assert not canal_web.tem_chave("besave.io/", CHAVE)


@pytest.mark.parametrize("rotulo,ok", [(" Enviada ", True), ("Entregue", True), ("LIDA", True), ("lida ", True),
                                       ("Pendente", False), ("", False), (None, False), ("Enviando", False)])
def test_status_do_balao(rotulo, ok):
    assert canal_web.status_confirmado(rotulo) is ok


def test_seletores_so_com_atributos_permitidos():
    todos = [v for nome, v in vars(canal_web).items() if nome.startswith("SEL_")]
    todos = [s for v in todos for s in (v if isinstance(v, list) else [v])]
    assert todos
    for s in todos:
        assert "data-icon" not in s and "_r_" not in s and "//" not in s, s
        assert not re.search(r"\.x[0-9a-z]", s), s                       # classe ofuscada
        assert not re.search(r"(?<![\w\]])\.[A-Za-z]", s), s              # nenhuma classe


def test_fixture_real_redigida_e_sem_script():
    html = FIXTURE.read_text(encoding="utf-8")
    assert not re.search(r'[0-9]{10,}|pps\.whatsapp|cdn\.whatsapp|blob:|data-pre-plain-text="\[', html)
    assert "<script" not in html and "<style" not in html and "<link" not in html
    assert not re.search(r'class="[^"]*\bx[0-9a-z]+', html)
    assert not re.search(r"\(\d+\) WhatsApp", html)
    assert not re.search(r'data-testid="conv-msg-(?!FAKE\d+")', html)
    assert "transcrito do mapeamento do dono" in html.lower()
    assert not (FIXTURES / "whatsapp_canal.html").exists()           # a sintetica saiu


def test_dom_gravado_e_redigido():
    html = ('<div title="+55 11 98765-4321">5511987654321@c.us</div><img src="https://pps.whatsapp.net/v/x.jpg" '
            'srcset="a 1x"><img src="blob:https://web.whatsapp.com/abc">')
    r = canal_web.redigir_dom(html)
    assert "98765" not in r and "5511987654321" not in r and "whatsapp.net" not in r and "blob:" not in r


# --- parte 2: Chromium real sobre a fixture real -----------------------------------------------------


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
def abrir(navegador):
    ctxs = []

    def _abrir(**sim):
        ctx = navegador.new_context()
        ctxs.append(ctx)
        page = ctx.new_page()
        page.set_content(FIXTURE.read_text(encoding="utf-8"))
        page.evaluate("s => { window.__sim = s; }", sim)
        page.add_script_tag(path=str(SIMULADOR))
        return page, CanalWeb(page, log=lambda s: None)
    yield _abrir
    for c in ctxs:
        c.close()


@pytest.fixture
def foto(tmp_path):
    from PIL import Image
    caminho = tmp_path / "5412.jpg"
    Image.new("RGB", (800, 800), (255, 255, 255)).save(caminho, format="JPEG")
    return caminho


def _postar(c, foto, modo="colar", timeout=3):
    c.abrir_canal(CANAL)
    c.anexar(foto)
    c.escrever_legenda(LEGENDA, modo)
    c.enviar()
    return c.confirmar(CHAVE, timeout)


def _envios(page):
    return page.evaluate("window.__envios")


def test_dom_logado_pelo_side(abrir):
    _page, c = abrir()
    assert c.sessao() == "ok"


def test_dom_seletores_da_tabela_existem_na_fixture_real(abrir):
    page, _ = abrir()
    unicos = {
        canal_web.SEL_ABA_CANAIS: 1, canal_web.SEL_BUSCA_CANAIS: 1,
        canal_web.SEL_CELULA.format(nome=CANAL): 1, canal_web.SEL_TITULO: 1, canal_web.SEL_CAIXA_CANAL: 1,
        canal_web.SEL_ANEXAR: 1, canal_web.SEL_LEGENDA: 1, canal_web.SEL_ENVIAR: 1,
    }
    for sel, n in unicos.items():
        assert page.locator(sel).count() == n, sel
    assert page.locator(canal_web.SEL_BALAO).count() == 9
    assert page.locator(canal_web.SEL_LEGENDA_BALAO).count() == 3
    rotulos = page.locator(canal_web.SEL_STATUS_BALAO).evaluate_all("e => e.map(x => x.getAttribute('aria-label'))")
    assert rotulos and all(canal_web.status_confirmado(r) for r in rotulos)     # real: " Enviada "
    assert page.locator('#main footer input[type="file"]').count() == 1      # existe, mas nao e usado
    assert not hasattr(canal_web, "SEL_INPUT_FOTO")


@pytest.mark.parametrize("modo", ["colar", "digitar"])
def test_dom_enviada_vira_confirmado_num_envio_so(abrir, foto, modo):
    page, c = abrir()
    assert _postar(c, foto, modo) is True
    assert _envios(page) == [LEGENDA] and page.evaluate("window.__enters") == 0
    assert page.evaluate("window.__cliquesCanais") == 0                       # canal ja aberto: pulou a navegacao


def test_dom_navega_pela_aba_busca_e_celula(abrir, foto):
    page, c = abrir(mainFechado=True)
    c.abrir_canal(CANAL)
    assert page.evaluate("window.__cliquesCanais") == 1
    assert page.locator(canal_web.SEL_BUSCA_CANAIS).input_value() == CANAL
    assert _postar(c, foto) is True


def test_dom_cabecalho_divergente_nao_envia(abrir, foto, monkeypatch):
    monkeypatch.setattr(canal_web, "ESPERA_PASSO_S", 2)
    page, c = abrir(mainFechado=True, tituloAoClicar="BeSave - Preços Baixos e Ofertas incríveis 2")
    with pytest.raises(ErroPagina):
        c.abrir_canal(CANAL)
    assert _envios(page) == []


def test_dom_legenda_divergente_na_previa_fecha_e_nao_envia(abrir, foto):
    page, c = abrir(rejeitaTexto=True)
    c.abrir_canal(CANAL)
    c.anexar(foto)
    with pytest.raises(ErroPagina):
        c.escrever_legenda(LEGENDA, "colar")
    assert _envios(page) == []
    assert page.locator(canal_web.SEL_LEGENDA).is_visible() is False           # Escape fechou a previa


def test_dom_balao_sem_a_chave_nao_confirma(abrir, foto):
    _page, c = abrir(semChave=True)
    assert _postar(c, foto, timeout=2) is False


@pytest.mark.parametrize("status", [" Pendente ", " Enviando ", None])
def test_dom_status_desconhecido_ou_ausente_nao_confirma(abrir, foto, status):
    _page, c = abrir(status=status)
    assert _postar(c, foto, timeout=2) is False


def test_dom_balao_antigo_com_a_mesma_chave_nao_confirma_o_novo(abrir, foto):
    page, c = abrir(naoChega=True)
    page.evaluate(f"window.__novoBalao('Promoção Amazon: https://{CHAVE}?utm_source=whatsapp', ' Enviada ')")
    assert _postar(c, foto, timeout=2) is False


def test_dom_previa_aberta_nao_confirma(abrir, foto):
    page, c = abrir()
    c.abrir_canal(CANAL)
    c.anexar(foto)
    c.escrever_legenda(LEGENDA)
    c._baloes_antes = c._ids_baloes()
    page.evaluate(f"window.__novoBalao('https://{CHAVE}', ' Enviada ')")   # balao novo, mas a previa nao fechou
    assert c.confirmar(CHAVE, 2) is False


def test_dom_limpar_fecha_a_previa(abrir, foto):
    page, c = abrir()
    c.abrir_canal(CANAL)
    c.anexar(foto)
    assert page.locator(canal_web.SEL_LEGENDA).is_visible()
    c.limpar()
    assert page.locator(canal_web.SEL_LEGENDA).is_visible() is False


# --- lacunas do Verifier (ciclo 3) -------------------------------------------------------------------


def test_dom_colar_rejeitado_tenta_de_novo_digitando_e_envia(abrir, foto):  # M-n
    page, c = abrir(rejeitaColar=True)
    assert _postar(c, foto) is True
    assert _envios(page) == [LEGENDA] and page.evaluate("window.__enters") == 0


def test_dom_celula_escolhida_pelo_aria_label_do_canal(abrir, foto):  # M-s
    page, c = abrir(mainFechado=True)
    page.evaluate("""() => {
        const real = document.querySelector('[data-testid="newsletter-tab-newsletter-cell"]');
        const isca = real.cloneNode(true);
        isca.setAttribute('aria-label', 'Canal Outro canal qualquer');
        isca.addEventListener('click', () => {
            document.querySelector('#main').style.display = '';
            document.querySelector('[data-testid="conversation-info-header-chat-title"]').textContent = 'Outro canal qualquer';
        });
        real.parentElement.insertBefore(isca, real);
    }""")
    assert page.locator('[data-testid="newsletter-tab-newsletter-cell"]').count() == 2
    assert _postar(c, foto) is True


def test_dom_canal_aberto_sem_caixa_de_mensagem_nao_envia(abrir, foto):  # M-t
    page, c = abrir()
    page.evaluate("document.querySelector('[data-testid=\"conversation-compose-box-input\"]').remove()")
    with pytest.raises(ErroPagina):
        c.abrir_canal(CANAL)
    assert _envios(page) == []


# --- achado do teste real na inst2 (17/11): previa lenta ou que nao abre pelo input -------------------


def _canal(page, logs, pasta=None, agora=None):
    from datetime import datetime
    return CanalWeb(page, log=logs.append, pasta_log=pasta, agora=agora or datetime.now)


def test_anexo_espera_da_previa_e_30s():
    assert canal_web.ESPERA_PREVIA_S == 30


def test_anexo_rotacao_o_21o_arquivo_apaga_o_mais_antigo(tmp_path):
    import os
    for k in range(21):
        p = tmp_path / f"falha_{k:02d}.png"
        p.write_bytes(b"x")
        os.utime(p, (1_000_000 + k, 1_000_000 + k))
    (tmp_path / "run_publicador_17_11_111700.log").write_text("x", encoding="utf-8")   # nao e evidencia
    canal_web.rodar_evidencias(tmp_path, 20)
    restantes = sorted(p.name for p in tmp_path.glob("falha_*"))
    assert len(restantes) == 20 and "falha_00.png" not in restantes and "falha_20.png" in restantes
    assert (tmp_path / "run_publicador_17_11_111700.log").exists()


def test_anexo_evidencia_roda_a_rotacao(abrir, tmp_path):
    import os
    from datetime import datetime
    page, _ = abrir()
    for k in range(20):
        p = tmp_path / f"falha_0101_0000{k:02d}.png"
        p.write_bytes(b"x")
        os.utime(p, (1_000_000 + k, 1_000_000 + k))
    c = _canal(page, [], tmp_path, agora=lambda: datetime(2026, 11, 17, 11, 35, 0))
    c._evidencia()
    nomes = sorted(p.name for p in tmp_path.glob("falha_*"))
    assert len(nomes) == 20
    assert "falha_1711_113500.png" in nomes and "falha_1711_113500.html" in nomes
    assert "falha_0101_000000.png" not in nomes and "falha_0101_000001.png" not in nomes


def test_anexo_sucesso_direto_nao_grava_evidencia(abrir, foto, tmp_path):
    page, _ = abrir()
    c = _canal(page, [], tmp_path / "log")
    assert _postar(c, foto) is True
    assert not list((tmp_path / "log").glob("falha_*"))



# --- 2o achado do teste real (17/11, 3fccc36): o caminho do usuario e o menu; clique curto; evidencia --------


def _publicador_real(page, tmp_path, pasta, quando=(2026, 11, 17, 13, 9, 0)):
    from datetime import datetime

    from pub_falso import Mundo
    m = Mundo(tmp_path / "mundo")
    m.fila.nome = CANAL
    m.pub.pagina = _canal(page, m.logs, pasta, agora=lambda: datetime(*quando))
    return m


def _evidencias(pasta):
    return sorted(p.name for p in pasta.glob("falha_*"))


def test_anexo_menu_e_o_caminho_mesmo_com_o_input_oculto(abrir, foto, tmp_path):
    page, _ = abrir()
    assert page.locator('#main footer input[type="file"]').count() == 1
    logs = []
    c = _canal(page, logs, tmp_path / "log")
    assert _postar(c, foto) is True
    assert page.evaluate("window.__arquivosPorCaminho") == {"input": 0, "menu": 1}
    assert page.evaluate("window.__cliquesAnexar") == 1
    assert any(re.fullmatch(r"\[anexo\] caminho=menu previa_s=\d+\.\d", x) for x in logs)
    assert _evidencias(tmp_path / "log") == []                       # sucesso nao grava evidencia


def test_anexo_previa_que_abre_em_20s_passa(abrir, foto):
    page, _ = abrir(atrasoPrevia=20_000)
    logs = []
    c = _canal(page, logs)
    c.abrir_canal(CANAL)
    c.anexar(foto)                                                    # com 15 s de espera falharia
    linha = next(x for x in logs if x.startswith("[anexo] caminho="))
    m = re.fullmatch(r"\[anexo\] caminho=menu previa_s=(\d+\.\d)", linha)
    assert m and 20.0 <= float(m.group(1)) < 30.0


def test_anexo_item_do_menu_ausente_falha_prevista_sem_d_com_evidencia(abrir, foto, tmp_path):
    page, _ = abrir(semItemMenu=True)
    pasta = tmp_path / "log"
    m = _publicador_real(page, tmp_path, pasta)
    i = m.fila.add(m.local())
    m.volta()
    assert m.fila.st(i) == ("P", None) and m.pub.falhas_seguidas == 1 and _envios(page) == []
    assert any("Fotos e vídeos nao apareceu" in x for x in m.logs)
    assert _evidencias(pasta) == ["falha_1711_130900.html", "falha_1711_130900.png"]


def test_anexo_camada_que_intercepta_o_clique_falha_em_ate_6s_com_causa(abrir, foto, tmp_path):
    import time
    page, _ = abrir(camadaFixa=True)
    pasta = tmp_path / "log"
    logs = []
    c = _canal(page, logs, pasta)
    c.abrir_canal(CANAL)
    inicio = time.monotonic()
    with pytest.raises(ErroPagina) as erro:
        c.anexar(foto)
    assert time.monotonic() - inicio <= 6.0                           # clique curto, nao os 30 s do padrao
    assert "intercepts pointer events" in str(erro.value)
    assert any("Anexar" in x and "intercepts pointer events" in x for x in logs)
    assert len(_evidencias(pasta)) == 2
    assert page.evaluate("window.__arquivosPorCaminho") == {"input": 0, "menu": 0}


def test_anexo_camada_que_intercepta_no_publicador_e_p_sem_d(abrir, foto, tmp_path):
    page, _ = abrir(camadaFixa=True)
    m = _publicador_real(page, tmp_path, tmp_path / "log")
    i = m.fila.add(m.local())
    m.volta()
    assert m.fila.st(i) == ("P", None) and _envios(page) == [] and m.pub.falhas_seguidas == 1


def test_anexo_escape_fecha_a_camada_e_o_footer_volta_antes_de_anexar(abrir, foto, tmp_path):
    page, _ = abrir(camadaDialogo=True)
    assert page.locator(canal_web.SEL_DIALOGO).count() == 1
    c = _canal(page, [], tmp_path / "log")
    assert _postar(c, foto) is True
    assert page.evaluate("window.__escapes") >= 1
    assert page.locator(canal_web.SEL_DIALOGO).count() == 0
    assert page.locator('[role="dialog"] [data-testid="conversation-subheader"]').count() == 1   # o aviso fica


def test_anexo_aviso_fixo_do_canal_nao_e_camada_e_nao_leva_escape(abrir, foto, tmp_path):
    page, _ = abrir()
    assert page.locator('[role="dialog"]').count() == 1                    # o aviso real do canal (role=dialog)
    assert page.locator(canal_web.SEL_DIALOGO).count() == 0
    c = _canal(page, [], tmp_path / "log")
    assert _postar(c, foto) is True
    assert (page.evaluate("window.__escapes") or 0) == 0                    # Escape sem camada fecharia a conversa
    assert _evidencias(tmp_path / "log") == []


def test_anexo_footer_que_nao_volta_falha_prevista_e_recarrega(abrir, foto, tmp_path, monkeypatch):
    page, _ = abrir(semCaixa=True)
    recargas = []
    c = _canal(page, [], tmp_path / "log")
    ordem = []
    evidencia = c._evidencia
    monkeypatch.setattr(c, "_evidencia", lambda: (ordem.append("evidencia"), evidencia()))
    monkeypatch.setattr(c, "_recarregar_pagina", lambda: (ordem.append("recarga"), recargas.append(1)))
    with pytest.raises(ErroPagina):
        c.anexar(foto)
    assert recargas == [1] and len(_evidencias(tmp_path / "log")) == 2
    assert ordem == ["evidencia", "recarga"]                          # o print e da falha, nao da pagina nova
    assert page.evaluate("window.__cliquesAnexar || 0") == 0          # nao tentou anexar sem o footer


def test_anexo_previa_que_nao_abre_falha_sem_d_com_evidencia_redigida(abrir, foto, tmp_path, monkeypatch):
    monkeypatch.setattr(canal_web, "ESPERA_PREVIA_S", 1)
    page, _ = abrir(menuNaoAbre=True)
    page.evaluate("document.querySelector('#app').insertAdjacentHTML('beforeend', '<span>5511987654321</span>')")
    pasta = tmp_path / "log"
    m = _publicador_real(page, tmp_path, pasta, quando=(2026, 11, 17, 11, 17, 5))
    i = m.fila.add(m.local())
    m.volta()
    assert m.fila.st(i) == ("P", None) and m.pub.falhas_seguidas == 1 and m.avisos == []
    assert "[anexo] caminho=menu previa=nao" in m.logs
    png, html = pasta / "falha_1711_111705.png", pasta / "falha_1711_111705.html"
    assert png.read_bytes()[:4] == bytes([0x89]) + b"PNG"
    texto = html.read_text(encoding="utf-8")
    assert "conversation-panel-wrapper" in texto
    assert not re.search(r"\d{10,}", texto) and "REDACTED" in texto


def test_anexo_excecao_inesperada_tambem_grava_evidencia(abrir, foto, tmp_path, monkeypatch):
    page, _ = abrir()
    logs = []
    c = _canal(page, logs, tmp_path / "log")
    c.abrir_canal(CANAL)

    def quebra():
        raise RuntimeError("erro inesperado de teste")
    monkeypatch.setattr(c, "_item_fotos", quebra)
    with pytest.raises(RuntimeError) as erro:
        c.anexar(foto)
    assert type(erro.value) is RuntimeError                           # re-lancada como esta: o publicador recarrega
    assert not isinstance(erro.value, ErroPagina)
    assert len(_evidencias(tmp_path / "log")) == 2
    assert any("RuntimeError" in x and "erro inesperado de teste" in x for x in logs)


def test_motivo_do_playwright_e_a_linha_do_porque():
    erro = Exception(
        "Locator.click: Timeout 5000ms exceeded.\nCall log:\n"
        "  - waiting for locator('#main footer button[aria-label=\"Anexar\"]')\n"
        "  -   locator resolved to <button aria-label=\"Anexar\">…</button>\n"
        "  - attempting click action\n"
        "  -     element is visible, enabled and stable\n"
        "  -     <div data-sim=\"camada-fixa\"></div> intercepts pointer events\n"
        "  -   retrying click action\n"
        "  -     waiting 500ms\n")
    assert canal_web.motivo_playwright(erro) == '<div data-sim="camada-fixa"></div> intercepts pointer events'
    fora = Exception("Locator.click: Timeout\nCall log:\n  - attempting click action\n"
                     "  -     element is outside of the viewport\n  -   retrying click action\n")
    assert canal_web.motivo_playwright(fora) == "element is outside of the viewport"
    assert canal_web.motivo_playwright(Exception("sem call log\nlinha 2")) == "sem call log"


def test_janela_cabe_na_tela_e_usa_no_viewport():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main_publicador_janela", Path(__file__).resolve().parent.parent / "publish-whatsapp-channel" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.opcoes_navegador({}) == {"headless": False, "no_viewport": True,
                                        "args": ["--window-size=1600,880", "--window-position=0,0"]}
    assert mod.opcoes_navegador({"BESAVE_JANELA": "1366x700"})["args"][0] == "--window-size=1366,700"
    assert mod.opcoes_navegador({"BESAVE_JANELA": "lixo"})["args"][0] == "--window-size=1600,880"


def test_enviar_interceptado_no_publicador_fica_d_com_aviso(abrir, foto, tmp_path):
    """Clique em "Enviar 1 item selecionado" que nao passa (camada por cima, timeout de 5 s): a linha ja e D e fica D;
    o aviso de D sai; nada volta a P."""
    import time
    page, _ = abrir(enviarCoberto=True)
    m = _publicador_real(page, tmp_path, tmp_path / "log")
    i = m.fila.add(m.local())
    inicio = time.monotonic()
    m.volta()
    assert m.fila.st(i) == ("D", "enviando")
    assert len(m.avisos) == 1 and f"linha {i}" in m.avisos[0] and "conferir no canal" in m.avisos[0]
    assert _envios(page) == []                                        # o clique nao passou
    assert any("Enviar da previa nao passou" in x and "intercepts pointer events" in x for x in m.logs)
    assert time.monotonic() - inicio < 30                             # 5 s do clique, nao 30 + 60 de espera


# --- lacunas do Verifier (ciclo 5) -------------------------------------------------------------------


def test_anexo_depois_da_falha_escape_fecha_a_camada_aberta(abrir, foto, tmp_path):  # M13
    page, _ = abrir(semItemMenu=True, dialogoNoAnexar=True)
    c = _canal(page, [], tmp_path / "log")
    c.abrir_canal(CANAL)
    with pytest.raises(ErroPagina):
        c.anexar(foto)
    assert page.evaluate("window.__cliquesAnexar") == 1
    assert page.locator(canal_web.SEL_DIALOGO).count() == 0                # fechada pelo Escape depois da falha
    assert page.evaluate("window.__escapes") >= 1


def test_anexo_no_maximo_3_escapes_numa_camada_que_nao_fecha(abrir, foto, tmp_path):  # M12
    page, _ = abrir(dialogoTeimoso=True)
    c = _canal(page, [], tmp_path / "log")
    c.abrir_canal(CANAL)
    c.anexar(foto)                                                          # a camada nao cobre o Anexar
    assert page.evaluate("window.__escapes") == 3
    assert page.locator(canal_web.SEL_DIALOGO).count() == 1


def test_anexo_item_do_menu_que_aparece_em_2s_passa(abrir, foto, tmp_path):  # M17: o prazo do item e 5 s
    page, _ = abrir(atrasoMenu=2_000)
    c = _canal(page, [], tmp_path / "log")
    assert _postar(c, foto) is True
    assert canal_web.ESPERA_MENU_S == 5


# --- 3o achado do teste real (17/11, f1b0f5e): re-render da lista durante a confirmacao ----------------


class _ListaVirtualizada:
    """Modelo do re-render da inst2 (17/11), fora do mundo JS da pagina: logo DEPOIS de cada leitura da lista de
    baloes (count() ou evaluate_all) pelo publicador, a lista tira 3 baloes antigos do DOM. Quem le em dois passos
    (count() e depois nth(i)) acha indices que sumiram e espera 30 s; a leitura atomica nao percebe nada."""

    def __init__(self, page):
        self.page = page
        self.remocoes = 0

    def __getattr__(self, nome):
        return getattr(self.page, nome)

    def _re_render(self):
        if self.remocoes < 2:
            self.remocoes += 1
            self.page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid^="conv-msg-FAKE"]'))
                .slice(0, 3).forEach(b => b.remove())""")

    def locator(self, seletor, *a, **k):
        loc = self.page.locator(seletor, *a, **k)
        return _LocatorQueRerenderiza(loc, self) if seletor == canal_web.SEL_BALAO else loc


class _LocatorQueRerenderiza:
    def __init__(self, loc, lista):
        self._loc, self._lista = loc, lista

    def __getattr__(self, nome):
        return getattr(self._loc, nome)

    def count(self):
        n = self._loc.count()
        self._lista._re_render()
        return n

    def evaluate_all(self, *a, **k):
        r = self._loc.evaluate_all(*a, **k)
        self._lista._re_render()
        return r


def test_confirmacao_com_re_render_da_lista_confirma_sem_excecao(abrir, foto):
    import time
    page, _ = abrir(pendenteMs=1_500)                                 # 1a varredura ve o balao novo pendente
    logs = []
    c = _canal(page, logs)
    c.abrir_canal(CANAL)
    c.anexar(foto)
    c.escrever_legenda(LEGENDA)
    lista = _ListaVirtualizada(page)
    c.page = lista
    inicio = time.monotonic()
    c.enviar()                                                        # _ids_baloes le a lista: 1o re-render
    assert c.confirmar(CHAVE, 8) is True                              # a confirmacao le de novo: 2o re-render
    assert time.monotonic() - inicio < 5                              # sem a espera de 30 s do nth(i)
    assert lista.remocoes == 2
    assert page.locator('[data-testid^="conv-msg-FAKE"]').count() == 3
    assert not any("sondagem falhou" in x for x in logs)


def test_balao_confirmado_le_uma_lista_atomica():
    antes = {"conv-msg-FAKE1"}
    novo = {"tid": "conv-msg-NOVO1", "legenda": f"Promo: https://{CHAVE}?utm_source=whatsapp", "status": " Enviada "}
    assert canal_web.balao_confirmado([{"tid": "conv-msg-FAKE1", "legenda": CHAVE, "status": "Enviada"}, novo],
                                      antes, CHAVE)
    assert not canal_web.balao_confirmado([{**novo, "tid": "conv-msg-FAKE1"}], antes, CHAVE)   # antigo
    assert not canal_web.balao_confirmado([{**novo, "legenda": None}], antes, CHAVE)            # sem legenda
    assert not canal_web.balao_confirmado([{**novo, "status": None}], antes, CHAVE)             # sem status
    assert not canal_web.balao_confirmado([], antes, CHAVE)


def test_confirmacao_excecao_transitoria_numa_sondagem_e_confirma_na_seguinte(abrir, foto, monkeypatch):
    page, _ = abrir()
    logs = []
    c = _canal(page, logs)
    c.abrir_canal(CANAL)
    c.anexar(foto)
    c.escrever_legenda(LEGENDA)
    c.enviar()
    ler = c._ler_baloes
    falhas = []

    def instavel():
        if not falhas:
            falhas.append(1)
            raise RuntimeError("Locator.evaluate_all: Execution context was destroyed")
        return ler()
    monkeypatch.setattr(c, "_ler_baloes", instavel)
    assert c.confirmar(CHAVE, 5) is True
    assert sum("sondagem falhou" in x for x in logs) == 1


def test_confirmacao_excecao_em_todas_as_sondagens_fica_d_com_aviso(abrir, foto, tmp_path, monkeypatch):
    import time
    page, _ = abrir()
    m = _publicador_real(page, tmp_path, tmp_path / "log")
    m.cfg["timeout_post_segundos"] = 3
    c = m.pub.pagina

    def sempre():
        raise RuntimeError("Locator.evaluate_all: Execution context was destroyed")
    i = m.fila.add(m.local())
    monkeypatch.setattr(c, "enviar", lambda: (CanalWeb.enviar(c), monkeypatch.setattr(c, "_ler_baloes", sempre)))
    inicio = time.monotonic()
    m.volta()
    assert time.monotonic() - inicio >= 3                               # sondou ate o prazo, nao abortou
    assert m.fila.st(i) == ("D", "enviando") and len(m.avisos) == 1 and "conferir no canal" in m.avisos[0]
    assert sum("sondagem falhou" in x for x in m.logs) == 1
    assert not any("erro depois do clique" in x for x in m.logs)       # confirmar nao levantou


def test_confirmacao_navegador_morto_fica_d_e_sai_com_1(abrir, foto, tmp_path, monkeypatch):
    page, _ = abrir()
    m = _publicador_real(page, tmp_path, tmp_path / "log")
    c = m.pub.pagina

    def morto():
        raise RuntimeError("Locator.evaluate_all: Target page, context or browser has been closed")
    monkeypatch.setattr(c, "enviar", lambda: (CanalWeb.enviar(c), monkeypatch.setattr(c, "_ler_baloes", morto)))
    i = m.fila.add(m.local())
    voltas = []

    def dormir(s):
        voltas.append(s)
        if len(voltas) >= 3:
            raise AssertionError("o laco seguiu depois do navegador morto")
    assert m.pub.rodar(dormir) == 1
    assert voltas == []                                                # saiu na mesma volta
    assert m.fila.st(i) == ("D", "enviando") and len(m.avisos) == 1 and "navegador caiu" in m.avisos[0]
