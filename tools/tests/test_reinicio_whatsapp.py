"""BSV-54 REI-01..06: reiniciar_whatsapp.sh com systemctl, journalctl, ps, log e Python falsos
(nada real e reiniciado nem enviado)."""
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


def _script(caminho: Path, corpo: str):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8", newline="\n")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)


class Ambiente:
    def __init__(self, raiz: Path, estado_antes="active", estado_depois="active"):
        self.chat = raiz / "capture-chat-groups"
        self.est = raiz / "estado"
        self.est.mkdir()
        (self.chat / "log").mkdir(parents=True)
        (self.chat / "log" / "run_captura_04_11_053001.log").write_text("log de ontem: Grupo aberto\n", encoding="utf-8")
        (self.chat / "user_data").mkdir()
        e = self.est.as_posix()
        log_dir = (self.chat / "log").as_posix()
        self.estado(estado_antes)
        self.arquivo("estado_depois", estado_depois)
        bin_ = raiz / "bin"
        # systemctl: is-active le 'estado'; restart troca para 'estado_depois' e cria o log novo
        _script(bin_ / "systemctl", f'''echo "$@" >> "{e}/systemctl.log"
case " $* " in
  *" is-active "*) cat "{e}/estado"; exit 0;;
  *" restart "*)
    [ -e "{e}/restart_rc" ] && exit "$(cat "{e}/restart_rc")"
    cp "{e}/estado_depois" "{e}/estado"
    nome=$(cat "{e}/log_novo_nome" 2>/dev/null || echo run_captura_05_11_053001.log)
    [ -e "{e}/log_novo" ] && cp "{e}/log_novo" "{log_dir}/$nome"
    exit 0;;
esac
exit 0
''')
        _script(bin_ / "journalctl", f'cat "{e}/journal" 2>/dev/null; exit 0\n')
        _script(bin_ / "ps", f'cat "{e}/ps" 2>/dev/null; exit 0\n')
        _script(self.chat / ".venv" / "bin" / "python", f'echo "$@" >> "{e}/py.log"\nexit 0\n')
        self.env = {
            **os.environ,
            "BESAVE_CHAT_DIR": self.chat.as_posix(),
            "BESAVE_SYSTEMCTL": (bin_ / "systemctl").as_posix(),
            "BESAVE_JOURNALCTL": (bin_ / "journalctl").as_posix(),
            "BESAVE_PS": (bin_ / "ps").as_posix(),
            "BESAVE_ESPERA_MAX": "1",
            "BESAVE_INTERVALO": "1",
        }

    def estado(self, valor):
        self.arquivo("estado", valor)

    def arquivo(self, nome, texto):
        (self.est / nome).write_text(texto, encoding="utf-8", newline="\n")

    def ler(self, nome):
        arq = self.est / nome
        return arq.read_text(encoding="utf-8") if arq.exists() else ""

    def rodar(self):
        return subprocess.run([BASH, (VPS / "reiniciar_whatsapp.sh").as_posix()], env=self.env,
                              check=False, capture_output=True, text=True, timeout=60)

    @property
    def avisos(self):
        return [linha for linha in self.ler("py.log").splitlines() if "wa.avisar" in linha]

    @property
    def reiniciou(self):
        return any(" restart " in f" {linha} " for linha in self.ler("systemctl.log").splitlines())


@pytest.fixture
def amb(tmp_path):
    return Ambiente(tmp_path)


def test_partida_confirmada_nao_avisa(amb):  # REI-01
    amb.arquivo("log_novo", "[monitor] Retomando contador de ofertas em ultimo_id_processado=46041.\nGrupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    assert amb.reiniciou
    assert amb.avisos == []
    assert "OK" in r.stdout


def test_grupo_aberto_tambem_confirma(amb):  # REI-01b
    amb.arquivo("log_novo", "[browser] Grupo aberto, painel de mensagens pronto.\n")
    r = amb.rodar()
    assert r.returncode == 0 and amb.avisos == []


def test_log_de_ontem_nao_confirma(amb):  # REI-02: so o log NOVO conta
    # o log antigo ja tem "Grupo aberto"; o restart nao gerou log novo nem journal
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "sem 'Grupo aberto'" in amb.avisos[0]


def test_log_novo_com_sufixo_nao_se_confunde_com_o_antigo(amb):  # REI-02b: X_2.log e novo, mesmo existindo X.log
    amb.arquivo("log_novo_nome", "run_captura_04_11_053001_2.log")
    amb.arquivo("log_novo", "[monitor] Retomando contador de ofertas em ultimo_id_processado=3.\nGrupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0 and amb.avisos == []


def test_retomando_contador_sem_grupo_aberto_nao_confirma(amb):  # REI-07: 08/11, laco de QR
    amb.arquivo("log_novo", "[monitor] Retomando contador de ofertas em ultimo_id_processado=9.\n"
                            "[browser] Aguardando o WhatsApp Web carregar...\n")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "sem 'Grupo aberto'" in amb.avisos[0]
    assert "OK:" not in r.stdout


def test_sem_broken_pipe_no_stderr(amb):  # REI-08
    amb.arquivo("log_novo", "Grupo aberto\n")
    assert "Broken pipe" not in amb.rodar().stderr


def test_contador_atrasado_avisa_com_o_motivo(amb):  # REI-03
    amb.arquivo("log_novo", "=== Lancador ===\n")
    amb.arquivo("journal", "ABORTADO: contador atrasado - corrija o config (com backup) antes de relancar.\n")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1
    assert "ABORTADO: contador atrasado" in amb.avisos[0]


def test_unidade_que_nao_sobe_avisa(amb):  # REI-04
    amb.arquivo("estado_depois", "failed")
    amb.arquivo("log_novo", "[monitor] Retomando contador de ofertas em ultimo_id_processado=1.\n[browser] Grupo aberto, painel pronto.\n")
    r = amb.rodar()  # mesmo com 'Grupo aberto' no log, unidade failed nao confirma
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "failed" in amb.avisos[0]


def test_restart_que_falha_avisa(amb):  # REI-04b
    amb.arquivo("restart_rc", "1")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "restart" in amb.avisos[0]


def test_unidade_parada_de_proposito_nao_reinicia(tmp_path):  # REI-05
    amb = Ambiente(tmp_path, estado_antes="inactive")
    r = amb.rodar()
    assert r.returncode == 0
    assert not amb.reiniciou
    assert amb.avisos == []
    assert "inactive" in r.stdout


def test_unidade_failed_antes_ainda_reinicia(tmp_path):  # REI-05b: so 'inactive' e parada de proposito
    amb = Ambiente(tmp_path, estado_antes="failed")
    amb.arquivo("log_novo", "[monitor] Retomando contador de ofertas em ultimo_id_processado=2.\nGrupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0 and amb.reiniciou


def test_registra_o_maior_rss_do_perfil(amb):  # REI-06
    # o caminho como o bash o enxerga (pwd -P), igual ao do script
    raiz = subprocess.run([BASH, "-c", f'cd "{amb.chat.as_posix()}" && pwd -P'], check=False, capture_output=True, text=True).stdout.strip()
    perfil = f"--user-data-dir={raiz}/user_data"
    amb.arquivo("ps", "\n".join([
        f"6710000 /usr/bin/chrome --type=renderer {perfil}",
        f"  120000 /usr/bin/chrome --type=gpu {perfil}",
        "9990000 /usr/bin/chrome --type=renderer --user-data-dir=/outro/perfil",
        "",
    ]))
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert "6552 MB" in r.stdout  # 6710000 KB / 1024; o de outro perfil nao conta


def test_nao_mata_processo_por_nome():  # regra 1: so systemctl
    corpo = (VPS / "reiniciar_whatsapp.sh").read_text(encoding="utf-8")
    for proibido in ("pkill", "killall", "kill ", "encerrar_captura"):
        assert proibido not in corpo
