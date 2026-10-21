"""VNC-01..03: iniciar_vnc.sh recusa subir sem senha e sobe a tela pedida (nada real e lancado)."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

VPS = Path(__file__).resolve().parent.parent / "vps"
BASH = shutil.which("bash")
if BASH and "system32" in BASH.lower().replace("\\", "/"):
    BASH = None

pytestmark = pytest.mark.skipif(BASH is None, reason="bash indisponivel")


def _rodar(tmp_path, *args, senha=None):
    falso = tmp_path / "vncserver"
    falso.write_text(f'#!/usr/bin/env bash\necho "$@" > "{(tmp_path / "args").as_posix()}"\n',
                     encoding="utf-8", newline="\n")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    arq = tmp_path / "passwd"
    if senha is not None:
        arq.write_bytes(senha)
    env = {**os.environ, "BESAVE_VNCSERVER": falso.as_posix(), "BESAVE_VNC_PASSWD": arq.as_posix()}
    return subprocess.run([BASH, (VPS / "iniciar_vnc.sh").as_posix(), *args],
                          capture_output=True, text=True, env=env, check=False)


@pytest.mark.parametrize("senha", [None, b""], ids=["ausente", "vazio"])
def test_vnc01_sem_senha_recusa_com_mensagem_e_codigo_78(tmp_path, senha):
    r = _rodar(tmp_path, "1", senha=senha)
    assert r.returncode == 78  # a unidade nao reinicia com 78
    assert "vncpasswd" in r.stderr
    assert not (tmp_path / "args").exists()  # nao chegou a subir a tela


@pytest.mark.parametrize("n", ["1", "2"])
def test_vnc02_com_senha_sobe_a_tela_pedida_so_em_localhost(tmp_path, n):
    r = _rodar(tmp_path, n, senha=b"x")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "args").read_text().split() == [
        f":{n}", "-fg", "-localhost", "yes", "-geometry", "1600x900",
        "-xstartup", "/usr/bin/startxfce4",
    ]


@pytest.mark.parametrize("args", [(), ("0",), ("x",), ("1; rm",)])
def test_vnc03_tela_invalida_e_erro_de_uso(tmp_path, args):
    r = _rodar(tmp_path, *args, senha=b"x")
    assert r.returncode == 2
    assert not (tmp_path / "args").exists()


def test_vnc04_readme_tem_o_tunel_das_duas_portas_e_o_vncpasswd():
    leia = (VPS / "README.md").read_text(encoding="utf-8")
    assert "5901" in leia and "5902" in leia
    assert "vncpasswd" in leia
