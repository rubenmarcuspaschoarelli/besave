"""Lojas: a conexao Oracle cai durante a gravacao. A linha e regravada depois da volta
e o ponteiro de retomada nunca passa de uma linha nao gravada (perda de 38132-38136, 21/10)."""
import sys

import falsos
import pytest
from conftest import LOJAS


class Var:
    def getvalue(self):
        return "TRUE"


class Cursor:
    def __init__(self, conn):
        self.conn = conn

    def var(self, tipo, tam):
        return Var()

    def setinputsizes(self, **kw):
        pass

    def execute(self, sql, binds=None):
        id_oferta = (binds or {}).get("P_ID_OFERTA")
        if id_oferta in self.conn.cai_em:
            self.conn.cai_em.discard(id_oferta)
            raise RuntimeError("DPY-1001: not connected to database")
        self.conn.gravados.append(id_oferta)

    def close(self):
        pass


class Conn:
    def __init__(self, cai_em=()):
        self.cai_em = set(cai_em)
        self.gravados = []

    def cursor(self):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Banco:
    DB_TYPE_VARCHAR = "VARCHAR"
    DB_TYPE_CLOB = "CLOB"

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


class Loja:
    ready_selector = None
    post_load_wait = 0
    baixar_imagens = False

    def prepare(self, page):
        pass

    def pagina_sem_produto(self, page):
        return False

    def status_descarte(self, page):
        return None

    def capture(self, page):
        return {}


class Pagina:
    url = "https://loja.exemplo/produto"

    def wait_for_timeout(self, ms):
        pass


@pytest.fixture
def lojas(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from core import estado
    monkeypatch.setattr(estado, "ler_raiz_s3", lambda *a, **k: "/s3-falso")
    mod = falsos.importar(monkeypatch, "main_lojas", LOJAS / "main.py")
    for nome, valor in [("resolver_loja", lambda url: "AMAZON"), ("get_store", lambda loja: Loja()),
                        ("loja_ativa", lambda *a: True)]:
        monkeypatch.setattr(mod.registry, nome, valor)
    monkeypatch.setattr(mod, "_goto_robusto", lambda *a, **k: None)
    monkeypatch.setattr(mod.afiliados, "gerar_url", lambda *a: "")
    monkeypatch.setattr(mod.afiliados, "loja_ativa", lambda *a: False)
    monkeypatch.setattr(mod.link_afiliado, "capturar", lambda *a: {})
    monkeypatch.setattr(mod.link_afiliado, "habilitado", lambda: False)
    monkeypatch.setattr(mod.imagens_oferta, "tem_imagem_publicada", lambda i: True)
    monkeypatch.setattr(mod.estado, "usa_imagem_loja", lambda g: False)
    mod.ponteiro = []
    monkeypatch.setattr(mod.estado, "gravar_ultimo_id", mod.ponteiro.append)
    yield mod
    for nome in set(sys.modules) - antes:
        if nome != "core.janela":
            sys.modules.pop(nome, None)


def _db(monkeypatch, *fila):
    from core import oracle_db
    banco = Banco(*fila)
    monkeypatch.setattr(oracle_db, "oracledb", banco)
    db = oracle_db.OracleDB({"habilitado": True, "modo": "thin", "usuario": "u", "senha": "s", "host": "h"})
    assert db.conectar()
    db.buscar_para_produto = lambda i: None   # etapas posteriores, fora deste teste
    db.buscar_para_cupom = lambda i: None
    return db, banco


def _linhas(*ids):
    return [{"ID_OFERTA": i, "url": "https://loja.exemplo/p", "numero_da_captura": str(i),
             "DS_ORIGEM": "g"} for i in ids]


def test_conexao_cai_durante_a_gravacao_e_a_linha_e_regravada(lojas, monkeypatch):
    morre = Conn(cai_em={38133})
    volta = Conn()
    db, _ = _db(monkeypatch, morre, volta)
    adiados = set()
    _, gravadas, _ = lojas._processar_lote(Pagina(), _linhas(38132, 38133, 38134), db, True, "img", adiados)
    assert gravadas == 3 and not adiados
    assert morre.gravados == [38132] and volta.gravados == [38133, 38134]
    assert lojas.ponteiro == [38132, 38133, 38134]


def test_ponteiro_nao_passa_da_linha_nao_gravada(lojas, monkeypatch):
    # 38133 cai e a reconexao falha; 38134 ja encontra o banco de volta
    db, _ = _db(monkeypatch, Conn(cai_em={38133}), RuntimeError("rede fora"), Conn())
    adiados = set()
    _, gravadas, _ = lojas._processar_lote(Pagina(), _linhas(38132, 38133, 38134, 38135), db, True, "img", adiados)
    assert gravadas == 3
    assert adiados == {38133}
    assert lojas.ponteiro == [38132]       # 38134 e 38135 gravadas, mas o ponteiro fica antes da 38133


def test_ponteiro_continua_travado_no_lote_seguinte(lojas, monkeypatch):
    db, _ = _db(monkeypatch, Conn(cai_em={38133}), RuntimeError("rede fora"), Conn())
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(38132, 38133), db, True, "img", adiados)
    lojas._processar_lote(Pagina(), _linhas(38136), db, True, "img", adiados)
    assert lojas.ponteiro == [38132]


def test_loja_nao_implementada_tambem_trava_o_ponteiro(lojas, monkeypatch):
    db, _ = _db(monkeypatch, Conn())
    lojas_antes = lojas.registry.get_store
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: None)
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(38133), db, True, "img", adiados)
    monkeypatch.setattr(lojas.registry, "get_store", lojas_antes)
    lojas._processar_lote(Pagina(), _linhas(38134), db, True, "img", adiados)
    assert adiados == {38133} and lojas.ponteiro == []


def test_erro_de_dado_nao_reconecta(lojas, monkeypatch):
    class ConnDado(Conn):
        def cursor(self):
            c = Cursor(self)
            c.execute = lambda sql, binds=None: (_ for _ in ()).throw(RuntimeError("ORA-01400: cannot insert NULL"))
            return c
    db, banco = _db(monkeypatch, ConnDado())
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(38132), db, True, "img", adiados)
    assert banco.conexoes == 1 and adiados == {38132} and lojas.ponteiro == []


class CursorFila:
    description = (("ID_OFERTA",),)

    def __init__(self, morta):
        self.morta = morta

    def execute(self, sql, binds=None):
        if self.morta:
            raise RuntimeError("ORA-03113: end-of-file")

    def __iter__(self):
        return iter([(7,)])

    def close(self):
        pass


def test_leitura_da_fila_tambem_reconecta(lojas, monkeypatch):
    morta, viva = Conn(), Conn()
    morta.cursor = lambda: CursorFila(True)
    viva.cursor = lambda: CursorFila(False)
    db, banco = _db(monkeypatch, morta, viva)
    assert db.ler_fila() == [{"ID_OFERTA": 7}]
    assert banco.conexoes == 2
