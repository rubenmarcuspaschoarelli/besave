"""SH-06: unidades systemd --user dos dois robos."""
import configparser
import re
from pathlib import Path

import pytest

VPS = Path(__file__).resolve().parent.parent / "vps"
UNIDADES = sorted((VPS / "systemd").glob("*.service"))
ROBOS = [u for u in UNIDADES if u.name.startswith("besave-captura-")]
# cada robo na sua tela VNC (BSV-48)
TELA = {"besave-captura-lojas.service": 1, "besave-captura-whatsapp.service": 2}


def _ler(caminho):
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str
    cfg.read(caminho, encoding="utf-8")
    return cfg


def test_existem_as_duas_unidades():
    assert [u.name for u in UNIDADES] == [
        "besave-captura-lojas.service", "besave-captura-whatsapp.service", "besave-reinicio-whatsapp.service",
        "besave-vnc@.service",
    ]


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_reinicia_em_falha_e_roda_no_tmux_com_display(unidade):
    cfg = _ler(unidade)
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    assert f"BESAVE_DISPLAY=:{TELA[unidade.name]}" in servico["Environment"].split()
    exec_start = servico["ExecStart"]
    assert re.search(r"/tools/vps/(rodar_em_tmux|iniciar_captura)\.sh\b", exec_start)
    assert cfg["Install"]["WantedBy"] == "default.target"


@pytest.mark.parametrize("unidade", UNIDADES, ids=lambda u: u.name)
def test_sem_segredo_na_unidade(unidade):
    texto = unidade.read_text(encoding="utf-8").lower()
    for palavra in ("senha", "password", "passwd", "secret", "token", "pass="):
        assert palavra not in texto


def test_whatsapp_usa_o_lancador_com_conferencias():
    servico = _ler(VPS / "systemd" / "besave-captura-whatsapp.service")["Service"]
    assert servico["ExecStart"].endswith("/tools/vps/iniciar_captura.sh --aguardar")
    assert (VPS / "iniciar_captura.sh").exists()


def test_lojas_roda_o_main_em_modo_monitor():
    servico = _ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"]
    partes = servico["ExecStart"].split()
    assert partes[1:3] == ["executar", "besave-lojas"]
    # BSV-55: --sem-perguntas, senao o arranque para num input() que ninguem responde
    assert partes[-4:] == ["-u", "main.py", "--monitorar", "--sem-perguntas"]
    assert partes[-5].endswith("/capture-store-pages/.venv/bin/python")


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_depende_da_tela_vnc(unidade):
    unit = _ler(unidade)["Unit"]
    tela = f"besave-vnc@{TELA[unidade.name]}.service"
    assert unit["After"] == tela
    assert unit["Requires"] == tela


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_nao_fica_failed_por_falha_de_partida(unidade):
    cfg = _ler(unidade)
    assert cfg["Unit"]["StartLimitIntervalSec"] == "0"  # sem limite: nunca 'start-limit-hit'
    assert int(cfg["Service"]["RestartSec"]) >= 30
    pre = cfg["Service"]["ExecStartPre"]
    assert f"/tmp/.X11-unix/X{TELA[unidade.name]} ]" in pre  # espera a SUA tela existir de fato
    assert "$$(" in pre  # systemd consome '$' simples


def test_vnc_e_unidade_modelo_da_tela_n_so_em_localhost():
    cfg = _ler(VPS / "systemd" / "besave-vnc@.service")
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    assert servico["ExecStart"].endswith("/tools/vps/iniciar_vnc.sh %i")  # tela :%i, porta 590%i
    assert servico["ExecStop"].endswith("vncserver -kill :%i")
    assert servico["RestartPreventExitStatus"] == "78"  # sem senha: nao reinicia em laco
    assert cfg["Unit"]["StartLimitIntervalSec"] == "0"
    assert cfg["Install"]["WantedBy"] == "default.target"


def test_readme_explica_o_linger_e_a_unidade_do_vnc():
    leia = (VPS / "README.md").read_text(encoding="utf-8")
    assert "loginctl enable-linger besave" in leia
    assert "besave-vnc" in leia
    assert re.search(r"reboot", leia)


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_para_com_sigint_e_da_tempo_de_salvar(unidade):
    servico = _ler(unidade)["Service"]
    assert servico["KillSignal"] == "SIGINT"  # SIGTERM nao roda o finally que salva o contador
    assert int(servico["TimeoutStopSec"]) >= 30


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_falha_se_a_tela_nao_aparece(unidade):
    pre = _ler(unidade)["Service"]["ExecStartPre"]
    assert not pre.startswith("-")  # sem '-': falha de verdade e o Restart= tenta de novo
    assert pre.rstrip("'").endswith("exit 1")


def test_vnc_detalhes_da_tela():
    servico = _ler(VPS / "systemd" / "besave-vnc@.service")["Service"]
    assert servico["ExecStartPre"].startswith("-")  # limpa tela velha, mas nao falha se nao ha
    assert servico["ExecStartPre"].endswith("vncserver -kill :%i")


# --- BSV-54: reinicio diario e teto de memoria --------------------------------
def test_timer_do_reinicio_a_cada_6h_sem_persistent():
    t = _ler(VPS / "systemd" / "besave-reinicio-whatsapp.timer")
    assert t["Timer"]["OnCalendar"] == "*-*-* 05,11,17,23:30:00"  # linha inteira: 05:30, 11:30, 17:30 e 23:30
    assert t["Timer"]["Persistent"] == "false"
    assert t["Install"]["WantedBy"] == "timers.target"


def test_service_do_reinicio_e_oneshot_e_chama_o_script():
    s = _ler(VPS / "systemd" / "besave-reinicio-whatsapp.service")["Service"]
    assert s["Type"] == "oneshot"
    assert s["ExecStart"].endswith("/tools/vps/reiniciar_whatsapp.sh")
    assert int(s["TimeoutStartSec"]) >= 240  # restart + 3 min de confirmacao


def test_whatsapp_teto_vem_do_environment_e_nao_da_unidade():
    # o painel do tmux fica fora da unidade (scope proprio): MemoryHigh/Max aqui nao pegariam o navegador
    servico = _ler(VPS / "systemd" / "besave-captura-whatsapp.service")["Service"]
    env = servico["Environment"].split()
    assert "BESAVE_MEM_HIGH=3500M" in env and "BESAVE_MEM_MAX=4500M" in env
    assert "BESAVE_MEM_SWAP_MAX=0" in env  # sem swap o MemoryMax vira thrashing, nao OOM-kill
    for chave in ("MemoryHigh", "MemoryMax"):
        assert chave not in servico
    assert servico["Restart"] == "on-failure"
    assert "MemoryMax" not in _ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"]


def test_whatsapp_execstop_para_o_scope_do_robo():
    servico = _ler(VPS / "systemd" / "besave-captura-whatsapp.service")["Service"]
    # '-' = scope ja ausente nao falha o stop; nada de encerrar_captura.sh (ele para a propria unidade)
    assert servico["ExecStop"] == "-/usr/bin/systemctl --user stop besave-whatsapp-robo.scope"
    assert int(servico["TimeoutStopSec"]) >= 40  # scope (30 s) + folga
