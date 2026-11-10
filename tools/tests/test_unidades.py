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
        "besave-vigia-robos.service", "besave-vnc@.service",
    ]


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_reinicia_em_falha_e_roda_no_tmux_com_display(unidade):
    cfg = _ler(unidade)
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    assert f"BESAVE_DISPLAY=:{TELA[unidade.name]}" in servico["Environment"].split()
    exec_start = servico["ExecStart"]
    assert re.search(r"/tools/vps/(rodar_em_tmux|iniciar_captura|iniciar_lojas)\.sh\b", exec_start)
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


def test_lojas_usa_o_lancador_com_scope():  # BSV-57 ESC-01, ESC-03
    servico = _ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"]
    assert servico["ExecStart"].endswith("/tools/vps/iniciar_lojas.sh --aguardar")
    assert servico["ExecStop"] == "-/usr/bin/systemctl --user stop besave-lojas-robo.scope"
    assert servico["TimeoutStopSec"] == "45"
    # BSV-55: --sem-perguntas, senao o arranque para num input() que ninguem responde
    texto = (VPS / "iniciar_lojas.sh").read_text(encoding="utf-8")
    assert "main.py --monitorar --sem-perguntas" in texto


def test_vigia_e_oneshot_com_timer_de_5_minutos():  # BSV-57 UNI-01
    servico = _ler(VPS / "systemd" / "besave-vigia-robos.service")["Service"]
    assert servico["Type"] == "oneshot"
    assert servico["ExecStart"] == "/usr/bin/python3 /srv/besave/repo/tools/vps/vigia_robos.py"
    assert (VPS / "vigia_robos.py").exists()
    timer = _ler(VPS / "systemd" / "besave-vigia-robos.timer")
    assert timer["Timer"]["OnUnitActiveSec"] == "5min"
    assert timer["Timer"]["OnBootSec"] == "5min"
    assert timer["Install"]["WantedBy"] == "timers.target"
