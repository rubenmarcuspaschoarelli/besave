"""BSV-56 SEQ-01..05, FORA-01..05: o robo do WhatsApp numera pela sequence do banco e espera o banco fora.
Oracle, Playwright, imagens, CSV e Telegram falsos; relogio e sleep injetados."""
import sys
import time
from datetime import datetime, timedelta

import falsos
import pytest

T0 = datetime(2026, 11, 9, 10, 0)
TOKEN = "123:SEGREDO"


@pytest.fixture
def zap(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from wa import monitor
    yield monitor
    for nome in set(sys.modules) - antes:
        if nome not in ("wa.janela",):
            sys.modules.pop(nome, None)


class Banco:
    """OracleDB falso: sequence em memoria; `fora` derruba o NEXTVAL; `volta_apos` = tentativas de disponivel()."""

    configurado = True
    habilitado = True
    espera_segundos = 60

    def __init__(self, erro_cls, inicio=1000, fora=False, ids_ate_cair=None, volta_apos=0, falhas_nextval=0):
        self.erro_cls = erro_cls
        self.valor = inicio
        self.fora = fora
        self.ids_ate_cair = ids_ate_cair
        self.volta_apos = volta_apos
        self.falhas_nextval = falhas_nextval   # NEXTVAL falha (ORA-02289) com o banco respondendo
        self.tentativas = 0
        self.inseridos = []
        self.ids_entregues = 0
        self.eventos = []

    def proximo_id(self):
        if self.ids_ate_cair is not None and self.ids_ate_cair <= 0:
            self.fora = True
        if self.falhas_nextval > 0:
            self.falhas_nextval -= 1
            self.eventos.append("id_falhou")
            raise self.erro_cls("ORA-02289")
        if self.fora:
            self.eventos.append("id_falhou")
            raise self.erro_cls("ORA-03113")
        if self.ids_ate_cair is not None:
            self.ids_ate_cair -= 1
        v, self.valor = self.valor, self.valor + 1
        self.ids_entregues += 1
        self.eventos.append(f"id:{v}")
        return v

    def disponivel(self):
        self.tentativas += 1
        self.eventos.append("disponivel")
        if self.tentativas > self.volta_apos:
            self.fora = False
            self.ids_ate_cair = None
            return True
        return False

    def inserir_oferta(self, linha):
        self.inseridos.append(linha["ID_OFERTA"])
        return True

    def conectar(self):
        return True

    def desconectar(self):
        pass


def campos(nome):
    return {"tipo_anuncio": "PRODUTO", "nome_do_produto": nome, "msg_aviso": "", "preco_de": "",
            "preco_por": "19,90", "descricao_pagamento": "", "url": "https://amzn.to/x", "mensagem_final": "",
            "cupom": "", "comentario_cupom": "", "loja_cupom": "", "loja": "AMAZON"}


class Registro:
    def __init__(self):
        self.imagens, self.renomes, self.descartados, self.csv = [], [], [], []


@pytest.fixture
def reg(zap, monkeypatch):
    r = Registro()
    msgs = {}

    def salvar_imagem(msg, bruto, numero, rotulo):
        r.imagens.append((numero, rotulo))
        return f"img/{numero}_{rotulo}.jpeg"

    def renomear(old, numero, rotulo):
        r.renomes.append((old, numero))
        return f"img/{numero}_{rotulo}.jpeg"

    monkeypatch.setattr(zap.parser, "extrair_bruto", lambda msg: msg)
    monkeypatch.setattr(zap.parser, "parse_campos", lambda bruto: campos(bruto["nome"]))
    monkeypatch.setattr(zap.parser, "extrair_data_hora", lambda bruto: bruto["dh"])
    monkeypatch.setattr(zap.storage, "salvar_imagem", salvar_imagem)
    monkeypatch.setattr(zap.storage, "renomear_imagem", renomear)
    monkeypatch.setattr(zap.storage, "gravar_linha", lambda caminho, linha: r.csv.append(dict(linha)))
    monkeypatch.setattr(zap, "_descartar_tmp", r.descartados.append)
    monkeypatch.setattr(zap, "_ir_ao_fim", lambda page: None)
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: None)
    r.msgs = msgs
    return r


class Pagina:
    def wait_for_timeout(self, ms):
        pass


def estado(ultimo_id=5):
    return {"grupos": {"g1": {"ultima_data_hora": "09/11/2026 09:00", "ultimo_data_id": "m0"}},
            "controle": {"ultimo_id_processado": ultimo_id},
            "alerta": {"telegram_token": TOKEN, "telegram_chat_id": "-100"}}


def msg(nome, minuto):
    return {"nome": nome, "dh": T0 + timedelta(minutes=minuto)}


def item(data_id, nome, minuto):
    return {"campos": campos(nome), "img_tmp": f"tmp_{data_id}", "data_id": data_id,
            "data_hora": T0 + timedelta(minutes=minuto)}


# --- ao vivo -------------------------------------------------------------------

def test_seq01_ao_vivo_ids_do_nextval_na_imagem_csv_e_insert(zap, reg, monkeypatch):
    novas = [("d1", msg("Fone", 1)), ("d2", msg("Perfume", 2))]
    monkeypatch.setattr(zap, "_coletar_novas", lambda page, vistos: (list(novas), []))
    db = Banco(zap.oracle_db.ErroSemId, inicio=46100)
    est = estado(ultimo_id=5)               # contador absurdo no config: nao pode influenciar
    numero, lidas = zap._ler_novas_do_grupo(Pagina(), "g1", set(), 5, "csv", est, db)
    assert lidas == 2 and numero == 46101
    assert [n for n, _ in reg.imagens] == [46100, 46101]
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [46100, 46101]
    assert [linha["DS_IMAGEM_OFERTA"] for linha in reg.csv] == ["img/46100_Fone.jpeg", "img/46101_Perfume.jpeg"]
    assert db.inseridos == [46100, 46101]
    assert est["controle"]["ultimo_id_processado"] == 46101   # so informativo
    assert est["grupos"]["g1"]["ultimo_data_id"] == "d2"


def test_seq02_contador_do_config_nao_e_lido(zap, reg, monkeypatch):
    monkeypatch.setattr(zap, "_coletar_novas", lambda page, vistos: ([("d1", msg("Fone", 1))], []))
    for absurdo in (5, 999999):
        reg.imagens.clear()
        db = Banco(zap.oracle_db.ErroSemId, inicio=46100)
        zap._ler_novas_do_grupo(Pagina(), "g1", set(), absurdo, "csv", estado(absurdo), db)
        assert reg.imagens[0][0] == 46100


# --- catch-up ------------------------------------------------------------------

def test_seq03_catch_up_renomeia_com_nextval_em_ordem_cronologica(zap, reg, monkeypatch):
    cron = [item("m0", "Ja lida", 0), item("a", "Fone", 1), item("b", "Perfume", 2)]
    monkeypatch.setattr(zap, "_coletar_subindo", lambda page, **k: (list(cron), True, set()))
    db = Banco(zap.oracle_db.ErroSemId, inicio=700)
    est = estado()
    numero, _ = zap._capturar_desde_ultima(Pagina(), "g1", "csv", 5, est, db,
                                           cutoff_dt=None, marker_id="m0", inclusivo=False)
    assert reg.renomes == [("tmp_a", 700), ("tmp_b", 701)]
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [700, 701] and db.inseridos == [700, 701]
    assert reg.descartados == ["tmp_m0"]
    assert numero == 701 and est["grupos"]["g1"]["ultimo_data_id"] == "b"


# --- banco fora ----------------------------------------------------------------

def test_fora01_ao_vivo_banco_fora_nao_grava_nem_move_marcador(zap, reg, monkeypatch):
    monkeypatch.setattr(zap, "_coletar_novas",
                        lambda page, vistos: ([("d1", msg("Fone", 1)), ("d2", msg("Perfume", 2))], []))
    db = Banco(zap.oracle_db.ErroSemId, fora=True)
    est = estado()
    vistos = set()
    with pytest.raises(zap.oracle_db.ErroSemId):
        zap._ler_novas_do_grupo(Pagina(), "g1", vistos, 5, "csv", est, db)
    assert reg.imagens == [] and reg.csv == [] and db.inseridos == []
    assert est["grupos"]["g1"] == {"ultima_data_hora": "09/11/2026 09:00", "ultimo_data_id": "m0"}
    assert est["controle"]["ultimo_id_processado"] == 5
    assert "d1" not in vistos and "d2" not in vistos


def test_fora05_catch_up_para_no_meio_apaga_tmp_e_marcador_no_ultimo_gravado(zap, reg, monkeypatch):
    cron = [item("m0", "Ja lida", 0), item("a", "Fone", 1), item("b", "Perfume", 2), item("c", "Bolsa", 3)]
    monkeypatch.setattr(zap, "_coletar_subindo", lambda page, **k: (list(cron), True, set()))
    db = Banco(zap.oracle_db.ErroSemId, inicio=700, ids_ate_cair=1)
    est = estado()
    with pytest.raises(zap.oracle_db.ErroSemId):
        zap._capturar_desde_ultima(Pagina(), "g1", "csv", 5, est, db,
                                   cutoff_dt=None, marker_id="m0", inclusivo=False)
    assert reg.renomes == [("tmp_a", 700)]
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [700]
    assert sorted(reg.descartados) == ["tmp_b", "tmp_c", "tmp_m0"]
    assert est["grupos"]["g1"]["ultimo_data_id"] == "a"


# --- laco inteiro: espera, aviso, lembrete, voltou e reprocessamento -----------

def _rodar(zap, reg, monkeypatch, volta_apos, fora_na_partida=True, est=None, grupos=("g1",), falhas_nextval=0):
    """captura_msg_whatsapp com 1 grupo cujo catch-up tem 1 mensagem nova ('a'). O banco cai no 1o id
    e volta depois de `volta_apos` tentativas de disponivel(); cada sleep anda o relogio. Para (Ctrl+C
    simulado) no fim da 1a volta ao vivo. Devolve (db, enviados, sleeps, estado)."""
    relogio = {"t": T0}
    sleeps, enviados, coletas = [], [], []

    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return relogio["t"]

    def dorme(s):
        sleeps.append(s)
        relogio["t"] += timedelta(seconds=s)

    def subir(page, **k):
        coletas.append(k.get("marker_id"))
        return [item("m0", "Ja lida", 0), item("a", "Fone", 1)], True, set()

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

    est = est or estado()
    db = Banco(zap.oracle_db.ErroSemId, inicio=46100, fora=fora_na_partida, volta_apos=volta_apos,
               falhas_nextval=falhas_nextval)
    monkeypatch.setattr(zap, "datetime", Rel)
    monkeypatch.setattr(time, "sleep", dorme)
    monkeypatch.setattr(zap.alerta, "enviar_telegram", lambda t, c, m: enviados.append((t, c, m)))
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", lambda page, nome: db.eventos.append(f"abrir:{nome}"))
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: est)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", lambda: db)
    monkeypatch.setattr(zap, "_coletar_subindo", subir)
    monkeypatch.setattr(zap, "_coletar_novas", lambda page, vistos: ([], []))
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    monkeypatch.setattr(zap.janela_mod, "dormir_ate_proxima_rodada", parar)
    zap.captura_msg_whatsapp(list(grupos), seg_grupo=0)
    db.coletas = coletas
    return db, enviados, sleeps, est


def test_fora02_sequence_falhando_com_banco_respondendo_nao_alterna_fora_e_voltou(zap, reg, monkeypatch):
    """SELECT 1 responde mas o NEXTVAL falha (ORA-02289, sem grant): 1 aviso so, e o 'voltou' so no 1o id."""
    db, enviados, sleeps, _ = _rodar(zap, reg, monkeypatch, volta_apos=0, fora_na_partida=False, falhas_nextval=3)
    textos = [m for _, _, m in enviados]
    assert len(textos) == 2, textos
    assert "Banco Oracle fora" in textos[0] and "ORA-02289" in textos[0] and "voltou" in textos[1]
    assert [s for s in sleeps if s == 60] == [60] * 3          # espera a cada falha, sem laco cego
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [46100]
    # "voltou" so depois do id: nenhum aviso de volta antes de o NEXTVAL entregar numero
    assert db.eventos.count("id_falhou") == 3 and "id:46100" in db.eventos


def test_fora03_banco_cai_no_resgate_espera_sem_andar_grupo_e_retoma(zap, reg, monkeypatch):
    """2 grupos com marcador; o NEXTVAL falha na partida e de novo no resgate. Entre cada falha e a
    tentativa seguinte de disponivel() nenhum grupo e aberto; o robo nao cai e a mensagem sai depois."""
    est = estado()
    est["grupos"]["g2"] = {"ultima_data_hora": "09/11/2026 09:00", "ultimo_data_id": "m0"}
    db, enviados, sleeps, est = _rodar(zap, reg, monkeypatch, volta_apos=0, fora_na_partida=False,
                                       est=est, grupos=("g1", "g2"), falhas_nextval=3)
    ev = db.eventos
    for i, e in enumerate(ev):
        if e == "id_falhou":
            prox = ev.index("disponivel", i)
            assert not [x for x in ev[i:prox] if x.startswith("abrir:")], ev
    assert ev.count("id_falhou") == 3 and ev.count("disponivel") == 3
    assert [s for s in sleeps if s == 60] == [60] * 3
    # g1 e g2 saem cada um com seu id, uma vez so, depois do banco voltar
    assert sorted(linha["ID_OFERTA"] for linha in reg.csv) == [46100, 46101]
    assert len(enviados) == 2 and "voltou" in enviados[1][2]


def test_fora02_04_banco_volta_mesma_mensagem_com_id_novo_e_voltou(zap, reg, monkeypatch, capsys):
    db, enviados, sleeps, est = _rodar(zap, reg, monkeypatch, volta_apos=3)
    out = capsys.readouterr().out
    # espera: 4 tentativas a cada 60 s, nada gravado enquanto isso
    assert [s for s in sleeps if s == 60] == [60] * 4
    # a mesma mensagem 'a' (relida pelo marcador m0) sai com id da sequence, uma vez so
    assert [linha["ID_OFERTA"] for linha in reg.csv] == [46100] and reg.csv[0]["DS_OFERTA"] == "Fone"
    assert reg.renomes == [("tmp_a", 46100)] and db.inseridos == [46100]
    assert db.coletas == ["m0", "m0"]                  # partida + resgate, ambos desde o marcador
    assert est["grupos"]["g1"]["ultimo_data_id"] == "a"
    # 1 aviso de fora + 1 "voltou", nesta ordem; token nunca no log
    assert len(enviados) == 2
    assert "Banco Oracle fora" in enviados[0][2] and "voltou" in enviados[1][2]
    assert TOKEN not in out
    assert "Retomando contador" not in out             # SEQ-05


def test_fora02_lembrete_so_depois_de_2h(zap, reg, monkeypatch):
    _, enviados, _, _ = _rodar(zap, reg, monkeypatch, volta_apos=119)   # ultima falha aos 119 min
    assert [m for _, _, m in enviados if "continua fora" in m] == []
    assert len(enviados) == 2


def test_fora02_lembrete_aos_120_min(zap, reg, monkeypatch):
    _, enviados, _, _ = _rodar(zap, reg, monkeypatch, volta_apos=120)   # falha tambem aos 120 min
    textos = [m for _, _, m in enviados]
    assert len(textos) == 3 and "continua fora ha 120 min" in textos[1] and "voltou" in textos[2]


def test_fora03_ao_vivo_banco_fora_nenhum_grupo_anda(zap, reg, monkeypatch):
    """Ao vivo, g1 tem mensagem nova e o banco cai: g2 nao e aberto enquanto o banco esta fora."""
    abertos, relogio = [], {"t": T0}
    voltas = {"n": 0}

    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return relogio["t"]

    def dorme(s):
        relogio["t"] += timedelta(seconds=s)

    def abrir(page, nome):
        abertos.append((nome, db.fora))

    def novas(page, vistos):
        if "d1" in vistos or db.tentativas:
            return [], []
        db.fora = True
        return [("d1", msg("Fone", 1))], []

    def parar(janela):
        voltas["n"] += 1
        if voltas["n"] >= 2:
            raise KeyboardInterrupt

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    class Ctx:
        def close(self):
            pass

    est = {"grupos": {}, "controle": {"ultimo_id_processado": 5}}
    db = Banco(zap.oracle_db.ErroSemId, inicio=46100, volta_apos=2)
    resgates = []
    monkeypatch.setattr(zap, "datetime", Rel)
    monkeypatch.setattr(time, "sleep", dorme)
    monkeypatch.setattr(zap.alerta, "enviar_telegram", lambda t, c, m: None)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", abrir)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: est)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", lambda: db)
    monkeypatch.setattr(zap, "_marcar_baseline", lambda *a, **k: None)
    monkeypatch.setattr(zap, "_coletar_novas", novas)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap, "_recuperar_lacuna",
                        lambda page, nomes, csv, numero, *a, **k: (resgates.append(numero) or (numero, True)))
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    monkeypatch.setattr(zap.janela_mod, "dormir_ate_proxima_rodada", parar)
    zap.captura_msg_whatsapp(["g1", "g2"], seg_grupo=0)
    # arranque abre g1 e g2; ao vivo g1 derruba o banco -> g2 so volta a abrir depois do banco voltar
    ao_vivo = abertos[2:]
    assert ao_vivo[0] == ("g1", False)
    assert ("g2", True) not in ao_vivo
    assert db.tentativas == 3 and resgates == [0]      # esperou e marcou o resgate
    assert reg.csv == [] and reg.imagens == []


def test_sem_banco_configurado_nao_sobe(zap, monkeypatch, capsys):
    class Desligado:
        configurado = False

    abriu = []
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: estado())
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Desligado)
    monkeypatch.setattr(zap, "sync_playwright", lambda: abriu.append(1))
    assert zap.captura_msg_whatsapp(["g1"]) == zap.SAIDA_SEM_BANCO
    assert abriu == []
    assert "DESLIGADA" in capsys.readouterr().out
