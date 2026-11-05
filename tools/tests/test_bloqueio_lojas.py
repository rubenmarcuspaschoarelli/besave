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
