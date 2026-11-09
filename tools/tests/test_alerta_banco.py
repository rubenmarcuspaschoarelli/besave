"""BSV-56 FORA-02: aviso de banco fora (relogio e Telegram simulados)."""
from datetime import datetime, timedelta

from wa import alerta

CFG = {"alerta": {"telegram_token": "123:SEGREDO", "telegram_chat_id": "-100"}}
T0 = datetime(2026, 11, 9, 10, 0)


def vigia(cfg=CFG, enviar=None):
    enviados = []
    v = alerta.VigiaBanco(cfg, enviar=enviar or (lambda t, c, m: enviados.append((t, c, m))))
    return v, enviados


def falhar_por(v, minutos, passo=1):
    for m in range(0, minutos + 1, passo):
        v.falhou("ORA-03113", T0 + timedelta(minutes=m))


def test_um_aviso_por_ocorrencia():
    v, env = vigia()
    falhar_por(v, 30)
    assert len(env) == 1
    assert env[0][:2] == ("123:SEGREDO", "-100")
    assert "Banco Oracle fora" in env[0][2] and "ORA-03113" in env[0][2]
    assert v.fora


def test_lembrete_so_depois_de_2h():
    v, env = vigia()
    falhar_por(v, 119)
    assert len(env) == 1                               # 1h59 sem lembrete
    v.falhou("ORA-03113", T0 + timedelta(minutes=120))
    assert len(env) == 2 and "continua fora ha 120 min" in env[1][2]
    falhar_por(v, 239)
    assert len(env) == 2                               # proximo so em 4 h
    v.falhou("ORA-03113", T0 + timedelta(minutes=240))
    assert len(env) == 3


def test_voltou_uma_vez_e_nova_ocorrencia_avisa_de_novo():
    v, env = vigia()
    falhar_por(v, 5)
    v.voltou(T0 + timedelta(minutes=7))
    assert len(env) == 2 and "voltou" in env[1][2] and "~7 min" in env[1][2]
    assert not v.fora
    v.voltou(T0 + timedelta(minutes=8))
    assert len(env) == 2                               # sem ocorrencia aberta, sem "voltou"
    v.falhou("DPY-1001", T0 + timedelta(minutes=9))
    assert len(env) == 3 and "DPY-1001" in env[2][2]


def test_sem_ocorrencia_voltou_nao_envia():
    v, env = vigia()
    v.voltou(T0)
    assert env == []


def test_sem_token_so_loga(capsys):
    v, env = vigia(cfg={"alerta": {"telegram_token": "", "telegram_chat_id": "-100"}})
    v.falhou("ORA-03113", T0)
    assert env == []
    assert "Banco Oracle fora" in capsys.readouterr().out


def test_falha_de_envio_nao_derruba_nem_loga_token(capsys):
    def explode(t, c, m):
        raise OSError(f"https://api.telegram.org/bot{t}/sendMessage falhou")

    v, _ = vigia(enviar=explode)
    v.falhou("ORA-03113", T0)
    out = capsys.readouterr().out
    assert "SEGREDO" not in out and "OSError" in out
