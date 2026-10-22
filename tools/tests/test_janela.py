"""JAN-01..06: janela noturna (inicio, fim, intervalo_minutos) nos dois robos, relogio injetado."""
import json
from datetime import datetime

import pytest
from core import janela as lojas
from wa import janela as whats

CFG = {"janela_noturna": {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}}
NORMAL = 180


def _em(h, m=0):
    return datetime(2026, 10, 21, h, m)


@pytest.fixture(params=[lojas, whats], ids=["lojas", "whatsapp"])
def mod(request):
    return request.param


def test_jan01_sem_bloco_ou_invalido_nao_ha_janela(mod):
    assert mod.ler_janela({}) is None
    assert mod.ler_janela(None) is None
    for ruim in (
        {"inicio": "22:00", "fim": "08:00"},                          # sem intervalo
        {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 0},
        {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": "x"},
        {"inicio": "25:00", "fim": "08:00", "intervalo_minutos": 120},
        {"inicio": "22h", "fim": "08:00", "intervalo_minutos": 120},
        {"inicio": "08:00", "fim": "08:00", "intervalo_minutos": 120},  # vazia
    ):
        assert mod.ler_janela({"janela_noturna": ruim}) is None
    assert mod.ler_janela({"janela_noturna": "22-08"}) is None


def test_jan02_sem_janela_ritmo_normal_a_qualquer_hora(mod):
    for h in (0, 3, 12, 23):
        assert not mod.dentro(None, _em(h))
        assert mod.espera_s(None, _em(h), NORMAL) == NORMAL


@pytest.mark.parametrize("h,m,esperado", [
    (21, 59, False),   # antes
    (22, 0, True),     # inicio inclusivo
    (23, 59, True),
    (0, 0, True),      # cruzou a meia-noite
    (3, 30, True),
    (7, 59, True),
    (8, 0, False),     # fim exclusivo (saida)
    (12, 0, False),
])
def test_jan03_janela_que_cruza_a_meia_noite(mod, h, m, esperado):
    assert mod.dentro(mod.ler_janela(CFG), _em(h, m)) is esperado


def test_jan04_janela_no_mesmo_dia(mod):
    j = mod.ler_janela({"janela_noturna": {"inicio": "01:00", "fim": "05:00", "intervalo_minutos": 60}})
    assert [mod.dentro(j, _em(h)) for h in (0, 1, 4, 5, 6)] == [False, True, True, False, False]


def test_jan05_dentro_espera_o_intervalo_cortado_no_fim(mod):
    j = mod.ler_janela(CFG)
    assert mod.espera_s(j, _em(22, 0), NORMAL) == 7200
    assert mod.espera_s(j, _em(2, 0), NORMAL) == 7200
    assert mod.espera_s(j, _em(7, 0), NORMAL) == 3600     # nao passa das 08:00
    assert mod.espera_s(j, _em(23, 30), NORMAL) == 7200   # cruza a meia-noite sem cortar
    assert mod.espera_s(j, _em(8, 0), NORMAL) == NORMAL   # saiu: ritmo normal
    assert mod.espera_s(j, _em(21, 0), NORMAL) == NORMAL  # antes: ritmo normal


def test_jan06_whatsapp_dorme_so_dentro_da_janela_em_fatias():
    j = whats.ler_janela(CFG)
    dormidos = []
    assert whats.dormir_ate_proxima_rodada(j, agora=lambda: _em(7, 0), dormir=dormidos.append) == 3600
    assert sum(dormidos) == 3600 and max(dormidos) <= 5  # fatias: Ctrl+C responde
    dormidos.clear()
    assert whats.dormir_ate_proxima_rodada(j, agora=lambda: _em(12), dormir=dormidos.append) == 0
    assert whats.dormir_ate_proxima_rodada(None, agora=lambda: _em(3), dormir=dormidos.append) == 0
    assert dormidos == []


def test_jan07_whatsapp_carrega_do_arquivo(tmp_path):
    cfg = tmp_path / "config.json"
    assert whats.carregar(cfg) is None            # ausente
    cfg.write_text("{ruim", encoding="utf-8")
    assert whats.carregar(cfg) is None            # ilegivel
    cfg.write_text(json.dumps(CFG), encoding="utf-8")
    assert whats.carregar(cfg) == whats.ler_janela(CFG)


def test_jan08_exemplos_documentam_a_chave():
    from pathlib import Path
    tools = Path(__file__).resolve().parent.parent
    for exemplo in ("capture-store-pages", "capture-chat-groups"):
        dados = json.loads((tools / exemplo / "conf" / "config.example.json").read_text(encoding="utf-8"))
        bloco = dados["janela_noturna"]
        assert {"inicio", "fim", "intervalo_minutos"} <= set(bloco)
        assert lojas.ler_janela(dados) is None  # copiar o exemplo nao liga a janela
