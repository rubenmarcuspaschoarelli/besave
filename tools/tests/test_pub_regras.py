"""BSV-63 RIT-02..04, ESC-02..04, CFG-02: ritmo do canal 2, descarte, escolha e config. Funcoes puras."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from pub import config, regras
from pub.regras import Linha, Parametros

P40 = Parametros(qt_max_dia=40, hora_inicio=8, hora_fim=22)


def bsb(h, m=0, dia=16):
    """Instante (UTC) de h:m em Brasilia, 16/11/2026."""
    return datetime(2026, 11, dia, h, m, tzinfo=UTC) + timedelta(hours=3)


def linha(id_envio=1, fila=None, ativa=True):
    return Linha(id_envio=id_envio, id_oferta=1000 + id_envio, legenda="*x*", area_slug="elas",
                 dt_fila=fila or datetime(2026, 11, 16, 10, 0), ativa=ativa)


# --- ritmo -------------------------------------------------------------------------------------------


def test_rit02_fora_da_janela_nao_e_devido():
    assert regras.esperado(P40, bsb(7, 59)) is None
    assert not regras.devido(P40, bsb(7, 59), 0)
    assert regras.esperado(P40, bsb(22, 0)) is None          # [INICIO, FIM): 22:00 ja e fora
    assert not regras.devido(P40, bsb(22, 0), 0)


def test_rit02_dentro_da_janela_o_primeiro_e_devido():
    assert regras.esperado(P40, bsb(8, 0)) == 1
    assert regras.devido(P40, bsb(8, 0), 0)
    assert regras.devido(P40, bsb(21, 59), 39)


def test_rit03_ritmo_l1_igual_ao_do_telegram():
    # min(40, 1 + floor(40 * minutos / 840)): 11:30 = 210 min -> 1 + 10 = 11
    assert regras.esperado(P40, bsb(11, 30)) == 11
    assert regras.devido(P40, bsb(11, 30), 10)
    assert not regras.devido(P40, bsb(11, 30), 11)
    assert regras.esperado(P40, bsb(21, 59)) == 40            # 839 min -> 1 + 39


def test_rit03_teto_mesmo_com_ritmo_folgado():
    p = Parametros(qt_max_dia=5, hora_inicio=0, hora_fim=24)
    assert regras.esperado(p, bsb(23, 0)) == 5
    assert not regras.devido(p, bsb(23, 0), 5)
    assert not regras.devido(p, bsb(23, 0), 7)                # D que estourou: nunca negativo vira devido


def test_rit03_hora_em_brasilia_nao_utc():
    # 10:30 UTC = 07:30 em Brasilia: fora da janela 8-22
    assert regras.esperado(P40, datetime(2026, 11, 16, 10, 30, tzinfo=UTC)) is None


def test_rit04_sono_com_variacao_de_30_porcento():
    assert regras.sono_segundos(15, 0.0) == pytest.approx(15 * 60 * 0.7)
    assert regras.sono_segundos(15, 0.5) == pytest.approx(15 * 60)
    assert regras.sono_segundos(15, 0.999999) == pytest.approx(15 * 60 * 1.3, rel=1e-5)


# --- descarte ----------------------------------------------------------------------------------------


def test_esc02_oferta_inativa_expirou():
    assert regras.motivo_descarte(linha(ativa=False), bsb(10, 5), 3) == "expirou"


def test_esc03_fila_de_4h_velha_e_3h_ainda_vale():
    agora = bsb(14, 0)
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 16, 10, 0)), agora, 3) == "velha"
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 16, 11, 0)), agora, 3) is None
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 16, 10, 59)), agora, 3) == "velha"
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 16, 12, 0)), agora, 1.5) == "velha"


def test_esc04_pendente_de_ontem_outro_dia_mesmo_recente():
    # 23:50 de ontem, agora 00:10: 20 min de fila, mas de outro dia (Brasilia)
    agora = bsb(0, 10)
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 15, 23, 50)), agora, 3) == "outro_dia"
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 16, 0, 5)), agora, 3) is None


def test_esc04_ontem_e_velha_vira_outro_dia_e_inativa_vira_expirou():
    agora = bsb(9, 0)
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 15, 21, 0)), agora, 3) == "outro_dia"
    assert regras.motivo_descarte(linha(fila=datetime(2026, 11, 15, 21, 0), ativa=False), agora, 3) == "expirou"


def test_esc01_escolhe_a_mais_recente():
    a = linha(1, datetime(2026, 11, 16, 10, 0))
    b = linha(2, datetime(2026, 11, 16, 10, 30))
    c = linha(3, datetime(2026, 11, 16, 10, 10))
    assert regras.escolher([a, b, c]) == b
    assert regras.escolher([]) is None


def test_separar_divide_validas_e_descartes():
    linhas = [linha(1, ativa=False), linha(2), linha(3, datetime(2026, 11, 15, 10, 0))]
    descartes, validas = regras.separar(linhas, bsb(10, 30), 3)
    assert [(x.id_envio, m) for x, m in descartes] == [(1, "expirou"), (3, "outro_dia")]
    assert [x.id_envio for x in validas] == [2]


# --- config ------------------------------------------------------------------------------------------


def test_cfg02_padroes():
    c = config.de_dict({})
    assert (c.habilitado, c.intervalo_minutos, c.max_horas_fila, c.timeout_post_segundos, c.id_canal) == \
        (True, 15, 3, 60, 2)
    assert c.modo_legenda == "colar"


def test_cfg02_valor_invalido_vira_padrao_com_aviso():
    c = config.de_dict({"intervalo_minutos": 0, "max_horas_fila": "3", "id_canal": True, "modo_legenda": "x"})
    assert (c.intervalo_minutos, c.max_horas_fila, c.id_canal, c.modo_legenda) == (15, 3, 2, "colar")
    assert len(c.avisos) == 4


def test_cfg01_habilitado_que_nao_e_booleano_desliga():
    assert config.de_dict({"habilitado": "false"}).habilitado is False
    assert config.de_dict({"habilitado": False}).habilitado is False


def test_cfg02_exemplo_versionado_tem_obs_e_nenhum_segredo():
    exemplo = config.CAMINHO.parent / "config.example.json"
    bruto = json.loads(exemplo.read_text(encoding="utf-8"))
    assert "_obs" in bruto and "_obs" in bruto["oracle"]
    assert bruto["oracle"]["senha"] == "" and bruto["oracle"]["usuario"] == "" and bruto["oracle"]["dsn"] == ""
    c = config.de_dict(bruto)
    assert c.avisos == [] and c.id_canal == 2


def test_cfg_config_ilegivel_e_erro(tmp_path):
    (tmp_path / "config.json").write_text("{", encoding="utf-8")
    with pytest.raises(config.ErroConfig):
        config.carregar(tmp_path / "config.json")
