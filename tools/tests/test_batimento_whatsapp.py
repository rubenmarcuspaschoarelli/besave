"""BSV-57 BAT-01..06: batimento do robo do WhatsApp (progresso, grupos falhando, sono, escrita atomica).
Playwright, Oracle e Telegram falsos; relogio e disco (diretorio temporario) controlados."""
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import falsos
import pytest

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def zap(monkeypatch):
    antes = set(sys.modules)
    falsos.instalar(monkeypatch)
    from wa import monitor
    yield monitor
    for nome in set(sys.modules) - antes:
        if nome not in ("wa.janela",):
            sys.modules.pop(nome, None)


@pytest.fixture
def bat():
    falsos_mod = sys.modules.get("wa.batimento")
    if falsos_mod is None:
        from wa import batimento
    else:
        batimento = falsos_mod
    return batimento


def _rodar(zap, monkeypatch, abre, voltas_max=8, janela_dorme_s=None, banco_fora_vezes=0):
    """Roda captura_msg_whatsapp com 1 grupo. `abre(volta)` -> True se abre. Devolve a lista de batimentos gravados."""
    gravados = []
    n = {"volta": 0, "falhas_banco": banco_fora_vezes, "chamadas_ler": 0}
    estado = {"grupos": {}, "controle": {"ultimo_id_processado": 0}}

    class Ctx:
        def close(self):
            pass

    class Pagina:
        def evaluate(self, js, arg=None):
            return {"dialogos": [], "tem_lista": True}

        def wait_for_timeout(self, ms):
            pass

        def is_closed(self):
            return False

    class Banco:
        habilitado = True
        configurado = True
        espera_segundos = 60
        ids_entregues = 0

        def conectar(self):
            return True

        def desconectar(self):
            pass

        def disponivel(self):
            if n["falhas_banco"] > 0:
                n["falhas_banco"] -= 1
                return False
            return True

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    def abrir(page, nome):
        n["volta"] += 1
        if n["volta"] > voltas_max:
            raise KeyboardInterrupt
        if not abre(n["volta"]):
            raise RuntimeError("falhou")

    def ler(page, nome, vistos, numero, *a, **k):
        n["chamadas_ler"] += 1
        if banco_fora_vezes and n["chamadas_ler"] == 1:
            raise zap.oracle_db.ErroSemId("ORA-03113")
        return numero, 0

    batim = zap.batimento_mod
    monkeypatch.setattr(batim, "agora_utc", lambda: T0 + timedelta(minutes=5 * n["volta"]))
    monkeypatch.setattr(batim, "gravar_atomico", lambda caminho, dados: gravados.append(dict(dados)) or True)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), Pagina()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", abrir)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: estado)
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: None)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Banco)
    monkeypatch.setattr(zap, "_marcar_baseline", lambda *a, **k: None)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap, "_ler_novas_do_grupo", ler)
    monkeypatch.setattr(zap, "_recuperar_lacuna", lambda page, nomes, csv, numero, *a, **k: (numero, True))
    monkeypatch.setattr(zap, "_relatar_bloqueio", lambda page: None)
    monkeypatch.setattr(zap.destravar, "recarregar", lambda page: None)
    if janela_dorme_s is None:
        monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    else:
        monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: (datetime(2026, 1, 1, 22).time(), datetime(2026, 1, 1, 8).time(), 7200))
        monkeypatch.setattr(zap.janela_mod, "dentro", lambda janela, agora=None: True)
        monkeypatch.setattr(zap.janela_mod, "espera_s", lambda janela, agora, normal: janela_dorme_s)
        monkeypatch.setattr(zap.janela_mod, "dormir_ate_proxima_rodada", lambda janela, **k: 0)
    zap.captura_msg_whatsapp(["g1"], seg_grupo=0)
    return gravados


def test_bat01_volta_com_grupo_aberto_renova_com_prazo_de_dez_minutos(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: v != 3, voltas_max=3)
    # volta 2 (clock T0+10) abriu: renova; volta 3 (T0+15) falhou: nao renova
    ultimo = g[-1]
    assert ultimo["robo"] == "whatsapp" and ultimo["pid"] == os.getpid()
    assert ultimo["fase"] == "rodizio"
    assert ultimo["em"] == iso(T0 + timedelta(minutes=10))
    assert ultimo["prazo"] == iso(T0 + timedelta(minutes=20))


def test_bat02_volta_com_todos_os_grupos_falhando_nao_renova(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=9)     # so o arranque abre
    assert g, "o arranque grava o batimento"
    assert all(b["fase"] in ("partida", "arranque") for b in g)
    assert g[-1]["em"] == iso(T0 + timedelta(minutes=5))             # nenhuma das 8 voltas cegas renovou


def test_bat02_uma_volta_que_abre_depois_de_varias_cegas_renova(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: v in (1, 6), voltas_max=7)
    assert g[-1]["fase"] == "rodizio"
    assert g[-1]["em"] == iso(T0 + timedelta(minutes=30))


def test_bat03_banco_fora_renova_com_fase_de_banco_fora(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: True, voltas_max=2, banco_fora_vezes=3)
    fora = [b for b in g if b["fase"] == "banco fora"]
    assert len(fora) >= 3
    assert all(b["prazo"] > b["em"] for b in fora)


def test_bat04_grupos_falhando_desde_a_primeira_falha_e_saem_ao_abrir(bat, tmp_path):
    t = {"agora": T0}
    b = bat.Batimento(tmp_path / "batimento.json", relogio=lambda: t["agora"])
    assert b.volta({"a": True, "b": False}) is True
    t["agora"] = T0 + timedelta(minutes=5)
    b.volta({"a": True, "b": False})                        # 2a falha: o "desde" nao anda
    dados = json.loads((tmp_path / "batimento.json").read_text(encoding="utf-8"))
    assert dados["grupos_falhando"] == {"b": iso(T0)}
    t["agora"] = T0 + timedelta(minutes=10)
    b.volta({"a": False, "b": True})                        # b abriu: sai; a falhou: entra
    dados = json.loads((tmp_path / "batimento.json").read_text(encoding="utf-8"))
    assert dados["grupos_falhando"] == {"a": iso(T0 + timedelta(minutes=10))}
    t["agora"] = T0 + timedelta(minutes=15)
    b.volta({"a": True, "b": True})
    dados = json.loads((tmp_path / "batimento.json").read_text(encoding="utf-8"))
    assert "grupos_falhando" not in dados


def test_bat04_volta_cega_nao_grava_mas_lembra_a_falha(bat, tmp_path):
    t = {"agora": T0}
    b = bat.Batimento(tmp_path / "batimento.json", relogio=lambda: t["agora"])
    b.volta({"a": True})
    t["agora"] = T0 + timedelta(minutes=5)
    assert b.volta({"a": False}) is False
    assert json.loads((tmp_path / "batimento.json").read_text(encoding="utf-8"))["em"] == iso(T0)
    t["agora"] = T0 + timedelta(minutes=10)
    b.volta({"a": True, "b": True})
    assert b.grupos_falhando == {}


def test_bat05_sono_grava_prazo_de_acordar_mais_dez_minutos(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: True, voltas_max=2, janela_dorme_s=7200)
    dormindo = [b for b in g if b["fase"] == "dormindo"]
    assert dormindo
    d = dormindo[0]
    em = datetime.strptime(d["em"], "%Y-%m-%dT%H:%M:%SZ")
    prazo = datetime.strptime(d["prazo"], "%Y-%m-%dT%H:%M:%SZ")
    assert prazo - em == timedelta(seconds=7200) + timedelta(minutes=10)


def test_bat05_bater_com_sono_soma_acordar_e_dez_minutos(bat, tmp_path):
    b = bat.Batimento(tmp_path / "batimento.json", relogio=lambda: T0)
    b.bater("dormindo", dorme_s=3600)
    dados = json.loads((tmp_path / "batimento.json").read_text(encoding="utf-8"))
    assert dados["prazo"] == iso(T0 + timedelta(minutes=70))
    assert dados["em"] == iso(T0)


def test_bat06_escrita_atomica_o_arquivo_nunca_e_lido_pela_metade(bat, tmp_path, monkeypatch):
    alvo = tmp_path / "batimento.json"
    alvo.write_text('{"antigo":1}', encoding="utf-8")
    vistos = {}
    real = os.replace

    def espia(origem, destino):
        vistos["alvo_antes"] = Path(destino).read_text(encoding="utf-8")
        vistos["tmp_completo"] = json.loads(Path(origem).read_text(encoding="utf-8"))
        vistos["dir_tmp"] = Path(origem).parent
        real(origem, destino)

    monkeypatch.setattr(bat.os, "replace", espia)
    assert bat.Batimento(alvo, relogio=lambda: T0).bater("rodizio") is True
    assert vistos["alvo_antes"] == '{"antigo":1}'              # ate o rename o arquivo e o antigo, inteiro
    assert vistos["tmp_completo"]["fase"] == "rodizio"         # o temporario ja esta completo
    assert vistos["dir_tmp"] == tmp_path                        # mesmo diretorio: rename atomico
    assert json.loads(alvo.read_text(encoding="utf-8"))["fase"] == "rodizio"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["batimento.json"]


def test_bat06_falha_de_escrita_so_loga_e_preserva_o_arquivo(bat, tmp_path, monkeypatch, capsys):
    alvo = tmp_path / "batimento.json"
    alvo.write_text('{"antigo":1}', encoding="utf-8")

    def quebra(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(bat.os, "replace", quebra)
    assert bat.Batimento(alvo, relogio=lambda: T0).bater("rodizio") is False
    assert alvo.read_text(encoding="utf-8") == '{"antigo":1}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["batimento.json"]    # sem sobra .tmp
    assert "OSError" in capsys.readouterr().out
