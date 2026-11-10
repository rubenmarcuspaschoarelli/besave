"""BSV-56: call_timeout em toda conexao do OracleDB do WhatsApp; tempo esgotado = banco fora.
oracledb falso: a "rede" trava as chamadas (DPI-1067, como o modo thick devolve) por N chamadas."""
import sys
import time
from datetime import datetime, timedelta

import falsos
import pytest
from test_id_sequence_whatsapp import T0, TOKEN, Pagina, estado, item, reg, zap  # noqa: F401

# Texto real do driver: no thick o python-oracledb converte o DPI-1067 em DPY-4024 e mantem o original abaixo.
TIMEOUT_THICK = "DPY-4024: call timeout of 30000 ms exceeded\nDPI-1067: call timeout of 30000 ms exceeded with ORA-3156"
TIMEOUT_THIN = "DPY-4024: call timeout of 30000 ms exceeded"
TIMEOUT_DPI_SO = "DPI-1067: call timeout of 30000 ms exceeded with ORA-3156"   # driver sem a conversao


class Rede:
    def __init__(self, travadas=0, erro=TIMEOUT_THICK):
        self.travadas = travadas      # chamadas (NEXTVAL, SELECT 1, SP) que ainda vao estourar o tempo
        self.erro = erro
        self.seq = 46100
        self.chamadas = []


class Var:
    def getvalue(self):
        return "TRUE"


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.linha = None

    def var(self, tipo, tam):
        return Var()

    def execute(self, sql, binds=None, **kw):
        rede = self.conn.rede
        sqlu = sql.upper()
        if "USER_ARGUMENTS" in sqlu:
            self.linha = [0]
            return
        rede.chamadas.append(sqlu.split()[1] if sqlu.startswith("SELECT") else "SP")
        if rede.travadas > 0:
            rede.travadas -= 1
            raise RuntimeError(rede.erro)
        if "NEXTVAL" in sqlu:
            self.linha = [rede.seq]
            rede.seq += 1
        else:
            self.linha = [1]

    def fetchone(self):
        return self.linha

    def close(self):
        pass


class Conn:
    def __init__(self, rede):
        self.rede = rede
        self.call_timeout = 0          # padrao do driver: sem limite

    def cursor(self):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Driver:
    DB_TYPE_VARCHAR = "VARCHAR"

    def __init__(self, rede):
        self.rede = rede
        self.conexoes = []

    def connect(self, **kw):
        c = Conn(self.rede)
        self.conexoes.append(c)
        return c

    def makedsn(self, *a, **kw):
        return "dsn"

    def init_oracle_client(self, **kw):
        pass


CFG = {"habilitado": True, "modo": "thin", "usuario": "u", "senha": "s", "host": "h"}


@pytest.fixture
def novo(monkeypatch):
    falsos.instalar(monkeypatch)
    from wa import oracle_db

    def criar(rede, cfg=None):
        drv = Driver(rede)
        monkeypatch.setattr(oracle_db, "oracledb", drv)
        db = oracle_db.OracleDB(dict(cfg or CFG))
        db.conectar()
        return db, drv, oracle_db
    yield criar
    sys.modules.pop("wa.oracle_db", None)


# --- OracleDB ------------------------------------------------------------------

@pytest.mark.parametrize("valor, ms", [(None, 30000), (5, 5000), (0.5, 500), (0, 30000), ("x", 30000), (-3, 30000)])
def test_call_timeout_do_config_na_conexao(novo, valor, ms):
    cfg = dict(CFG)
    if valor is not None:
        cfg["call_timeout_segundos"] = valor
    _, drv, _ = novo(Rede(), cfg)
    assert [c.call_timeout for c in drv.conexoes] == [ms]


def test_call_timeout_tambem_na_reconexao(novo):
    rede = Rede()
    db, drv, _ = novo(rede, {**CFG, "call_timeout_segundos": 7})
    rede.travadas, rede.erro = 1, "DPY-1001: not connected"     # cai; proximo_id reconecta
    assert db.proximo_id() == 46100
    assert len(drv.conexoes) == 2
    assert [c.call_timeout for c in drv.conexoes] == [7000, 7000]


@pytest.mark.parametrize("erro, codigo", [(TIMEOUT_THICK, "DPY-4024"), (TIMEOUT_THIN, "DPY-4024"),
                                          (TIMEOUT_DPI_SO, "DPI-1067")])
def test_tempo_esgotado_no_nextval_e_banco_fora_sem_reconectar(novo, erro, codigo):
    rede = Rede()
    db, drv, oracle_db = novo(rede)
    rede.travadas, rede.erro = 1, erro
    with pytest.raises(oracle_db.ErroSemId) as e:
        db.proximo_id()
    assert str(e.value) == codigo
    assert len(drv.conexoes) == 1          # reconectar com a rede caida travaria de novo
    assert db.ids_entregues == 0
    assert db.proximo_id() == 46100        # a conexao segue utilizavel quando a rede volta


@pytest.mark.parametrize("erro", [TIMEOUT_THICK, TIMEOUT_THIN, TIMEOUT_DPI_SO])
def test_tempo_esgotado_no_insert_falha_pelo_caminho_de_sempre(novo, erro):
    rede = Rede()
    db, drv, _ = novo(rede)
    rede.travadas, rede.erro = 1, erro
    assert db.inserir_oferta({"ID_OFERTA": "46100", "DS_OFERTA": "x"}) is False
    assert db.sem_conexao is True          # log do monitor: "db=ERRO (sem conexão)"
    assert rede.chamadas == ["SP"]         # sem repetir a SP
    assert len(drv.conexoes) == 1


# --- laco do monitor com o OracleDB de verdade ----------------------------------

def test_rede_travada_vira_um_aviso_e_a_mesma_mensagem_sai_com_id_novo(zap, reg, monkeypatch, novo):  # noqa: F811
    """A rede trava (DROP): o NEXTVAL estoura o call_timeout -> 1 aviso, nada no CSV, marcador parado.
    O SELECT 1 da espera tambem estoura uma vez; depois a rede volta: a mesma mensagem sai com id novo
    e chega o "voltou". Toda conexao aberta no caminho tem o call_timeout."""
    rede = Rede()
    db, drv, _ = novo(rede, {**CFG, "call_timeout_segundos": 30})
    rede.travadas = 3                       # NEXTVAL na partida, SELECT 1 da espera, SELECT 1 apos reconectar
    relogio = {"t": T0}
    enviados, sleeps = [], []

    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return relogio["t"]

    def dorme(s):
        sleeps.append(s)
        relogio["t"] += timedelta(seconds=s)

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    class Ctx:
        def close(self):
            pass

    def parar(janela):
        raise KeyboardInterrupt

    est = estado()
    csv_na_queda = []

    def enviar(t, c, m):
        enviados.append(m)
        csv_na_queda.append(len(reg.csv))

    monkeypatch.setattr(zap, "datetime", Rel)
    monkeypatch.setattr(time, "sleep", dorme)
    monkeypatch.setattr(zap.alerta, "enviar_telegram", enviar)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", lambda page, nome: None)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: est)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", lambda: db)
    monkeypatch.setattr(zap, "_coletar_subindo",
                        lambda page, **k: ([item("m0", "Ja lida", 0), item("a", "Fone", 1)], True, set()))
    monkeypatch.setattr(zap, "_coletar_novas", lambda page, vistos: ([], []))
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    monkeypatch.setattr(zap.janela_mod, "dormir_ate_proxima_rodada", parar)
    zap.captura_msg_whatsapp(["g1"], seg_grupo=0)

    assert len(enviados) == 2 and "Banco Oracle fora (DPY-4024)" in enviados[0] and "voltou" in enviados[1]
    assert csv_na_queda[0] == 0                                    # nada no CSV quando o aviso saiu
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [46100] and reg.csv[0]["DS_OFERTA"] == "Fone"
    assert est["grupos"]["g1"]["ultimo_data_id"] == "a"
    assert [s for s in sleeps if s == 60] == [60, 60]
    assert drv.conexoes and all(c.call_timeout == 30000 for c in drv.conexoes)
    assert len(drv.conexoes) >= 2                                  # houve reconexao no caminho
    assert TOKEN not in "".join(enviados)
