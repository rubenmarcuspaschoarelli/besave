"""BSV-63: fila no Oracle (SQL, troca de estado guardada, reconexao), avisos redigidos e batimento."""
import json
from datetime import UTC, datetime

import pytest
from pub import avisos, batimento, fila

TOKEN = "123456789:AAFakeTokenParaTesteNaoEReal_abcdefghij"
CHAT = "-1001234567890"


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0
        self._linhas = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, binds):
        self.conn.execucoes.append((sql, binds))
        if self.conn.falhas:
            raise self.conn.falhas.pop(0)
        r = self.conn.responder(sql, binds)
        self._linhas = r if isinstance(r, list) else []
        self.rowcount = r if isinstance(r, int) else len(self._linhas)

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def fetchall(self):
        return list(self._linhas)


class Conn:
    def __init__(self, responder, falhas=None):
        self.responder = responder
        self.falhas = list(falhas or [])
        self.execucoes = []
        self.commits = 0
        self.fechada = False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        self.fechada = True


def test_pendentes_so_p_do_canal_com_st_ativo_da_oferta():
    dt = datetime(2026, 11, 16, 10, 0)
    conn = Conn(lambda sql, b: [(1, 501, "*t*\n\nx", "elas", dt, 1), (2, 502, "*u*", "pets", dt, 0)])
    linhas = fila.Fila(lambda: conn).pendentes(2)
    sql, binds = conn.execucoes[0]
    assert "e.ST_ENVIO = 'P'" in sql and "e.ID_CANAL = :1" in sql and "LEFT JOIN OFERTA" in sql
    assert binds == [2]
    assert [(x.id_envio, x.id_oferta, x.ativa, x.area_slug) for x in linhas] == [(1, 501, True, "elas"),
                                                                               (2, 502, False, "pets")]
    assert linhas[0].legenda == "*t*\n\nx"


def test_enviados_do_dia_contam_e_e_d():
    conn = Conn(lambda sql, b: [(7,)])
    inicio = datetime(2026, 11, 16, 0, 0)
    assert fila.Fila(lambda: conn).enviados_desde(2, inicio) == 7
    sql, binds = conn.execucoes[0]
    assert "ST_ENVIO IN ('E', 'D')" in sql and "DT_ENVIO >= :2" in sql and binds == [2, inicio]


def test_marcar_e_guardado_pelo_estado_de_origem_e_commita():
    conn = Conn(lambda sql, b: 0)                       # a linha ja nao estava em P
    f = fila.Fila(lambda: conn)
    assert f.marcar(9, "P", "D", "enviando", datetime(2026, 11, 16, 10, 0)) is False
    sql, binds = conn.execucoes[0]
    assert "AND ST_ENVIO = :de" in sql
    assert binds == {"para": "D", "motivo": "enviando", "dt": datetime(2026, 11, 16, 10, 0), "id": 9, "de": "P"}
    conn.responder = lambda sql, b: 1
    assert f.marcar(9, "P", "D", "enviando", None) is True and conn.commits == 2


def test_parametros_e_nome_do_canal():
    def resp(sql, b):
        return [(40, 8, 22)] if "PARAMETROS_ENVIO" in sql else [("Canal X",)]
    f = fila.Fila(lambda: Conn(resp))
    p = f.parametros(2)
    assert (p.qt_max_dia, p.hora_inicio, p.hora_fim) == (40, 8, 22)
    assert f.nome_canal(2) == "Canal X"


def test_erro_de_conexao_reconecta_uma_vez_e_repete():
    conns = [Conn(lambda s, b: [(1,)], falhas=[Exception("DPY-4011: the database or network closed the connection")]),
             Conn(lambda s, b: [(3,)])]
    abertas = []

    def conectar():
        abertas.append(conns[len(abertas)])
        return abertas[-1]

    assert fila.Fila(conectar, log=lambda s: None).enviados_desde(2, datetime(2026, 11, 16)) == 3
    assert len(abertas) == 2 and conns[0].fechada


def test_erro_que_nao_e_de_conexao_vira_erro_banco_so_com_o_codigo():
    conn = Conn(lambda s, b: [], falhas=[Exception("ORA-00942: table or view does not exist host=segredo.interno")])
    with pytest.raises(fila.ErroBanco) as e:
        fila.Fila(lambda: conn).pendentes(2)
    assert str(e.value) == "ORA-00942"


def test_conexao_que_cai_duas_vezes_vira_erro_banco():
    def conectar():
        return Conn(lambda s, b: [], falhas=[Exception("DPY-1001: not connected")])
    with pytest.raises(fila.ErroBanco):
        fila.Fila(conectar, log=lambda s: None).pendentes(2)


# --- avisos ------------------------------------------------------------------------------------------


def test_aviso_redige_token_e_url_e_falha_do_telegram_nao_derruba():
    saida, enviados = [], []
    a = avisos.Avisador(TOKEN, CHAT, enviar=enviados.append, log=saida.append)
    a(f"erro {TOKEN} em https://api.telegram.org/bot{TOKEN}/x chat {CHAT}")
    assert TOKEN not in enviados[0] and CHAT not in enviados[0] and "https://" not in enviados[0]

    def quebra(texto):
        raise OSError(f"https://api.telegram.org/bot{TOKEN}/sendMessage")
    b = avisos.Avisador(TOKEN, CHAT, enviar=quebra, log=saida.append)
    b("oi")
    assert any("OSError" in s for s in saida) and not any(TOKEN in s for s in saida)


def test_credenciais_do_ambiente_ou_do_worker_env(tmp_path):
    arq = tmp_path / "worker.env"
    arq.write_text(f"export TELEGRAM_BOT_TOKEN='{TOKEN}'\nTELEGRAM_CHAT_ID={CHAT}\n", encoding="utf-8")
    assert avisos.credenciais({"BESAVE_WORKER_ENV": str(arq)}) == (TOKEN, CHAT)
    assert avisos.credenciais({"TELEGRAM_BOT_TOKEN": "a", "TELEGRAM_CHAT_ID": "b",
                               "BESAVE_WORKER_ENV": str(arq)}) == ("a", "b")
    assert avisos.credenciais({"BESAVE_WORKER_ENV": str(tmp_path / "nao")}) == ("", "")


# --- batimento ---------------------------------------------------------------------------------------


def test_bat01_formato_da_bsv57(tmp_path):
    b = batimento.Batimento(tmp_path / "conf" / "batimento.json", pid=42)
    assert b.bater(datetime(2026, 11, 16, 13, 0, tzinfo=UTC), "volta", dorme_s=900)
    d = json.loads((tmp_path / "conf" / "batimento.json").read_text(encoding="utf-8"))
    assert d == {"robo": "publicador", "pid": 42, "em": "2026-11-16T13:00:00Z", "prazo": "2026-11-16T13:25:00Z",
                 "fase": "volta"}
