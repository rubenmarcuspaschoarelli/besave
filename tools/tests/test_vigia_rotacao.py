"""BSV-57 ROT-01..03: rotacao diaria dos logs (diretorio temporario; nada fora das duas pastas e dos dois padroes)."""
import os
from datetime import timedelta

import pytest
from vigia_falso import T0, Mundo

MB = 1024 * 1024


@pytest.fixture
def m(tmp_path):
    return Mundo(tmp_path)


def idade(caminho, dias):
    """Marca o arquivo como modificado ha `dias` dias."""
    t = (T0 - timedelta(days=dias)).timestamp()
    os.utime(caminho, (t, t))
    return caminho


def pasta_wa(m):
    return m.tools / "capture-chat-groups" / "log"


def pasta_lojas(m):
    return m.tools / "capture-store-pages" / "destino" / "log"


def test_rot01_whatsapp_apaga_com_mais_de_14_dias_e_mantem_13(m):
    velho = idade(m.log_whatsapp(T0 - timedelta(days=15), "x"), 15)
    novo13 = idade(m.log_whatsapp(T0 - timedelta(days=13), "x"), 13)
    recente = m.log_whatsapp(T0 - timedelta(minutes=3), "x")
    m.rodar_vigia()
    assert not velho.exists() and novo13.exists() and recente.exists()


def test_rot01_nunca_apaga_o_mais_recente_mesmo_velho(m):
    unico = idade(m.log_whatsapp(T0 - timedelta(days=40), "x"), 40)
    m.rodar_vigia()
    assert unico.exists()


def test_rot01_exatamente_14_dias_ainda_fica(m):
    limite = idade(m.log_whatsapp(T0 - timedelta(days=14), "x"), 14)
    m.log_whatsapp(T0 - timedelta(minutes=3), "x")
    m.rodar_vigia()
    assert limite.exists()


def test_rot02_main_monitorar_de_51_mb_e_copiado_e_truncado_no_mesmo_inode(m):
    principal = pasta_lojas(m) / "main_monitorar.log"
    principal.write_bytes(b"x" * (51 * MB))
    inode = principal.stat().st_ino
    m.rodar_vigia()
    copia = pasta_lojas(m) / f"main_monitorar_{T0:%Y%m%d}.log"
    assert copia.stat().st_size == 51 * MB
    assert principal.stat().st_size == 0 and principal.stat().st_ino == inode
    with open(principal, "ab") as f:                          # o `tee -a` do robo segue escrevendo
        f.write(b"nova linha\n")
    assert principal.read_bytes() == b"nova linha\n"


def test_rot02_main_monitorar_de_49_mb_fica_intocado(m):
    principal = pasta_lojas(m) / "main_monitorar.log"
    principal.write_bytes(b"x" * (49 * MB))
    m.rodar_vigia()
    assert principal.stat().st_size == 49 * MB
    assert sorted(p.name for p in pasta_lojas(m).iterdir()) == ["main_monitorar.log"]


def test_rot02_copias_com_mais_de_14_dias_sao_apagadas(m):
    velha = pasta_lojas(m) / "main_monitorar_20261020.log"
    velha.write_text("x", encoding="utf-8")
    idade(velha, 15)
    nova = pasta_lojas(m) / "main_monitorar_20261030.log"
    nova.write_text("x", encoding="utf-8")
    idade(nova, 13)
    m.rodar_vigia()
    assert not velha.exists() and nova.exists()


def test_rot03_so_toca_os_padroes_de_nome_nas_duas_pastas(m):
    intocados = []
    for pasta, nome in [
        (pasta_wa(m), "captura_whatsapp.csv"), (pasta_wa(m), "run_captura_notas.log"),
        (pasta_wa(m), "outro.log"), (pasta_lojas(m), "captura_x.csv"),
        (pasta_lojas(m), "main_monitorar_antigo.log"), (pasta_lojas(m), "oracle_10_11_2026.csv"),
        (m.tools / "capture-chat-groups" / "conf", "run_captura_10_09_120000.log"),
        (m.tools / "capture-store-pages" / "conf", "main_monitorar_20200101.log"),
        (m.raiz, "run_captura_10_09_120000.log"),
    ]:
        pasta.mkdir(parents=True, exist_ok=True)
        p = pasta / nome
        p.write_text("x", encoding="utf-8")
        idade(p, 90)
        intocados.append(p)
    m.log_whatsapp(T0 - timedelta(minutes=3), "x")
    m.rodar_vigia()
    assert all(p.exists() for p in intocados)


def test_rot_uma_vez_por_dia(m):
    velho = idade(m.log_whatsapp(T0 - timedelta(days=15), "x"), 15)
    m.log_whatsapp(T0 - timedelta(minutes=3), "x")
    m.rodar_vigia()
    assert not velho.exists() and m.estado()["rotacao_em"] == f"{T0:%Y-%m-%d}"
    outro = idade(m.log_whatsapp(T0 - timedelta(days=16), "x", sufixo="_2"), 16)
    m.andar(hours=2)
    m.bater("lojas", em=m.t - timedelta(minutes=1))
    m.bater("whatsapp", em=m.t - timedelta(minutes=1))
    m.rodar_vigia()
    assert outro.exists()                                      # mesmo dia: nao rodou de novo
    m.andar(days=1)
    m.bater("lojas", em=m.t - timedelta(minutes=1))
    m.bater("whatsapp", em=m.t - timedelta(minutes=1))
    m.rodar_vigia()
    assert not outro.exists()


def test_rot_contagem_vai_ao_journal(m, capsys):
    idade(m.log_whatsapp(T0 - timedelta(days=15), "x"), 15)
    idade(m.log_whatsapp(T0 - timedelta(days=16), "x", sufixo="_2"), 16)
    m.log_whatsapp(T0 - timedelta(minutes=3), "x")
    m.rodar_vigia()
    assert "rotacao de logs: 2 arquivo(s) apagado(s)" in capsys.readouterr().out
