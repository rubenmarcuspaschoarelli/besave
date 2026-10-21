"""JAN-05: o rodizio do WhatsApp usa a pausa da janela noturna (relogio e sleep injetados)."""
import sys
import time
from datetime import datetime

import falsos
import pytest
from wa import janela as janela_mod

CFG = {"janela_noturna": {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}}


class Contexto:
    def __init__(self):
        self.fechado = False

    def close(self):
        self.fechado = True


class Pagina:
    def wait_for_timeout(self, ms):
        pass


@pytest.fixture
def zap(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from wa import monitor
    yield monitor
    for nome in set(sys.modules) - antes:
        if nome not in ("wa.janela",):
            sys.modules.pop(nome, None)


def _rodar(zap, monkeypatch, agora, voltas_max, janela_cfg=CFG):
    """Roda o rodizio com relogio fixo em `agora`. Encerra (Ctrl+C simulado) apos `voltas_max` voltas
    ou, dentro da janela, quando a pausa terminar. Devolve (voltas, dormidos, salvos, contexto)."""
    class Rel(datetime):
        @classmethod
        def now(cls, tz=None):
            return agora

    voltas, dormidos, salvos = [], [], []
    ctx = Contexto()

    def dorme(s):
        dormidos.append(s)
        if s > 0 and sum(dormidos) >= 7200:
            raise KeyboardInterrupt

    def ler_novas(page, nome, vistos, numero, *a, **k):
        voltas.append(nome)
        if len(voltas) >= voltas_max:
            raise KeyboardInterrupt
        return numero, 0

    class Banco:
        habilitado = False

        def desconectar(self):
            pass

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(janela_mod, "datetime", Rel)
    monkeypatch.setattr(time, "sleep", dorme)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (ctx, Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", lambda page, nome: None)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar",
                        lambda: {"grupos": {}, "controle": {"ultimo_id_processado": 0}})
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: salvos.append(1))
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Banco)
    monkeypatch.setattr(zap, "_marcar_baseline", lambda *a, **k: None)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap, "_ler_novas_do_grupo", ler_novas)
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: janela_mod.ler_janela(janela_cfg))

    zap.captura_msg_whatsapp(["g1"], seg_grupo=0)
    return voltas, dormidos, salvos, ctx


def test_jan05_dentro_da_janela_dorme_o_intervalo_entre_rodadas(zap, monkeypatch):
    voltas, dormidos, salvos, ctx = _rodar(zap, monkeypatch, datetime(2026, 10, 21, 23, 0), voltas_max=9)
    assert len(voltas) == 1                    # uma rodada e dorme; nao gira de novo
    longos = [s for s in dormidos if s > 0]
    assert sum(longos) == 7200 and max(longos) <= 5   # 2 h em fatias de ate 5 s
    assert salvos and ctx.fechado              # o finally salva o estado e fecha o navegador


def test_jan05_fora_da_janela_ritmo_normal_sem_pausa_longa(zap, monkeypatch):
    voltas, dormidos, salvos, _ = _rodar(zap, monkeypatch, datetime(2026, 10, 21, 12, 0), voltas_max=3)
    assert len(voltas) == 3                    # gira direto, como hoje
    assert [s for s in dormidos if s > 0] == []
    assert salvos


def test_jan05_sem_janela_nao_dorme_a_noite(zap, monkeypatch):
    voltas, dormidos, _, _ = _rodar(zap, monkeypatch, datetime(2026, 10, 21, 23, 0), voltas_max=3,
                                    janela_cfg={})
    assert len(voltas) == 3
    assert [s for s in dormidos if s > 0] == []
