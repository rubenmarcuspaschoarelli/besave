"""SH-01..05: conferencias do iniciar_captura.sh / encerrar_captura.sh com
processos, tmux e Python simulados (nada real e lancado)."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

VPS = Path(__file__).resolve().parent.parent / "vps"
BASH = shutil.which("bash")
if BASH and "system32" in BASH.lower().replace("\\", "/"):  # bash.exe do WSL nao serve
    BASH = None

pytestmark = pytest.mark.skipif(BASH is None, reason="bash indisponivel")


def _script(caminho: Path, corpo: str):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8", newline="\n")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)


class Ambiente:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.chat = raiz / "capture-chat-groups"
        self.est = raiz / "estado"
        self.est.mkdir()
        (self.chat / "diag").mkdir(parents=True)
        (self.chat / "diag" / "checa_contador.py").write_text("", encoding="utf-8")
        (self.chat / "user_data").mkdir()
        self.py = self.chat / ".venv" / "bin" / "python"
        # python falso: registra os argumentos; checa_contador sai com o codigo de contador_rc
        _script(self.py, f'''echo "$@" >> "{self.est.as_posix()}/py.log"
case "$1" in *checa_contador.py) exit "$(cat "{self.est.as_posix()}/contador_rc" 2>/dev/null || echo 0)";; esac
''')
        bin_ = raiz / "bin"
        e = self.est.as_posix()
        _script(bin_ / "pgrep", f'''padrao="${{@: -1}}"
case "$padrao" in
  *run_captura*) cat "{e}/pids_run" 2>/dev/null; [ -e "{e}/lancado" ] && echo 4242;;
  *user-data-dir*) cat "{e}/pids_perfil" 2>/dev/null;;
esac
exit 0
''')
        _script(bin_ / "tmux", f'''echo "$@" >> "{e}/tmux.log"
case " $* " in *" new-session "*) touch "{e}/lancado";; esac
exit 0
''')
        _script(bin_ / "kill", f'''echo "$@" >> "{e}/kill.log"
alvo="${{@: -1}}"
for f in "{e}/pids_run" "{e}/pids_perfil"; do
  [ -e "$f" ] && grep -vx "$alvo" "$f" > "$f.tmp"; [ -e "$f.tmp" ] && mv "$f.tmp" "$f"
done
exit 0
''')
        self.env = {
            **os.environ,
            "BESAVE_CHAT_DIR": self.chat.as_posix(),
            "BESAVE_PGREP": (bin_ / "pgrep").as_posix(),
            "BESAVE_TMUX": (bin_ / "tmux").as_posix(),
            "BESAVE_KILL": (bin_ / "kill").as_posix(),
            "BESAVE_ESPERA": "0",
            "BESAVE_GRACA": "1",
            "XDG_RUNTIME_DIR": e,
            "BESAVE_UNIDADE": "besave-unidade-inexistente-teste.service",
        }

    def pids(self, run=(), perfil=()):
        (self.est / "pids_run").write_text("".join(f"{p}\n" for p in run), encoding="utf-8")
        (self.est / "pids_perfil").write_text("".join(f"{p}\n" for p in perfil), encoding="utf-8")

    def contador_atrasado(self):
        (self.est / "contador_rc").write_text("1", encoding="utf-8")

    def log(self, nome):
        arq = self.est / nome
        return arq.read_text(encoding="utf-8") if arq.exists() else ""

    def rodar(self, script, *args, **env):
        return subprocess.run(
            [BASH, (VPS / script).as_posix(), *args],
            env={**self.env, **env}, capture_output=True, text=True, timeout=60, check=False,
        )


@pytest.fixture
def amb(tmp_path):
    return Ambiente(tmp_path)


def test_sh01_dois_processos_recusa_sem_lancar(amb):
    amb.pids(run=[111, 222])
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "Ja existe captura rodando" in r.stderr
    assert "new-session" not in amb.log("tmux.log")
    assert amb.log("py.log") == ""  # nem o contador chegou a rodar


def test_sh01_um_processo_tambem_recusa(amb):
    amb.pids(run=[111])
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "Ja existe captura rodando" in r.stderr
    assert "new-session" not in amb.log("tmux.log")


def test_sh02_perfil_preso_recusa_sem_lancar(amb):
    amb.pids(perfil=[333])
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "user_data esta travado" in r.stderr
    assert "new-session" not in amb.log("tmux.log")
    assert amb.log("py.log") == ""


def test_sh03_contador_atrasado_recusa_sem_lancar(amb):
    amb.contador_atrasado()
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "checa_contador.py" in amb.log("py.log")
    assert "contador atrasado" in r.stderr
    assert "new-session" not in amb.log("tmux.log")


def test_sh04_tudo_ok_lanca_no_tmux_com_display(amb):
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode == 0, r.stderr
    tmux = amb.log("tmux.log")
    assert "-L besave-whatsapp new-session -d -s besave-whatsapp" in tmux
    assert " -c " in tmux and "capture-chat-groups" in tmux
    assert "DISPLAY=:1" in tmux
    assert "run_captura.py" in tmux
    assert "-u" in tmux


def test_sh04_processo_que_morre_no_inicio_falha(amb):
    # o tmux "sobe", mas o robo nao aparece vivo
    _script(Path(amb.env["BESAVE_TMUX"]), 'echo "$@" >> "' + amb.est.as_posix() + '/tmux.log"\nexit 0\n')
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode != 0
    assert "captura nao subiu" in r.stderr


def test_sh05_encerrar_mata_so_o_que_casa_e_informa(amb):
    amb.pids(run=[111], perfil=[333, 334])
    r = amb.rodar("encerrar_captura.sh")
    assert r.returncode == 0, r.stderr
    mortos = amb.log("kill.log")
    for pid in ("111", "333", "334"):
        assert pid in mortos
    assert "-L besave-whatsapp kill-session -t besave-whatsapp" in amb.log("tmux.log")
    assert "Restantes: python=0  navegador=0" in r.stdout


def test_sh05_nada_rodando(amb):
    r = amb.rodar("encerrar_captura.sh")
    assert r.returncode == 0
    assert amb.log("kill.log") == ""
    assert "Nada rodando" in r.stdout


def test_sh05_sobrou_processo_avisa(amb):
    amb.pids(run=[111])
    _script(Path(amb.env["BESAVE_KILL"]), "exit 0\n")  # kill que nao mata
    r = amb.rodar("encerrar_captura.sh")
    assert r.returncode != 0
    assert "ATENCAO" in r.stderr


def test_esperar_devolve_o_codigo_do_robo(amb):
    # tmux wait-for falso volta na hora; o codigo vem do arquivo gravado pelo robo
    (amb.est / "besave-besave-whatsapp.rc").write_text("3\n", encoding="utf-8")
    r = amb.rodar("rodar_em_tmux.sh", "esperar", "besave-whatsapp")
    assert r.returncode == 3


def test_executar_inicia_e_devolve_o_codigo_do_robo(amb):
    (amb.est / "besave-besave-lojas.rc").write_text("0\n", encoding="utf-8")
    r = amb.rodar("rodar_em_tmux.sh", "executar", "besave-lojas", str(amb.chat), str(amb.est / "x.log"), "/bin/true")
    assert r.returncode == 1  # iniciar apaga o codigo antigo; o tmux falso nunca grava outro
    tmux = amb.log("tmux.log")
    assert "-L besave-lojas new-session -d -s besave-lojas" in tmux
    assert "-L besave-lojas wait-for besave-besave-lojas" in tmux


def test_sh05_encerrar_usa_sigint_antes_de_sigkill(amb):
    amb.pids(run=[111])
    amb.rodar("encerrar_captura.sh")
    assert amb.log("kill.log").splitlines()[0] == "-INT 111"


def test_sh01_pega_run_com_argumentos_e_sem_u(amb):
    # o regex real (nao o glob do pgrep falso) casa as formas de linha de comando do robo
    import re
    padrao = None
    for linha in (VPS / "iniciar_captura.sh").read_text(encoding="utf-8").splitlines():
        if linha.startswith("PADRAO_RUN="):
            padrao = re.compile(linha.split("'")[1])
    assert padrao
    casam = ["/srv/.venv/bin/python -u run_captura.py", "python3 run_captura.py --max 40",
             "/x/python -u run_captura.py --seg-grupo 8"]
    nao_casam = ["bash /v/rodar_em_tmux.sh interno s l /x/python -u run_captura.py",
                 "tmux -L s new-session -d env DISPLAY=:1 /x/python -u run_captura.py", "vim run_captura.py"]
    assert all(padrao.search(c) for c in casam)
    assert not any(padrao.search(c) for c in nao_casam)


# --- rodar_em_tmux.sh: o fluxo que faz o Restart=on-failure funcionar (A4) -----

def _tmux_que_devolve(amb, rc):
    """tmux falso: 'wait-for CANAL' (sem -S) grava o codigo de saida do robo, como
    o `interno` faria, e acorda."""
    e = amb.est.as_posix()
    _script(amb.raiz / "bin" / "tmux", f'''echo "$@" >> "{e}/tmux.log"
case " $* " in
  *" new-session "*) touch "{e}/lancado";;
  *" wait-for -S "*) ;;
  *" wait-for "*) echo {rc} > "{e}/besave-besave-whatsapp.rc";;
esac
exit 0
''')


def test_sh06_interno_propaga_codigo_grava_log_e_sinaliza(amb):
    log = amb.est / "robo.log"
    r = amb.rodar("rodar_em_tmux.sh", "interno", "sess", log.as_posix(), "sh", "-c", "echo linha-do-robo; exit 7")
    assert r.returncode == 7
    assert (amb.est / "besave-sess.rc").read_text().strip() == "7"
    assert "linha-do-robo" in log.read_text()
    assert "-L sess wait-for -S besave-sess" in amb.log("tmux.log")


def test_sh06_interno_acrescenta_ao_log(amb):
    log = amb.est / "robo.log"
    log.write_text("antes\n")
    amb.rodar("rodar_em_tmux.sh", "interno", "sess", log.as_posix(), "echo", "depois")
    assert log.read_text() == "antes\ndepois\n"


def test_sh06_esperar_sai_com_o_codigo_do_robo(amb):
    (amb.est / "besave-sess.rc").write_text("5\n")
    r = amb.rodar("rodar_em_tmux.sh", "esperar", "sess")
    assert r.returncode == 5
    assert "-L sess wait-for besave-sess" in amb.log("tmux.log")


def test_sh06_esperar_sem_arquivo_de_codigo_e_falha(amb):
    assert amb.rodar("rodar_em_tmux.sh", "esperar", "sess").returncode == 1


def test_sh06_iniciar_cria_sessao_propria_com_display_e_limpa_codigo_antigo(amb):
    (amb.est / "besave-sess.rc").write_text("0\n")
    r = amb.rodar("rodar_em_tmux.sh", "iniciar", "sess", amb.raiz.as_posix(), (amb.est / "x.log").as_posix(),
                  "echo", "oi", BESAVE_DISPLAY=":7")
    assert r.returncode == 0
    assert not (amb.est / "besave-sess.rc").exists()
    chamada = amb.log("tmux.log")
    assert "-L sess new-session -d -s sess" in chamada
    assert "DISPLAY=:7" in chamada and "interno" in chamada


def test_sh06_executar_inicia_e_espera(amb):
    (amb.est / "besave-sess.rc").write_text("0\n")
    e = amb.est.as_posix()
    _script(amb.raiz / "bin" / "tmux", f'''echo "$@" >> "{e}/tmux.log"
case " $* " in *" wait-for "*) echo 3 > "{e}/besave-sess.rc";; esac
exit 0
''')
    r = amb.rodar("rodar_em_tmux.sh", "executar", "sess", amb.raiz.as_posix(), (amb.est / "x.log").as_posix(), "echo", "oi")
    assert r.returncode == 3
    linhas = amb.log("tmux.log").splitlines()
    assert any("new-session" in l for l in linhas) and any("wait-for besave-sess" in l for l in linhas)


def test_sh06_aguardar_espera_e_devolve_o_codigo_do_robo(amb):
    _tmux_que_devolve(amb, 9)
    r = amb.rodar("iniciar_captura.sh", "--aguardar")
    assert r.returncode == 9
    assert "wait-for besave-besave-whatsapp" in amb.log("tmux.log").replace("-L besave-whatsapp ", "")


def test_sh06_sem_aguardar_volta_sem_esperar(amb):
    r = amb.rodar("iniciar_captura.sh")
    assert r.returncode == 0
    assert "wait-for" not in amb.log("tmux.log")
