"""BSV-54 SCO-01..05: o robo do WhatsApp roda num scope systemd-run (teto de memoria e SIGINT),
com systemd-run, systemctl, tmux e Python falsos."""
import subprocess
from pathlib import Path

import pytest
from test_iniciar_captura import BASH, VPS, Ambiente, _script

pytestmark = pytest.mark.skipif(BASH is None, reason="bash indisponivel")

PREFIXO = ["--user", "--scope", "--collect", "--unit=besave-whatsapp-robo"]
FIXOS = ["-p", "KillSignal=SIGINT", "-p", "TimeoutStopSec=30", "--"]


@pytest.fixture
def amb(tmp_path):
    a = Ambiente(tmp_path)
    bin_ = tmp_path / "bin"
    _script(bin_ / "systemd-run", "exit 0\n")
    # systemctl falso: registra TODA chamada em ordem.log (junto com o tmux) e so diz "ativo" para o comando exato
    # do lancador com o arquivo scope_vivo presente (sem --user ou sem o nome do scope, o scope "nao existe")
    ordem = f"{a.est.as_posix()}/ordem.log"
    _script(bin_ / "systemctl", f'''echo "systemctl $*" >> "{ordem}"
[ "$*" = "--user is-active --quiet besave-whatsapp-robo.scope" ] && [ -e "{a.est.as_posix()}/scope_vivo" ]
''')
    _script(bin_ / "tmux", f'''echo "$@" >> "{a.est.as_posix()}/tmux.log"
case " $* " in *" new-session "*) echo "tmux new-session" >> "{ordem}"; touch "{a.est.as_posix()}/lancado";; esac
exit 0
''')
    a.env["BESAVE_SYSTEMD_RUN"] = (bin_ / "systemd-run").as_posix()
    a.env["BESAVE_SYSTEMCTL"] = (bin_ / "systemctl").as_posix()
    return a


def test_comando_montado_inteiro_com_padroes(amb):  # SCO-01 (lição 14: o comando inteiro)
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode == 0, r.stderr
    linha = next(x for x in amb.log("tmux.log").splitlines() if "new-session" in x)
    tokens = linha.split()
    i = tokens.index(amb.env["BESAVE_SYSTEMD_RUN"])
    cauda = tokens[i:]
    assert cauda[1:-3] == PREFIXO + ["-p", "MemoryHigh=3500M", "-p", "MemoryMax=4500M", "-p", "MemorySwapMax=0"] + FIXOS
    assert cauda[-3].endswith("/.venv/bin/python")
    assert cauda[-2:] == ["-u", "run_captura.py"]
    # roda dentro do `interno` (que grava o rc do systemd-run) e com o display do WhatsApp
    assert "interno" in tokens[:i] and "DISPLAY=:2" in tokens[:i]


def test_valores_do_environment_chegam_ao_scope(amb):  # SCO-02
    r = amb.rodar("iniciar_captura.sh", BESAVE_MEM_HIGH="1G", BESAVE_MEM_MAX="2G", BESAVE_MEM_SWAP_MAX="512M")
    assert r.returncode == 0, r.stderr
    tmux = amb.log("tmux.log")
    assert "-p MemoryHigh=1G -p MemoryMax=2G -p MemorySwapMax=512M -p KillSignal=SIGINT -p TimeoutStopSec=30 --" in tmux
    assert "3500M" not in tmux


def test_scope_sobrando_recusa_sem_lancar(amb):  # SCO-03
    (amb.est / "scope_vivo").write_text("", encoding="utf-8")
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "besave-whatsapp-robo.scope ainda existe" in r.stderr
    assert "new-session" not in amb.log("tmux.log")
    assert amb.log("py.log") == ""  # nem o contador chegou a rodar


def test_sem_systemd_run_sobe_direto_e_avisa(amb):  # SCO-04
    r = amb.rodar("iniciar_captura.sh", BESAVE_SYSTEMD_RUN="/nao/existe/systemd-run")
    assert r.returncode == 0, r.stderr
    assert "SEM teto de memoria" in r.stderr
    tmux = amb.log("tmux.log")
    assert "systemd-run" not in tmux and "run_captura.py" in tmux


def test_oom_kill_do_scope_vira_codigo_de_saida_da_unidade(amb, tmp_path):  # SCO-05
    # cadeia: systemd-run (rc 137 = SIGKILL do OOM) -> `interno` grava o rc -> `esperar` devolve -> unidade falha
    _script(tmp_path / "bin" / "systemd-run", "exit 137\n")
    estado = tmp_path / "estado-rc"
    estado.mkdir()
    env = {**amb.env, "XDG_RUNTIME_DIR": estado.as_posix()}
    interno = subprocess.run(
        [BASH, (VPS / "rodar_em_tmux.sh").as_posix(), "interno", "besave-whatsapp", (tmp_path / "x.log").as_posix(),
         amb.env["BESAVE_SYSTEMD_RUN"], *PREFIXO, "--", "python"],
        env=env, capture_output=True, text=True, timeout=60, check=False)
    assert interno.returncode == 137
    assert (estado / "besave-besave-whatsapp.rc").read_text(encoding="utf-8").strip() == "137"
    esperar = subprocess.run([BASH, (VPS / "rodar_em_tmux.sh").as_posix(), "esperar", "besave-whatsapp"],
                             env=env, capture_output=True, text=True, timeout=60, check=False)
    assert esperar.returncode == 137


def test_limpa_residuo_do_scope_antes_de_lancar(amb):  # SCO-06: reset-failed e revert, nesta ordem, antes do tmux
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode == 0, r.stderr
    assert amb.log("ordem.log").splitlines() == [
        "systemctl --user is-active --quiet besave-whatsapp-robo.scope",
        "systemctl --user reset-failed besave-whatsapp-robo.scope",
        "systemctl --user revert besave-whatsapp-robo.scope",
        "tmux new-session",
    ]


def test_scope_vivo_nao_e_tocado(amb):  # SCO-06b: nada de reset-failed/revert num scope ativo
    (amb.est / "scope_vivo").write_text("", encoding="utf-8")
    amb.rodar("iniciar_captura.sh")
    assert amb.log("ordem.log").splitlines() == ["systemctl --user is-active --quiet besave-whatsapp-robo.scope"]


def test_erro_do_systemd_run_vai_no_abortado(amb):  # SCO-07
    # o painel "morre": o tmux so grava a mensagem do systemd-run no log do dia e o robo nunca aparece vivo
    msg = "Failed to start transient scope unit: Unit besave-whatsapp-robo.scope was already loaded or has a fragment file."
    corpo = "\n".join([
        f'echo "$@" >> "{amb.est.as_posix()}/tmux.log"',
        # o log do dia e o argumento *.log da linha do tmux (o nome muda a cada partida)
        'for t in $*; do case "$t" in *.log) l="$t";; esac; done',
        'echo "linha anterior do log" >> "$l"',
        f'echo "{msg}" >> "$l"',
        "exit 0",
        "",
    ])
    _script(Path(amb.env["BESAVE_TMUX"]), corpo)
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    abortado = next(x for x in r.stderr.splitlines() if x.startswith("ABORTADO"))
    assert "captura nao subiu" in abortado and "already loaded or has a fragment file" in abortado
    assert "linha anterior" not in abortado  # e a ULTIMA linha, nao a primeira
