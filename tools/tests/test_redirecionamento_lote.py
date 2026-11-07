"""BSV-58 no lote real (_processar_lote / _monitorar): encurtador bloqueado resolvido pelo proxy residencial.

`curl` e navegador falsos; links redigidos (regra 11).
"""
import argparse
import subprocess
from datetime import datetime, timedelta

import pytest
from conftest import Loja

PROXY = "socks5h://127.0.0.1:1080"
REDIR = {"proxy": PROXY, "dominios": ["promos.link"], "timeout_segundos": 20, "max_saltos": 5}
ALERTA = {"telegram_token": "123456:SEGREDO_REDACTED", "telegram_chat_id": "-100REDACTED"}
CURTO = "https://amzn.promos.link/REDACTED{}"
AMAZON = "https://www.amazon.com.br/dp/B0REDACTED{}?tag=REDACTED-20"
DESCONHECIDO = "https://achadinhos.exemplo.com.br/oferta/{}"
T0 = datetime(2026, 11, 6, 10, 0)
BLOQUEIO_CF = ("<html><head><title>Attention Required! | Cloudflare</title></head><body>"
               "<h1>Sorry, you have been blocked</h1></body></html>")


class Relogio:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class Pagina:
    """Navegador falso: `destinos[url]` = (url final, html). Sem entrada: fica na propria URL, pagina comum."""

    def __init__(self, destinos):
        self.destinos = destinos
        self.url = ""
        self.html = ""
        self.visitas = []

    def wait_for_timeout(self, ms):
        pass

    def is_closed(self):
        return False

    def title(self):
        ini = self.html.find("<title>")
        return self.html[ini + 7:self.html.find("</title>")] if ini >= 0 else ""

    def content(self):
        return self.html

    def evaluate(self, js):
        return ""


class Db:
    sem_conexao = False

    def __init__(self):
        self.capturas, self.erros, self.ofertas = [], [], []

    def atualizar_captura(self, id_oferta, out, ativo=False):
        self.capturas.append(id_oferta)
        return True, None

    def marcar_erro(self, id_oferta, status, url_final, ativo=False):
        self.erros.append((id_oferta, status))
        return True, None

    def buscar_para_produto(self, i):
        return {"ID_OFERTA": i}

    def buscar_para_cupom(self, i):
        return None

    def buscar_para_oferta(self, i):
        return {"ID_OFERTA": i}


class Curl:
    """`curl` falso por URL: (codigo de saida, stdout). Guarda os comandos."""

    def __init__(self):
        self.respostas = {}
        self.padrao = None
        self.comandos = []

    def __call__(self, cmd, **k):
        assert cmd[0] == "curl" and not k.get("shell")
        self.comandos.append(cmd)
        codigo, saida = self.respostas.get(cmd[-1], self.padrao)
        return subprocess.CompletedProcess(cmd, codigo, saida, "curl: (7) Failed to connect to 127.0.0.1 port 1080")


@pytest.fixture
def amb(lojas, monkeypatch):
    rel = Relogio()
    enviados = []
    cfg = {"redirecionamento": dict(REDIR), "alerta": ALERTA, "bloqueio": {"pausa_minutos": 60}}
    monkeypatch.setattr(lojas.estado, "_ler_config", lambda *a, **k: cfg)
    curl = Curl()
    monkeypatch.setattr(subprocess, "run", curl)
    lojas_por_dominio = {"amazon.com.br": "amazon", "mercadolivre.com.br": "mercadolivre"}
    monkeypatch.setattr(lojas.registry, "resolver_loja",
                        lambda url: next((v for k, v in lojas_por_dominio.items() if k in (url or "")), None))
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: Loja())
    monkeypatch.setattr(lojas.registry, "nome_loja",
                        lambda loja, url=None: {"amazon": "Amazon", "mercadolivre": "Mercado Livre"}.get(loja, ""))
    monkeypatch.setattr(lojas.produtos, "cadastrar_produto", lambda db, i, linha: (900 + i, None, None))
    monkeypatch.setattr(lojas.imagens_produto, "publicar_imagens_produto", lambda *a: 0)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda db: True)
    monkeypatch.setattr(lojas.afiliados, "loja_ativa", lambda loja: True)

    def publicar(db, id_oferta, *a):
        db.ofertas.append(id_oferta)
        return True, None
    monkeypatch.setattr(lojas.ofertas, "publicar_oferta", publicar)
    destinos = {}

    def navegar(page, url, timeout=0):
        page.visitas.append(url)
        page.url, page.html = destinos.get(url, (url, "<html><title>Achadinhos</title></html>"))
    monkeypatch.setattr(lojas, "_goto_robusto", navegar)

    def nova_pausa():
        p = lojas.bloqueio.PausaLojas(cfg, agora=rel, nome=lambda loja: lojas.registry.nome_loja(loja))
        p.avisar = lojas.bloqueio.Avisador(cfg, enviar=lambda t, c, m: enviados.append(m)).avisar
        return p
    pausa = nova_pausa()

    def rodar(linhas, db=None):
        db = db or Db()
        pagina = Pagina(destinos)
        rows = [{"ID_OFERTA": i, "url": u, "numero_da_captura": str(i), "DS_ORIGEM": "g"} for i, u in linhas]
        saidas, _, _ = lojas._processar_lote(pagina, rows, db, True, "img", set(), pausa)
        return {o["ID_OFERTA"]: o["status_captura"] for o in saidas}, pagina.visitas, db

    return argparse.Namespace(rodar=rodar, curl=curl, cfg=cfg, destinos=destinos, pausa=pausa, rel=rel,
                              enviados=enviados, nova_pausa=nova_pausa)


def curto(i):
    return CURTO.format(i)


def amz(i):
    return AMAZON.format(i)


# --- RES-01 ----------------------------------------------------------------------------------------

def test_res01_302_amazon_pelo_proxy_e_pagina_aberta_direto(amb, lojas, capsys):
    amb.curl.respostas[curto(1)] = (0, f"302 {amz(1)}")
    status, visitas, db = amb.rodar([(1, curto(1))])
    assert status[1] == "ok" and db.capturas == [1] and db.ofertas == [1]
    assert visitas == [amz(1)]                       # o navegador nunca abriu o encurtador
    assert [c[-1] for c in amb.curl.comandos] == [curto(1)]
    out = capsys.readouterr().out
    assert "redirect (proxy) -> amazon" in out and "oracle=ok" in out
    assert lojas.ponteiro == [1]


def test_res01_dois_saltos_ate_o_ml(amb):
    meio = "https://promos.link/REDACTED-meio"
    ml = "https://produto.mercadolivre.com.br/MLB-REDACTED-_JM"
    amb.curl.respostas.update({curto(1): (0, f"302 {meio}"), meio: (0, f"302 {ml}")})
    status, visitas, _ = amb.rodar([(1, curto(1))])
    assert status[1] == "ok" and visitas == [ml] and len(amb.curl.comandos) == 2


# --- RES-03 ----------------------------------------------------------------------------------------

def test_res03_sem_redirect_segue_o_navegador_como_hoje(amb):
    amb.curl.respostas[curto(1)] = (0, "200 ")
    amb.destinos[curto(1)] = (amz(1), "")             # o navegador segue o redirect por JavaScript
    status, visitas, db = amb.rodar([(1, curto(1))])
    assert visitas[0] == curto(1) and status[1] == "ok" and db.capturas == [1]


def test_res03_sem_redirect_em_pagina_comum_continua_9(amb):
    amb.curl.respostas[curto(1)] = (0, "200 ")
    status, _, db = amb.rodar([(1, curto(1))])
    assert status[1] == "loja_desconhecida" and db.erros == [(1, "loja_desconhecida")]


# --- CFG-01 ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("bloco", [None, {"proxy": PROXY, "dominios": []}])
def test_cfg01_sem_bloco_e_o_fluxo_de_hoje(amb, bloco):
    if bloco is None:
        del amb.cfg["redirecionamento"]
    else:
        amb.cfg["redirecionamento"] = bloco
    amb.destinos[curto(1)] = (amz(1), "")
    status, visitas, _ = amb.rodar([(1, curto(1))])
    assert amb.curl.comandos == [] and visitas[0] == curto(1) and status[1] == "ok"


# --- FAL-01 / FAL-02 -------------------------------------------------------------------------------

@pytest.mark.parametrize("resposta", [(7, "000 "), (0, "403 "), (0, "429 "), (0, "503 ")])
def test_fal_linha_retida_nada_gravado_e_ponteiro_travado(amb, lojas, capsys, resposta):
    amb.curl.respostas[curto(1)] = resposta
    status, visitas, db = amb.rodar([(1, curto(1)), (2, amz(2))])
    assert status[1] == "redirecionamento_indisponivel" and status[2] == "ok"
    assert curto(1) not in visitas
    assert db.capturas == [2] and db.erros == [] and db.ofertas == [2]
    assert lojas.ponteiro == []                      # a 2 nao passa da 1 retida
    assert "oracle=retida(0)" in capsys.readouterr().out


def test_fal01_sem_proxy_configurado_retem_e_nao_chama_curl(amb):
    amb.cfg["redirecionamento"]["proxy"] = ""
    status, visitas, db = amb.rodar([(1, curto(1))])
    assert status[1] == "redirecionamento_indisponivel" and amb.curl.comandos == [] and visitas == []
    assert db.erros == [] and db.capturas == []


# --- PAU-01 ----------------------------------------------------------------------------------------

def test_pau01_tres_falhas_pausam_o_dominio_avisam_uma_vez_e_voltam(amb, lojas):
    amb.curl.padrao = (7, "000 ")
    status, visitas, _ = amb.rodar([(1, curto(1)), (2, curto(2)), (3, amz(3)), (4, curto(4)),
                                    (5, curto(5)), (6, amz(6))])
    assert [status[i] for i in (1, 2, 4)] == ["redirecionamento_indisponivel"] * 3
    assert status[5] == "loja_pausada" and status[3] == status[6] == "ok"
    assert len(amb.curl.comandos) == 3               # a 5 nem chamou o curl
    assert len(amb.enviados) == 1
    assert "promos.link em pausa: túnel residencial fora? 4 linha(s) retida(s)" in amb.enviados[0]
    assert amb.pausa.em_pausa("promos.link") and not amb.pausa.em_pausa("amazon")

    amb.rel.t += timedelta(minutes=61)
    amb.curl.padrao = (0, f"302 {amz(5)}")
    status, visitas, db = amb.rodar([(5, curto(5))])
    assert status[5] == "ok" and db.capturas == [5] and visitas == [amz(5)]
    assert len(amb.enviados) == 2 and "voltou" in amb.enviados[1] and "promos.link" in amb.enviados[1]


def test_pau01_linha_pausada_e_pausada0(amb, capsys):
    amb.curl.padrao = (7, "000 ")
    amb.rodar([(1, curto(1)), (2, curto(2)), (3, curto(3))])
    capsys.readouterr()
    status, _, db = amb.rodar([(4, curto(4))])
    assert status[4] == "loja_pausada" and db.erros == [] and "oracle=pausada(0)" in capsys.readouterr().out


def test_pau01_monitor_nao_rele_em_laco_so_com_linhas_do_dominio_em_pausa(amb, lojas, monkeypatch):
    amb.curl.padrao = (7, "000 ")
    amb.rodar([(1, curto(1)), (2, curto(2)), (3, curto(3))])
    monkeypatch.setattr(lojas, "_pausa_padrao", lambda: amb.pausa)
    filas = iter([[{"ID_OFERTA": 9, "url": curto(9), "numero_da_captura": "9"}]])
    lotes, esperas = [], []

    def ler(*a, **k):
        try:
            return next(filas)
        except StopIteration:
            raise KeyboardInterrupt from None
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", esperas.append)
    for nome in ("_varrer_validade", "_recuperar_publicacoes"):
        monkeypatch.setattr(lojas, nome, lambda *a, **k: None)
    monkeypatch.setattr(lojas, "_processar_lote", lambda *a, **k: lotes.append(a) or ([], 0, 0))
    lojas._monitorar(None, Pagina({}), None, argparse.Namespace(desde=None, limite=0), [], None, 3, None)
    assert lotes == [] and esperas == [180]


def test_pau01_monitor_real_resolve_pelo_proxy(amb, lojas, monkeypatch):
    """Laco real do --monitorar com o _processar_lote real (licao 23): a config chega ao lote."""
    amb.curl.respostas[curto(1)] = (0, f"302 {amz(1)}")
    monkeypatch.setattr(lojas, "_pausa_padrao", lambda: amb.pausa)
    for nome in ("_gravar_csv", "_resumo_oracle", "_varrer_validade", "_recuperar_publicacoes"):
        monkeypatch.setattr(lojas, nome, lambda *a, **k: None)
    filas = iter([[{"ID_OFERTA": 1, "url": curto(1), "numero_da_captura": "1", "DS_ORIGEM": "g"}]])

    def ler(*a, **k):
        try:
            return next(filas)
        except StopIteration:
            raise KeyboardInterrupt from None
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    db = Db()
    pagina = Pagina({})
    lojas._monitorar(None, pagina, db, argparse.Namespace(desde=None, limite=0), [], "img", 3, None)
    assert db.capturas == [1] and pagina.visitas == [amz(1)]


# --- SEG-01 ----------------------------------------------------------------------------------------

def test_seg01_proxy_nunca_aparece_na_saida(amb, lojas, monkeypatch, capsys):
    amb.curl.padrao = (7, "000 ")
    amb.rodar([(1, curto(1)), (2, curto(2)), (3, curto(3)), (4, curto(4))])
    amb.rel.t += timedelta(hours=7)
    amb.pausa.lembrar()
    amb.curl.padrao = (0, f"302 {amz(5)}")
    amb.rodar([(5, curto(5))])
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    for nome in ("_varrer_validade", "_recuperar_publicacoes"):
        monkeypatch.setattr(lojas, nome, lambda *a, **k: None)
    lojas._monitorar(None, Pagina({}), None, argparse.Namespace(desde=None, limite=0), [], None, 3, None)
    saida = capsys.readouterr()
    texto = saida.out + saida.err + "\n".join(amb.enviados)
    assert "promos.link" in texto and len(amb.enviados) == 3
    assert PROXY not in texto and "1080" not in texto and "127.0.0.1" not in texto


# --- CF-01 / CF-02 ---------------------------------------------------------------------------------

def desc(i):
    return DESCONHECIDO.format(i)


SO_TITULO = "<html><head><title>Attention Required! | Cloudflare</title></head><body>Error 1020</body></html>"
SO_TEXTO = "<html><head><title>Just a moment</title></head><body><h2>You have been blocked</h2></body></html>"


@pytest.mark.parametrize("html", [BLOQUEIO_CF, SO_TITULO, SO_TEXTO])
def test_cf01_bloqueio_do_cloudflare_fora_da_lista_retem_e_sugere(amb, lojas, capsys, html):
    amb.destinos[desc(1)] = (desc(1), html)
    status, _, db = amb.rodar([(1, desc(1)), (2, amz(2))])
    assert status[1] == "redirecionamento_indisponivel" and status[2] == "ok"
    assert db.erros == [] and db.capturas == [2] and lojas.ponteiro == []
    out = capsys.readouterr().out
    assert ("achadinhos.exemplo.com.br bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?"
            in out)
    assert "oracle=retida(0)" in out and amb.curl.comandos == []


def test_cf01_tres_seguidas_pausam_o_dominio_e_avisam_com_a_sugestao(amb):
    for i in (1, 2, 3, 4):
        amb.destinos[desc(i)] = (desc(i), BLOQUEIO_CF)
    status, visitas, _ = amb.rodar([(1, desc(1)), (2, desc(2)), (3, desc(3)), (4, desc(4)), (5, amz(5))])
    assert status[4] == "loja_pausada" and desc(4) not in visitas and status[5] == "ok"
    assert len(amb.enviados) == 1
    assert "achadinhos.exemplo.com.br bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?" \
        in amb.enviados[0]


def test_cf01_vale_sem_o_bloco_de_redirecionamento(amb):
    del amb.cfg["redirecionamento"]
    amb.destinos[desc(1)] = (desc(1), BLOQUEIO_CF)
    status, _, db = amb.rodar([(1, desc(1))])
    assert status[1] == "redirecionamento_indisponivel" and db.erros == []


def test_cf02_pagina_comum_de_dominio_desconhecido_continua_9(amb):
    amb.destinos[desc(1)] = (desc(1), "<html><title>Achadinhos da Carol</title><body>Promo blocked? nao</body></html>")
    status, _, db = amb.rodar([(1, desc(1))])
    assert status[1] == "loja_desconhecida" and db.erros == [(1, "loja_desconhecida")]


def test_cf01_dominio_que_volta_a_responder_avisa_voltou(amb):
    for i in (1, 2, 3):
        amb.destinos[desc(i)] = (desc(i), BLOQUEIO_CF)
    amb.rodar([(1, desc(1)), (2, desc(2)), (3, desc(3))])
    amb.rel.t += timedelta(minutes=61)
    amb.destinos[desc(4)] = (amz(4), "")             # agora redireciona para a loja
    status, _, db = amb.rodar([(4, desc(4))])
    assert status[4] == "ok" and db.capturas == [4]
    assert len(amb.enviados) == 2 and "voltou" in amb.enviados[1]
