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
    """`senha`: pasta relativa ao HOME falso onde existe o arquivo (None = nenhum)."""
    falso = tmp_path / "vncserver"
    corpo = "#!/usr/bin/env bash"+chr(10)+f'echo "$@" > "{(tmp_path / "args").as_posix()}"'+chr(10)
    falso.write_text(corpo, encoding="utf-8", newline=chr(10))
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    if senha is not None:
        arq = home / senha / "passwd"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(b"x")
    env = {**os.environ, "BESAVE_VNCSERVER": falso.as_posix(), "HOME": home.as_posix()}
    return subprocess.run([BASH, (VPS / "iniciar_vnc.sh").as_posix(), *args],
                          capture_output=True, text=True, env=env, check=False)


def test_vnc01_sem_senha_recusa_com_mensagem_e_codigo_78(tmp_path):
    r = _rodar(tmp_path, "1")
    assert r.returncode == 78  # a unidade nao reinicia com 78
    assert "vncpasswd" in r.stderr
    assert ".config/tigervnc/passwd" in r.stderr and ".vnc/passwd" in r.stderr
    assert not (tmp_path / "args").exists()  # nao chegou a subir a tela


def test_vnc01_senha_vazia_ou_em_outro_lugar_tambem_recusa(tmp_path):
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / ".vncpasswd").write_bytes(b"x")          # caminho que NAO vale
    (tmp_path / "home" / ".vnc").mkdir()
    (tmp_path / "home" / ".vnc" / "passwd").write_bytes(b"")      # vazio
    r = _rodar(tmp_path, "1")
    assert r.returncode == 78 and not (tmp_path / "args").exists()


@pytest.mark.parametrize("onde", [".config/tigervnc", ".vnc"], ids=["tigervnc-1.13", "antigo"])
@pytest.mark.parametrize("n", ["1", "2"])
def test_vnc02_com_senha_em_qualquer_caminho_padrao_sobe_a_tela_so_em_localhost(tmp_path, n, onde):
    r = _rodar(tmp_path, n, senha=onde)
    assert r.returncode == 0, r.stderr
    argv = (tmp_path / "args").read_text().split()
    assert argv[:7] == [f":{n}", "-fg", "-localhost", "yes", "-geometry", "1600x900", "-xstartup"]
    assert argv[7].endswith("/xstartup-xfce.sh" if n == "1" else "/xstartup-leve.sh")


def test_vnc05_tela_do_whatsapp_sem_segunda_sessao_xfce_e_com_dbus_proprio():
    leve = (VPS / "xstartup-leve.sh").read_text(encoding="utf-8")
    assert "dbus-run-session" in leve and "xfwm4" in leve
    assert "startxfce4" not in leve
    xfce = (VPS / "xstartup-xfce.sh").read_text(encoding="utf-8")
    assert "dbus-run-session" in xfce and "startxfce4" in xfce


@pytest.mark.parametrize("args", [(), ("0",), ("x",), ("1; rm",)])
def test_vnc03_tela_invalida_e_erro_de_uso(tmp_path, args):
    r = _rodar(tmp_path, *args, senha=".vnc")
    assert r.returncode == 2
    assert not (tmp_path / "args").exists()


def test_vnc04_readme_tem_o_tunel_das_duas_portas_e_o_vncpasswd():
    leia = (VPS / "README.md").read_text(encoding="utf-8")
    assert "5901" in leia and "5902" in leia
    assert "vncpasswd" in leia
    assert "xfwm4" in leia and "dbus-run-session" in leia
    assert ".config/tigervnc/passwd" in leia
