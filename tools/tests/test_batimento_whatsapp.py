"""BSV-57 BAT-01..06: batimento do robo do WhatsApp (progresso, grupos falhando, sono, escrita atomica).
Playwright, Oracle e Telegram falsos; relogio e disco (diretorio temporario) controlados."""
import itertools
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


def _rodar(zap, monkeypatch, abre, voltas_max=8, janela_dorme_s=None, banco_fora_vezes=0, resgate_ok=False):
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
    monkeypatch.setattr(zap, "_recuperar_lacuna", lambda page, nomes, csv, numero, *a, **k: (numero, resgate_ok))
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


def test_bat_resgate_pendente_sem_concluir_nao_renova(zap, monkeypatch):
    # 8 voltas cegas deixam o resgate pendente; resgate que nao conclui (pagina cega) nao e progresso
    g = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=11, resgate_ok=False)
    assert not any(b["fase"] == "resgate" for b in g)
    assert g[-1]["em"] == iso(T0 + timedelta(minutes=5))


def test_bat_resgate_concluido_renova(zap, monkeypatch):
    g = _rodar(zap, monkeypatch, lambda v: v == 1, voltas_max=11, resgate_ok=True)
    assert any(b["fase"] == "resgate" for b in g)


# --- arranque e resgate lentos: batimento por grupo que abriu (caso real: arranque de 5-8,7 min) ------------

GRUPOS = ["g1", "g2", "g3"]
MARCADORES = {n: {"ultima_data_hora": "10/11/2026 09:00", "ultimo_data_id": f"m_{n}"} for n in GRUPOS}


class PaginaOk:
    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js, arg=None):
        return {"dialogos": [], "tem_lista": True}

    def is_closed(self):
        return False


def _arranque(zap, monkeypatch, abrem, min_por_grupo):
    """Arranque de 3 grupos; `abrem[i]` = o i-esimo grupo abre. Cada grupo consome `min_por_grupo` min (catch-up
    ou timeout). Devolve (batimentos gravados com o instante da gravacao, instante em que o arranque acabou)."""
    rel = {"t": T0}
    gravados, fim = [], {}
    chamadas = {"abrir": 0}

    class Ctx:
        def close(self):
            pass

    class Banco:
        habilitado = True
        configurado = True
        espera_segundos = 60
        ids_entregues = 0

        def conectar(self):
            return True

        def desconectar(self):
            pass

    class PW:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    def abrir(page, nome):
        chamadas["abrir"] += 1
        if chamadas["abrir"] > len(GRUPOS):               # acabou o arranque: o rodizio nao interessa
            fim["t"] = rel["t"]
            raise KeyboardInterrupt
        if not abrem[chamadas["abrir"] - 1]:
            rel["t"] += timedelta(minutes=min_por_grupo)  # o timeout tambem leva tempo
            raise RuntimeError("falhou")

    def catchup(page, nome, csv, numero, est, db, **k):
        rel["t"] += timedelta(minutes=min_por_grupo)
        return numero, set()

    batim = zap.batimento_mod
    monkeypatch.setattr(batim, "agora_utc", lambda: rel["t"])
    monkeypatch.setattr(batim, "gravar_atomico",
                        lambda caminho, dados: gravados.append((rel["t"], dict(dados))) or True)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(zap, "sync_playwright", lambda: PW())
    monkeypatch.setattr(zap.browser, "abrir_whatsapp", lambda pw, headless=False: (Ctx(), PaginaOk()))
    monkeypatch.setattr(zap.browser, "abrir_grupo", abrir)
    monkeypatch.setattr(zap.storage, "novo_csv", lambda: "csv")
    monkeypatch.setattr(zap.estado_mod, "carregar", lambda: {"grupos": json.loads(json.dumps(MARCADORES)),
                                                              "controle": {"ultimo_id_processado": 0}})
    monkeypatch.setattr(zap.estado_mod, "salvar", lambda e: None)
    monkeypatch.setattr(zap.oracle_db, "OracleDB", Banco)
    monkeypatch.setattr(zap, "_capturar_desde_ultima", catchup)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])
    monkeypatch.setattr(zap.janela_mod, "carregar", lambda caminho: None)
    zap.captura_msg_whatsapp(GRUPOS, seg_grupo=0)
    return gravados, fim["t"]


def test_arranque_lento_de_3_grupos_de_4_min_nunca_deixa_o_prazo_vencer(zap, monkeypatch):
    gravados, fim = _arranque(zap, monkeypatch, [True, True, True], 4)
    assert fim == T0 + timedelta(minutes=12)               # arranque de 12 min, mais lento que o de 8,7 do caso real
    instantes = [t for t, _ in gravados]
    assert len(gravados) == 4                              # partida + 1 por grupo
    for (t, d) in gravados:
        assert d["fase"] in ("partida", "arranque")
    for a, b in itertools.pairwise(instantes):
        assert b - a <= timedelta(minutes=10)              # nenhum buraco maior que o prazo
    # no fim do arranque o ultimo prazo ainda vale
    assert fim <= datetime.strptime(gravados[-1][1]["prazo"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def test_arranque_com_os_3_grupos_falhando_por_11_min_fica_vencido(zap, monkeypatch):
    gravados, fim = _arranque(zap, monkeypatch, [False, False, False], 11 / 3)
    assert [d["fase"] for _, d in gravados] == ["partida"]  # grupo que falhou nao renova
    prazo = datetime.strptime(gravados[-1][1]["prazo"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert fim - timedelta(minutes=11) == T0
    assert fim > prazo                                     # o vigia ve parado


def test_arranque_grupo_que_falha_nao_renova_mas_os_outros_sim(zap, monkeypatch):
    gravados, _ = _arranque(zap, monkeypatch, [True, False, True], 4)
    assert [d["fase"] for _, d in gravados] == ["partida", "arranque", "arranque"]
    assert [t for t, _ in gravados] == [T0, T0 + timedelta(minutes=4), T0 + timedelta(minutes=12)]


def _resgate(zap, monkeypatch, abrem, min_por_grupo):
    rel = {"t": T0}
    gravados = []
    chamadas = {"n": 0}
    batim = zap.batimento_mod

    def abrir(page, nome):
        chamadas["n"] += 1
        if not abrem[chamadas["n"] - 1]:
            raise RuntimeError("falhou")

    def catchup(page, nome, csv, numero, est, db, **k):
        rel["t"] += timedelta(minutes=min_por_grupo)
        return numero, set()

    monkeypatch.setattr(batim, "agora_utc", lambda: rel["t"])
    monkeypatch.setattr(batim, "gravar_atomico",
                        lambda caminho, dados: gravados.append((rel["t"], dict(dados))) or True)
    monkeypatch.setattr(zap.browser, "abrir_grupo", abrir)
    monkeypatch.setattr(zap, "_capturar_desde_ultima", catchup)
    monkeypatch.setattr(zap, "_ids_baloes", lambda page: [])

    class Pagina:
        def wait_for_timeout(self, ms):
            pass

    zap._BAT["atual"] = batim.Batimento(relogio=lambda: rel["t"])
    try:
        _numero, ok = zap._recuperar_lacuna(Pagina(), GRUPOS, "csv", 0, {"grupos": json.loads(json.dumps(MARCADORES))},
                                           set(), object(), 2 * 3600)
    finally:
        zap._BAT["atual"] = None
    return gravados, ok, rel["t"]


def test_resgate_de_3_grupos_de_3_min_bate_a_cada_grupo(zap, monkeypatch):
    gravados, ok, fim = _resgate(zap, monkeypatch, [True, True, True], 3)
    assert ok is True and fim == T0 + timedelta(minutes=9)
    assert [d["fase"] for _, d in gravados] == ["resgate"] * 3
    assert [t for t, _ in gravados] == [T0 + timedelta(minutes=m) for m in (3, 6, 9)]


def test_resgate_grupo_que_falha_nao_renova(zap, monkeypatch):
    gravados, ok, _ = _resgate(zap, monkeypatch, [True, False, True], 3)
    assert ok is False
    assert [t for t, _ in gravados] == [T0 + timedelta(minutes=3), T0 + timedelta(minutes=6)]


def test_resgate_com_todos_os_grupos_falhando_nao_renova(zap, monkeypatch):
    gravados, ok, _ = _resgate(zap, monkeypatch, [False, False, False], 3)
    assert ok is False and gravados == []
