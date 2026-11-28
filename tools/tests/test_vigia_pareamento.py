"""BSV-67 VIG-01, VIG-02, MEM-01, MEM-02: o vigia entende a espera do vinculo e reinicia por memoria.
Mundo falso do vigia (relogio, systemctl, cgroup, /proc, logs e Telegram em tmp); nada real e reiniciado."""
from datetime import timedelta

import pytest
import vigia_falso as vf
from vigia_falso import PID, REINICIO, UNIDADE, v

CHROME = 101
START_REINICIO = ["systemctl", "--user", "start", "--no-block", REINICIO]


@pytest.fixture
def m(tmp_path):
    mundo = vf.Mundo(tmp_path)
    mundo.so("whatsapp")
    return mundo


def _restarts(m):
    return [c for c in m.cmds if c[2] == "restart"]


def _starts(m):
    return [c for c in m.cmds if c[2] == "start"]


def _pareamento(m, em=None):
    m.bater("whatsapp", em=em or m.t, prazo=(em or m.t) + timedelta(minutes=15), fase="pareamento")


def _laco(m):
    """3 partidas nos ultimos 30 min sem Grupo aberto: sem a fase pareamento, o vigia chamaria o operador."""
    for k in (25, 15, 5):
        m.log_whatsapp(m.t - timedelta(minutes=k), "[browser] Aguardando o WhatsApp Web carregar...\n")


# --- VIG-01 -----------------------------------------------------------------------------------------------


def test_pareamento_em_dia_sem_reinicio_sem_laco_sem_aviso(m):  # VIG-01
    _laco(m)
    for _ in range(12):                                      # 1 h de vigia, batimento sempre em dia
        _pareamento(m)
        m.rodar_vigia()
        m.andar(minutes=5)
    assert _restarts(m) == [] and _starts(m) == []
    assert m.enviados == []


def test_laco_sem_pareamento_ainda_chama_o_operador(m):  # VIG-01: o laco continua valendo nos outros casos
    _laco(m)
    m.bater("whatsapp", em=m.t)
    m.rodar_vigia()
    assert len(m.enviados) == 1 and "laco de partidas" in m.enviados[0]


def test_lembrete_so_depois_de_6_h_e_a_cada_6_h(m):  # VIG-01
    inicio = m.t
    while m.t <= inicio + timedelta(hours=12, minutes=5):
        _pareamento(m)
        m.rodar_vigia()
        if m.t == inicio + timedelta(hours=5, minutes=55):
            assert m.enviados == []
        m.andar(minutes=5)
    assert m.enviados == ["Vigia dos robos: whatsapp aguardando vinculo pelo celular ha 6 h.",
                          "Vigia dos robos: whatsapp aguardando vinculo pelo celular ha 12 h."]
    assert _restarts(m) == []


# --- VIG-02 -----------------------------------------------------------------------------------------------


def test_pareamento_vencido_reinicia_como_hoje(m):  # VIG-02
    m.log_whatsapp(m.t - timedelta(minutes=40), "[browser] Aguardando o WhatsApp Web carregar...\n"
                                                 "[sessao] codigo pedido para ***0000\n")
    _pareamento(m, em=m.t - timedelta(minutes=20))          # prazo venceu ha 5 min: o laco de espera travou
    m.rodar_vigia()
    assert _restarts(m) == [["systemctl", "--user", "restart", UNIDADE["whatsapp"]]]
    assert len(m.enviados) == 1 and "reiniciado 1/2" in m.enviados[0]


# --- MEM-01, MEM-02 ---------------------------------------------------------------------------------------


def _chrome(m, mb):
    m.scope_pids("whatsapp", {PID["whatsapp"], CHROME})
    m.processo(CHROME, "chrome", mb * 1024)


def test_rss_acima_do_limite_dispara_o_reinicio_programado(m, capsys):  # MEM-01
    _chrome(m, 2501)
    m.rodar_vigia()
    assert _starts(m) == [START_REINICIO]
    assert _restarts(m) == []
    assert m.enviados == []                                  # 1o disparo: so log
    assert "maior chrome 2501 MB > 2500 MB; reinicio programado disparado (1 em 6 h)" in capsys.readouterr().out
    assert m.estado()["robos"]["whatsapp"]["reinicios"] == []   # fora da conta do robo parado


@pytest.mark.parametrize("mb", [2499, 2500])
def test_rss_no_limite_ou_abaixo_nao_dispara(m, mb):  # MEM-01
    _chrome(m, mb)
    m.rodar_vigia()
    assert _starts(m) == [] and _restarts(m) == [] and m.enviados == []


def test_rss_alto_com_batimento_vencido_segue_a_regra_de_parado(m):  # MEM-01
    _chrome(m, 2501)
    m.bater("whatsapp", em=m.t - timedelta(minutes=30))
    m.rodar_vigia()
    assert _starts(m) == []
    assert _restarts(m) == [["systemctl", "--user", "restart", UNIDADE["whatsapp"]]]


@pytest.mark.parametrize("fase", ["dormindo", "pareamento", "arranque"])
def test_rss_alto_fora_do_rodizio_nao_dispara(m, fase):  # MEM-01: so na fase rodizio
    _chrome(m, 3000)
    m.bater("whatsapp", em=m.t, fase=fase)
    m.rodar_vigia()
    assert _starts(m) == []


def test_um_por_60_min_e_aviso_so_no_segundo_em_6_h(m):  # MEM-01, MEM-02
    _chrome(m, 2600)
    m.rodar_vigia()                                          # 1o
    m.andar(minutes=50)
    m.bater("whatsapp", em=m.t)
    m.rodar_vigia()                                          # 50 min depois: nao
    assert len(_starts(m)) == 1 and m.enviados == []
    m.andar(minutes=10)
    m.bater("whatsapp", em=m.t)
    _chrome(m, 2700)
    m.rodar_vigia()                                          # 60 min depois do 1o: 2o disparo e aviso
    assert _starts(m) == [START_REINICIO, START_REINICIO]
    assert m.enviados == ["Vigia dos robos: whatsapp reiniciado por memoria 2 vezes em 6 h (maior chrome: 2700 MB)."]
    m.andar(minutes=60)
    m.bater("whatsapp", em=m.t)
    m.rodar_vigia()                                          # 3o em 6 h: dispara, sem novo aviso
    assert len(_starts(m)) == 3 and len(m.enviados) == 1


def test_segundo_disparo_depois_de_6_h_nao_avisa(m):  # MEM-02
    _chrome(m, 2600)
    m.rodar_vigia()
    m.andar(hours=6, minutes=1)
    m.bater("whatsapp", em=m.t)
    m.rodar_vigia()
    assert len(_starts(m)) == 2 and m.enviados == []


def test_limite_vem_do_ambiente():  # MEM-01
    amb = v.ambiente_real({"BESAVE_WHATSAPP_RSS_MAX_MB": "500", "BESAVE_WORKER_ENV": "/nao/existe"})
    assert amb.rss_max_mb == 500
    assert v.ambiente_real({"BESAVE_WORKER_ENV": "/nao/existe"}).rss_max_mb == 2500
