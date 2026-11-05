"""BSV-55 BLQ/AFI: bloqueio (captcha, login, sessao de afiliado) deixa a linha em '0' e nao perde oferta.

URLs de exemplo redigidas (regra 11): os parametros reais viram REDACTED.
"""
import pytest
from conftest import Loja

# Telas de bloqueio conhecidas das tres lojas (05/11 e anteriores).
BLOQUEIOS = [
    "https://www.mercadolivre.com.br/captcha/wall/logged?go=REDACTED",          # incidente de 05/11
    "https://www.mercadolivre.com.br/gz/account-verification?go=REDACTED",
    "https://www.mercadolivre.com.br/jms/mlb/lgz/login?platform_id=ML&go=REDACTED",
    "https://shopee.com.br/verify/traffic?anti_bot_tracking_id=REDACTED",
    "https://shopee.com.br/verify/captcha?anti_bot_tracking_id=REDACTED",
    "https://shopee.com.br/buyer/login?next=REDACTED",
    "https://www.amazon.com.br/errors/validateCaptcha?amzn=REDACTED",
    "https://www.amazon.com.br/ap/signin?openid.return_to=REDACTED",
]

PRODUTOS = [
    "https://produto.mercadolivre.com.br/MLB-REDACTED-serum-facial-_JM",
    "https://shopee.com.br/Kit-Batom-i.REDACTED.REDACTED",
    "https://www.amazon.com.br/dp/B0REDACTED",
    # marca so na query nao e a tela de bloqueio
    "https://shopee.com.br/Kit-Batom-i.1.2?next=/verify/traffic",
]


class LojaSemProduto(Loja):
    """Como o ML no captcha: a pagina nao tem produto (hoje viraria 'pagina_sem_produto' -> '9')."""

    def pagina_sem_produto(self, page):
        return True


class Pagina:
    def __init__(self, urls):
        self.urls = urls        # ID_OFERTA -> URL final apos navegar
        self.url = ""

    def wait_for_timeout(self, ms):
        pass


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


@pytest.fixture
def lote(lojas, monkeypatch):
    """Roda _processar_lote com a URL final de cada id; devolve (db, saidas)."""
    monkeypatch.setattr(lojas.produtos, "cadastrar_produto", lambda db, i, linha: (900 + i, None, None))
    monkeypatch.setattr(lojas.imagens_produto, "publicar_imagens_produto", lambda *a: 0)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda db: True)
    monkeypatch.setattr(lojas.afiliados, "loja_ativa", lambda loja: True)

    def publicar(db, id_oferta, *a):
        db.ofertas.append(id_oferta)
        return True, None
    monkeypatch.setattr(lojas.ofertas, "publicar_oferta", publicar)

    def rodar(urls, store=None, adiados=None, db=None):
        db = db or Db()
        pagina = Pagina(urls)
        monkeypatch.setattr(lojas, "_goto_robusto",
                            lambda page, url, timeout=0: setattr(page, "url", page.urls[int(url.rsplit("/", 1)[1])]))
        monkeypatch.setattr(lojas.registry, "get_store", lambda loja: store or Loja())
        linhas = [{"ID_OFERTA": i, "url": f"https://loja.exemplo/{i}", "numero_da_captura": str(i),
                   "DS_ORIGEM": "g"} for i in urls]
        saidas, _, _ = lojas._processar_lote(pagina, linhas, db, True, "img", adiados)
        return db, {o["ID_OFERTA"]: o for o in saidas}
    return rodar


@pytest.mark.parametrize("url", BLOQUEIOS)
def test_blq01_telas_de_bloqueio_viram_bloqueado_ou_login(lote, url):
    _, saidas = lote({5: url}, store=LojaSemProduto())
    assert saidas[5]["status_captura"] == "bloqueado_ou_login"


@pytest.mark.parametrize("url", PRODUTOS)
def test_blq01_pagina_de_produto_nao_e_bloqueio(lote, url):
    _, saidas = lote({5: url})
    assert saidas[5]["status_captura"] == "ok"


def test_blq02_captcha_do_ml_deixa_a_linha_em_0_sem_gravar_oferta(lote, lojas):
    adiados = set()
    db, _ = lote({7: BLOQUEIOS[0]}, store=LojaSemProduto(), adiados=adiados)
    assert db.capturas == [] and db.erros == [] and db.ofertas == []   # nem '1', nem '9', nem OFERTA
    assert 7 not in adiados            # relida na proxima varredura


def test_blq02_ponteiro_nao_passa_da_linha_bloqueada(lote, lojas):
    ok = PRODUTOS[0]
    db = Db()
    lote({10: ok, 11: BLOQUEIOS[0], 12: ok}, db=db)
    assert db.capturas == [10, 12] and db.ofertas == [10, 12]
    assert lojas.ponteiro == [10]
    lote({13: ok}, db=db)               # lote seguinte do monitor: continua travado
    assert lojas.ponteiro == [10]


# --- AFI: motivo do link de afiliado (sem a fixture `lojas`, que troca capturar por um falso) ---

class Elemento:
    def __init__(self, aparece):
        self.aparece = aparece

    @property
    def first(self):
        return self

    def wait_for(self, **k):
        if not self.aparece:
            raise TimeoutError("nao apareceu")

    def fill(self, texto):
        pass

    def click(self, **k):
        pass


class AbaAfiliado:
    """Painel affiliate.shopee: `formulario` = sessao logada; `gera` = o gerador devolve link."""

    def __init__(self, contexto, formulario, gera):
        self.context, self.formulario, self.gera = contexto, formulario, gera
        self.url = "https://affiliate.shopee.com.br/offer/custom_link"

    def bring_to_front(self):
        pass

    def goto(self, url, **k):
        if not self.formulario:
            self.url = "https://shopee.com.br/buyer/login?next=REDACTED"

    def is_closed(self):
        return False

    def set_default_timeout(self, ms):
        pass

    def locator(self, seletor):
        from core import link_afiliado
        if seletor == link_afiliado.SHP_TEXTAREA:
            return Elemento(self.formulario)
        if seletor == link_afiliado.SHP_COPIAR:
            return Elemento(self.gera)
        return Elemento(True)


class ContextoAfiliado:
    def __init__(self, formulario, gera):
        self.formulario, self.gera, self.pages = formulario, gera, []

    def new_page(self):
        aba = AbaAfiliado(self, self.formulario, self.gera)
        self.pages.append(aba)
        return aba


class PaginaProduto:
    url = "https://shopee.com.br/Kit-Batom-i.REDACTED.REDACTED"

    def __init__(self, contexto):
        self.context = contexto

    def bring_to_front(self):
        pass


def _shopee(formulario, gera):
    from core import link_afiliado
    link_afiliado.configurar(True)
    pagina = PaginaProduto(ContextoAfiliado(formulario, gera))
    return link_afiliado.capturar(pagina, "shopee", pagina.url)


def test_afi01_formulario_do_gerador_nao_abre_e_sessao():
    from core import link_afiliado
    r = _shopee(formulario=False, gera=False)
    assert r["url_afiliado"] == "" and r[link_afiliado.MOTIVO] == link_afiliado.SESSAO


def test_afi01_gerador_sem_link_para_a_url_e_outro():
    from core import link_afiliado
    r = _shopee(formulario=True, gera=False)
    assert r["url_afiliado"] == "" and r[link_afiliado.MOTIVO] == link_afiliado.OUTRO


def test_afi01_sessao_nao_desliga_a_loja_no_corta_circuito():
    from core import link_afiliado
    link_afiliado.configurar(True)
    for _ in range(link_afiliado.LIMITE_FALHAS + 1):
        pagina = PaginaProduto(ContextoAfiliado(False, False))
        r = link_afiliado.capturar(pagina, "shopee", pagina.url)
    # depois do novo login a loja volta a gerar link (o corta-circuito nao a desligou)
    assert r[link_afiliado.MOTIVO] == link_afiliado.SESSAO


def _afiliado(lojas, monkeypatch, motivo):
    from core import link_afiliado
    monkeypatch.setattr(lojas.link_afiliado, "capturar",
                        lambda *a: {**link_afiliado.vazio(), link_afiliado.MOTIVO: motivo})


def test_afi02_sessao_deixa_a_linha_em_0_sem_oferta_e_trava_o_ponteiro(lote, lojas, monkeypatch):
    _afiliado(lojas, monkeypatch, "sessao")
    adiados = set()
    db, saidas = lote({20: PRODUTOS[1]}, adiados=adiados)
    assert saidas[20]["status_captura"] == "sessao_afiliado_ausente"
    assert db.capturas == [] and db.erros == [] and db.ofertas == []
    assert 20 not in adiados
    _afiliado(lojas, monkeypatch, "")
    lote({21: PRODUTOS[1]}, db=db)
    assert lojas.ponteiro == []        # 21 gravada, mas o ponteiro nao passa da 20


def test_afi02_outro_grava_como_hoje(lote, lojas, monkeypatch):
    _afiliado(lojas, monkeypatch, "outro")
    db, saidas = lote({22: PRODUTOS[1]})
    assert saidas[22]["status_captura"] == "ok"
    assert db.capturas == [22] and db.ofertas == [22]
    assert lojas.ponteiro == [22]
