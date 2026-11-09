"""BSV-52 (decisao do dono): linha capturada ('1') cuja publicacao falhou por falta de conexao
(duplicidade) ou de cache de afiliados fica numa lista persistida e volta sozinha para a fila ('0')."""

import json
from datetime import datetime

from test_reconexao_cursores import (  # noqa: F401 - estado_limpo e fixture autouse
    DPY,
    Conn,
    Pagina,
    _core,
    _db,
    _linhas,
    _preparar_publicacao,
    estado_limpo,
)


def _devolveu(conn):
    return [s for s in conn.escritas if "ST_CAPTURA = '0'" in s]


def _sem_afiliados_fora(lojas, monkeypatch):
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda d: True)


def test_queda_entre_gravacao_e_publicacao_e_publicada_uma_vez_na_volta_seguinte(lojas, monkeypatch):
    volta = Conn()
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"), volta)
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    _sem_afiliados_fora(lojas, monkeypatch)
    adiados = set()

    lojas._processar_lote(Pagina(), _linhas(100), db, True, "img", adiados)
    assert publicadas == [] and lojas.pendentes == [100]
    assert lojas.ponteiro == [] and adiados == {100}

    lojas._recuperar_publicacoes(db, adiados)            # volta seguinte do monitor, banco de volta
    assert lojas.pendentes == [] and adiados == set()
    assert len(_devolveu(volta)) == 1

    lojas._processar_lote(Pagina(), _linhas(100), db, True, "img", adiados)   # a fila a le de novo
    assert publicadas == [100]
    assert lojas.ponteiro == [100]


def test_reinicio_do_processo_no_meio_publica_depois(lojas, monkeypatch):
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"))
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas._processar_lote(Pagina(), _linhas(100, 101), db, True, "img", set())
    assert publicadas == [] and lojas.pendentes == [100, 101]
    persistido = list(lojas.pendentes)          # o que o config.json guardou

    # reinicio: processo novo, conexao nova, adiados vazio, so a lista persistida sobrevive
    lojas.pendentes[:] = persistido
    db2, _ = _db(monkeypatch, Conn())
    publicadas2 = _preparar_publicacao(lojas, monkeypatch, db2)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas._recuperar_publicacoes(db2, set())
    assert lojas.pendentes == []
    lojas._processar_lote(Pagina(), _linhas(100, 101), db2, True, "img", set())
    assert publicadas2 == [100, 101] and lojas.ponteiro == [100, 101]


def test_cache_de_afiliados_fora_deixa_pendentes_e_publica_todas_quando_volta(lojas, monkeypatch):
    afiliados = _core("afiliados")
    t = [0.0]
    monkeypatch.setattr(afiliados, "_relogio", lambda: t[0])
    voltou = Conn(rows=[("AMAZON", "tag", "ref")])
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("fora"), voltou)
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    afiliados.carregar(db)
    assert not afiliados._carregado

    t[0] += 10
    lojas._processar_lote(Pagina(), _linhas(200, 201, 202), db, True, "img", set())
    assert publicadas == [] and lojas.pendentes == [200, 201, 202] and lojas.ponteiro == []

    adiados = {200}
    lojas._recuperar_publicacoes(db, adiados)            # ainda dentro do minuto: nada volta
    assert lojas.pendentes == [200, 201, 202] and not _devolveu(voltou)

    t[0] += 61                                           # banco voltou, cache carrega
    lojas._recuperar_publicacoes(db, adiados)
    assert lojas.pendentes == [] and adiados == set()
    assert len(_devolveu(voltou)) == 3
    lojas._processar_lote(Pagina(), _linhas(200, 201, 202), db, True, "img", set())
    assert publicadas == [200, 201, 202]                 # nenhuma pulada
    assert lojas.ponteiro == [200, 201, 202]


def test_duplicada_de_verdade_continua_nao_publicada_depois_da_recuperacao(lojas, monkeypatch):
    mais_barata = [(7, 5.0, datetime.now(), "https://www.amazon.com.br/dp/B000000001", 10)]
    c2 = Conn(rows=mais_barata)
    db, _ = _db(monkeypatch, Conn(DPY), RuntimeError("rede fora"), c2)
    publicadas = _preparar_publicacao(lojas, monkeypatch, db)
    _sem_afiliados_fora(lojas, monkeypatch)
    adiados = set()
    lojas._processar_lote(Pagina(), _linhas(100), db, True, "img", adiados)
    assert lojas.pendentes == [100]

    lojas._recuperar_publicacoes(db, adiados)
    lojas._processar_lote(Pagina(), _linhas(100), db, True, "img", adiados)
    assert publicadas == [] and lojas.pendentes == []
    marcas = [s for s in c2.escritas if "ST_CAPTURA" in s]
    assert "ST_CAPTURA = '0'" in marcas[0] and "ST_CAPTURA = '9'" in marcas[-1]
    assert len(marcas) == 2                              # devolvida uma vez, marcada '9' uma vez


def test_causa_que_continua_mantem_o_id_na_lista_sem_laco(lojas, monkeypatch):
    db, banco = _db(monkeypatch, Conn(DPY), RuntimeError("fora"), RuntimeError("fora"), RuntimeError("fora"))
    _preparar_publicacao(lojas, monkeypatch, db)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas.pendentes[:] = [100, 101]
    lojas._recuperar_publicacoes(db, set())              # 1 volta = 1 tentativa de reconexao
    assert lojas.pendentes == [100, 101]
    assert banco.conexoes <= 3


def test_ponteiro_nao_passa_do_menor_id_pendente_nem_apos_reinicio(lojas, monkeypatch):
    db, _ = _db(monkeypatch, Conn())
    _preparar_publicacao(lojas, monkeypatch, db)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas.pendentes[:] = [101]                           # veio do config.json
    lojas._processar_lote(Pagina(), _linhas(100, 102, 103), db, True, "img", set())
    assert lojas.ponteiro == [100]


def test_lista_persiste_no_config_json(tmp_path):
    estado = _core("estado")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"controle": {"ultimo_id_processado": 9}, "outro": 1}), encoding="utf-8")
    estado.adicionar_publicacao_pendente(30, caminho=str(cfg))
    estado.adicionar_publicacao_pendente(10, caminho=str(cfg))
    estado.adicionar_publicacao_pendente(30, caminho=str(cfg))
    assert estado.ler_publicacao_pendente(str(cfg)) == [10, 30]
    estado.gravar_ultimo_id(11, caminho=str(cfg))
    dados = json.loads(cfg.read_text(encoding="utf-8"))
    assert dados["controle"] == {"ultimo_id_processado": 11, "publicacao_pendente": [10, 30]}
    assert dados["outro"] == 1
    estado.gravar_publicacao_pendente([], caminho=str(cfg))
    assert estado.ler_publicacao_pendente(str(cfg)) == []
    assert estado.ler_publicacao_pendente(str(tmp_path / "nao_existe.json")) == []


def test_monitor_recupera_pendentes_no_comeco_de_cada_volta(lojas, monkeypatch):
    chamadas = []
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda db, adiados: chamadas.append("recuperar"))
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_esperar", lambda s: None)

    def ler(db, ultimo, limite, adiados):
        chamadas.append("ler")
        if chamadas.count("ler") == 2:
            raise KeyboardInterrupt
        return []
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    args = type("A", (), {"desde": None, "limite": 0})()
    lojas._monitorar(None, None, object(), args, [], "img", 3)
    assert chamadas == ["recuperar", "ler", "recuperar", "ler"]


def test_devolucao_so_reabre_linha_capturada(lojas, monkeypatch):
    c = Conn()
    db, _ = _db(monkeypatch, c)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas.pendentes[:] = [100]
    lojas._recuperar_publicacoes(db, set())
    assert c.escritas == [("UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '0' "
                           "WHERE ID_OFERTA = :id AND ST_CAPTURA = '1'")]


def test_banco_fora_para_na_primeira_falha_mesmo_com_muitos_pendentes(lojas, monkeypatch):
    db, banco = _db(monkeypatch, Conn(DPY), *[RuntimeError("fora")] * 8)
    _sem_afiliados_fora(lojas, monkeypatch)
    lojas.pendentes[:] = [1, 2, 3, 4, 5, 6]
    lojas._recuperar_publicacoes(db, set())
    assert lojas.pendentes == [1, 2, 3, 4, 5, 6]
    assert banco.conexoes == 2          # a conexao inicial + 1 reconexao; nada de 1 por id
