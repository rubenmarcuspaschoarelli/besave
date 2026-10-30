"""BSV-52: os cursores diretos do robo das lojas (duplicidade, afiliados, produtos,
desativar oferta, validade) passam pela regra de reconexao do OracleDB.transacao."""

import importlib
import re
import sys
from datetime import datetime

import falsos
import pytest
from conftest import LOJAS


def _core(nome):
    # `from core import x` usaria o atributo do pacote, que sobrevive ao pop do sys.modules
    return importlib.import_module(f"core.{nome}")


DPY = "DPY-1001: not connected to database"


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 3

    def execute(self, sql, *args, **binds):
        self.conn.tentativas += 1
        if self.conn.erro and self.conn.tentativas > self.conn.ok_ate:
            raise RuntimeError(self.conn.erro)
        self.conn.escritas.append(sql)

    def __iter__(self):
        return iter(self.conn.rows)

    def close(self):
        pass


class Conn:
    """`erro` dispara a partir do execute n.o `ok_ate + 1` (padrao: ja no primeiro)."""

    def __init__(self, erro=None, rows=(), ok_ate=0):
        self.erro, self.rows, self.ok_ate = erro, list(rows), ok_ate
        self.tentativas, self.escritas, self.commits, self.rollbacks = 0, [], 0, 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

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


def _db(monkeypatch, *fila):
    oracle_db = _core("oracle_db")
    banco = Banco(*fila)
    monkeypatch.setattr(oracle_db, "oracledb", banco)
    db = oracle_db.OracleDB({"habilitado": True, "modo": "thin", "usuario": "u", "senha": "s", "host": "h"})
    assert db.conectar()
    return db, banco


@pytest.fixture(autouse=True)
def estado_limpo(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch, "oracledb")
    afiliados, produtos = _core("afiliados"), _core("produtos")
    monkeypatch.setattr(afiliados, "_afiliados", {})
    monkeypatch.setattr(afiliados, "_carregado", False)
    monkeypatch.setattr(afiliados, "_falhou", False)
    monkeypatch.setattr(afiliados, "_ultima_tentativa", None)
    monkeypatch.setattr(produtos, "_comunidades_cache", None)
    yield
    for nome in set(sys.modules) - antes:
        if nome.startswith("core") and nome != "core.janela":
            sys.modules.pop(nome, None)


# --- operacoes por modulo ----------------------------------------------------------
AGORA = datetime(2026, 10, 29, 12, 0)


def _concorrentes(db):
    duplicidade = _core("duplicidade")
    return duplicidade.oferta_mantida(db, 1, "https://www.amazon.com.br/dp/B000000001", 10.0, AGORA)


def _marcar_duplicada(db):
    duplicidade = _core("duplicidade")
    duplicidade.marcar_duplicada(db, 1, 2)


def _afiliados_carregar(db):
    afiliados = _core("afiliados")
    afiliados.carregar(db)


def _mapa(db):
    produtos = _core("produtos")
    return produtos._mapa_comunidades(db)


def _classificacao(db):
    produtos = _core("produtos")
    produtos._comunidades_cache = {"Tech": 7}
    produtos.gravar_classificacao(db, 55, [("Tech", 3)], "Feminino")


def _desativar(db):
    ofertas = _core("ofertas")
    ofertas._desativar(db, 1)


def _validade(db):
    validade = _core("validade")
    validade.desativar_vencidas(db, dias=45)


# nome, operacao, escreve?  (escreve = faz commit; leitura nao)
OPERACOES = [
    ("duplicidade_checagem", _concorrentes, False),
    ("duplicidade_marcacao", _marcar_duplicada, True),
    ("afiliados", _afiliados_carregar, False),
    ("produtos_mapa", _mapa, False),
    ("produtos_classificacao", _classificacao, True),
    ("desativar", _desativar, True),
    ("validade", _validade, True),
]
IDS = [o[0] for o in OPERACOES]


@pytest.mark.parametrize("nome,operacao,escreve", OPERACOES, ids=IDS)
def test_queda_unica_reconecta_e_a_operacao_roda_uma_vez(monkeypatch, nome, operacao, escreve):
    morta, viva = Conn(DPY), Conn()
    db, banco = _db(monkeypatch, morta, viva)
    operacao(db)
    assert banco.conexoes == 2
    assert morta.escritas == [] and morta.commits == 0
    assert len(viva.escritas) >= 1
    assert viva.commits == (1 if escreve else 0)
    # a funcao inteira roda uma unica vez na conexao nova
    assert len(viva.escritas) == viva.tentativas


def test_queda_no_meio_da_transacao_repete_a_funcao_inteira(monkeypatch):
    # classificacao = DELETE + INSERT + DELETE + INSERT; cai no 2.o: repete os 4 na conexao nova
    morta, viva = Conn(DPY, ok_ate=1), Conn()
    db, _ = _db(monkeypatch, morta, viva)
    _classificacao(db)
    assert len(morta.escritas) == 1 and morta.rollbacks == 1 and morta.commits == 0
    assert len(viva.escritas) == 4 and viva.commits == 1


@pytest.mark.parametrize("nome,operacao,escreve", OPERACOES, ids=IDS)
def test_erro_de_dado_nao_reconecta(monkeypatch, nome, operacao, escreve):
    conn = Conn("ORA-01400: cannot insert NULL")
    db, banco = _db(monkeypatch, conn)
    try:
        operacao(db)
    except Exception as e:  # noqa: BLE001 - alguns modulos engolem (best-effort)
        assert "ORA-01400" in str(e)
    assert banco.conexoes == 1 and conn.commits == 0


@pytest.mark.parametrize("nome,operacao", [(o[0], o[1]) for o in OPERACOES
                                           if o[0] in ("duplicidade_checagem", "duplicidade_marcacao",
                                                       "desativar", "validade")], ids=lambda x: x if isinstance(x, str) else "")
def test_queda_persistente_levanta_sem_conexao(monkeypatch, nome, operacao):
    ErroSemConexao = _core("oracle_db").ErroSemConexao
    db, banco = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    with pytest.raises(ErroSemConexao):
        operacao(db)
    assert banco.conexoes == 2


def test_afiliados_queda_persistente_nao_marca_carregado(monkeypatch, capsys):
    afiliados = _core("afiliados")
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    afiliados.carregar(db)
    assert afiliados._carregado is False
    assert not afiliados.loja_ativa("amazon")
    assert "cache não carregado" in capsys.readouterr().out


def test_produtos_queda_persistente_so_loga(monkeypatch, capsys):
    produtos = _core("produtos")
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    assert produtos._mapa_comunidades(db) == {}
    assert produtos._comunidades_cache is None          # sem cache: tenta de novo depois
    assert "falha ao ler COMUNIDADE" in capsys.readouterr().out
    db2, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    produtos._comunidades_cache = {"Tech": 7}
    produtos.gravar_classificacao(db2, 55, [("Tech", 3)], "Feminino")   # nao propaga
    assert "falha ao gravar PRODUTO_COMUNIDADE" in capsys.readouterr().out


def test_produtos_mapa_le_e_cacheia(monkeypatch):
    produtos = _core("produtos")
    viva = Conn(rows=[("Tech", 7)])
    db, _ = _db(monkeypatch, viva)
    assert produtos._mapa_comunidades(db) == {"Tech": 7}
    assert produtos._mapa_comunidades(db) == {"Tech": 7}
    assert viva.tentativas == 1


def test_validade_queda_persistente_na_varredura_so_loga(lojas, monkeypatch, capsys):
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    monkeypatch.setattr(lojas.estado, "ler_validade_ofertas", lambda: 45)
    lojas._varrer_validade(db)                  # nao propaga
    assert "[validade] falhou" in capsys.readouterr().out


def test_desativar_vencida_com_queda_persistente_nao_derruba_a_publicacao(monkeypatch, capsys):
    ofertas = _core("ofertas")
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    linha = {"DT_OFERTA": datetime(2020, 1, 1), "VL_PRECO_POR": 10.0}
    assert ofertas.publicar_oferta(db, 1, 9, "Amazon", linha) == (False, "vencida")
    assert "desativando vencida" in capsys.readouterr().out


# --- afiliados: retentativa ------------------------------------------------------
def test_afiliados_retenta_no_maximo_uma_vez_por_minuto(monkeypatch):
    afiliados = _core("afiliados")
    t = [1000.0]
    monkeypatch.setattr(afiliados, "_relogio", lambda: t[0])
    db, banco = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"),
                    RuntimeError("rede fora"), Conn(rows=[("AMAZON", " tag ", "ref")]))
    afiliados.carregar(db)                       # arranque: falha
    assert banco.conexoes == 2                   # conexao inicial + 1 tentativa de reconectar
    conexoes = banco.conexoes
    t[0] += 59
    assert afiliados.garantir_carregado(db) is False
    assert banco.conexoes == conexoes            # dentro do minuto: nem encosta no banco
    t[0] += 2
    assert afiliados.garantir_carregado(db) is False      # 61 s: tenta, banco ainda fora
    assert banco.conexoes > conexoes
    t[0] += 61
    assert afiliados.garantir_carregado(db) is True       # banco voltou
    assert afiliados._afiliados["amazon"]["id_afiliado"] == "tag"
    assert afiliados.garantir_carregado(db) is True


def test_afiliados_log_uma_vez_por_ocorrencia_e_avisa_a_volta(monkeypatch, capsys):
    afiliados = _core("afiliados")
    t = [0.0]
    monkeypatch.setattr(afiliados, "_relogio", lambda: t[0])
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("x"), RuntimeError("x"), RuntimeError("x"),
                Conn(rows=[("SHOPEE", "a", "b")]))
    afiliados.carregar(db)
    for _ in range(2):
        t[0] += 61
        afiliados.garantir_carregado(db)
    out = capsys.readouterr().out
    assert out.count("cache não carregado") == 1
    t[0] += 61
    assert afiliados.garantir_carregado(db)
    assert "cache carregado (banco voltou)" in capsys.readouterr().out


def test_afiliados_falha_na_recarga_nao_zera_cache_carregado(monkeypatch):
    afiliados = _core("afiliados")
    db, _ = _db(monkeypatch, Conn(rows=[("AMAZON", "tag", "ref")]))
    afiliados.carregar(db)
    assert afiliados.loja_ativa("amazon")
    assert afiliados.garantir_carregado(db) is True


# --- integracao com o laco da captura --------------------------------------------
class Pagina:
    url = "https://loja.exemplo/produto"

    def wait_for_timeout(self, ms):
        pass


def _linhas(*ids):
    return [{"ID_OFERTA": i, "url": "https://loja.exemplo/p", "numero_da_captura": str(i),
             "DS_ORIGEM": "g"} for i in ids]


def _preparar_publicacao(lojas, monkeypatch, db):
    """Captura sempre ok; produto cadastrado; so a publicacao em OFERTA e real."""
    publicadas = []
    db.atualizar_captura = lambda *a, **k: (True, None)
    db.buscar_para_produto = lambda i: {"x": 1}
    db.buscar_para_cupom = lambda i: None
    db.buscar_para_oferta = lambda i: {"DT_OFERTA": datetime.now(), "VL_PRECO_POR": 10.0,
                                       "DS_URL_FINAL": "https://www.amazon.com.br/dp/B000000001"}

    def sp(nome, params, outs, clob_params=None):
        publicadas.append(params["P_ID_OFERTA"])
        return {"PV_RETORNO": "TRUE"}
    db.executar_stored_procedure = sp
    monkeypatch.setattr(lojas.produtos, "cadastrar_produto", lambda d, i, l: (10, {}, None))
    monkeypatch.setattr(lojas.imagens_produto, "publicar_imagens_produto", lambda *a: 0)
    monkeypatch.setattr(lojas.afiliados, "loja_ativa", lambda *a: True)
    return publicadas


def test_duplicidade_com_queda_persistente_nao_publica_e_trava_o_ponteiro(lojas, monkeypatch):
    # linha ok = 2 execute (checagem + concorrentes a desativar); a conexao morre no 3.o
    # (checagem da 101) e a reconexao falha
    c1 = Conn(DPY, ok_ate=2)
    db, _ = _db(monkeypatch, c1, RuntimeError("rede fora"), Conn())
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda d: True)
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(100, 101, 102), db, True, "img", adiados)
    assert publicadas == [100, 102]            # a repostagem possivel (101) NAO e publicada
    assert adiados == {101}
    assert lojas.ponteiro == [100]             # 102 foi publicada, mas o ponteiro fica antes da 101


def test_duplicidade_com_queda_unica_publica_normalmente(lojas, monkeypatch):
    db, _ = _db(monkeypatch, Conn(DPY, ok_ate=2), Conn())
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda d: True)
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(100, 101), db, True, "img", adiados)
    assert publicadas == [100, 101] and not adiados
    assert lojas.ponteiro == [100, 101]


def test_duplicidade_erro_que_nao_e_de_conexao_continua_publicando(lojas, monkeypatch):
    db, banco = _db(monkeypatch, Conn("ORA-00942: table or view does not exist"))
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda d: True)
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(100), db, True, "img", adiados)
    assert publicadas == [100] and not adiados and banco.conexoes == 1


def test_afiliados_fora_no_arranque_trava_e_volta_depois(lojas, monkeypatch):
    afiliados = _core("afiliados")
    t = [0.0]
    monkeypatch.setattr(afiliados, "_relogio", lambda: t[0])
    # conexoes: 1) inicial, que morre na leitura do arranque; 2) reconexao falha; 3) e 4) ainda fora
    # (uma por linha antes do minuto: cada linha so le o banco se o intervalo passou); 5) volta
    voltou = Conn(rows=[("AMAZON", "tag", "ref")])
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("fora"), voltou)
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    monkeypatch.setattr(lojas.afiliados, "loja_ativa", lambda *a: True)
    afiliados.carregar(db)
    assert not afiliados._carregado

    adiados = set()
    t[0] += 10
    lojas._processar_lote(Pagina(), _linhas(200, 201), db, True, "img", adiados)
    assert publicadas == [] and adiados == {200, 201}        # dentro do minuto: nada publicado
    assert lojas.ponteiro == []

    t[0] += 61                                               # passou o minuto, banco voltou
    lojas._processar_lote(Pagina(), _linhas(202, 203), db, True, "img", adiados)
    assert publicadas == [202, 203]
    assert lojas.ponteiro == []                              # nunca pula 200/201


# --- varredura: nada de db._conn fora do OracleDB ----------------------------------
def test_nenhum_acesso_a_db_conn_fora_do_oracle_db():
    alvos = [p for p in (LOJAS / "core").glob("*.py") if p.name != "oracle_db.py"] + [LOJAS / "main.py"]
    achados = [f"{p.name}:{n}" for p in alvos
               for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if re.search(r"\._conn\b", linha)]
    assert achados == []
