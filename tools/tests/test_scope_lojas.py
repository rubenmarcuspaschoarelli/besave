"""BSV-57 ESC-01..03: o robo das lojas roda num scope systemd-run (SIGINT e SIGKILL no stop), com systemd-run,
systemctl, tmux e Python falsos. Comando montado comparado inteiro (licao 14)."""
import os
import subprocess
from pathlib import Path

import pytest
from test_iniciar_captura import BASH, VPS, _script

pytestmark = pytest.mark.skipif(BASH is None, reason="bash indisponivel")

COMANDO = ["--user", "--scope", "--collect", "--unit=besave-lojas-robo", "-p", "KillSignal=SIGINT", "-p",
           "TimeoutStopSec=30", "--"]


class Lojas:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.dir = raiz / "capture-store-pages"
        self.est = raiz / "estado"
        self.est.mkdir()
        e = self.est.as_posix()
        self.py = self.dir / ".venv" / "bin" / "python"
        _script(self.py, f'echo "$@" >> "{e}/py.log"\nexit 0\n')
        bin_ = raiz / "bin"
        self.ordem = f"{e}/ordem.log"
        _script(bin_ / "systemctl", f'''echo "systemctl $*" >> "{self.ordem}"
[ "$*" = "--user is-active --quiet besave-lojas-robo.scope" ] && [ -e "{e}/scope_vivo" ]
''')
        _script(bin_ / "systemd-run", "exit 0\n")
        _script(bin_ / "tmux", f'''echo "$@" >> "{e}/tmux.log"
case " $* " in *" new-session "*) echo "tmux new-session" >> "{self.ordem}";; esac
exit 0
''')
        self.env = {
            **os.environ,
            "BESAVE_LOJAS_DIR": self.dir.as_posix(),
            "BESAVE_SYSTEMCTL": (bin_ / "systemctl").as_posix(),
            "BESAVE_SYSTEMD_RUN": (bin_ / "systemd-run").as_posix(),
            "BESAVE_TMUX": (bin_ / "tmux").as_posix(),
            "XDG_RUNTIME_DIR": e,
        }

    def log(self, nome):
        arq = self.est / nome
        return arq.read_text(encoding="utf-8") if arq.exists() else ""

    def rodar(self, *args, **env):
        return subprocess.run([BASH, (VPS / "iniciar_lojas.sh").as_posix(), *args], env={**self.env, **env},
                              capture_output=True, text=True, timeout=60, check=False)


@pytest.fixture
def amb(tmp_path):
    return Lojas(tmp_path)


def test_esc01_comando_montado_inteiro(amb):
    r = amb.rodar()
    assert r.returncode == 0, r.stderr
    linha = next(x for x in amb.log("tmux.log").splitlines() if "new-session" in x)
    tokens = linha.split()
    i = tokens.index(amb.env["BESAVE_SYSTEMD_RUN"])
    assert tokens[i + 1:i + 1 + len(COMANDO)] == COMANDO
    cauda = tokens[i + 1 + len(COMANDO):]
    assert cauda[0].endswith("/capture-store-pages/.venv/bin/python")
    assert cauda[1:] == ["-u", "main.py", "--monitorar", "--sem-perguntas"]
    assert "interno" in tokens[:i] and "DISPLAY=:1" in tokens[:i]
    # sessao, diretorio e log do robo das lojas
    assert "besave-lojas" in tokens[:i]
    assert any(t.endswith("/capture-store-pages/destino/log/main_monitorar.log") for t in tokens[:i])


def test_esc02_ordem_is_active_reset_failed_revert_tmux(amb):
    r = amb.rodar()
    assert r.returncode == 0, r.stderr
    assert amb.log("ordem.log").splitlines() == [
        "systemctl --user is-active --quiet besave-lojas-robo.scope",
        "systemctl --user reset-failed besave-lojas-robo.scope",
        "systemctl --user revert besave-lojas-robo.scope",
        "tmux new-session",
    ]


def test_esc02_scope_ativo_recusa_sem_lancar_nem_limpar(amb):
    (amb.est / "scope_vivo").write_text("", encoding="utf-8")
    r = amb.rodar()
    assert r.returncode != 0
    assert "besave-lojas-robo.scope ainda existe" in r.stderr
    assert amb.log("ordem.log").splitlines() == ["systemctl --user is-active --quiet besave-lojas-robo.scope"]
    assert "new-session" not in amb.log("tmux.log")


def test_sem_python_do_venv_aborta(amb):
    r = amb.rodar(BESAVE_PY=(amb.raiz / "nao-existe").as_posix())
    assert r.returncode != 0 and "ABORTADO" in r.stderr
    assert amb.log("ordem.log") == ""


def test_aguardar_devolve_o_codigo_do_robo(amb):
    (amb.est / "besave-besave-lojas.rc").write_text("137\n", encoding="utf-8")
    # `iniciar` apaga o arquivo de rc; o tmux falso nao roda o robo, entao o rc fica ausente (=1)
    r = amb.rodar("--aguardar")
    assert r.returncode == 1
    assert "wait-for besave-besave-lojas" in amb.log("tmux.log")


def test_sem_systemd_run_sobe_direto_e_avisa(amb):
    r = amb.rodar(BESAVE_SYSTEMD_RUN="/nao/existe/systemd-run")
    assert r.returncode == 0, r.stderr
    assert "SEM teto de memoria" in r.stderr
    tmux = amb.log("tmux.log")
    assert "systemd-run" not in tmux and "main.py --monitorar --sem-perguntas" in tmux
