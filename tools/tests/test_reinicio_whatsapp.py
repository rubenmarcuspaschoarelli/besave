"""BSV-54 REI-01..06: reiniciar_whatsapp.sh com systemctl, journalctl, ps, log e Python falsos
(nada real e reiniciado nem enviado)."""
import os
import re
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
        copia = (self.chat / "user_data.copia").as_posix()
        # systemctl: is-active le 'estado'; stop deixa inactive; start troca para 'estado_depois' e cria o log
        # novo. stop e start anotam em eventos.log se a copia da sessao ja existia (ordem stop, copia, start).
        _script(bin_ / "systemctl", f'''echo "$@" >> "{e}/systemctl.log"
copia_agora() {{ if [ -e "{copia}/copiada_em" ]; then echo "copia:$(cat "{copia}/copiada_em")"; else echo "copia:ausente"; fi; }}
case " $* " in
  *" is-active "*) cat "{e}/estado"; exit 0;;
  *" stop "*)
    echo "$*" >> "{e}/eventos.log"; copia_agora >> "{e}/eventos.log"
    [ -e "{e}/stop_rc" ] && exit "$(cat "{e}/stop_rc")"
    echo inactive > "{e}/estado"
    exit 0;;
  *" start "*)
    echo "$*" >> "{e}/eventos.log"; copia_agora >> "{e}/eventos.log"
    [ -e "{e}/start_rc" ] && exit "$(cat "{e}/start_rc")"
    cp "{e}/estado_depois" "{e}/estado"
    nome=$(cat "{e}/log_novo_nome" 2>/dev/null || echo run_captura_05_11_053001.log)
    [ -e "{e}/log_novo" ] && cp "{e}/log_novo" "{log_dir}/$nome"
    exit 0;;
esac
exit 0
''')
        _script(bin_ / "journalctl", f'cat "{e}/journal" 2>/dev/null; exit 0\n')
        _script(bin_ / "ps", f'echo "$@" >> "{e}/ps.log"; cat "{e}/ps" 2>/dev/null; exit 0\n')
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
        """Parou e partiu a unidade (BSV-67: stop + copia + start no lugar do restart)."""
        linhas = self.ler("systemctl.log").splitlines()
        return any(" start " in f" {x} " for x in linhas) and any(" stop " in f" {x} " for x in linhas)


@pytest.fixture
def amb(tmp_path):
    return Ambiente(tmp_path)


def test_partida_confirmada_nao_avisa(amb):  # REI-01
    amb.arquivo("log_novo", "Grupo aberto\n")
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
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0 and amb.avisos == []


def test_log_novo_sem_grupo_aberto_nao_confirma(amb):  # REI-07: 08/11, laco de QR
    amb.arquivo("log_novo", "[monitor] Oracle: conectado.\n"
                            "[browser] Aguardando o WhatsApp Web carregar...\n")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "sem 'Grupo aberto'" in amb.avisos[0]
    assert "OK:" not in r.stdout


def test_sem_broken_pipe_no_stderr(amb):  # REI-08
    # o systemd roda a unidade com SIGPIPE ignorado (IgnoreSIGPIPE=yes): `printf lista | grep -q` entao
    # escreve "write error: Broken pipe" quando a lista passa de 64 KB (buffer do pipe) e o grep sai no 1o acerto
    for i in range(500):
        (amb.chat / "log" / f"run_captura_01_01_{i:06d}_{'x' * 200}.log").write_text("antigo", encoding="utf-8")
    amb.arquivo("log_novo", "Grupo aberto\n")
    script = (VPS / "reiniciar_whatsapp.sh").as_posix()
    r = subprocess.run([BASH, "-c", f"trap '' PIPE; exec bash {script}"], env=amb.env,
                       check=False, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Broken pipe" not in r.stderr and "write error" not in r.stderr


def test_partida_abortada_avisa_com_o_motivo(amb):  # REI-03
    amb.arquivo("log_novo", "=== Lancador ===\n")
    amb.arquivo("journal", "ABORTADO: o perfil user_data esta travado. Rode encerrar_captura.sh e tente de novo.\n")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1
    assert "ABORTADO: o perfil user_data esta travado" in amb.avisos[0]


def test_unidade_que_nao_sobe_avisa(amb):  # REI-04
    amb.arquivo("estado_depois", "failed")
    amb.arquivo("log_novo", "[browser] Grupo aberto, painel pronto.\n")
    r = amb.rodar()  # mesmo com 'Grupo aberto' no log, unidade failed nao confirma
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "failed" in amb.avisos[0]


def test_start_que_falha_avisa(amb):  # REI-04b (BSV-67: o restart virou stop + copia + start)
    amb.arquivo("start_rc", "1")
    r = amb.rodar()
    assert r.returncode != 0
    assert len(amb.avisos) == 1 and "o start de besave-captura-whatsapp.service falhou" in amb.avisos[0]


def test_unidade_parada_de_proposito_nao_reinicia(tmp_path):  # REI-05
    amb = Ambiente(tmp_path, estado_antes="inactive")
    r = amb.rodar()
    assert r.returncode == 0
    assert not amb.reiniciou
    assert amb.avisos == []
    assert "inactive" in r.stdout


def test_unidade_failed_antes_ainda_reinicia(tmp_path):  # REI-05b: so 'inactive' e parada de proposito
    amb = Ambiente(tmp_path, estado_antes="failed")
    amb.arquivo("log_novo", "Grupo aberto\n")
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


# --- BSV-67 COP-01..03: copia da sessao boa entre o stop e o start ---------------------------------------

UNID = "besave-captura-whatsapp.service"
FICAM = ["Default/Preferences", "Default/IndexedDB/https_web.whatsapp.com_0.indexeddb.leveldb/000003.log",
         "Default/Local Storage/leveldb/CURRENT", "Default/Service Worker/Database/MANIFEST", "Local State"]
CACHES = ["Default/Cache/Cache_Data/data_0", "Default/Code Cache/js/index", "Default/GPUCache/data_1",
          "GPUPersistentCache/index", "Default/Service Worker/CacheStorage/abc/index"]


def _perfil(amb):
    for rel in FICAM + CACHES + ["SingletonLock"]:
        arq = amb.chat / "user_data" / rel
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text("x" * 10, encoding="utf-8")


def _arquivos(raiz: Path):
    return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file())


def _log_parado(amb, texto):
    """Log da partida em andamento (o de maior mtime)."""
    p = amb.chat / "log" / "run_captura_05_11_000001.log"
    p.write_text(texto, encoding="utf-8")
    t = os.path.getmtime(amb.chat / "log" / "run_captura_04_11_053001.log") + 3600
    os.utime(p, (t, t))


def test_copia_sem_os_caches_entre_stop_e_start(amb):  # COP-01, COP-02
    _perfil(amb)
    _log_parado(amb, "[browser] Grupo aberto, painel de mensagens pronto.\n")
    velha = amb.chat / "user_data.copia"
    velha.mkdir()
    (velha / "restaurada_em").write_text("2026-11-26T10:00:00Z", encoding="utf-8")
    (velha / "arquivo_da_copia_velha").write_text("v", encoding="utf-8")
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    eventos = amb.ler("eventos.log").splitlines()
    assert eventos[0] == f"--user stop {UNID}" and eventos[1] == "copia:ausente"
    assert eventos[2] == f"--user start {UNID}" and re.fullmatch(r"copia:\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", eventos[3])
    assert len(eventos) == 4
    assert _arquivos(amb.chat / "user_data.copia") == sorted(FICAM + ["copiada_em"])   # sem restaurada_em
    assert not (amb.chat / "user_data.copia.nova").exists() and not (amb.chat / "user_data.copia.velha").exists()
    assert re.search(r"\[reinicio\] .* copia da sessao: \d+ MB em \d+ s", r.stdout)
    assert amb.avisos == []
    assert _arquivos(amb.chat / "user_data") == sorted(FICAM + CACHES + ["SingletonLock"])  # perfil intocado


def test_sem_grupo_aberto_na_partida_parada_nao_copia(amb):  # COP-02
    _perfil(amb)
    _log_parado(amb, "[browser] Aguardando o WhatsApp Web carregar...\n")   # o de ontem tem Grupo aberto
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (amb.chat / "user_data.copia").exists()
    assert amb.ler("eventos.log").splitlines() == [f"--user stop {UNID}", "copia:ausente",
                                                    f"--user start {UNID}", "copia:ausente"]
    assert "copia da sessao: pulada" in r.stdout


def test_copia_que_falha_avisa_e_parte_mesmo_assim(amb):  # COP-03
    _perfil(amb)
    _log_parado(amb, "Grupo aberto\n")
    anterior = amb.chat / "user_data.copia"
    anterior.mkdir()
    (anterior / "copiada_em").write_text("2026-11-26T08:30:00Z", encoding="utf-8")
    falso = amb.est.parent / "bin_tar"
    _script(falso / "tar", "exit 2\n")
    amb.env["PATH"] = falso.as_posix() + os.pathsep + amb.env["PATH"]
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    assert amb.ler("eventos.log").splitlines() == [f"--user stop {UNID}", "copia:2026-11-26T08:30:00Z",
                                                    f"--user start {UNID}", "copia:2026-11-26T08:30:00Z"]
    assert amb.avisos == [("-m wa.avisar Reinicio diario do robo do WhatsApp: a copia da sessao falhou (leitura do "
                          "perfil; a anterior continua valendo); a captura parte mesmo assim.")]
    assert not (amb.chat / "user_data.copia.nova").exists()


def test_stop_que_falha_nao_copia_e_parte(amb):  # COP-01: copia so com a unidade parada (regra 2)
    _perfil(amb)
    _log_parado(amb, "Grupo aberto\n")
    amb.arquivo("stop_rc", "1")
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert not (amb.chat / "user_data.copia").exists()
    assert amb.ler("eventos.log").splitlines()[2] == f"--user start {UNID}"
    assert amb.avisos == [("-m wa.avisar Reinicio diario do robo do WhatsApp: o stop de besave-captura-whatsapp.service "
                          "falhou (estado: active); sem copia da sessao.")]
    assert r.returncode == 0


def _perfil_como_o_bash_ve(amb):
    raiz = subprocess.run([BASH, "-c", f'cd "{amb.chat.as_posix()}" && pwd -P'], check=False, capture_output=True,
                          text=True).stdout.strip()
    return f"--user-data-dir={raiz}/user_data"


@pytest.mark.parametrize("depois", [" --no-first-run", ""])     # perfil no meio ou no fim da linha
def test_perfil_ainda_em_uso_pula_a_copia_e_avisa(amb, depois):  # COP-03: Chromium orfao fora do scope (inst1, 28/11)
    _perfil(amb)
    _log_parado(amb, "Grupo aberto\n")
    perfil = _perfil_como_o_bash_ve(amb)
    amb.arquivo("ps", f"3400000 /usr/lib/chromium/chromium --type=browser {perfil}{depois}\n")
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (amb.chat / "user_data.copia").exists()
    assert amb.ler("ps.log").splitlines() == ["-eo rss=,args=", "-eo rss=,args="]   # passo 2 e antes da copia
    assert re.search(r"^\[reinicio\] \d\d/\d\d/\d{4} \d\d:\d\d:\d\d copia da sessao: pulada \(perfil ainda em uso "
                     r"por 1 processo\(s\)\)$", r.stdout, re.MULTILINE)
    assert amb.avisos == [("-m wa.avisar Reinicio diario do robo do WhatsApp: a copia da sessao falhou (perfil ainda "
                           "em uso por 1 processo(s); a anterior continua valendo); a captura parte mesmo assim.")]
    assert amb.ler("eventos.log").splitlines()[2] == f"--user start {UNID}"


def test_outros_perfis_no_ps_nao_seguram_a_copia(amb):  # COP-02: so o caminho exato do perfil conta
    _perfil(amb)
    _log_parado(amb, "Grupo aberto\n")
    perfil = _perfil_como_o_bash_ve(amb)
    amb.arquivo("ps", "\n".join([
        f"  90000 /usr/lib/chromium/chromium --type=renderer {perfil}.copia",
        "9990000 /usr/bin/chrome --type=renderer --user-data-dir=/outro/perfil",
        "",
    ]))
    amb.arquivo("log_novo", "Grupo aberto\n")
    r = amb.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    assert (amb.chat / "user_data.copia" / "copiada_em").exists()
    assert amb.avisos == []
    assert amb.ler("ps.log").splitlines() == ["-eo rss=,args=", "-eo rss=,args="]
