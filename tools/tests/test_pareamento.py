"""BSV-67 PAR-01..07, TEL-01/02, FIX-01: vinculo pelo codigo sem WhatsApp real.

A pagina e um falso de estados (QR -> numero -> codigo -> logado); o codigo vem da fixture real redigida
(tools/tests/fixtures/whatsapp/codigo_pt.html). Relogio, Telegram e batimento sao falsos ou em tmp.
Os seletores contra o DOM real ficam em test_pareamento_pagina.py.
"""
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from wa import batimento as batimento_mod
from wa import pareamento as p

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "whatsapp"
NUMERO = "5511987650000"
# 12:00 em Brasilia (15:00 UTC); minuto 0 de proposito: as contas por hora cheia ficam faceis de ler
T0 = datetime(2026, 11, 27, 15, 0, 0, tzinfo=UTC)


def codigo_da_fixture() -> str:
    html = (FIXTURES / "codigo_pt.html").read_text(encoding="utf-8")
    return re.search(r'data-testid="link-with-phone-number-code-cells" data-link-code="([^"]+)"', html).group(1)


class Relogio:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += timedelta(seconds=s)


class TelaFalsa:
    """Estados da pagina real. `vincula_em`: instante em que o celular conclui o vinculo (estado vira logado)."""

    def __init__(self, relogio, estado=p.QR, valor=None, codigos=None, vincula_em=None):
        self.relogio = relogio
        self._estado = estado
        self.valor = valor          # o que o campo mostra depois de digitar (None = mascara do WhatsApp)
        self.codigos = list(codigos) if codigos is not None else None
        self.vincula_em = vincula_em
        self.acoes: list[str] = []
        self.digitado = []

    def estado(self):
        if self.vincula_em is not None and self.relogio() >= self.vincula_em:
            return p.LOGADO
        return self._estado

    def abrir_numero(self):
        self.acoes.append("abrir_numero")
        self._estado = p.NUMERO

    def informar_numero(self, digitos):
        self.acoes.append("informar_numero")
        self.digitado.append(digitos)
        if self.valor is not None:
            return self.valor
        return f"+{digitos[:2]} {digitos[2:4]} {digitos[4:9]}-{digitos[9:]}"

    def avancar(self):
        self.acoes.append("avancar")

    def ler_codigo(self):
        self.acoes.append("ler_codigo")
        self._estado = p.CODIGO
        return self.codigos.pop(0) if self.codigos else codigo_da_fixture()


class Cenario:
    def __init__(self, tmp_path, numero=NUMERO, validade=10, **tela):
        self.relogio = Relogio()
        self.enviados: list[str] = []
        self.batidas: list[datetime] = []
        self.teto = p.Teto(tmp_path / "pedidos.json")
        self.tela = TelaFalsa(self.relogio, **tela)
        self.vinculo = p.Vinculo(self.tela, numero, validade, self.teto, self.enviados.append,
                                 lambda: self.batidas.append(self.relogio()), relogio=self.relogio,
                                 dormir=self.relogio.dormir)

    def rodar(self):
        self.vinculo.aguardar()


# --- PAR-01, PAR-07: codigo lido da fixture, mensagem inteira, numero mascarado ---------------------------


def test_fixture_do_codigo_e_redigida():  # FIX-01
    assert codigo_da_fixture() == "T,E,S,T,E,1,2,3"
    for arq in FIXTURES.glob("*.html"):
        texto = arq.read_text(encoding="utf-8")
        assert "<script" not in texto and "kpm" not in texto and "class=" not in texto, arq.name
        assert not re.search(r"\d{8,}", texto), arq.name       # nenhum numero de telefone


def test_codigo_da_fixture_vai_ao_telegram_com_a_mensagem_inteira(tmp_path, capsys):  # PAR-01, PAR-07
    c = Cenario(tmp_path, vincula_em=T0 + timedelta(minutes=3))
    c.rodar()
    assert c.enviados == [
        ("WhatsApp desconectado. No celular: WhatsApp > Aparelhos conectados > Conectar aparelho > "
         "Conectar com numero de telefone e digite TEST-E123 (pedido as 12:00, Brasilia)."),
        "WhatsApp: vinculado de novo pelo codigo; captura retomada.",
    ]
    assert c.tela.acoes == ["abrir_numero", "informar_numero", "avancar", "ler_codigo"]
    assert c.tela.digitado == [NUMERO]
    log = capsys.readouterr().out
    assert "***0000" in log
    assert NUMERO not in log and "TESTE123" not in log and "TEST-E123" not in log
    assert "[sessao] vinculado pelo codigo" in log
    assert all(NUMERO not in m for m in c.enviados)


def test_codigo_fora_do_formato_nao_vai_ao_telegram_e_pede_de_novo(tmp_path, capsys):  # PAR-01
    c = Cenario(tmp_path, codigos=["T,E,S,T", "A,B,C,D,E,F,G,H"], vincula_em=T0 + timedelta(minutes=2))
    c.rodar()
    assert c.enviados[0].endswith("digite ABCD-EFGH (pedido as 12:00, Brasilia).")
    assert len([m for m in c.enviados if "digite" in m]) == 1
    assert c.tela.acoes.count("avancar") == 2
    assert "ERRO: codigo da pagina" in capsys.readouterr().out


@pytest.mark.parametrize("bruto, esperado", [
    ("R,H,S,D,E,V,N,N", "RHSDEVNN"), ("T,E,S,T,E,1,2,3", "TESTE123"),
    ("R,H,S,D,E,V,N", None), ("r,h,s,d,e,v,n,n", None), ("R,H,S,D,E,V,N,*", None), ("", None), (None, None),
])
def test_codigo_valido(bruto, esperado):  # PAR-01: 8 [A-Z0-9]; fora disso -> erro
    assert p.codigo_valido(bruto) == esperado


def test_mascara_mostra_so_os_4_ultimos():  # PAR-07
    assert p.mascarar("5511987654321") == "***4321"


# --- PAR-02: numero divergente na mascara ------------------------------------------------------------------


def test_campo_com_ddi_duplicado_nao_avanca_e_manda_o_vnc(tmp_path, capsys):  # PAR-02
    c = Cenario(tmp_path, valor="+55 +55 11 98765-0000", vincula_em=T0 + timedelta(minutes=5))
    c.rodar()
    assert "avancar" not in c.tela.acoes
    assert c.enviados == [p.MSG_SEM_NUMERO]
    assert c.tela.acoes.count("informar_numero") == 1       # nao insiste nesta partida
    log = capsys.readouterr().out
    assert NUMERO not in log and "***0000" in log
    assert not (tmp_path / "pedidos.json").exists()          # nao pediu codigo: nao conta no teto


# --- PAR-03: espera viva e batimento -----------------------------------------------------------------------


def test_espera_viva_bate_a_cada_volta_com_fase_pareamento(tmp_path, monkeypatch):  # PAR-03
    relogio = Relogio()
    caminho = tmp_path / "batimento.json"
    bat = batimento_mod.Batimento(caminho=caminho, relogio=relogio, pid=42)
    lidos = []

    def bater():
        bat.bater("pareamento", dorme_s=(p.PRAZO_PAREAMENTO - batimento_mod.PRAZO).total_seconds())
        lidos.append(json.loads(caminho.read_text(encoding="utf-8")))

    tela = TelaFalsa(relogio, vincula_em=T0 + timedelta(minutes=12))
    v = p.Vinculo(tela, NUMERO, 10, p.Teto(tmp_path / "pedidos.json"), lambda m: None, bater,
                  relogio=relogio, dormir=relogio.dormir)
    v.aguardar()                                            # voltou: nao saiu do processo nem levantou
    assert len(lidos) == 12 * 60 // p.INTERVALO_S          # uma batida por volta de 5 s ate vincular
    for d in lidos:
        em = datetime.strptime(d["em"], "%Y-%m-%dT%H:%M:%SZ")
        prazo = datetime.strptime(d["prazo"], "%Y-%m-%dT%H:%M:%SZ")
        assert d["fase"] == "pareamento" and prazo - em == timedelta(minutes=15)


# --- PAR-04: codigo expirado -------------------------------------------------------------------------------


def test_validade_passou_pede_outro(tmp_path):  # PAR-04
    c = Cenario(tmp_path, validade=10, vincula_em=T0 + timedelta(minutes=25))
    c.rodar()
    pedidos = [m for m in c.enviados if "digite" in m]
    assert [m[-28:] for m in pedidos] == ["(pedido as 12:00, Brasilia).", "(pedido as 12:10, Brasilia).",
                                          "(pedido as 12:20, Brasilia)."]


@pytest.mark.parametrize("volta", [p.QR, p.NUMERO])
def test_pagina_voltou_ao_qr_ou_ao_numero_pede_outro_antes_da_validade(tmp_path, volta):  # PAR-04
    c = Cenario(tmp_path, validade=10, vincula_em=T0 + timedelta(minutes=6))
    orig = c.tela.estado

    def estado():
        if c.relogio() == T0 + timedelta(minutes=2):
            c.tela._estado = volta          # o WhatsApp tirou o codigo vencido da tela
        return orig()

    c.tela.estado = estado
    c.rodar()
    pedidos = [m for m in c.enviados if "digite" in m]
    assert [m[-28:] for m in pedidos] == ["(pedido as 12:00, Brasilia).", "(pedido as 12:02, Brasilia)."]


# --- PAR-05: teto ------------------------------------------------------------------------------------------


def test_quarto_pedido_na_mesma_hora_nao_sai_e_virou_a_hora_sai(tmp_path):  # PAR-05
    c = Cenario(tmp_path, validade=10, vincula_em=T0 + timedelta(minutes=65))
    c.rodar()
    pedidos = [m for m in c.enviados if "digite" in m]
    assert [m[-28:] for m in pedidos] == ["(pedido as 12:00, Brasilia).", "(pedido as 12:10, Brasilia).",
                                          "(pedido as 12:20, Brasilia).", "(pedido as 13:00, Brasilia)."]
    assert c.enviados.count(
        "WhatsApp desconectado: limite de codigos atingido; proximo pedido as 13:00 (Brasilia).") == 1
    assert c.enviados.index(pedidos[2]) < c.enviados.index(
        "WhatsApp desconectado: limite de codigos atingido; proximo pedido as 13:00 (Brasilia).") < c.enviados.index(pedidos[3])


def test_teto_por_hora_e_por_dia(tmp_path):  # PAR-05
    teto = p.Teto(tmp_path / "pedidos.json")
    for h in range(4):                                       # 3 por hora em 4 horas = 12 no dia
        for m in (0, 10, 20):
            t = T0 + timedelta(hours=h, minutes=m)
            assert teto.proximo(t) is None
            teto.registrar(t)
        if h < 3:                                            # 4o na hora nao sai; na hora cheia seguinte sai
            assert teto.proximo(T0 + timedelta(hours=h, minutes=30)) == T0 + timedelta(hours=h + 1)
    # 13o no dia nao sai, nem na hora seguinte; so a 00:00 de Brasilia (03:00 UTC)
    assert teto.proximo(T0 + timedelta(hours=4)) == datetime(2026, 11, 28, 3, 0, tzinfo=UTC)
    assert teto.proximo(datetime(2026, 11, 28, 2, 59, tzinfo=UTC)) == datetime(2026, 11, 28, 3, 0, tzinfo=UTC)
    assert teto.proximo(datetime(2026, 11, 28, 3, 0, tzinfo=UTC)) is None


def test_decimo_terceiro_no_dia_nao_sai_e_avisa_a_meia_noite(tmp_path):  # PAR-05
    c = Cenario(tmp_path, validade=10, vincula_em=datetime(2026, 11, 28, 3, 5, tzinfo=UTC))
    for h in range(4):                      # 12 pedidos ja feitos hoje: 3 por hora das 08 as 11 (Brasilia)
        for m in (0, 10, 20):
            c.teto.registrar(T0 - timedelta(hours=4 - h) + timedelta(minutes=m))
    c.rodar()
    assert c.enviados[0] == "WhatsApp desconectado: limite de codigos atingido; proximo pedido as 00:00 (Brasilia)."
    pedidos = [m for m in c.enviados if "digite" in m]
    assert [m[-28:] for m in pedidos] == ["(pedido as 00:00, Brasilia)."]
    assert c.enviados == [c.enviados[0], pedidos[0], p.MSG_VINCULADO]


def test_teto_sobrevive_a_partida_nova(tmp_path):  # PAR-05: o arquivo guarda a conta
    for m in (0, 10, 20):
        p.Teto(tmp_path / "pedidos.json").registrar(T0 + timedelta(minutes=m))
    assert p.Teto(tmp_path / "pedidos.json").proximo(T0 + timedelta(minutes=30)) == T0 + timedelta(hours=1)


# --- PAR-06: sem numero -----------------------------------------------------------------------------------


def test_sem_numero_manda_o_vnc_uma_vez_sem_clicar_e_espera_viva(tmp_path):  # PAR-06
    c = Cenario(tmp_path, numero="", vincula_em=T0 + timedelta(hours=3))
    c.rodar()
    assert c.enviados == ["WhatsApp desconectado e sem pareamento.numero no config: ler o QR pela tela VNC :2."]
    assert c.tela.acoes == []
    assert len(c.batidas) == 3 * 3600 // p.INTERVALO_S


@pytest.mark.parametrize("cfg, esperado", [
    ({}, ("", 10)), ({"pareamento": {"numero": "", "validade_min": 10}}, ("", 10)),
    ({"pareamento": {"numero": "+55 (11) 98765-0000", "validade_min": 7}}, (NUMERO, 7)),
])
def test_ler_config(cfg, esperado):
    assert p.ler_config(cfg) == esperado


# --- TEL-01/02: espera pela primeira tela ------------------------------------------------------------------


class PaginaContador:
    """Page minima: `locator(sel).count()` responde pelos seletores presentes em `presentes`."""

    def __init__(self):
        self.presentes: set[str] = set()

    def locator(self, sel):
        pag = self

        class L:
            def count(self):
                return 1 if sel in pag.presentes else 0

        return L()


@pytest.mark.parametrize("sel, esperado", [
    (p.SEL_LOGADO, p.LOGADO), (p.SEL_QR, p.QR), (p.SEL_LINK_NUMERO, p.QR), (p.SEL_CAMPO, p.NUMERO),
    (p.SEL_CODIGO, p.CODIGO),
])
def test_esperar_devolve_a_primeira_tela_que_aparece(sel, esperado):  # TEL-01
    pag = PaginaContador()
    passos = []

    def dormir(s):
        passos.append(s)
        if len(passos) == 3:
            pag.presentes.add(sel)

    tela = p.TelaWhatsApp(pag, dormir=dormir, relogio=lambda: len(passos))
    assert tela.esperar(300) == esperado


def test_nenhuma_tela_em_5_min_levanta_timeout():  # TEL-02
    pag = PaginaContador()
    t = [0.0]
    tela = p.TelaWhatsApp(pag, dormir=lambda s: t.__setitem__(0, t[0] + s), relogio=lambda: t[0])
    with pytest.raises(TimeoutError):
        tela.esperar()
    assert t[0] == 300
