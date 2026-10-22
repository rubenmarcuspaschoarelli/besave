"""Reconexao do OracleDB do WhatsApp: cai e volta, tenta uma vez, e o log diz "sem conexão"."""
import sys
import types

import falsos
import pytest


class Var:
    def getvalue(self):
        return "TRUE"


class Cursor:
    def __init__(self, conn):
        self.conn = conn

    def var(self, tipo, tam):
        return Var()

    def execute(self, sql, binds=None):
        if self.conn.erro:
            raise RuntimeError(self.conn.erro)
        self.conn.execucoes += 1

    def fetchone(self):
        return [1]

    def close(self):
        pass


class Conn:
    def __init__(self, erro=None):
        self.erro = erro      # mensagem lancada em todo execute; None = saudavel
        self.execucoes = 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Banco:
    """oracledb falso: cada connect() entrega a proxima conexao da fila (ou levanta)."""

    DB_TYPE_VARCHAR = "VARCHAR"

    def __init__(self, *fila):
        self.fila = list(fila)
        self.conexoes = 0

    def connect(self, **kw):
        self.conexoes += 1
        item = self.fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def makedsn(self, *a, **kw):
        return "dsn"

    def init_oracle_client(self, **kw):
        pass


LINHA = {"ID_OFERTA": "7", "DS_OFERTA": "x"}
CFG = {"habilitado": True, "modo": "thin", "usuario": "u", "senha": "s", "host": "h"}


@pytest.fixture
def novo(monkeypatch):
    falsos.instalar(monkeypatch)
    from wa import oracle_db

    def criar(*fila):
        banco = Banco(*fila)
        monkeypatch.setattr(oracle_db, "oracledb", banco)
        db = oracle_db.OracleDB(dict(CFG))
        assert db.conectar()
        return db, banco
    yield criar
    sys.modules.pop("wa.oracle_db", None)


def test_conexao_cai_e_volta(novo):
    velha, nova = Conn("DPY-1001: not connected to database"), Conn()
    db, banco = novo(velha, nova)
    assert db.inserir_oferta(LINHA) is True
    assert banco.conexoes == 2 and nova.execucoes == 1
    assert db.sem_conexao is False


def test_reconexao_falha_vira_sem_conexao_e_proxima_oferta_tenta_de_novo(novo):
    db, _ = novo(Conn("ORA-03113: end-of-file"), RuntimeError("rede fora"), Conn())
    assert db.inserir_oferta(LINHA) is False
    assert db.sem_conexao is True
    assert db.habilitado is True          # nao desliga o banco pelo resto da noite
    assert db.inserir_oferta(LINHA) is True
    assert db.sem_conexao is False


def test_segunda_tentativa_tambem_cai(novo):
    db, banco = novo(Conn("DPY-1001: x"), Conn("DPY-1001: x"))
    assert db.inserir_oferta(LINHA) is False
    assert db.sem_conexao is True
    assert banco.conexoes == 2            # uma repeticao so, sem laco


def test_erro_de_dados_nao_reconecta(novo):
    db, banco = novo(Conn("ORA-01400: cannot insert NULL"))
    assert db.inserir_oferta(LINHA) is False
    assert banco.conexoes == 1
    assert db.sem_conexao is False


@pytest.mark.parametrize("codigo", ["DPY-1001", "DPI-1010", "ORA-03113", "ORA-03114", "ORA-03135"])
def test_codigos_de_conexao(novo, codigo):
    db, banco = novo(Conn(f"{codigo}: queda"), Conn())
    assert db.inserir_oferta(LINHA) is True
    assert banco.conexoes == 2


def test_sp_generica_tambem_reconecta(novo):
    db, banco = novo(Conn("ORA-03114: not connected"), Conn())
    out = db.executar_stored_procedure("SP", {"P": 1}, {"PV_RETORNO": "VARCHAR"})
    assert out == {"PV_RETORNO": "TRUE"} and banco.conexoes == 2


def test_marca_do_log(monkeypatch):
    falsos.instalar(monkeypatch)
    from wa import monitor
    sem = types.SimpleNamespace(sem_conexao=True)
    com = types.SimpleNamespace(sem_conexao=False)
    assert monitor._marca_db(None, com) == ""
    assert monitor._marca_db(True, com) == " | db=ok"
    assert monitor._marca_db(False, com) == " | db=ERRO"
    assert monitor._marca_db(False, sem) == " | db=ERRO (sem conexão)"
    sys.modules.pop("wa.monitor", None)
