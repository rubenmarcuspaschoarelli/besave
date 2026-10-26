"""BSV-51 REC-01/02 e ALE no rodizio: voltas cegas -> recarregar + resgate; vigia por volta."""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import falsos
import pytest

BLOQUEIO = "intercepts pointer events"
T0 = datetime(2026, 10, 22, 13, 0)
CFG_ALERTA = {"sem_abrir_minutos": 45, "telegram_token": "t", "telegram_chat_id": "c"}


@pytest.fixture
def zap(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from wa import monitor
    yield monitor
    for nome in set(sys.modules) - antes:
        if nome not in ("wa.janela",):
            sys.modules.pop(nome, None)


def _rodar(zap, monkeypatch, abre, estado=None, voltas_max=12):
    """`abre(volta)` -> True se o grupo abre naquela volta. Devolve (eventos, estado, telegram)."""
    eventos, enviados = [], []
    estado = estado if estado is not None else {"grupos": {"g1": {"ultima_data_hora": "22/10/2026 12:00",
                                                                   "ultimo_data_id": "m1"}},
                                                "controle": {"ultimo_id_processado": 7}}
    n = {"volta": 0}

    class Ctx:
        def close(self):
            pass

    class Pagina:
        def reload(self, **k):
            eventos.append("reload")

        def wait_for_selector(self, sel, timeout=None):
            eventos.append(f"esperou:{sel}")

        def evaluate(self, js, arg=None):
            return {"dialogos": [], "tem_lista": True}

        def wait_for_timeout(self, ms):
            pass

        def is_closed(self):
            return False

    def abrir(page, nome):
        n["volta"] += 1
        if n["volta"] > voltas_max:
            raise KeyboardInterrupt
        if not abre(n["volta"]):
            eventos.append("falhou")
            raise RuntimeError(BLOQUEIO)
        eventos.append("abriu")

    def recuperar(page, nomes, csv, numero, est, vistos, db, parado_s):
        eventos.append("resgate")
        return numero, False

    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return T0 + timedelta(minutes=5 * n["volta"])

    class Banco:
        habilitado = False

        def desconectar(self):
            pass

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(zap.alerta, "datetime", Rel)
    monkeypatch.setattr(zap.alerta, "enviar_telegram", lambda t, c, m: enviados.append(m))
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", abrir)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: estado)
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: None)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Banco)
    monkeypatch.setattr(zap, "_capturar_desde_ultima", lambda *a, **k: (a[3], set()))
    monkeypatch.setattr(zap, "_marcar_baseline", lambda *a, **k: None)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap, "_ler_novas_do_grupo", lambda page, nome, vistos, numero, *a, **k: (numero, 0))
    monkeypatch.setattr(zap, "_recuperar_lacuna", recuperar)
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    zap.captura_msg_whatsapp(["g1"], seg_grupo=0)
    return eventos, estado, enviados


def test_oito_voltas_cegas_recarregam_e_depois_roda_o_resgate(zap, monkeypatch):  # REC-01
    eventos, _, _ = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=9)
    # arranque (1 abrir) + 8 voltas cegas -> reload -> resgate antes da proxima tentativa
    i = eventos.index("reload")
    assert eventos[:i].count("falhou") == 8 and eventos.count("reload") == 1
    assert eventos[i + 1] == "esperou:#pane-side" and eventos[i + 2] == "resgate"


def test_sete_voltas_cegas_ainda_nao_recarregam(zap, monkeypatch):  # REC-01 (fronteira)
    eventos, _, _ = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=8)
    assert eventos.count("falhou") == 7
    assert "reload" not in eventos


def test_recarregar_voltas_configuravel_e_repete(zap, monkeypatch):  # REC-01
    est = {"grupos": {}, "controle": {"ultimo_id_processado": 0}, "destravar": {"recarregar_voltas": 3}}
    eventos, _, _ = _rodar(zap, monkeypatch, lambda v: v == 1, estado=est, voltas_max=8)
    assert eventos.count("reload") == 2        # voltas cegas 3 e 6


def test_recarregar_nao_mexe_em_contador_nem_marcadores(zap, monkeypatch):  # REC-02
    antes = json.dumps({"grupos": {"g1": {"ultima_data_hora": "22/10/2026 12:00", "ultimo_data_id": "m1"}},
                        "controle": {"ultimo_id_processado": 7}}, sort_keys=True)
    eventos, estado, _ = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=9)
    assert "reload" in eventos
    assert json.dumps(estado, sort_keys=True) == antes


def test_volta_com_grupo_aberto_zera_a_contagem(zap, monkeypatch):
    eventos, _, _ = _rodar(zap, monkeypatch, lambda v: v % 5 != 0, voltas_max=40)
    assert "reload" not in eventos             # nunca 8 cegas seguidas


def test_captura_parada_avisa_e_voltou_sai_uma_vez(zap, monkeypatch):  # ALE-01, ALE-03
    est = {"grupos": {}, "controle": {"ultimo_id_processado": 0}, "alerta": CFG_ALERTA}
    # volta = 5 min no relogio simulado; cega da 2 a 14 (60 min), abre depois
    _, _, enviados = _rodar(zap, monkeypatch, lambda v: v == 1 or v >= 15, estado=est, voltas_max=18)
    assert len(enviados) == 2
    assert "parado" in enviados[0] and "voltou" in enviados[1]


def test_sem_chaves_do_telegram_so_loga(zap, monkeypatch):  # ALE-04
    _, _, enviados = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=14)
    assert enviados == []


def test_config_example_documenta_as_chaves_novas():  # spec saida 5
    cfg = json.loads((Path(__file__).resolve().parent.parent
                      / "capture-chat-groups/conf/config.example.json").read_text(encoding="utf-8"))
    sem_obs = {k: {c: v for c, v in blo.items() if c != "_obs"} for k, blo in cfg.items() if k in ("alerta", "destravar")}
    assert sem_obs["alerta"] == {"sem_abrir_minutos": 45, "telegram_token": "", "telegram_chat_id": ""}
    assert sem_obs["destravar"] == {"recarregar_voltas": 8}
