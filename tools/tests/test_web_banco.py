"""BSV-66 Saídas 5 e 6: SQL de "já vista", INSERT inteiro (SQL e binds) e reconexão."""

from decimal import Decimal

import pytest
from webapoio.banco import Banco, BancoFora, ErroDado, normalizar_titulo

AGORA_BRT = "CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE)"

INSERT_ESPERADO = (
    "INSERT INTO BESAVE.OFERTA_FILA_CAPTURA (DS_TIPO_ORIGEM, DS_ORIGEM, DS_TIPO_OFERTA, DT_OFERTA, DT_CAPTACAO, "
    "DS_OFERTA, VL_PRECO_DE, VL_PRECO_POR, DS_URL_ORIGEM, DS_LOJA, DS_CUPOM, DS_CUPOM_LOJA, ST_CAPTURA) "
    "VALUES ('CAPTURA WEB', :origem, 'PRODUTO', CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE), "
    "CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE), :titulo, :preco_de, :preco_por, :url, :loja, :cupom, "
    ":cupom_loja, '0') RETURNING ID_OFERTA INTO :id"
)

VISTA_COM_CHAVE = (
    "SELECT 'F', NULL FROM BESAVE.OFERTA_FILA_CAPTURA "
    "WHERE DT_OFERTA >= CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE) - 1 "
    "AND DS_URL_ORIGEM LIKE '%' || :chave || '%' "
    "UNION ALL "
    "SELECT 'O', NULL FROM BESAVE.OFERTA "
    "WHERE ST_ATIVO = 1 AND DS_URL_FINAL LIKE '%' || :chave || '%' AND VL_PRECO_POR <= :preco "
    "UNION ALL "
    "SELECT 'T', DS_OFERTA FROM BESAVE.OFERTA_FILA_CAPTURA "
    "WHERE DT_OFERTA >= CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE) - 1 "
    "AND DS_LOJA = :loja AND VL_PRECO_POR BETWEEN :pmin AND :pmax"
)
VISTA_SEM_CHAVE = (
    "SELECT 'T', DS_OFERTA FROM BESAVE.OFERTA_FILA_CAPTURA "
    "WHERE DT_OFERTA >= CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE) - 1 "
    "AND DS_LOJA = :loja AND VL_PRECO_POR BETWEEN :pmin AND :pmax"
)


class Var:
    def __init__(self, valor):
        self.valor = valor

    def getvalue(self):
        return [self.valor]


class Cursor:
    def __init__(self, conn):
        self.conn = conn

    def var(self, tipo):
        assert tipo is int
        return Var(self.conn.proximo_id)

    def execute(self, sql, binds):
        if self.conn.falhas:
            raise self.conn.falhas.pop(0)
        self.conn.executados.append((sql, binds))

    def fetchall(self):
        return list(self.conn.linhas)

    def close(self):
        pass


class Conn:
    def __init__(self, falhas=None, linhas=None):
        self.falhas = list(falhas or [])
        self.linhas = linhas or []
        self.executados = []
        self.commits = 0
        self.proximo_id = 5001
        self.fechada = False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        self.fechada = True


def _banco(conns):
    fila = list(conns)

    def conectar():
        c = fila.pop(0)
        if isinstance(c, Exception):
            raise c
        return c
    b = Banco({}, conectar=conectar, dormir=lambda s: None)
    return b


LINHA = {'origem': 'PROMOBIT', 'titulo': 'Grand Theft Auto VI - PlayStation 5', 'preco_de': Decimal('499.00'),
         'preco_por': Decimal('343.48'), 'url': 'https://www.mercadolivre.com.br/gta/p/MLB123456789',
         'loja': 'MERCADO LIVRE', 'cupom': 'LIVREOFF', 'cupom_loja': 'MERCADO LIVRE'}


def test_insert_inteiro_com_binds_e_commit():
    conn = Conn()
    b = _banco([conn])
    assert b.abrir()
    assert b.gravar(LINHA) == 5001
    (sql, binds), = conn.executados
    assert sql == INSERT_ESPERADO
    var = binds.pop('id')
    assert isinstance(var, Var)
    assert binds == LINHA
    assert conn.commits == 1


def test_ja_vista_sql_inteiro_com_chave():
    conn = Conn()
    b = _banco([conn])
    b.abrir()
    assert b.ja_vista('123456789', Decimal('100.00'), 'MERCADO LIVRE', 'GTA') is None
    (sql, binds), = conn.executados
    assert sql == VISTA_COM_CHAVE
    assert binds == {'chave': '123456789', 'preco': Decimal('100.00'), 'loja': 'MERCADO LIVRE',
                     'pmin': Decimal('99.0000'), 'pmax': Decimal('101.0000')}


def test_ja_vista_sql_inteiro_sem_chave():
    conn = Conn()
    b = _banco([conn])
    b.abrir()
    b.ja_vista(None, Decimal('10.00'), 'MERCADO LIVRE', 'X')
    (sql, binds), = conn.executados
    assert sql == VISTA_SEM_CHAVE
    assert binds == {'loja': 'MERCADO LIVRE', 'pmin': Decimal('9.9000'), 'pmax': Decimal('10.1000')}


@pytest.mark.parametrize('linhas,esperado', [
    ([('F', None)], 'vista_fila'),
    ([('O', None)], 'vista_oferta'),
    ([('T', 'Lâmpada  Inteligente, Smart-Color 10W!')], 'mesmo_titulo'),
    ([('T', 'Lampada Inteligente Smart Color 10W Elgin')], None),
    ([], None),
])
def test_ja_vista_motivos(linhas, esperado):
    b = _banco([Conn(linhas=linhas)])
    b.abrir()
    assert b.ja_vista('B0', Decimal(10), 'AMAZON', 'LAMPADA inteligente smart color 10w') == esperado


def test_normalizar_titulo():
    assert normalizar_titulo('  Óculos  Esportivo—PACE (Proteção UV400)! ') == 'oculos esportivo pace protecao uv400'


def test_reconecta_uma_vez_e_repete():
    caida = Conn(falhas=[Exception('DPY-4011: the database or network closed the connection')])
    nova = Conn()
    b = _banco([caida, nova])
    b.abrir()
    assert b.gravar(LINHA) == 5001
    assert caida.fechada
    assert len(nova.executados) == 1 and nova.commits == 1


def test_duas_quedas_banco_fora():
    b = _banco([Conn(falhas=[Exception('ORA-03113: end-of-file')]),
                Conn(falhas=[Exception('ORA-03113: end-of-file')])])
    b.abrir()
    with pytest.raises(BancoFora):
        b.gravar(LINHA)


def test_queda_e_reconexao_falha_banco_fora():
    b = _banco([Conn(falhas=[Exception('DPY-1001: not connected')]), Exception('ORA-12541'),
                Exception('ORA-12541')])
    b.abrir()
    with pytest.raises(BancoFora):
        b.ja_vista('B0', Decimal(1), 'AMAZON', 't')


def test_erro_de_dado_nao_reconecta():
    conn = Conn(falhas=[Exception('ORA-12899: value too large for column')])
    b = _banco([conn])
    b.abrir()
    with pytest.raises(ErroDado):
        b.gravar(LINHA)
    assert not conn.fechada


def test_abrir_falha_duas_vezes():
    b = _banco([Exception('ORA-12541: no listener'), Exception('ORA-12541: no listener')])
    assert b.abrir() is False
