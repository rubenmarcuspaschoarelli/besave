"""SH-06: unidades systemd --user dos dois robos."""
import configparser
import re
from pathlib import Path

import pytest

VPS = Path(__file__).resolve().parent.parent / "vps"
UNIDADES = sorted((VPS / "systemd").glob("*.service"))


def _ler(caminho):
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str
    cfg.read(caminho, encoding="utf-8")
    return cfg


def test_existem_as_duas_unidades():
    assert [u.name for u in UNIDADES] == ["besave-captura-lojas.service", "besave-captura-whatsapp.service"]


@pytest.mark.parametrize("unidade", UNIDADES, ids=lambda u: u.name)
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
