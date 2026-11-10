"""BSV-56 SEQ-04: proximo_id() vem do NEXTVAL; queda reconecta uma vez; falha nunca devolve numero."""
import sys

import falsos
import pytest
from test_reconexao_oracle import CFG, Banco


class Sequence:
    def __init__(self, inicio):
        self.valor = inicio - 1
        self.pedidos = []

    def nextval(self):
        self.valor += 1
        return self.valor


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.linha = None

    def execute(self, sql, binds=None, **kw):
        if self.conn.erro:
            raise RuntimeError(self.conn.erro)
        self.conn.sqls.append(sql)
        if "NEXTVAL" in sql.upper():
            self.linha = [self.conn.seq.nextval()]
        elif "DUAL" in sql.upper():
            self.linha = [1]
        else:  # dicionario (user_arguments)
            self.linha = [0]

    def fetchone(self):
        return self.linha

    def close(self):
        pass


class Conn:
    def __init__(self, seq, erro=None):
        self.seq = seq
        self.erro = erro
        self.sqls = []

    def cursor(self):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def novo(monkeypatch):
    falsos.instalar(monkeypatch)
    from wa import oracle_db

    def criar(*fila, cfg=None):
        banco = Banco(*fila)
        monkeypatch.setattr(oracle_db, "oracledb", banco)
        db = oracle_db.OracleDB(dict(cfg or CFG))
        db.conectar()
        return db, banco, oracle_db
    yield criar
    sys.modules.pop("wa.oracle_db", None)


def test_ids_seguidos_vem_do_nextval(novo):
    seq = Sequence(46100)
    conn = Conn(seq)
    db, _, _ = novo(conn)
    assert [db.proximo_id(), db.proximo_id()] == [46100, 46101]
    assert sum("SQ_OFERTA_FILA.NEXTVAL" in s.upper() for s in conn.sqls) == 2


def test_queda_reconecta_uma_vez_e_segue_a_sequence(novo):
    seq = Sequence(500)
    db, banco, _ = novo(Conn(seq, "DPY-1001: not connected"), Conn(seq))
    assert db.proximo_id() == 500
    assert banco.conexoes == 2


def test_reconexao_falha_levanta_sem_numero(novo):
    seq = Sequence(500)
    db, banco, oracle_db = novo(Conn(seq, "ORA-03113: end-of-file on communication channel host-x"),
                                RuntimeError("DPY-6005: rede fora"))
    with pytest.raises(oracle_db.ErroSemId) as e:
        db.proximo_id()
    assert banco.conexoes == 2            # uma repeticao so
    assert seq.valor == 499               # nenhum numero consumido nem inventado
    assert "host-x" not in str(e.value)


def test_segunda_queda_tambem_levanta(novo):
    seq = Sequence(1)
    db, banco, oracle_db = novo(Conn(seq, "DPY-1001: x"), Conn(seq, "DPY-1001: x"))
    with pytest.raises(oracle_db.ErroSemId) as e:
        db.proximo_id()
    assert banco.conexoes == 2
    assert str(e.value) == "DPY-1001"


def test_sequence_ausente_levanta_sem_reconectar(novo):
    db, banco, oracle_db = novo(Conn(Sequence(1), "ORA-02289: sequence does not exist"))
    with pytest.raises(oracle_db.ErroSemId) as e:
        db.proximo_id()
    assert banco.conexoes == 1
    assert str(e.value) == "ORA-02289"


def test_partida_sem_banco_reconecta_no_primeiro_id(novo):
    seq = Sequence(70)
    db, banco, _ = novo(RuntimeError("ORA-12541: no listener"), Conn(seq))
    assert db.proximo_id() == 70          # conectar() falhou na partida; o id tenta de novo
    assert banco.conexoes == 2


def test_desligado_no_config_levanta(novo):
    db, banco, oracle_db = novo(cfg={**CFG, "habilitado": False})
    assert db.configurado is False
    with pytest.raises(oracle_db.ErroSemId):
        db.proximo_id()
    assert banco.conexoes == 0


def test_disponivel_nao_gasta_numero(novo):
    seq = Sequence(10)
    db, _, _ = novo(Conn(seq))
    assert db.disponivel() is True
    assert seq.valor == 9


def test_disponivel_falso_com_banco_fora_e_verdadeiro_ao_voltar(novo):
    seq = Sequence(10)
    db, _, _ = novo(Conn(seq, "DPY-1001: x"), RuntimeError("ORA-12541"), Conn(seq))
    assert db.disponivel() is False
    assert db.disponivel() is True
    assert db.proximo_id() == 10


@pytest.mark.parametrize("valor, esperado", [(None, 60), (5, 5), (0, 60), ("x", 60), (-1, 60)])
def test_espera_segundos(novo, valor, esperado):
    cfg = dict(CFG)
    if valor is not None:
        cfg["espera_segundos"] = valor
    db, _, _ = novo(Conn(Sequence(1)), cfg=cfg)
    assert db.espera_segundos == esperado


def test_ids_entregues_conta_so_numero_de_verdade(novo):
    # o "voltou" do monitor depende deste contador (BSV-56, FORA-02)
    seq = Sequence(10)
    db, _, oracle_db = novo(Conn(seq), Conn(seq, "ORA-02289: sequence does not exist"),
                            RuntimeError("DPY-6005"), Conn(seq))
    assert db.ids_entregues == 0
    assert db.proximo_id() == 10 and db.ids_entregues == 1
    assert db.disponivel() is True and db.ids_entregues == 1          # SELECT 1 nao conta
    db._conn = Conn(seq, "DPY-1001: x")                                  # cai; reconexao pega a fila
    with pytest.raises(oracle_db.ErroSemId):
        db.proximo_id()                                                  # ORA-02289 na nova conexao
    assert db.ids_entregues == 1                                         # falha nao conta
    db._conn = Conn(seq, "DPY-1001: x")
    with pytest.raises(oracle_db.ErroSemId):
        db.proximo_id()                                                  # reconexao falha
    assert db.ids_entregues == 1
    db._conn = Conn(seq, "DPY-1001: x")
    assert db.proximo_id() == 11 and db.ids_entregues == 2              # id depois de reconectar conta
