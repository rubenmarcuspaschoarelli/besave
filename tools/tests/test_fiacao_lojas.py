"""JAN-04: o laço do --monitorar das lojas usa a pausa da janela noturna (relogio injetado)."""
import argparse
import sys
from datetime import datetime

import falsos
import pytest
from conftest import LOJAS
from core import janela as janela_mod

CFG = {"janela_noturna": {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}}
NORMAL_MIN = 3


class Parar(Exception):
    pass


@pytest.fixture
def lojas(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    yield falsos.importar(monkeypatch, "main_lojas", LOJAS / "main.py")
    for nome in set(sys.modules) - antes:  # nada importado com os falsos vaza para outros testes
        if nome != "core.janela":
            sys.modules.pop(nome, None)


def _rodar(lojas, monkeypatch, agora, filas):
    """Roda _monitorar com relogio fixo em `agora`; `filas` = respostas sucessivas da leitura da fila."""
    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return agora

    pausas, leituras = [], []
    respostas = iter(filas)

    def ler(*a, **k):
        leituras.append(1)
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(lojas, "datetime", Rel)
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", lambda s: pausas.append(s))
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_processar_lote", lambda *a, **k: ([], 0, 0))
    monkeypatch.setattr(lojas, "_gravar_csv", lambda *a, **k: None)
    monkeypatch.setattr(lojas, "_resumo_oracle", lambda *a, **k: None)

    class Pagina:
        def is_closed(self):
            return False

    args = argparse.Namespace(desde=None, limite=0)
    lojas._monitorar(None, Pagina(), None, args, [], None, NORMAL_MIN,
                     janela_mod.ler_janela(CFG))
    return pausas, len(leituras)


def test_jan04_fila_vazia_dentro_da_janela_dorme_o_intervalo_da_janela(lojas, monkeypatch):
    pausas, _ = _rodar(lojas, monkeypatch, datetime(2026, 10, 21, 23, 0), [[]])
    assert pausas == [7200]


def test_jan04_fila_vazia_fora_da_janela_ritmo_normal(lojas, monkeypatch):
    pausas, _ = _rodar(lojas, monkeypatch, datetime(2026, 10, 21, 12, 0), [[]])
    assert pausas == [NORMAL_MIN * 60]


def test_jan04_lote_dentro_da_janela_dorme_antes_de_reler_a_fila(lojas, monkeypatch):
    pausas, leituras = _rodar(lojas, monkeypatch, datetime(2026, 10, 21, 23, 0), [[{"x": 1}]])
    assert pausas == [7200]  # nao releu a fila na hora
    assert leituras == 2     # a 2a leitura so veio depois da pausa (e ai o teste encerra)


def test_jan04_lote_fora_da_janela_rele_a_fila_na_hora(lojas, monkeypatch):
    pausas, leituras = _rodar(lojas, monkeypatch, datetime(2026, 10, 21, 12, 0), [[{"x": 1}]])
    assert pausas == []      # comportamento de hoje: sem pausa depois do lote
    assert leituras == 2


def test_jan04_pausa_dentro_da_janela_e_cortada_no_fim(lojas, monkeypatch):
    pausas, _ = _rodar(lojas, monkeypatch, datetime(2026, 10, 21, 7, 0), [[]])
    assert pausas == [3600]
