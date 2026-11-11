"""BSV-57 item 2 (inst1 11/11): a parada do robo das lojas manda SIGINT so ao python do scope, espera, e so entao
para o scope. systemctl, kill, sleep, cgroup e /proc falsos; sequencia de comandos comparada inteira (licao 14)."""
import os
import subprocess

import pytest
from test_iniciar_captura import BASH, VPS, _script

pytestmark = pytest.mark.skipif(BASH is None, reason="bash indisponivel")

CG = "/user.slice/app.slice/besave-lojas-robo.scope"


class Parada:
    def __init__(self, raiz, vivo_por=2):
        """vivo_por: quantas consultas `is-active` ainda dizem ativo (None = nunca morre, python congelado)."""
        self.raiz = raiz
        e = raiz / "estado"
        e.mkdir()
        self.ordem = e / "ordem.log"
        self.cgroup = raiz / "cgroup"
        self.proc = raiz / "proc"
        bin_ = raiz / "bin"
        self.vivo_por = vivo_por
        cont = e / "consultas"
        cont.write_text("0", encoding="utf-8", newline=chr(10))
        limite = "999999" if vivo_por is None else str(vivo_por)
        _script(bin_ / "systemctl", f'''echo "systemctl $*" >> "{self.ordem.as_posix()}"
case "$*" in
  "--user show -p ControlGroup --value besave-lojas-robo.scope") echo "{CG}" ;;
  "--user is-active --quiet besave-lojas-robo.scope")
    n=$(cat "{cont.as_posix()}"); echo $((n + 1)) > "{cont.as_posix()}"
    [ "$n" -lt {limite} ]; exit $? ;;
esac
exit 0
''')
        _script(bin_ / "kill", f'echo "kill $*" >> "{self.ordem.as_posix()}"\nexit 0\n')
        _script(bin_ / "sleep", f'echo "sleep $*" >> "{self.ordem.as_posix()}"\nexit 0\n')
        self.env = {
            **os.environ,
            "BESAVE_SYSTEMCTL": (bin_ / "systemctl").as_posix(), "BESAVE_KILL": (bin_ / "kill").as_posix(),
            "BESAVE_SLEEP": (bin_ / "sleep").as_posix(), "BESAVE_CGROUP_RAIZ": self.cgroup.as_posix(),
            "BESAVE_PROC_RAIZ": self.proc.as_posix(),
        }

    def processos(self, **comm_por_pid):
        pasta = self.cgroup / CG.lstrip("/")
        pasta.mkdir(parents=True, exist_ok=True)
        pids = sorted(int(k[1:]) for k in comm_por_pid)
        (pasta / "cgroup.procs").write_text("".join(f"{p}" + chr(10) for p in pids), encoding="utf-8", newline=chr(10))
        for k, comm in comm_por_pid.items():
            d = self.proc / k[1:]
            d.mkdir(parents=True, exist_ok=True)
            (d / "comm").write_text(comm + chr(10), encoding="utf-8", newline=chr(10))

    def rodar(self, *args):
        r = subprocess.run([BASH, (VPS / "parar_scope.sh").as_posix(), *args], env=self.env, capture_output=True,
                           text=True, timeout=60, check=False)
        linhas = self.ordem.read_text(encoding="utf-8").splitlines() if self.ordem.exists() else []
        return r, linhas


SHOW = "systemctl --user show -p ControlGroup --value besave-lojas-robo.scope"
ATIVO = "systemctl --user is-active --quiet besave-lojas-robo.scope"
STOP = "systemctl --user stop besave-lojas-robo.scope"


def test_sigint_so_no_python_espera_sair_e_so_entao_para_o_scope(tmp_path):
    p = Parada(tmp_path, vivo_por=2)
    p.processos(p10="python", p11="node", p12="chrome", p13="chrome")
    r, linhas = p.rodar("besave-lojas-robo")
    assert r.returncode == 0, r.stderr
    assert linhas == [SHOW, "kill -INT 10", ATIVO, "sleep 1", ATIVO, "sleep 1", ATIVO, STOP]


def test_python_congelado_espera_o_prazo_inteiro_e_depois_para_o_scope(tmp_path):
    p = Parada(tmp_path, vivo_por=None)
    p.processos(p10="python")
    r, linhas = p.rodar("besave-lojas-robo", "3")
    assert r.returncode == 0, r.stderr
    assert linhas == [SHOW, "kill -INT 10", ATIVO, "sleep 1", ATIVO, "sleep 1", ATIVO, "sleep 1", STOP]


def test_prazo_padrao_e_20_segundos(tmp_path):
    p = Parada(tmp_path, vivo_por=None)
    p.processos(p10="python")
    _, linhas = p.rodar("besave-lojas-robo")
    assert linhas.count("sleep 1") == 20 and linhas[-1] == STOP


def test_scope_inexistente_so_tenta_o_stop_e_sai_0(tmp_path):
    p = Parada(tmp_path)                                       # sem cgroup.procs: nada a sinalizar
    r, linhas = p.rodar("besave-lojas-robo")
    assert r.returncode == 0 and linhas == [SHOW, STOP]


def test_nunca_sinaliza_processo_que_nao_e_python(tmp_path):
    p = Parada(tmp_path, vivo_por=0)
    p.processos(p11="node", p12="chrome", p14="tmux: server")
    _, linhas = p.rodar("besave-lojas-robo")
    assert linhas == [SHOW, ATIVO, STOP]                       # nenhum kill


def test_g11_so_comm_que_comeca_com_python_recebe_sigint(tmp_path):
    p = Parada(tmp_path, vivo_por=0)
    p.processos(p10="ipython", p11="mypython", p12="python3.12")
    _, linhas = p.rodar("besave-lojas-robo")
    assert linhas == [SHOW, "kill -INT 12", ATIVO, STOP]
