"""BSV-65 T2: navegador quebrado e timeouts no lote do robo das lojas (Saidas 2, 4, 5 "voltou" e 6).
Sem Playwright nem Oracle: page, loja, banco e Telegram simulados."""
from datetime import UTC, datetime

import pytest
from conftest import Loja

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
CRASH = "Page.goto: Page crashed"
VOLTOU_1 = "Robo das lojas: navegador voltou (1 linha(s) retida(s) voltam a ser processadas)."


class Pagina:
    url = ""

    def wait_for_timeout(self, ms):
        pass

    def is_closed(self):
        return False


class Db:
    sem_conexao = False

    def __init__(self):
        self.capturas, self.erros = [], []

    def atualizar_captura(self, id_oferta, out, ativo=False):
        self.capturas.append(id_oferta)
        return True, None

    def marcar_erro(self, id_oferta, status, url, ativo=False):
        self.erros.append((id_oferta, status))
        return True, None

    def buscar_para_produto(self, i):
        return None

    def buscar_para_cupom(self, i):
        return None


class PausaFalsa:
    def __init__(self):
        self.bloqueios = []

    def em_pausa(self, loja):
        return False

    def registrar_bloqueio(self, *a, **k):
        self.bloqueios.append(a)

    def __getattr__(self, nome):
        return lambda *a, **k: None


@pytest.fixture
def amb(lojas, monkeypatch):
    """`falhas[id]` = excecao do goto (ou callable por fase); o resto navega ok."""
    enviados = []
    lojas.NAV = lojas.navegador.Controle(avisar=enviados.append, agora=lambda: 0.0)
    bat = []
    monkeypatch.setattr(lojas.batimento, "agora_utc", lambda: T0)
    monkeypatch.setattr(lojas.batimento, "gravar_atomico", lambda c, d: bat.append(dict(d)) or True)
    monkeypatch.setattr(lojas.batimento, "_navegador", {"ultimo_ok": None, "tentativas": 0})
    goto = {}
    visitas = []

    def navegar(page, url, timeout=0):
        i = int(url.rsplit("/", 1)[1])
        visitas.append(i)
        if i in goto:
            raise goto[i]
        page.url = url
    monkeypatch.setattr(lojas, "_goto_robusto", navegar)

    def rodar(ids, loja_cls=Loja, db=None, dominio="amazon.com.br"):
        db = db or Db()
        monkeypatch.setattr(lojas.registry, "get_store", lambda loja: loja_cls())
        rows = [{"ID_OFERTA": i, "url": f"https://{dominio}/p/{i}", "numero_da_captura": str(i), "DS_ORIGEM": "g"}
                for i in ids]
        pausa = PausaFalsa()
        saidas, _, _ = lojas._processar_lote(Pagina(), rows, db, True, "img", set(), pausa)
        return {o["ID_OFERTA"]: o["status_captura"] for o in saidas}, db, pausa

    class A:
        pass
    a = A()
    a.lojas, a.rodar, a.goto, a.visitas, a.enviados, a.bat = lojas, rodar, goto, visitas, enviados, bat
    return a


# --- LIN-01 / LIN-02: Page crashed em cada fase -----------------------------------------------------------

def _crash_no_capture():
    class L(Loja):
        def capture(self, page):
            raise RuntimeError("Locator.inner_text: Page crashed")
    return L


def _crash_no_prepare():
    class L(Loja):
        def prepare(self, page):
            raise RuntimeError("Page.click: Target crashed")
    return L


@pytest.mark.parametrize("fase", ["goto", "capture", "prepare", "afiliado", "imagens"])
def test_lin01_page_crashed_retem_a_linha_e_para_o_lote(amb, monkeypatch, fase):
    loja_cls = Loja
    if fase == "goto":
        amb.goto[2] = RuntimeError(CRASH)
    elif fase == "capture":
        loja_cls = _crash_no_capture()
    elif fase == "prepare":
        loja_cls = _crash_no_prepare()
    elif fase == "afiliado":
        def capturar(page, loja, url):
            if url.endswith("/2"):
                raise RuntimeError("Page.evaluate: Page crashed")
            return {}
        monkeypatch.setattr(amb.lojas.link_afiliado, "capturar", capturar)
    elif fase == "imagens":
        class L(Loja):
            baixar_imagens = True

            def get_images(self, page, folder):
                amb.lojas.NAV.crash = True       # evento 'crash' da page; a loja engole a excecao
        loja_cls = L
    if fase in ("capture", "prepare", "imagens"):
        # a linha 1 passa, a 2 quebra
        base = loja_cls

        class Uma(base):
            n = 0

            def __init__(self):
                Uma.n += 1
                self.quebra = Uma.n == 2

            def capture(self, page):
                return base.capture(self, page) if self.quebra else {}

            def prepare(self, page):
                return base.prepare(self, page) if self.quebra else None

            def get_images(self, page, folder):
                return base.get_images(self, page, folder) if self.quebra else 0
        loja_cls = Uma
    status, db, pausa = amb.rodar([1, 2, 3, 4], loja_cls)
    assert status[1] == "ok"
    assert 2 in status and 3 not in status and 4 not in status          # lote parado
    assert 3 not in amb.visitas
    assert db.erros == []                                                # marcar_erro nao chamado
    assert db.capturas == [1]
    assert amb.lojas.ponteiro == [1]                                     # nao passa da 2
    amb.rodar([5], db=db)
    assert amb.lojas.ponteiro == [1]                                     # travado na 2 (mesmo banco)
    assert amb.lojas.NAV.pendente is not None
    assert pausa.bloqueios == []                                         # nao conta para a pausa da loja


def test_lin01_log_mostra_retida(amb, capsys):
    amb.goto[1] = RuntimeError(CRASH)
    amb.rodar([1])
    out = capsys.readouterr().out
    assert "oracle=retida(0)" in out and "status=erro: RuntimeError: Page.goto: Page crashed" in out


def test_lin01_ponte_com_navegador_quebrado_nao_vira_loja_desconhecida(amb, monkeypatch):
    def ponte(page, url, captura):
        raise RuntimeError("Page.goto: Page crashed")
    monkeypatch.setattr(amb.lojas, "_goto_robusto", lambda page, url, timeout=0: ponte(page, url, ""))
    monkeypatch.setattr(amb.lojas.registry, "resolver_loja", lambda url: None)
    status, db, _ = amb.rodar([7], dominio="exemplo-ponte.com")
    assert db.erros == [] and status[7].startswith("erro:")
    assert amb.lojas.NAV.pendente == "Page crashed"


def test_lin01_erro_comum_continua_indo_para_9(amb):
    class L(Loja):
        def capture(self, page):
            raise RuntimeError("seletor sumiu")
    _, db, _ = amb.rodar([1, 2], L)
    assert [i for i, _ in db.erros] == [1, 2]                           # e o lote segue
    assert amb.lojas.NAV.pendente is None


# --- TMO-01..03 -------------------------------------------------------------------------------------------

def _timeout():
    return TimeoutError("Page.goto: Timeout 60000ms exceeded")


def test_tmo01_dois_timeouts_so_retem(amb):
    amb.goto.update({1: _timeout(), 2: _timeout()})
    status, db, _ = amb.rodar([1, 2, 3])
    assert status[3] == "ok"
    assert db.erros == [] and db.capturas == [3]
    assert amb.lojas.NAV.pendente is None
    assert amb.lojas.ponteiro == []                                     # travado na 1


def test_tmo02_tres_timeouts_seguidos_disparam_recuperacao(amb):
    amb.goto.update({1: _timeout(), 2: _timeout(), 3: _timeout()})
    status, db, _ = amb.rodar([1, 2, 3, 4])
    assert 4 not in status and 4 not in amb.visitas
    assert db.erros == []
    assert amb.lojas.NAV.pendente == "3 timeouts seguidos"


def test_tmo02_ok_no_meio_zera_a_sequencia(amb):
    amb.goto.update({1: _timeout(), 2: _timeout(), 4: _timeout(), 5: _timeout()})
    status, _, _ = amb.rodar([1, 2, 3, 4, 5, 6])
    assert status[3] == status[6] == "ok"
    assert amb.lojas.NAV.pendente is None


def test_tmo02_shopee_api_ok_nao_zera_a_sequencia(amb, monkeypatch):
    lojas = amb.lojas
    monkeypatch.setattr(lojas.shopee_api, "ler_config", lambda cfg: object())
    monkeypatch.setattr(lojas, "_capturar_shopee_api", lambda *a: ({}, "ok", ""))
    monkeypatch.setattr(lojas.registry, "resolver_loja", lambda url: "shopee" if "shopee" in url else "amazon")
    amb.goto.update({1: _timeout(), 2: _timeout(), 4: _timeout()})
    amb.rodar([1, 2])
    status, _, _ = amb.rodar([3], dominio="shopee.com.br")
    assert status[3] == "ok"
    amb.rodar([4])
    assert lojas.NAV.pendente == "3 timeouts seguidos"


def test_tmo03_mesma_linha_com_tres_timeouts_vai_para_9(amb):
    amb.goto[1] = _timeout()
    for _ in range(2):
        _, db, _ = amb.rodar([1])
        assert db.erros == []
    amb.lojas.NAV.seq_timeouts = 0                                      # isola da regra dos seguidos
    _, db, _ = amb.rodar([1])
    assert db.erros == [(1, "erro: TimeoutError: Page.goto: Timeout 60000ms exceeded")]


def test_tmo01_timeout_fora_do_goto_nao_retem(amb):
    class L(Loja):
        def capture(self, page):
            raise TimeoutError("Locator.click: Timeout 15000ms exceeded")
    _, db, _ = amb.rodar([1], L)
    assert [i for i, _ in db.erros] == [1]


# --- TEL-03: "voltou" ---------------------------------------------------------------------------------------

def test_tel03_voltou_so_depois_de_ocorrencia_e_ok_por_navegador(amb):
    amb.rodar([1])
    assert amb.enviados == []                                           # sem ocorrencia, sem "voltou"
    amb.goto[2] = RuntimeError(CRASH)
    amb.rodar([2])
    amb.lojas.NAV.pendente = None
    amb.lojas.NAV.aberta = True                                         # a recuperacao (T3) abre a ocorrencia
    amb.goto.clear()
    amb.rodar([2, 3])
    assert amb.enviados == [VOLTOU_1]                                   # uma vez so


def test_tel03_ok_da_shopee_pela_api_nao_fecha(amb, monkeypatch):
    lojas = amb.lojas
    monkeypatch.setattr(lojas.shopee_api, "ler_config", lambda cfg: object())
    monkeypatch.setattr(lojas, "_capturar_shopee_api", lambda *a: ({}, "ok", ""))
    monkeypatch.setattr(lojas.registry, "resolver_loja", lambda url: "shopee" if "shopee" in url else "amazon")
    lojas.NAV.aberta, lojas.NAV.retidas = True, 1
    amb.rodar([9], dominio="shopee.com.br")
    assert amb.enviados == []
    amb.rodar([10])
    assert amb.enviados == [VOLTOU_1]


# --- CLS-02 / VIG-01 no lote -------------------------------------------------------------------------------

def test_cls02_linha_quebrada_nao_renova_o_batimento(amb):
    amb.goto[1] = RuntimeError(CRASH)
    amb.rodar([1])
    assert amb.bat == []


def test_vig01_campos_do_batimento_andam_so_com_navegador(amb, monkeypatch):
    lojas = amb.lojas

    class L(Loja):
        def capture(self, page):
            raise RuntimeError("seletor sumiu")
    amb.rodar([1, 2], L)
    assert amb.bat[-1]["tentativas_navegador"] == 2
    monkeypatch.setattr(lojas.shopee_api, "ler_config", lambda cfg: object())
    monkeypatch.setattr(lojas, "_capturar_shopee_api", lambda *a: ({}, "ok", ""))
    monkeypatch.setattr(lojas.registry, "resolver_loja", lambda url: "shopee" if "shopee" in url else "amazon")
    amb.rodar([3], dominio="shopee.com.br")
    assert amb.bat[-1]["tentativas_navegador"] == 2                     # Shopee pela API nao mexe
    amb.rodar([4])
    assert amb.bat[-1]["tentativas_navegador"] == 0
    assert amb.bat[-1]["ultimo_ok_navegador"] == "2026-11-25T12:00:00Z"


def test_vig01_loja_pausada_nao_conta_em_tentativas(amb, lojas, monkeypatch):
    class L(Loja):
        def capture(self, page):
            raise RuntimeError("seletor sumiu")
    amb.rodar([1], L)
    assert amb.bat[-1]["tentativas_navegador"] == 1

    class Pausada(PausaFalsa):
        def em_pausa(self, loja):
            return True
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: Loja())
    rows = [{"ID_OFERTA": 2, "url": "https://amazon.com.br/p/2", "numero_da_captura": "2", "DS_ORIGEM": "g"}]
    saidas, _, _ = lojas._processar_lote(Pagina(), rows, Db(), True, "img", set(), Pausada())
    assert saidas[0]["status_captura"] == "loja_pausada"
    assert amb.bat[-1]["tentativas_navegador"] == 1                     # a pausada renova, mas nao conta


def test_tel01_linha_que_vai_para_9_no_terceiro_timeout_nao_conta_como_retida(amb):
    amb.goto[1] = _timeout()
    for _ in range(3):
        amb.lojas.NAV.seq_timeouts = 0                                  # isola da regra dos seguidos
        amb.rodar([1])
    assert amb.lojas.NAV.retidas == 2                                   # 2 retidas; a 3a foi para '9'
