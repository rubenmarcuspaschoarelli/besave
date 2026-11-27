"""BSV-65 VIG-02: o vigia ve a captura por navegador parada com o robo das lojas vivo (licao 33).
So aviso, nunca reinicio. Mundo falso do vigia (vigia_falso.py); rodar tambem no WSL (licao 32)."""
import json
from datetime import timedelta

import pytest
from vigia_falso import T0, Mundo, iso

AVISO_61 = ("Vigia dos robos: lojas sem captura por navegador desde 10/11 10:59 (Brasilia): 10 linha(s) sem ok. "
            "Acao: nenhuma (o robo segue vivo; ver o log e o VNC).")


@pytest.fixture
def m(tmp_path):
    mundo = Mundo(tmp_path)
    mundo.so("lojas")
    return mundo


def bater_nav(m, ok_ha_min, tentativas, em=None):
    """Batimento saudavel do robo das lojas com os campos da BSV-65."""
    m.bater("lojas", em=em or m.t - timedelta(minutes=1))
    p = m.pasta("lojas") / "conf" / "batimento.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["ultimo_ok_navegador"] = iso(m.t - timedelta(minutes=ok_ha_min))
    d["tentativas_navegador"] = tentativas
    p.write_text(json.dumps(d), encoding="utf-8")


def test_vig02_dez_tentativas_e_61_min_avisam_sem_reiniciar(m):
    bater_nav(m, 61, 10)
    m.rodar_vigia()
    assert m.enviados == [AVISO_61]
    assert m.restarts() == []


@pytest.mark.parametrize("minutos, tentativas", [(61, 9), (59, 10), (60, 10)])
def test_vig02_abaixo_do_limite_nada(m, minutos, tentativas):
    bater_nav(m, minutos, tentativas)
    m.rodar_vigia()
    assert m.enviados == [] and m.restarts() == []


def test_vig02_batimento_sem_os_campos_nada(m):
    m.bater("lojas", em=m.t - timedelta(minutes=1))       # versao antiga do robo
    m.rodar_vigia()
    assert m.enviados == [] and m.restarts() == []


def test_vig02_um_aviso_por_ocorrencia_e_lembrete_em_2h(m):
    bater_nav(m, 61, 10)
    m.rodar_vigia()
    ok_fixo = m.t - timedelta(minutes=61)
    for minutos in (5, 60, 114):                          # ate 1 h 59 min depois: nada novo
        m.t = T0 + timedelta(minutes=minutos)
        bater_nav(m, int((m.t - ok_fixo).total_seconds() // 60), 12)
        m.rodar_vigia()
    assert len(m.enviados) == 1
    m.t = T0 + timedelta(minutes=120)
    bater_nav(m, int((m.t - ok_fixo).total_seconds() // 60), 30)
    m.rodar_vigia()
    assert len(m.enviados) == 2
    assert m.enviados[1].startswith("Lembrete. Vigia dos robos: lojas sem captura por navegador desde 10/11 10:59")
    assert m.restarts() == []


def test_vig02_voltou_quando_o_campo_anda(m):
    bater_nav(m, 61, 10)
    m.rodar_vigia()
    m.t = T0 + timedelta(minutes=10)
    bater_nav(m, 1, 0)                                    # ok ha 1 min: 70 min depois do ok antigo
    m.rodar_vigia()
    assert m.enviados[1] == "Vigia dos robos: lojas voltou a capturar pelo navegador (sem ok por 70 min)."
    assert "navegador" not in m.estado()["robos"]["lojas"]["ocorrencias"]
    m.t = T0 + timedelta(minutes=20)
    bater_nav(m, 11, 0)
    m.rodar_vigia()
    assert len(m.enviados) == 2


def test_vig02_campos_ilegiveis_nada(m):
    bater_nav(m, 61, 10)
    p = m.pasta("lojas") / "conf" / "batimento.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["tentativas_navegador"] = "10"
    p.write_text(json.dumps(d), encoding="utf-8")
    m.rodar_vigia()
    assert m.enviados == [] and m.restarts() == []


def test_vig02_robo_parado_segue_a_regra_de_sempre(m):
    """Prazo vencido: reinicio pela regra do batimento (BSV-57); a conferencia do navegador nao entra."""
    bater_nav(m, 120, 50, em=m.t - timedelta(minutes=11))
    m.rodar_vigia()
    assert len(m.restarts()) == 1
    assert len(m.enviados) == 1 and "sem captura por navegador" not in m.enviados[0]
