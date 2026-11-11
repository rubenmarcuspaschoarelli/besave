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
    # BSV-57 item 2: o stop manda SIGINT so ao python (parar_scope.sh); `systemctl stop scope` direto deixava a
    # unidade em `failed`. Comparado inteiro (licao 14); 20 s do python + 30 s do scope + folga cabem no timeout.
    assert servico["ExecStop"] == "-/srv/besave/repo/tools/vps/parar_scope.sh besave-lojas-robo"
    assert servico["TimeoutStopSec"] == "60"
    # BSV-55: --sem-perguntas, senao o arranque para num input() que ninguem responde
    texto = (VPS / "iniciar_lojas.sh").read_text(encoding="utf-8")
    assert "main.py --monitorar --sem-perguntas" in texto


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_depende_da_tela_vnc(unidade):
    unit = _ler(unidade)["Unit"]
    tela = f"besave-vnc@{TELA[unidade.name]}.service"
    assert unit["After"] == tela
    assert unit["Requires"] == tela


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_nao_fica_failed_por_falha_de_partida(unidade):
    cfg = _ler(unidade)
    assert cfg["Unit"]["StartLimitIntervalSec"] == "0"  # sem limite: nunca 'start-limit-hit'
    assert int(cfg["Service"]["RestartSec"]) >= 30
    pre = cfg["Service"]["ExecStartPre"]
    assert f"/tmp/.X11-unix/X{TELA[unidade.name]} ]" in pre  # espera a SUA tela existir de fato
    assert "$$(" in pre  # systemd consome '$' simples


def test_vnc_e_unidade_modelo_da_tela_n_so_em_localhost():
    cfg = _ler(VPS / "systemd" / "besave-vnc@.service")
    servico = cfg["Service"]
    assert servico["Restart"] == "on-failure"
    assert servico["ExecStart"].endswith("/tools/vps/iniciar_vnc.sh %i")  # tela :%i, porta 590%i
    assert servico["ExecStop"].endswith("vncserver -kill :%i")
    assert servico["RestartPreventExitStatus"] == "78"  # sem senha: nao reinicia em laco
    assert cfg["Unit"]["StartLimitIntervalSec"] == "0"
    assert cfg["Install"]["WantedBy"] == "default.target"


def test_readme_explica_o_linger_e_a_unidade_do_vnc():
    leia = (VPS / "README.md").read_text(encoding="utf-8")
    assert "loginctl enable-linger besave" in leia
    assert "besave-vnc" in leia
    assert re.search(r"reboot", leia)


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_para_com_sigint_e_da_tempo_de_salvar(unidade):
    servico = _ler(unidade)["Service"]
    assert servico["KillSignal"] == "SIGINT"  # SIGTERM nao roda o finally que salva o contador
    assert int(servico["TimeoutStopSec"]) >= 30


@pytest.mark.parametrize("unidade", ROBOS, ids=lambda u: u.name)
def test_robo_falha_se_a_tela_nao_aparece(unidade):
    pre = _ler(unidade)["Service"]["ExecStartPre"]
    assert not pre.startswith("-")  # sem '-': falha de verdade e o Restart= tenta de novo
    assert pre.rstrip("'").endswith("exit 1")


def test_vnc_detalhes_da_tela():
    servico = _ler(VPS / "systemd" / "besave-vnc@.service")["Service"]
    assert servico["ExecStartPre"].startswith("-")  # limpa tela velha, mas nao falha se nao ha
    assert servico["ExecStartPre"].endswith("vncserver -kill :%i")


# --- BSV-54: reinicio diario e teto de memoria --------------------------------
def test_timer_do_reinicio_a_cada_6h_sem_persistent():
    t = _ler(VPS / "systemd" / "besave-reinicio-whatsapp.timer")
    assert t["Timer"]["OnCalendar"] == "*-*-* 05,11,17,23:30:00"  # linha inteira: 05:30, 11:30, 17:30 e 23:30
    assert t["Timer"]["Persistent"] == "false"
    assert t["Install"]["WantedBy"] == "timers.target"


def test_service_do_reinicio_e_oneshot_e_chama_o_script():
    s = _ler(VPS / "systemd" / "besave-reinicio-whatsapp.service")["Service"]
    assert s["Type"] == "oneshot"
    assert s["ExecStart"].endswith("/tools/vps/reiniciar_whatsapp.sh")
    assert int(s["TimeoutStartSec"]) >= 240  # restart + 3 min de confirmacao


def test_whatsapp_teto_vem_do_environment_e_nao_da_unidade():
    # o painel do tmux fica fora da unidade (scope proprio): MemoryHigh/Max aqui nao pegariam o navegador
    servico = _ler(VPS / "systemd" / "besave-captura-whatsapp.service")["Service"]
    env = servico["Environment"].split()
    assert "BESAVE_MEM_HIGH=3500M" in env and "BESAVE_MEM_MAX=4500M" in env
    assert "BESAVE_MEM_SWAP_MAX=0" in env  # sem swap o MemoryMax vira thrashing, nao OOM-kill
    for chave in ("MemoryHigh", "MemoryMax"):
        assert chave not in servico
    assert servico["Restart"] == "on-failure"
    assert "MemoryMax" not in _ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"]


def test_whatsapp_execstop_para_o_scope_do_robo():
    servico = _ler(VPS / "systemd" / "besave-captura-whatsapp.service")["Service"]
    # '-' = scope ja ausente nao falha o stop; nada de encerrar_captura.sh (ele para a propria unidade)
    assert servico["ExecStop"] == "-/usr/bin/systemctl --user stop besave-whatsapp-robo.scope"
    assert int(servico["TimeoutStopSec"]) >= 40  # scope (30 s) + folga


def test_vigia_e_oneshot_com_timer_de_5_minutos():  # BSV-57 UNI-01
    servico = _ler(VPS / "systemd" / "besave-vigia-robos.service")["Service"]
    assert servico["Type"] == "oneshot"
    assert servico["ExecStart"] == "/usr/bin/python3 /srv/besave/repo/tools/vps/vigia_robos.py"
    assert (VPS / "vigia_robos.py").exists()
    timer = _ler(VPS / "systemd" / "besave-vigia-robos.timer")
    assert timer["Timer"]["OnUnitActiveSec"] == "5min"
    assert timer["Timer"]["OnBootSec"] == "5min"
    assert timer["Install"]["WantedBy"] == "timers.target"


def test_vigia_systemd_nao_mata_o_vigia_no_meio_de_dois_restarts():  # G13 (verifier ciclo 4)
    import vigia_falso  # noqa: F401  (poe vps/ no sys.path)
    import vigia_robos

    s = _ler(VPS / "systemd" / "besave-vigia-robos.service")["Service"]
    # cada systemctl pode levar TIMEOUT_SYSTEMCTL_S; 2 robos, cada um com restart + alguns comandos de leitura
    assert int(s["TimeoutStartSec"]) > 2 * vigia_robos.TIMEOUT_SYSTEMCTL_S + 60
    # um restart das lojas espera o stop (20 s do python + 30 s do scope) e o ExecStartPre (60 s)
    assert vigia_robos.TIMEOUT_SYSTEMCTL_S >= 20 + 30 + 60


LOJAS_SERVICE = {
    "ExecStartPre": "/bin/sh -c 'for i in $$(seq 1 60); do [ -S /tmp/.X11-unix/X1 ] && exit 0; sleep 1; done; exit 1'",
    "ExecStart": "/srv/besave/repo/tools/vps/iniciar_lojas.sh --aguardar",
    "ExecStop": "-/srv/besave/repo/tools/vps/parar_scope.sh besave-lojas-robo",
    "KillSignal": "SIGINT",
    "SuccessExitStatus": "130",
    "Restart": "on-failure",
    "RestartSec": "30",
    "TimeoutStopSec": "60",
    "Type": "simple",
    "WorkingDirectory": "/srv/besave/repo/tools/capture-store-pages",
    "Environment": "BESAVE_DISPLAY=:1",
}


def test_lojas_unit_inteira_com_saida_130_como_sucesso():  # BSV-57 item 2 (reteste inst1): licao 14
    servico = dict(_ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"])
    assert servico == LOJAS_SERVICE


def test_saida_130_da_parada_nao_deixa_a_unidade_failed_e_queda_real_sim():
    """Modelo da regra do systemd: codigo em SuccessExitStatus = sucesso (unidade `inactive`, sem Restart);
    outro codigo != 0 = falha (`failed`, e Restart=on-failure sobe de novo)."""
    s = _ler(VPS / "systemd" / "besave-captura-lojas.service")["Service"]
    ok = {0, *(int(x) for x in s["SuccessExitStatus"].split())}
    assert 130 in ok                       # SIGINT (128 + 2) da parada: inactive
    assert 1 not in ok and 137 not in ok   # queda real e SIGKILL seguem em failed -> on-failure
    assert s["Restart"] == "on-failure"
