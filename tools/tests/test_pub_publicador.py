"""BSV-63: laco do publicador com Oracle, relogio e pagina falsos (criterios de aceite da spec)."""
from datetime import UTC, datetime, timedelta

import pytest
from pub import regras
from pub.publicador import QR, BrowserMorto
from pub_falso import T0, Mundo


@pytest.fixture
def m(tmp_path):
    return Mundo(tmp_path)


# --- ritmo -------------------------------------------------------------------------------------------


def test_rit01_dia_simulado_teto_40_janela_8_22(m):
    """Um dia inteiro em voltas de 15 min, sempre com oferta nova na fila: <= 40 posts, todos em [08:00, 22:00)."""
    m.t = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)               # 00:00 em Brasilia
    horas = []
    for _ in range(24 * 4):
        m.fila.add(m.local())
        antes = len(m.pagina.envios)
        m.volta()
        if len(m.pagina.envios) > antes:
            horas.append(regras.local(m.t))
        m.andar(minutes=15)
    assert 38 <= len(horas) <= 40                                 # o ritmo chega perto do teto, nunca passa
    assert all(8 <= h.hour < 22 for h in horas)
    assert len(m.pagina.envios) == len(horas)


def test_rit02_0759_zero_tentativas(m):
    m.t = datetime(2026, 11, 16, 10, 59, tzinfo=UTC)              # 07:59 em Brasilia
    m.fila.add(m.local())
    m.volta()
    assert m.pagina.envios == [] and "abrir_canal" not in m.pagina.chamadas


def test_rit03_fora_do_ritmo_zero_tentativas(m):
    # 10:00 -> esperado = 1 + floor(40*120/840) = 6; ja houve 6 hoje
    for _ in range(6):
        i = m.fila.add(m.local(hours=-1))
        m.fila.linhas[i].update(st="E", dt_envio=m.local(hours=-1))
    m.fila.add(m.local())
    m.volta()
    assert m.pagina.envios == []


def test_rit03_d_de_hoje_conta_no_teto(m):
    m.fila.params = regras.Parametros(2, 8, 22)
    for st in ("E", "D"):
        i = m.fila.add(m.local(hours=-1))
        m.fila.linhas[i].update(st=st, dt_envio=m.local(hours=-1))
    m.fila.add(m.local())
    m.volta()
    assert m.pagina.envios == []


def test_rit04_parametros_lidos_a_cada_volta(m):
    m.fila.add(m.local())
    m.fila.params = regras.Parametros(40, 11, 22)                 # janela mudou no banco: 10:00 fica fora
    m.volta()
    assert m.pagina.envios == []
    m.fila.params = regras.Parametros(40, 8, 22)
    m.volta()
    assert len(m.pagina.envios) == 1


def test_rit04_sono_com_variacao(m):
    assert m.volta() == pytest.approx(15 * 60)                   # aleatorio 0.5 = intervalo cheio
    m.pub.aleatorio = lambda: 0.0
    assert m.volta() == pytest.approx(15 * 60 * 0.7)


# --- escolha e descarte ------------------------------------------------------------------------------


def test_esc01_tres_p_posta_a_mais_recente(m):
    a = m.fila.add(m.local(minutes=-30))
    b = m.fila.add(m.local(minutes=-5))
    c = m.fila.add(m.local(minutes=-20))
    m.volta()
    assert [x[2] for x in m.pagina.envios] == [m.fila.linhas[b]["legenda"]]
    assert m.fila.st(b) == ("E", None) and m.fila.st(a)[0] == "P" and m.fila.st(c)[0] == "P"


def test_esc02_oferta_inativa_vira_x_expirou_sem_post(m):
    i = m.fila.add(m.local(), ativa=False)
    m.volta()
    assert m.fila.st(i) == ("X", "expirou") and m.pagina.envios == []


def test_esc03_fila_de_4h_vira_x_velha(m):
    i = m.fila.add(m.local(hours=-4))
    m.volta()
    assert m.fila.st(i) == ("X", "velha") and m.pagina.envios == []


def test_esc04_pendente_de_ontem_vira_x_outro_dia(m):
    i = m.fila.add(m.local(hours=-11))                            # 23:00 de ontem
    m.volta()
    assert m.fila.st(i) == ("X", "outro_dia")


def test_esc04_teto_nao_descarta_e_a_virada_do_dia_sim(m):
    m.fila.params = regras.Parametros(1, 0, 24)
    m.t = datetime(2026, 11, 17, 2, 30, tzinfo=UTC)               # 23:30 em Brasilia
    j = m.fila.add(m.local(minutes=-40))
    j2 = m.fila.add(m.local(minutes=-10))
    m.fila.linhas[j].update(st="E", dt_envio=m.local(minutes=-30))  # teto do dia (1) ja atingido
    m.volta()
    assert m.fila.st(j2) == ("P", None)                            # o teto nao descarta sozinho
    m.andar(minutes=40)                                            # 00:10 do dia seguinte
    m.fila.params = regras.Parametros(1, 8, 22)
    m.volta()
    assert m.fila.st(j2) == ("X", "outro_dia")


# --- estados -----------------------------------------------------------------------------------------


def test_est01_confirmado_vira_e_depois_de_d_antes_do_clique(m, monkeypatch):
    i = m.fila.add(m.local())
    estado_no_clique = []
    original = m.pagina.enviar

    def enviar():
        estado_no_clique.append(m.fila.st(i))
        original()
    monkeypatch.setattr(m.pagina, "enviar", enviar)
    m.volta()
    assert estado_no_clique == [("D", "enviando")]
    st = m.fila.linhas[i]
    assert (st["st"], st["motivo"]) == ("E", None) and st["dt_envio"] == regras.local(T0)
    assert m.pagina.envios[0][0] == "BeSave - Canal de Teste"


@pytest.mark.parametrize("passo", ["abrir_canal", "anexar", "escrever_legenda"])
def test_est02_falha_antes_do_clique_volta_a_p_e_conta(m, passo):
    i = m.fila.add(m.local())
    m.pagina.falhar = passo
    m.volta()
    assert m.fila.st(i) == ("P", None) and m.pagina.envios == []
    assert m.pub.falhas_seguidas == 1
    assert m.pagina.recargas == 1                                 # excecao na pagina: recarrega uma vez
    assert m.pagina.chamadas[-1] == "limpar"


def test_est03_sem_confirmacao_fica_d_e_avisa_com_o_id(m):
    i = m.fila.add(m.local())
    m.pagina.confirma = False
    m.volta()
    assert m.fila.st(i) == ("D", "enviando")
    assert len(m.avisos) == 1 and f"linha {i}" in m.avisos[0] and "conferir no canal" in m.avisos[0]
    assert m.pub.falhas_seguidas == 1


def test_est03_erro_no_clique_tambem_fica_d(m):
    i = m.fila.add(m.local())
    m.pagina.falhar = "enviar"
    m.volta()
    assert m.fila.st(i) == ("D", "enviando") and len(m.avisos) == 1


def test_est04_d_nunca_e_tentada_de_novo(m):
    i = m.fila.add(m.local())
    m.pagina.confirma = False
    m.volta()
    m.pagina.confirma = True
    for _ in range(6):
        m.andar(minutes=15)
        m.volta()
    assert m.envios_da_oferta(i) == 1                             # so o clique original
    assert m.fila.st(i) == ("D", "enviando")


def test_est04_d_sozinha_na_fila_nao_e_lida_como_pendente(m):
    i = m.fila.add(m.local(), st="D")
    m.volta()
    assert m.envios_da_oferta(i) == 0 and m.fila.st(i)[0] == "D"


def test_est_linha_que_saiu_de_p_por_fora_nao_e_clicada(m, monkeypatch):
    i = m.fila.add(m.local())
    original = m.pagina.escrever_legenda

    def escrever(texto, modo):
        original(texto, modo)
        m.fila.linhas[i]["st"] = "X"                              # o dono descartou enquanto preparava
    monkeypatch.setattr(m.pagina, "escrever_legenda", escrever)
    m.volta()
    assert m.pagina.envios == [] and m.fila.st(i)[0] == "X"


# --- foto --------------------------------------------------------------------------------------------


def test_fot03_sem_foto_volta_a_p_sem_post_e_sem_d(m):
    i = m.fila.add(m.local())
    m.sem_foto.add(m.fila.linhas[i]["oferta"])
    m.volta()
    assert m.fila.st(i) == ("P", None) and m.pagina.envios == []
    assert "abrir_canal" not in m.pagina.chamadas and m.pub.falhas_seguidas == 1


def test_fot_post_leva_a_foto_preparada(m):
    i = m.fila.add(m.local())
    m.volta()
    foto = m.pagina.envios[0][1]
    assert foto is not None and foto.name == f"{m.fila.linhas[i]['oferta']}.jpg"


# --- pausa -------------------------------------------------------------------------------------------


def _falhar_tres(m):
    m.pagina.falhar = "anexar"
    for _ in range(3):
        m.fila.add(m.local())
        m.volta()
        m.andar(minutes=15)


def test_pau01_tres_falhas_pausa_com_um_aviso_e_zero_tentativas(m):
    _falhar_tres(m)
    assert len(m.avisos) == 1 and "pausa de 60 min" in m.avisos[0]
    tentativas = m.pagina.chamadas.count("abrir_canal")
    m.pagina.falhar = None
    for _ in range(3):                                            # 15, 30, 45 min depois da 3a falha
        m.volta()
        m.andar(minutes=15)
    assert m.pagina.chamadas.count("abrir_canal") == tentativas
    assert len(m.avisos) == 1


def test_pau02_volta_avisa_voltou(m):
    _falhar_tres(m)
    m.pagina.falhar = None
    m.andar(minutes=60)
    m.fila.add(m.local())
    m.volta()
    assert len(m.pagina.envios) == 1
    assert len(m.avisos) == 2 and "voltou" in m.avisos[1]


def test_pau01_nova_pausa_na_mesma_ocorrencia_nao_avisa_e_lembra_em_6h(m):
    _falhar_tres(m)
    for _ in range(6):                                            # ~6 h de falhas e pausas
        m.andar(minutes=60)
        _falhar_tres(m)
    assert len(m.avisos) == 2 and m.avisos[1].startswith("Lembrete")


def test_pau_sucesso_zera_o_contador(m):
    m.pagina.falhar = "anexar"
    for _ in range(2):
        m.fila.add(m.local())
        m.volta()
        m.andar(minutes=15)
    m.pagina.falhar = None
    m.fila.add(m.local())
    m.volta()
    assert m.pub.falhas_seguidas == 0 and m.avisos == []


# --- sessao, config, navegador -----------------------------------------------------------------------


def test_qr01_deslogado_avisa_sem_tentar(m):
    m.fila.add(m.local())
    m.pagina.estado_sessao = QR
    m.volta()
    m.andar(minutes=15)
    m.volta()
    assert m.pagina.envios == [] and "abrir_canal" not in m.pagina.chamadas
    assert len(m.avisos) == 1 and "ler o QR pelo VNC" in m.avisos[0]
    assert any("Aguardando o WhatsApp Web carregar" in x for x in m.logs)
    m.pagina.estado_sessao = "ok"
    m.andar(minutes=15)
    m.volta()
    assert len(m.pagina.envios) == 1 and any("Sessao autenticada" in x for x in m.logs)


def test_cfg01_habilitado_false_zero_tentativas_na_volta_seguinte(m):
    m.fila.add(m.local())
    m.cfg["habilitado"] = False
    m.volta()
    assert m.pagina.chamadas == [] and m.fila.leituras_de_estado == []
    m.cfg["habilitado"] = True
    m.volta()
    assert len(m.pagina.envios) == 1


def test_bat01_bate_a_cada_volta_mesmo_sem_post(m):
    m.volta()                                                     # fila vazia
    m.cfg["habilitado"] = False
    m.volta()
    assert [f for _, f, _ in m.batidas] == ["fila_vazia", "desligado"]
    assert m.batidas[0][2] == pytest.approx(15 * 60)


def test_banco_fora_nao_tenta_nem_derruba(m):
    m.fila.add(m.local())
    m.fila.fora = True
    m.volta()
    assert m.pagina.envios == [] and m.batidas[-1][1] == "banco_fora"


def test_lim01_navegador_morto_sai_com_codigo_1(m):
    m.fila.add(m.local())
    m.pagina.morto_em = "abrir_canal"
    assert m.pub.rodar(lambda s: None) == 1


def test_lim01_navegador_morto_depois_do_clique_deixa_d_e_avisa(m):
    i = m.fila.add(m.local())
    m.pagina.morto_em = "confirmar"
    assert m.pub.rodar(lambda s: None) == 1
    assert m.fila.st(i) == ("D", "enviando") and len(m.avisos) == 1


def test_lim01_recarregar_que_falha_e_navegador_morto(m, monkeypatch):
    m.fila.add(m.local())
    m.pagina.falhar = "anexar"

    def recarregar():
        raise RuntimeError("net::ERR")
    monkeypatch.setattr(m.pagina, "recarregar", recarregar)
    with pytest.raises(BrowserMorto):
        m.volta()


def test_laco_dorme_o_sono_da_volta(m):
    sonos = []

    def dormir(s):
        sonos.append(s)
        if len(sonos) == 2:
            m.pagina.morto_em = "sessao"
    assert m.pub.rodar(dormir) == 1 and sonos == [pytest.approx(900)] * 2


def test_config_ilegivel_no_meio_mantem_o_anterior(m):
    m.volta()
    from pub import config

    def quebrado():
        raise config.ErroConfig("nao consegui ler config.json (JSONDecodeError)")
    m.pub.carregar_config = quebrado
    m.fila.add(m.local())
    m.volta()
    assert len(m.pagina.envios) == 1


def test_t0_e_10h_em_brasilia():
    assert regras.local(T0) == datetime(2026, 11, 16, 10, 0) and T0 - timedelta(hours=0) == T0
