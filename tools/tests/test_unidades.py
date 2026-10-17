"""SH-06: unidades systemd --user dos dois robos."""
import configparser
import re
from pathlib import Path

import pytest

VPS = Path(__file__).resolve().parent.parent / "vps"
UNIDADES = sorted((VPS / "systemd").glob("*.service"))
ROBOS = [u for u in UNIDADES if u.name.startswith("besave-captura-")]


def _ler(caminho):
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str
    cfg.read(caminho, encoding="utf-8")
    return cfg


def test_existem_as_duas_unidades():
    assert [u.name for u in UNIDADES] == [
        "besave-captura-lojas.service", "besave-captura-whatsapp.service", "besave-vnc.service",
    ]


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_reinicia_em_falha_e_roda_no_tmux_com_display(unidade):
    cfg = _ler(unidade)
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    assert servico["Environment"] == "BESAVE_DISPLAY=:1"
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
    assert partes[-3:] == ["-u", "main.py", "--monitorar"]
    assert partes[-4].endswith("/capture-store-pages/.venv/bin/python")


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_depende_da_tela_vnc(unidade):
    unit = _ler(unidade)["Unit"]
    assert unit["After"] == "besave-vnc.service"
    assert unit["Requires"] == "besave-vnc.service"


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_nao_fica_failed_por_falha_de_partida(unidade):
    cfg = _ler(unidade)
    assert cfg["Unit"]["StartLimitIntervalSec"] == "0"  # sem limite: nunca 'start-limit-hit'
    assert int(cfg["Service"]["RestartSec"]) >= 30
    pre = cfg["Service"]["ExecStartPre"]
    assert "/tmp/.X11-unix/X1" in pre  # espera a tela existir de fato
    assert "$$(" in pre  # systemd consome '$' simples


def test_vnc_e_a_tela_1_em_primeiro_plano_e_sobe_sozinha():
    cfg = _ler(VPS / "systemd" / "besave-vnc.service")
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    partes = servico["ExecStart"].split()
    assert partes[1:3] == [":1", "-fg"]
    assert "-localhost yes" in servico["ExecStart"]  # tela so por tunel SSH
    assert servico["ExecStop"].endswith("vncserver -kill :1")
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
    servico = _ler(VPS / "systemd" / "besave-vnc.service")["Service"]
    assert servico["ExecStartPre"].startswith("-")  # limpa tela velha, mas nao falha se nao ha
    assert "-geometry 1600x900" in servico["ExecStart"]
    assert "-xstartup /usr/bin/startxfce4" in servico["ExecStart"]
