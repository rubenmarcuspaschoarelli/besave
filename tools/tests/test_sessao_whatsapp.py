"""BSV-67 RES-01..03, PAR-03 (fiacao): restauracao da copia da sessao e entrada sem operador.

Sem navegador: `lancar` devolve contexto/pagina falsos e a tela e um falso de estados. Os diretorios
user_data*, a copia e as marcas sao reais, num diretorio temporario.
"""
import sys
from datetime import UTC, datetime

import falsos
import pytest
from wa import pareamento, sessao

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)
COPIADA = "2026-11-27T08:30:12Z"          # 05:30 em Brasilia


class Contexto:
    def __init__(self, mundo):
        self.mundo = mundo
        self.fechado = False

    def close(self):
        self.fechado = True
        self.mundo.eventos.append("close")


class Mundo:
    """`telas`: o que cada lancamento mostra (logado/qr), na ordem."""

    def __init__(self, raiz, telas):
        self.raiz = raiz
        self.telas = list(telas)
        self.eventos: list[str] = []
        self.avisos: list[str] = []
        self.vinculos: list[tuple] = []
        self.contextos: list[Contexto] = []

    def lancar(self):
        # o que o Chromium leria do perfil nesse instante
        perfil = self.raiz / "user_data" / "Default" / "sessao.txt"
        self.eventos.append("lancar:" + (perfil.read_text(encoding="utf-8") if perfil.exists() else "(vazio)"))
        ctx = Contexto(self)
        self.contextos.append(ctx)
        return ctx, self.telas.pop(0)

    def tela_de(self, estado):
        class Tela:
            def esperar(self_):
                return estado

        return Tela()

    def vinculo_de(self, tela, numero, validade, teto, avisar, bater):
        mundo = self

        class V:
            def aguardar(self_):
                mundo.vinculos.append((numero, validade))
                mundo.eventos.append("vinculo")

        return V()

    def entrar(self, cfg=None):
        return sessao.entrar(self.lancar, cfg or {}, self.avisos.append, lambda: None, raiz=self.raiz,
                             agora=lambda: AGORA, tela_de=self.tela_de, teto=object(), vinculo_de=self.vinculo_de)


def _perfil(raiz, nome, texto):
    d = raiz / nome / "Default"
    d.mkdir(parents=True)
    (d / "sessao.txt").write_text(texto, encoding="utf-8")


def _copia(raiz, restaurada=False):
    _perfil(raiz, "user_data.copia", "boa")
    (raiz / "user_data.copia" / "copiada_em").write_text(COPIADA, encoding="utf-8")
    if restaurada:
        (raiz / "user_data.copia" / "restaurada_em").write_text("2026-11-26T10:00:00Z", encoding="utf-8")


def test_logado_direto_nao_toca_em_nada(tmp_path):
    _perfil(tmp_path, "user_data", "atual")
    _copia(tmp_path)
    m = Mundo(tmp_path, [pareamento.LOGADO])
    m.entrar()
    assert m.eventos == ["lancar:atual"] and m.avisos == []
    assert not (tmp_path / "user_data.copia" / "restaurada_em").exists()


def test_login_com_copia_nao_tentada_restaura_uma_vez(tmp_path, capsys):  # RES-01, RES-02
    _perfil(tmp_path, "user_data", "perdida")
    _perfil(tmp_path, "user_data.qr", "antiga")
    _copia(tmp_path)
    m = Mundo(tmp_path, [pareamento.QR, pareamento.LOGADO])
    ctx, tela = m.entrar()
    assert m.eventos == ["lancar:perdida", "close", "lancar:boa"]        # fechou antes de mexer no perfil
    assert ctx is m.contextos[1] and tela == pareamento.LOGADO
    assert m.vinculos == []
    # user_data movido (substitui a user_data.qr anterior), nunca apagado
    assert (tmp_path / "user_data.qr" / "Default" / "sessao.txt").read_text(encoding="utf-8") == "perdida"
    assert sorted(p.name for p in (tmp_path / "user_data").iterdir()) == ["Default"]   # sem as marcas
    assert (tmp_path / "user_data.copia" / "restaurada_em").read_text(encoding="utf-8") == "2026-11-27T15:00:00Z"
    assert (tmp_path / "user_data.copia" / "Default" / "sessao.txt").exists()          # a copia continua la
    log = capsys.readouterr().out
    assert "[sessao] tela de login; restaurando a copia de 2026-11-27T08:30:12Z" in log
    assert "[sessao] copia restaurada; sessao ok" in log
    assert m.avisos == ["WhatsApp: sessao perdida e restaurada da copia de 27/11 05:30 (sem acao)."]


def test_copia_ja_tentada_vai_direto_ao_codigo(tmp_path):  # RES-03
    _perfil(tmp_path, "user_data", "perdida")
    _copia(tmp_path, restaurada=True)
    m = Mundo(tmp_path, [pareamento.QR])
    m.entrar({"pareamento": {"numero": "+55 11 98765-0000", "validade_min": 10}})
    assert m.eventos == ["lancar:perdida", "vinculo"]
    assert m.vinculos == [("5511987650000", 10)]
    assert (tmp_path / "user_data" / "Default" / "sessao.txt").read_text(encoding="utf-8") == "perdida"
    assert not (tmp_path / "user_data.qr").exists()


def test_sem_copia_vai_ao_codigo(tmp_path):  # RES-03
    _perfil(tmp_path, "user_data", "perdida")
    m = Mundo(tmp_path, [pareamento.QR])
    m.entrar()
    assert m.eventos == ["lancar:perdida", "vinculo"] and m.avisos == []
    assert (tmp_path / "user_data").exists()


def test_copia_que_tambem_cai_no_login_vai_ao_codigo_e_nao_repete(tmp_path, capsys):  # RES-01, RES-03
    _perfil(tmp_path, "user_data", "perdida")
    _copia(tmp_path)
    m = Mundo(tmp_path, [pareamento.QR, pareamento.QR])
    m.entrar()
    assert m.eventos == ["lancar:perdida", "close", "lancar:boa", "vinculo"]
    assert m.avisos == []
    assert "a copia tambem caiu na tela de login" in capsys.readouterr().out
    # partida seguinte: a mesma copia nao e restaurada de novo (nada de laco)
    m2 = Mundo(tmp_path, [pareamento.QR])
    m2.entrar()
    assert m2.eventos == ["lancar:boa", "vinculo"]
    assert (tmp_path / "user_data.qr" / "Default" / "sessao.txt").read_text(encoding="utf-8") == "perdida"


# --- PAR-03: o monitor passa o config e um batimento de fase "pareamento" com prazo de 15 min -------------


@pytest.fixture
def zap(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from wa import monitor
    yield monitor
    for nome in set(sys.modules) - antes:
        if nome not in ("wa.janela",):
            sys.modules.pop(nome, None)


def test_monitor_passa_config_e_batimento_de_pareamento(zap, monkeypatch):  # PAR-03
    gravados, recebidos = [], {}
    estado = {"grupos": {}, "pareamento": {"numero": "5511987650000"}}

    class Banco:
        configurado = True
        espera_segundos = 60

        def conectar(self):
            return True

        def desconectar(self):
            pass

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    def abrir(pw, headless=False, cfg=None, bater=None):
        recebidos["cfg"] = cfg
        bater()
        raise KeyboardInterrupt

    monkeypatch.setattr(zap.batimento_mod, "agora_utc", lambda: AGORA)
    monkeypatch.setattr(zap.batimento_mod, "gravar_atomico", lambda caminho, dados: gravados.append(dict(dados)) or True)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", abrir)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: estado)
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: None)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Banco)
    zap.captura_msg_whatsapp(["g1"])
    assert recebidos["cfg"] is estado
    assert [g["fase"] for g in gravados] == ["partida", "pareamento"]
    assert gravados[1]["em"] == "2026-11-27T15:00:00Z" and gravados[1]["prazo"] == "2026-11-27T15:15:00Z"
