"""BSV-51 ALE-01..04: aviso de captura parada (relogio e Telegram simulados)."""
from datetime import datetime, timedelta

from wa import alerta
from wa import janela as janela_mod

JAN = janela_mod.ler_janela({"janela_noturna": {"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}})
CFG = {"alerta": {"sem_abrir_minutos": 45, "telegram_token": "123:SEGREDO", "telegram_chat_id": "-100"}}
T0 = datetime(2026, 10, 22, 13, 0)


def vigia(cfg=CFG, janela=JAN, inicio=T0):
    enviados = []
    v = alerta.VigiaCaptura(cfg, janela, inicio=inicio, enviar=lambda t, c, m: enviados.append((t, c, m)))
    return v, enviados


def andar(v, ini, minutos, abriu=False, passo=2):
    for m in range(0, minutos + 1, passo):
        v.registrar_volta(abriu, ini + timedelta(minutes=m))


def test_dispara_depois_do_limite_e_nao_antes():  # ALE-01
    v, env = vigia()
    andar(v, T0, 44)
    assert env == []
    andar(v, T0 + timedelta(minutes=44), 4)
    assert len(env) == 1 and env[0][:2] == ("123:SEGREDO", "-100") and "parado" in env[0][2]


def test_uma_mensagem_por_ocorrencia_e_lembrete_a_cada_2h():  # ALE-01
    v, env = vigia()
    andar(v, T0, 100)
    assert len(env) == 1
    andar(v, T0 + timedelta(minutes=100), 20)       # 45 + 120 min = 165 min
    assert len(env) == 1
    andar(v, T0 + timedelta(minutes=120), 60)
    assert len(env) == 2 and "continua parado" in env[1][2]


def test_nao_dispara_dentro_da_janela_noturna_nem_ao_sair_dela():  # ALE-02
    noite = datetime(2026, 10, 22, 23, 0)
    v, env = vigia(inicio=noite)
    andar(v, noite, 8 * 60 + 40, passo=5)            # 23:00 -> 07:40, nada abre
    assert env == []
    v.registrar_volta(False, datetime(2026, 10, 23, 8, 10))   # saiu da janela ha 10 min
    assert env == []
    v.registrar_volta(False, datetime(2026, 10, 23, 8, 50))   # 50 min depois de 08:00 sem abrir
    assert len(env) == 1


def test_voltou_sai_uma_vez_so_depois_de_alertar():  # ALE-03
    v, env = vigia()
    v.registrar_volta(True, T0 + timedelta(minutes=10))        # abriu normal: nada
    assert env == []
    andar(v, T0 + timedelta(minutes=10), 50)
    assert len(env) == 1
    v.registrar_volta(True, T0 + timedelta(minutes=70))
    v.registrar_volta(True, T0 + timedelta(minutes=72))
    assert len(env) == 2 and "voltou" in env[1][2]
    andar(v, T0 + timedelta(minutes=72), 44)                   # nova contagem do zero
    assert len(env) == 2


def test_sem_chaves_so_loga(capsys):  # ALE-04
    for cfg in ({}, {"alerta": {}}, {"alerta": {"telegram_token": "x"}}, {"alerta": {"telegram_chat_id": "1"}}):
        v, env = vigia(cfg)
        andar(v, T0, 60)
        assert env == []
        assert "so log" in capsys.readouterr().out


def test_falha_de_envio_nao_levanta_nem_loga_o_token(capsys):  # ALE-04
    def quebra(t, c, m):
        raise OSError(f"https://api.telegram.org/bot{t}/sendMessage falhou")

    v = alerta.VigiaCaptura(CFG, JAN, inicio=T0, enviar=quebra)
    andar(v, T0, 60)
    saida = capsys.readouterr().out
    assert "Falha ao enviar" in saida and "SEGREDO" not in saida


def test_limite_padrao_45_e_configuravel():
    v, _ = vigia({"alerta": {}})
    assert v.limite == timedelta(minutes=45)
    v, env = vigia({"alerta": {"sem_abrir_minutos": 10, "telegram_token": "t", "telegram_chat_id": "c"}})
    andar(v, T0, 12)
    assert len(env) == 1


def test_limite_exato_dispara_e_um_minuto_antes_nao():  # fronteira ALE-01
    v, env = vigia()
    v.registrar_volta(False, T0 + timedelta(minutes=44, seconds=59))
    assert env == []
    v.registrar_volta(False, T0 + timedelta(minutes=45))
    assert len(env) == 1


def test_lembrete_exato_em_2h_e_um_segundo_antes_nao():  # fronteira ALE-01
    v, env = vigia()
    v.registrar_volta(False, T0 + timedelta(minutes=45))
    v.registrar_volta(False, T0 + timedelta(minutes=45, hours=2, seconds=-1))
    assert len(env) == 1
    v.registrar_volta(False, T0 + timedelta(minutes=45, hours=2))
    assert len(env) == 2


def test_voltou_informa_quanto_tempo_ficou_parado():  # ALE-03
    v, env = vigia()
    v.registrar_volta(False, T0 + timedelta(minutes=50))
    v.registrar_volta(True, T0 + timedelta(minutes=90))
    assert "~90 min" in env[1][2]


def test_limite_zero_ou_negativo_cai_no_padrao():
    for m in (0, -5, "x"):
        v, _ = vigia({"alerta": {"sem_abrir_minutos": m}})
        assert v.limite == timedelta(minutes=45)


def test_tempo_parado_conta_do_fim_da_janela_e_nao_da_ultima_volta_dentro_dela():  # achado real 30/10
    cfg = {"alerta": {"sem_abrir_minutos": 2, "telegram_token": "t", "telegram_chat_id": "c"}}
    ult = datetime(2026, 10, 30, 7, 41)
    v, env = vigia(cfg, inicio=ult - timedelta(hours=1))
    v.registrar_volta(True, ult)                                    # ultima volta dentro da janela
    v.registrar_volta(False, datetime(2026, 10, 30, 8, 1, 24))      # 1a cega, 1 min depois das 08:00
    assert env == []
    v.registrar_volta(False, datetime(2026, 10, 30, 8, 2))
    assert len(env) == 1 and "ha 2 min" in env[0][2]
    v.registrar_volta(True, datetime(2026, 10, 30, 8, 16))
    assert len(env) == 2 and "~16 min" in env[1][2]                 # do fim da janela, nao das 07:41


def test_fim_da_janela_de_ontem_nao_atrapalha_quem_abriu_de_dia():
    v, env = vigia()
    v.registrar_volta(True, T0)                                    # 13:00 abriu
    v.registrar_volta(False, T0 + timedelta(minutes=44))
    assert env == []
    v.registrar_volta(False, T0 + timedelta(minutes=45))
    assert len(env) == 1 and "ha 45 min" in env[0][2]
