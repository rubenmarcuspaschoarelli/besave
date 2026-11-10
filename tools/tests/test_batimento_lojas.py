"""BSV-57 BAT-05..08: batimento do robo das lojas (linha, varredura, fila vazia, pausa, navegador fechado).
Sem Playwright nem Oracle; relogio e gravacao controlados."""
import argparse
import json
import os
from datetime import UTC, datetime, timedelta

import pytest
from conftest import Loja
from core import janela as janela_mod

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
CFG_JANELA = {"janela_noturna": {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def gravados(lojas, monkeypatch):
    registro = []
    bat = lojas.batimento
    monkeypatch.setattr(bat, "agora_utc", lambda: T0)
    monkeypatch.setattr(bat, "gravar_atomico", lambda caminho, dados: registro.append(dict(dados)) or True)
    return registro


class Pagina:
    url = ""

    def wait_for_timeout(self, ms):
        pass

    def is_closed(self):
        return False


class Db:
    sem_conexao = False

    def atualizar_captura(self, id_oferta, out, ativo=False):
        return True, None

    def marcar_erro(self, *a, **k):
        return True, None

    def buscar_para_produto(self, i):
        return None

    def buscar_para_cupom(self, i):
        return None


class PausaFalsa:
    """Todas as lojas em pausa: nada e navegado, tudo e retido."""

    def __init__(self, em_pausa):
        self._em_pausa = em_pausa

    def em_pausa(self, loja):
        return self._em_pausa

    def __getattr__(self, nome):
        return lambda *a, **k: None


def _linha(i=1):
    return [{"ID_OFERTA": i, "url": f"https://amazon.com.br/p/{i}", "numero_da_captura": str(i), "DS_ORIGEM": "g"}]


def _lote(lojas, monkeypatch, loja_cls=Loja, pausa=None):
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: loja_cls())
    return lojas._processar_lote(Pagina(), _linha(), Db(), True, "img", set(), pausa or PausaFalsa(False))


def test_bat07_linha_ok_renova(lojas, gravados, monkeypatch):
    saidas, _, _ = _lote(lojas, monkeypatch)
    assert saidas[0]["status_captura"] == "ok"
    assert len(gravados) == 1
    assert gravados[0]["robo"] == "lojas" and gravados[0]["pid"] == os.getpid()
    assert gravados[0]["em"] == iso(T0) and gravados[0]["prazo"] == iso(T0 + timedelta(minutes=10))


def test_bat07_linha_de_loja_em_pausa_renova(lojas, gravados, monkeypatch):
    saidas, _, _ = _lote(lojas, monkeypatch, pausa=PausaFalsa(True))
    assert saidas[0]["status_captura"] == "loja_pausada"
    assert len(gravados) == 1


def test_bat07_linha_com_erro_comum_renova(lojas, gravados, monkeypatch):
    class Quebra(Loja):
        def capture(self, page):
            raise RuntimeError("seletor sumiu")

    saidas, _, _ = _lote(lojas, monkeypatch, Quebra)
    assert saidas[0]["status_captura"].startswith("erro:")
    assert len(gravados) == 1


@pytest.mark.parametrize("mensagem", [
    "Target page, context or browser has been closed",
    "Page.goto: Target closed",
    "BrowserContext.new_page: Browser has been closed",
])
def test_bat08_navegador_fechado_nao_renova(lojas, gravados, monkeypatch, mensagem):
    class Fechada(Loja):
        def capture(self, page):
            raise RuntimeError(mensagem)

    saidas, _, _ = _lote(lojas, monkeypatch, Fechada)
    assert saidas[0]["status_captura"].startswith("erro:")
    assert gravados == []


def _monitorar(lojas, monkeypatch, agora, filas, retidas=0):
    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return agora

    pausas = []
    respostas = iter(filas)

    def ler(*a, **k):
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
    monkeypatch.setattr(lojas, "_sem_lojas_em_pausa", lambda rows, pausa, redir: ([] if retidas else rows, retidas))
    lojas._monitorar(None, Pagina(), None, argparse.Namespace(desde=None, limite=0), [], None, 3,
                     janela_mod.ler_janela(CFG_JANELA))
    return pausas


def test_bat07_varredura_com_fila_vazia_renova_e_dorme_com_prazo(lojas, gravados, monkeypatch):
    pausas = _monitorar(lojas, monkeypatch, datetime(2026, 11, 10, 12, 0), [[]])
    assert pausas == [180]
    fases = [g["fase"] for g in gravados]
    assert fases[:2] == ["varredura", "dormindo"]
    # prazo = acordar (agora + 3 min) + 10 min
    assert gravados[1]["prazo"] == iso(T0 + timedelta(minutes=13))


def test_bat05_madrugada_prazo_e_acordar_mais_dez_minutos(lojas, gravados, monkeypatch):
    pausas = _monitorar(lojas, monkeypatch, datetime(2026, 11, 10, 23, 0), [[]])
    assert pausas == [7200]
    assert gravados[1]["fase"] == "dormindo"
    assert gravados[1]["prazo"] == iso(T0 + timedelta(hours=2, minutes=10))


def test_bat07_fila_so_de_loja_em_pausa_renova(lojas, gravados, monkeypatch):
    pausas = _monitorar(lojas, monkeypatch, datetime(2026, 11, 10, 12, 0), [[{"x": 1}]], retidas=2)
    assert pausas == [180]
    assert [g["fase"] for g in gravados][:2] == ["varredura", "dormindo"]


def test_bat07_banco_fora_na_leitura_renova(lojas, gravados, monkeypatch):
    pausas = _monitorar(lojas, monkeypatch, datetime(2026, 11, 10, 12, 0), [None])
    assert pausas == [180]
    assert [g["fase"] for g in gravados][:2] == ["varredura", "dormindo"]


def test_bat06_escrita_real_em_disco_e_json_valido(lojas, tmp_path, monkeypatch):
    bat = lojas.batimento
    alvo = tmp_path / "conf" / "batimento.json"
    monkeypatch.setenv("BESAVE_BATIMENTO", str(alvo))
    monkeypatch.setattr(bat, "agora_utc", lambda: T0)
    assert bat.bater("varredura", dorme_s=60) is True
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    assert dados == {"robo": "lojas", "pid": os.getpid(), "em": iso(T0), "prazo": iso(T0 + timedelta(minutes=11)),
                     "fase": "varredura"}
    assert sorted(p.name for p in alvo.parent.iterdir()) == ["batimento.json"]


def test_bat06_falha_de_escrita_so_loga(lojas, tmp_path, monkeypatch, capsys):
    bat = lojas.batimento
    alvo = tmp_path / "batimento.json"
    alvo.write_text('{"antigo":1}', encoding="utf-8")

    def quebra(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(bat.os, "replace", quebra)
    assert bat.bater("varredura", caminho=alvo) is False
    assert alvo.read_text(encoding="utf-8") == '{"antigo":1}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["batimento.json"]
    assert "OSError" in capsys.readouterr().out
