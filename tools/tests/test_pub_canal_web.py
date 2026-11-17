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
        canal_web.SEL_ANEXAR: 1, canal_web.SEL_INPUT_FOTO: 1, canal_web.SEL_LEGENDA: 1, canal_web.SEL_ENVIAR: 1,
    }
    for sel, n in unicos.items():
        assert page.locator(sel).count() == n, sel
    assert page.locator(canal_web.SEL_BALAO).count() == 9
    assert page.locator(canal_web.SEL_LEGENDA_BALAO).count() == 3
    rotulos = page.locator(canal_web.SEL_STATUS_BALAO).evaluate_all("e => e.map(x => x.getAttribute('aria-label'))")
    assert rotulos and all(canal_web.status_confirmado(r) for r in rotulos)     # real: " Enviada "
    assert page.locator('input[type="file"]').count() == 1                     # o oculto do footer


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


def test_dom_input_ausente_usa_o_anexar(abrir, foto):
    page, c = abrir(semInput=True)
    assert page.locator('input[type="file"]').count() == 0
    assert _postar(c, foto) is True
    assert page.locator(canal_web.SEL_ANEXAR).get_attribute("aria-expanded") == "true"


def test_dom_sem_input_nenhum_usa_fotos_e_videos_com_expect_file_chooser(abrir, foto):
    page, c = abrir(menuSemInput=True)
    assert _postar(c, foto) is True
    assert _envios(page) == [LEGENDA]


def test_dom_input_de_arquivo_fora_do_footer_nao_e_usado(abrir, foto):
    page, c = abrir()
    page.evaluate("""const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/*';
        i.id = 'isca'; document.body.prepend(i);""")
    c.abrir_canal(CANAL)
    c.anexar(foto)
    assert page.evaluate("document.getElementById('isca').files.length") == 0
    assert page.evaluate("document.querySelector('#main footer input[type=file]').files.length") == 1


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


def test_anexo_previa_que_abre_em_20s_passa(abrir, foto):
    page, _ = abrir(atrasoPrevia=20_000)
    logs = []
    c = _canal(page, logs)
    c.abrir_canal(CANAL)
    c.anexar(foto)                                          # com 15 s de espera falharia
    linha = next(x for x in logs if x.startswith("[anexo] "))
    m = re.fullmatch(r"\[anexo\] caminho=input previa_s=(\d+\.\d)", linha)
    assert m and 20.0 <= float(m.group(1)) < 30.0
    assert page.evaluate("window.__arquivosPorCaminho") == {"input": 1, "menu": 0}


def test_anexo_espera_da_previa_e_30s():
    assert canal_web.ESPERA_PREVIA_S == 30


def test_anexo_input_sem_previa_cai_para_o_menu_uma_vez(abrir, foto, monkeypatch):
    monkeypatch.setattr(canal_web, "ESPERA_PREVIA_S", 2)
    page, _ = abrir(inputNaoAbre=True, menu=True)
    logs = []
    c = _canal(page, logs)
    assert _postar(c, foto) is True
    anexo = [x for x in logs if x.startswith("[anexo] ")]
    assert anexo[0] == "[anexo] caminho=input previa=nao"
    assert re.fullmatch(r"\[anexo\] caminho=menu previa_s=\d+\.\d", anexo[1]) and len(anexo) == 2
    assert page.evaluate("window.__arquivosPorCaminho") == {"input": 1, "menu": 1}
    assert page.evaluate("window.__escapesAntesDoMenu") >= 1            # Escape antes do 2o caminho


def test_anexo_os_dois_caminhos_falham_linha_p_sem_d_com_evidencia(abrir, foto, tmp_path, monkeypatch):
    from datetime import datetime

    from pub_falso import Mundo
    monkeypatch.setattr(canal_web, "ESPERA_PREVIA_S", 1)
    page, _ = abrir(inputNaoAbre=True, menu=True, menuNaoAbre=True)
    page.evaluate("document.querySelector('#app').insertAdjacentHTML('beforeend', '<span>5511987654321</span>')")
    pasta = tmp_path / "log"
    m = Mundo(tmp_path / "mundo")
    m.fila.nome = CANAL
    m.pub.pagina = _canal(page, m.logs, pasta, agora=lambda: datetime(2026, 11, 17, 11, 17, 5))
    i = m.fila.add(m.local())
    m.volta()
    assert m.fila.st(i) == ("P", None) and m.pub.falhas_seguidas == 1      # sem D
    assert _envios(page) == [] and m.avisos == []
    assert page.evaluate("window.__arquivosPorCaminho") == {"input": 1, "menu": 1}
    assert "[anexo] caminho=input previa=nao" in m.logs and "[anexo] caminho=menu previa=nao" in m.logs
    png, html = pasta / "falha_1711_111705.png", pasta / "falha_1711_111705.html"
    assert png.read_bytes()[:4] == bytes([0x89]) + b"PNG"
    texto = html.read_text(encoding="utf-8")
    assert "conversation-panel-wrapper" in texto                 # e o DOM da pagina
    assert not re.search(r"\d{10,}", texto) and "REDACTED" in texto


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
