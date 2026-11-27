"""BSV-65 T3: recuperacao do navegador (aba nova, relancamento, codigo 3), mensagens do Telegram, evento
`crash` e relancamento preventivo. Playwright, contexto, aba, relogio e Telegram simulados."""
import argparse
from datetime import datetime

import pytest

ABA_1 = "Robo das lojas: navegador quebrou (Page crashed); aba nova. 1 linha(s) retida(s)."
RELANCADO_1 = "Robo das lojas: navegador quebrou (Page crashed); navegador relancado. 1 linha(s) retida(s)."
NAO_REABRIU = "Robo das lojas: navegador nao reabriu; saindo (codigo 3) para o vigia reiniciar."
VOLTOU_1 = "Robo das lojas: navegador voltou (1 linha(s) retida(s) voltam a ser processadas)."
HORA = 3600.0


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Aba:
    def __init__(self, ctx, n):
        self.ctx, self.n, self.fechada, self.handlers = ctx, n, False, {}
        self.url = ""

    def set_default_timeout(self, ms):
        pass

    def on(self, evento, funcao):
        self.handlers[evento] = funcao

    def close(self):
        self.fechada = True
        self.ctx.eventos.append(f"fecha_aba{self.n}")

    def is_closed(self):
        return self.fechada

    def wait_for_timeout(self, ms):
        pass


class Contexto:
    def __init__(self, eventos, nome, falha_new_page=False):
        self.eventos, self.nome, self.falha_new_page, self.abas = eventos, nome, falha_new_page, []
        self.fechado = False

    def new_page(self):
        if self.falha_new_page:
            raise RuntimeError("BrowserContext.new_page: Target page, context or browser has been closed")
        aba = Aba(self, len(self.eventos))
        self.abas.append(aba)
        self.eventos.append(f"nova_aba@{self.nome}")
        return aba

    def close(self):
        self.fechado = True
        self.eventos.append(f"fecha_contexto@{self.nome}")


@pytest.fixture
def rec(lojas, monkeypatch):
    rel = Relogio()
    enviados = []
    eventos = []
    lojas.NAV = lojas.navegador.Controle(avisar=enviados.append, agora=rel)
    monkeypatch.setattr(lojas.batimento, "gravar_atomico", lambda c, d: eventos.append(f"batimento:{d['fase']}") or True)
    lancados = []
    falha_launch = []

    def launch(p, headless=False):
        eventos.append("launch")
        lancados.append((p, headless))
        if falha_launch:
            raise RuntimeError("BrowserType.launch_persistent_context: Executable doesn't exist")
        return Contexto(eventos, f"ctx{len(lancados)}")
    monkeypatch.setattr(lojas, "launch_persistent", launch)
    preparados = []
    monkeypatch.setattr(lojas.link_afiliado, "preparar_contexto", lambda ctx: preparados.append(ctx.nome))
    ctx0 = Contexto(eventos, "ctx0")
    sessao = lojas._Sessao("PLAYWRIGHT", ctx0, lojas._nova_page(ctx0), capturar_link=True)
    eventos.clear()

    class R:
        pass
    r = R()
    r.lojas, r.rel, r.enviados, r.eventos, r.sessao, r.ctx0 = lojas, rel, enviados, eventos, sessao, ctx0
    r.lancados, r.preparados, r.falha_launch = lancados, preparados, falha_launch
    return r


def _quebra(rec, sinal="Page crashed"):
    rec.lojas.NAV.quebrou(sinal)


# --- REC-01 / TEL-01 -----------------------------------------------------------------------------------

def test_rec01_aba_nova_no_mesmo_contexto_com_mensagem_inteira(rec):
    aba_velha = rec.sessao.page
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    assert aba_velha.fechada
    assert rec.sessao.context is rec.ctx0 and rec.sessao.page is not aba_velha
    assert rec.eventos == ["fecha_aba0", "nova_aba@ctx0"]
    assert rec.lancados == []
    assert rec.enviados == [ABA_1]
    assert rec.lojas.NAV.pendente is None


def test_tel01_mensagem_de_timeouts_seguidos(rec):
    nav = rec.lojas.NAV
    for i in (1, 2, 3):
        nav.timeout(i)
    rec.lojas._recuperar_navegador(rec.sessao)
    assert rec.enviados == ["Robo das lojas: navegador quebrou (3 timeouts seguidos); aba nova. 3 linha(s) retida(s)."]


# --- REC-02 -----------------------------------------------------------------------------------------------

def test_rec02_aba_nova_quebrada_na_primeira_navegacao_relanca_com_o_mesmo_perfil(rec):
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    rec.lojas.NAV.retidas = 0
    _quebra(rec)                                    # a 1a navegacao da aba nova tambem quebrou
    rec.lojas._recuperar_navegador(rec.sessao)
    assert rec.ctx0.fechado
    assert rec.lancados == [("PLAYWRIGHT", False)]
    assert rec.preparados == ["ctx1"]               # preparar_contexto refeito, como no arranque
    assert rec.sessao.context.nome == "ctx1" and rec.sessao.page.ctx.nome == "ctx1"
    assert rec.eventos[2:] == ["fecha_contexto@ctx0", "launch", "nova_aba@ctx1"]
    assert rec.enviados == [ABA_1, RELANCADO_1]


def test_rec02_launch_usa_o_perfil_persistente(lojas, monkeypatch):
    chamadas = []

    class Chromium:
        def launch_persistent_context(self, perfil, **k):
            chamadas.append(perfil)

    class P:
        chromium = Chromium()
    from core import browser
    monkeypatch.setattr(browser, "_ler_config", lambda *a: {})
    browser.launch_persistent(P())
    assert chamadas == [browser.PERFIL_DIR]


def test_rec02_abrir_aba_falhando_relanca(rec):
    rec.ctx0.falha_new_page = True
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    assert rec.lancados == [("PLAYWRIGHT", False)]
    assert rec.enviados == [RELANCADO_1]


def test_rec02_aba_nova_seguida_de_ok_volta_a_usar_aba_nova(rec):
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    rec.lojas.NAV.aba_nova = False                  # o goto da aba nova passou
    rec.lojas.NAV.ok()
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    assert rec.lancados == []
    assert rec.enviados == [ABA_1, VOLTOU_1, ABA_1]


# --- REC-03 / TEL-02 -----------------------------------------------------------------------------------------

def test_rec03_relancamento_falhando_sai_com_codigo_3(rec):
    rec.ctx0.falha_new_page = True
    rec.falha_launch.append(True)
    _quebra(rec)
    with pytest.raises(SystemExit) as fim:
        rec.lojas._recuperar_navegador(rec.sessao)
    assert fim.value.code == 3
    assert rec.enviados == [NAO_REABRIU]


def _relancamento_por_falha(rec):
    rec.lojas.NAV.aba_nova = True
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)


def test_rec03_dois_relancamentos_em_60_min_seguem(rec):
    _relancamento_por_falha(rec)
    rec.rel.t = 50 * 60
    _relancamento_por_falha(rec)
    assert len(rec.lancados) == 2


def test_rec03_terceiro_relancamento_em_60_min_sai_com_codigo_3(rec):
    _relancamento_por_falha(rec)
    rec.rel.t = 30 * 60
    _relancamento_por_falha(rec)
    rec.rel.t = 59 * 60
    with pytest.raises(SystemExit) as fim:
        _relancamento_por_falha(rec)
    assert fim.value.code == 3
    assert len(rec.lancados) == 2
    assert rec.enviados[-1] == NAO_REABRIU


def test_rec03_fora_da_janela_de_60_min_segue(rec):
    _relancamento_por_falha(rec)
    rec.rel.t = 30 * 60
    _relancamento_por_falha(rec)
    rec.rel.t = 61 * 60                             # o 1o ja saiu da janela
    _relancamento_por_falha(rec)
    assert len(rec.lancados) == 3


# --- Integracao no monitor --------------------------------------------------------------------------------

class Db:
    sem_conexao = False

    def __init__(self):
        self.capturas, self.erros = [], []

    def atualizar_captura(self, id_oferta, out, ativo=False):
        self.capturas.append(id_oferta)
        return True, None

    def marcar_erro(self, id_oferta, status, url, ativo=False):
        self.erros.append(id_oferta)
        return True, None

    def buscar_para_produto(self, i):
        return None

    def buscar_para_cupom(self, i):
        return None


def _rows(*ids):
    return [{"ID_OFERTA": i, "url": f"https://amazon.com.br/p/{i}", "numero_da_captura": str(i), "DS_ORIGEM": "g"}
            for i in ids]


def _monitor(rec, monkeypatch, filas, lote=None):
    lojas = rec.lojas
    respostas = iter(filas)

    def ler(*a, **k):
        try:
            resp = next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None
        return resp() if callable(resp) else resp
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", lambda s: rec.eventos.append("dorme"))
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_gravar_csv", lambda *a, **k: None)
    monkeypatch.setattr(lojas, "_resumo_oracle", lambda *a, **k: None)
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda *a: None)
    if lote is not None:
        monkeypatch.setattr(lojas, "_processar_lote", lote)
    db = Db()
    lojas._monitorar(rec.sessao.context, rec.sessao.page, db, argparse.Namespace(desde=None, limite=0), [], "img", 3,
                     None, sessao=rec.sessao)
    return db


def test_monitor_crash_aba_nova_mesma_linha_ok_e_voltou(rec, monkeypatch):
    aba_velha = rec.sessao.page
    visitas = []

    def navegar(page, url, timeout=0):
        visitas.append((page.n, url[-1]))
        if page is aba_velha:
            raise RuntimeError("Page.goto: Page crashed")
        page.url = url
    monkeypatch.setattr(rec.lojas, "_goto_robusto", navegar)
    db = _monitor(rec, monkeypatch, [_rows(1, 2), _rows(1, 2), []])
    assert visitas[0][0] == aba_velha.n and all(n != aba_velha.n for n, _ in visitas[1:])
    assert [u for _, u in visitas] == ["1", "1", "2"]                 # a 2 nao foi tentada na aba quebrada
    assert db.erros == [] and db.capturas == [1, 2]
    assert rec.enviados == [ABA_1, VOLTOU_1]


def test_monitor_relancamento_falhando_sai_3_sem_batimento_depois(rec, monkeypatch):
    rec.ctx0.falha_new_page = True
    rec.falha_launch.append(True)
    monkeypatch.setattr(rec.lojas, "_goto_robusto",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Page.goto: Page crashed")))
    with pytest.raises(SystemExit) as fim:
        _monitor(rec, monkeypatch, [_rows(1, 2)])
    assert fim.value.code == 3
    decisao = rec.eventos.index("launch")
    assert not any(e.startswith("batimento:") for e in rec.eventos[decisao:])
    assert rec.enviados == [NAO_REABRIU]


# --- DIA-01: evento crash ---------------------------------------------------------------------------------

def test_dia01_evento_crash_da_page_loga_diagnostico_e_marca_a_aba(rec, capsys, monkeypatch):
    monkeypatch.setattr(rec.lojas.NAV, "diagnostico", lambda: "[navegador] diagnostico: mem_disponivel=1 MB")
    aba = rec.lojas._nova_page(rec.ctx0)
    aba.handlers["crash"](aba)
    assert "[navegador] diagnostico: mem_disponivel=1 MB\n" in capsys.readouterr().out
    assert rec.lojas.NAV.crash is True


def test_dia01_recuperacao_loga_diagnostico(rec, capsys, monkeypatch):
    monkeypatch.setattr(rec.lojas.NAV, "diagnostico", lambda: "[navegador] diagnostico: X")
    _quebra(rec)
    rec.lojas._recuperar_navegador(rec.sessao)
    assert "[navegador] diagnostico: X" in capsys.readouterr().out


# --- PRE-01: preventivo ---------------------------------------------------------------------------------------

def _lote_que_anda(rec, horas):
    def lote(page, rows, *a, **k):
        rec.eventos.append("lote:inicio")
        rec.rel.t += horas * HORA
        rec.eventos.append("lote:fim")
        return [], 0, 0
    return lote


def test_pre01_relanca_depois_de_6h_so_entre_lotes(rec, monkeypatch, capsys):
    rec.lojas.NAV.relancar_horas = 6
    rec.rel.t = 5.5 * HORA
    _monitor(rec, monkeypatch, [_rows(1), []], lote=_lote_que_anda(rec, 1))
    ev = [e for e in rec.eventos if not e.startswith("batimento") and e != "dorme"]
    assert ev == ["lote:inicio", "lote:fim", "fecha_contexto@ctx0", "launch", "nova_aba@ctx1"]
    assert rec.enviados == []                                       # sucesso nao vai ao Telegram
    out = capsys.readouterr().out
    assert out.index("[navegador] diagnostico:") < out.index("[monitor] contexto fechado")


def test_pre01_antes_de_6h_nao_relanca(rec, monkeypatch):
    rec.lojas.NAV.relancar_horas = 6
    rec.rel.t = 5.9 * HORA
    _monitor(rec, monkeypatch, [[], []])
    assert rec.lancados == []


def test_pre01_zero_desliga(rec, monkeypatch):
    rec.lojas.NAV.relancar_horas = 0
    rec.rel.t = 100 * HORA
    _monitor(rec, monkeypatch, [[], []])
    assert rec.lancados == []


def test_pre01_preventivo_nao_conta_para_os_3_em_60_min(rec, monkeypatch):
    rec.lojas.NAV.relancar_horas = 0.1                              # 6 min
    rec.rel.t = 7 * 60
    _monitor(rec, monkeypatch, [[]])                                # preventivo 1
    rec.rel.t += 7 * 60
    _monitor(rec, monkeypatch, [[]])                                # preventivo 2
    assert len(rec.lancados) == 2
    _relancamento_por_falha(rec)
    _relancamento_por_falha(rec)                                    # 2 por falha: segue
    assert len(rec.lancados) == 4


def test_pre01_falha_do_preventivo_sai_com_codigo_3(rec, monkeypatch):
    rec.lojas.NAV.relancar_horas = 6
    rec.rel.t = 6 * HORA
    rec.falha_launch.append(True)
    with pytest.raises(SystemExit) as fim:
        _monitor(rec, monkeypatch, [[]])
    assert fim.value.code == 3
    assert rec.enviados == [NAO_REABRIU]


def test_pre01_janela_noturna_relanca_na_rodada(rec, monkeypatch):
    """Na janela, o robo dorme entre rodadas: o preventivo vencido no sono espera a rodada seguinte."""
    rec.lojas.NAV.relancar_horas = 6
    rec.rel.t = 5.9 * HORA

    def dormir(s):
        rec.eventos.append("dorme")
        rec.rel.t += 2 * HORA
    lojas = rec.lojas

    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 25, 23, 0)
    monkeypatch.setattr(lojas, "datetime", Rel)
    respostas = iter([[], []])

    def ler(*a, **k):
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", dormir)
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda *a: None)
    janela = lojas.janela_mod.ler_janela({"janela_noturna": {"inicio": "22:00", "fim": "08:00",
                                                             "intervalo_minutos": 120}})
    lojas._monitorar(rec.sessao.context, rec.sessao.page, Db(), argparse.Namespace(desde=None, limite=0), [], "img",
                     3, janela, sessao=rec.sessao)
    ev = [e for e in rec.eventos if not e.startswith("batimento")]
    assert ev == ["dorme", "fecha_contexto@ctx0", "launch", "nova_aba@ctx1", "dorme"]


def test_rec01_aba_nova_zera_o_crash_e_nao_relanca(rec, monkeypatch):
    """Evento `crash` na aba velha: a aba nova nasce limpa; a linha seguinte sai ok sem relancamento."""
    aba_velha = rec.sessao.page

    def navegar(page, url, timeout=0):
        if page is aba_velha:
            page.handlers["crash"](page)
            raise RuntimeError("Page.goto: Page crashed")
        page.url = url
    monkeypatch.setattr(rec.lojas, "_goto_robusto", navegar)
    db = _monitor(rec, monkeypatch, [_rows(1, 2), _rows(1, 2), []])
    assert db.capturas == [1, 2] and db.erros == []
    assert rec.lancados == []
    assert rec.enviados == [ABA_1, VOLTOU_1]


def test_rec01_lote_sem_monitor_recupera_e_segue_da_linha_retida(rec, monkeypatch):
    aba_velha = rec.sessao.page
    visitas = []

    def navegar(page, url, timeout=0):
        visitas.append((page is aba_velha, url[-1]))
        if page is aba_velha:
            raise RuntimeError("Page.goto: Page crashed")
        page.url = url
    monkeypatch.setattr(rec.lojas, "_goto_robusto", navegar)
    db = Db()
    out, gravadas, com_erro = rec.lojas._lote_com_recuperacao(rec.sessao, _rows(1, 2, 3), db, True, "img", None)
    assert visitas == [(True, "1"), (False, "1"), (False, "2"), (False, "3")]
    assert [o["ID_OFERTA"] for o in out] == [1, 1, 2, 3]
    assert db.capturas == [1, 2, 3] and db.erros == []
    assert (gravadas, com_erro) == (3, 0)
    assert rec.enviados == [ABA_1, VOLTOU_1]
