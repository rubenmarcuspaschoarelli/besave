"""BSV-59 ASS/PRO/LNK/ERR: cliente da API de afiliados da Shopee contra um servidor HTTP local.

Credenciais ficticias e distintas de qualquer outro valor do teste (licao 11); ids e links redigidos.
"""
import hashlib
import json
import threading
import time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

APP_ID = "app-ficticio-7781"
SECRET = "segredo-ficticio-4402"
TS = 1762790400
SHOP, ITEM = 300100200, 22334455667
CURTO = "https://s.shopee.com.br/REDACTED1"
# Textos reais da pre-condicao (docs/specs/BSV-59.md).
ERRO_ASSINATURA = {"errors": [{"message": "error [10020]: Invalid Signature",
                               "extensions": {"code": 10020, "message": "Invalid Signature"}}]}
ERRO_EXPIRADO = {"errors": [{"message": "error [10020]: Request Expired",
                             "extensions": {"code": 10020, "message": "Request Expired"}}]}


def no(item=ITEM, shop=SHOP, price="19.93", **k):
    base = {"itemId": item, "shopId": shop, "productName": "  Batom Matte REDACTED  ", "price": price,
            "priceMin": "19.93", "priceMax": "57.9", "imageUrl": "https://cf.shopee.com.br/file/REDACTED",
            "ratingStar": "4.6", "sales": 1351, "commissionRate": "0.13",
            "offerLink": "https://s.shopee.com.br/REDACTED2", "shopName": "Loja REDACTED"}
    base.update(k)
    return base


def produto_ok(*nos, mais=False):
    return {"data": {"productOfferV2": {"nodes": list(nos), "pageInfo": {"hasNextPage": mais}}}}


class Servidor:
    """GraphQL falso: responde `respostas` em ordem (status, corpo); guarda cada pedido."""

    def __init__(self):
        self.pedidos = []
        self.respostas = []
        self.atraso = 0
        dono = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = self.rfile.read(int(self.headers["Content-Length"]))
                dono.pedidos.append({"path": self.path, "headers": dict(self.headers), "corpo": corpo})
                time.sleep(dono.atraso)
                status, resposta = dono.respostas.pop(0) if dono.respostas else (200, produto_ok(no()))
                dados = resposta if isinstance(resposta, bytes) else json.dumps(resposta).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/graphql"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def fechar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def api():
    from core import shopee_api
    return shopee_api


@pytest.fixture
def srv():
    s = Servidor()
    yield s
    s.fechar()


@pytest.fixture
def cliente(api, srv):
    return api.Cliente(APP_ID, SECRET, timeout=2, endpoint=srv.url, relogio=lambda: TS)


def esperado(corpo):
    assinatura = hashlib.sha256(APP_ID.encode() + str(TS).encode() + corpo + SECRET.encode()).hexdigest()
    return f"SHA256 Credential={APP_ID}, Timestamp={TS}, Signature={assinatura}"


# --- ASS-01 -------------------------------------------------------------------------------------
def test_ass01_vetor_fixo(api):
    # sha256("app-ficticio-7781" + "1762790400" + '{"query":"{ ping }"}' + "segredo-ficticio-4402")
    assert api.assinar(APP_ID, TS, '{"query":"{ ping }"}', SECRET) == (
        "83c486ec71bbac20738a7c146f266122e167e73812016e06b79d973ac8f67c28")


def test_ass01_cabecalho_inteiro_e_corpo_e_o_payload_assinado(cliente, srv):
    cliente.produto(SHOP, ITEM)
    cliente.link_afiliado(SHOP, ITEM)
    assert len(srv.pedidos) == 2
    for p in srv.pedidos:
        assert p["headers"]["Authorization"] == esperado(p["corpo"])
        assert p["headers"]["Content-Type"] == "application/json"
        assert set(json.loads(p["corpo"])) == {"query"}


# --- PRO-01 / PRO-02 ----------------------------------------------------------------------------
def test_pro01_um_no_do_item_vira_as_chaves_da_captura(cliente, srv):
    dados, motivo = cliente.produto(SHOP, ITEM)
    assert motivo is None
    assert dados == {
        "produto_titulo": "Batom Matte REDACTED",
        "preco_1": "19.93",
        "avaliacao_nota": "4.6",
        "quantidade_vendida": "1351",
        "taxa_comissao_afiliado": "13%",
        "id_produto_afiliado": f"{SHOP}.{ITEM}",
        "imagem_url": "https://cf.shopee.com.br/file/REDACTED",
    }
    query = json.loads(srv.pedidos[0]["corpo"])["query"]
    assert "productOfferV2" in query and f"shopId: {SHOP}" in query and f"itemId: {ITEM}" in query
    assert "matchId" not in query


@pytest.mark.parametrize("price, preco", [("89.99", "89.99"), ("19.9", "19.90"), ("120", "120.00")])
def test_pro01_preco_em_decimal_duas_casas(cliente, srv, price, preco):
    srv.respostas.append((200, produto_ok(no(price=price))))
    dados, _ = cliente.produto(SHOP, ITEM)
    assert dados["preco_1"] == preco
    assert Decimal(dados["preco_1"]) == Decimal(preco)


@pytest.mark.parametrize("taxa, texto", [("0.13", "13%"), ("0.135", "13,5%"), ("0.07", "7%")])
def test_pro01_comissao_em_percentual(cliente, srv, taxa, texto):
    srv.respostas.append((200, produto_ok(no(commissionRate=taxa))))
    dados, _ = cliente.produto(SHOP, ITEM)
    assert dados["taxa_comissao_afiliado"] == texto


def test_pro01_itemid_como_texto_tambem_e_o_item(cliente, srv):
    srv.respostas.append((200, produto_ok(no(item=str(ITEM), shop=str(SHOP)))))
    dados, motivo = cliente.produto(SHOP, ITEM)
    assert motivo is None and dados["id_produto_afiliado"] == f"{SHOP}.{ITEM}"


def test_pro02_zero_nos_fora_do_programa(cliente, srv):
    srv.respostas.append((200, produto_ok()))
    assert cliente.produto(SHOP, ITEM) == (None, "fora_do_programa")


def test_pro02_no_de_outro_item_divergente(cliente, srv):
    srv.respostas.append((200, produto_ok(no(item=ITEM + 1))))
    assert cliente.produto(SHOP, ITEM) == (None, "item_divergente")


def test_pro02_vinte_nos_caso_do_matchid_divergente(cliente, srv):
    srv.respostas.append((200, produto_ok(no(), *[no(item=ITEM + i) for i in range(1, 20)], mais=True)))
    assert cliente.produto(SHOP, ITEM) == (None, "item_divergente")


@pytest.mark.parametrize("price", ["", "  ", "abc", None, "NaN", "0", "-5"])
def test_pro02_preco_invalido_divergente(cliente, srv, price):
    srv.respostas.append((200, produto_ok(no(price=price))))
    assert cliente.produto(SHOP, ITEM) == (None, "item_divergente")


# --- LNK-01 -------------------------------------------------------------------------------------
def test_lnk01_origin_url_limpa_e_short_link(cliente, srv):
    srv.respostas.append((200, {"data": {"generateShortLink": {"shortLink": CURTO}}}))
    assert cliente.link_afiliado(SHOP, ITEM) == (CURTO, None)
    query = json.loads(srv.pedidos[0]["corpo"])["query"]
    assert "generateShortLink" in query
    assert f'originUrl: "https://shopee.com.br/product/{SHOP}/{ITEM}"' in query
    assert "utm_" not in query and "an_" not in query


def test_lnk01_sem_short_link_retem(cliente, srv):
    srv.respostas.append((200, {"data": {"generateShortLink": {"shortLink": ""}}}))
    assert cliente.link_afiliado(SHOP, ITEM) == (None, "api_indisponivel")


# --- ERR-01 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("corpo, mensagem", [(ERRO_ASSINATURA, "Invalid Signature"),
                                             (ERRO_EXPIRADO, "Request Expired")])
@pytest.mark.parametrize("chamada", ["produto", "link_afiliado"])
def test_err01_10020_com_http_200_e_credencial(cliente, srv, corpo, mensagem, chamada):
    srv.respostas.append((200, corpo))
    assert getattr(cliente, chamada)(SHOP, ITEM) == (None, "api_credencial")
    assert mensagem in cliente.detalhe


def test_err01_10030_limite(cliente, srv):
    srv.respostas.append((200, {"errors": [{"message": "error [10030]: rate limit",
                                            "extensions": {"code": 10030}}]}))
    assert cliente.produto(SHOP, ITEM) == (None, "api_limite")


def test_err01_outro_codigo_com_http_200_indisponivel(cliente, srv, capsys):
    srv.respostas.append((200, {"errors": [{"message": "error [11001]: corpo-secreto-da-resposta",
                                            "extensions": {"code": 11001}}]}))
    assert cliente.produto(SHOP, ITEM) == (None, "api_indisponivel")
    log = capsys.readouterr().out
    assert "11001" in log and "corpo-secreto-da-resposta" not in log


def test_err01_errors_ganha_de_data_com_http_200(cliente, srv):
    srv.respostas.append((200, {**produto_ok(no()), **ERRO_ASSINATURA}))
    assert cliente.produto(SHOP, ITEM) == (None, "api_credencial")


@pytest.mark.parametrize("status", [500, 429, 403])
def test_err01_http_diferente_de_200_indisponivel(cliente, srv, status):
    srv.respostas.append((status, produto_ok(no())))
    assert cliente.produto(SHOP, ITEM) == (None, "api_indisponivel")


def test_err01_json_ilegivel_indisponivel(cliente, srv):
    srv.respostas.append((200, b"<html>gateway</html>"))
    assert cliente.produto(SHOP, ITEM) == (None, "api_indisponivel")


def test_err01_timeout_indisponivel(api, srv):
    srv.atraso = 1.5
    c = api.Cliente(APP_ID, SECRET, timeout=0.3, endpoint=srv.url, relogio=lambda: TS)
    assert c.produto(SHOP, ITEM) == (None, "api_indisponivel")


def test_err01_sem_servidor_indisponivel(api):
    c = api.Cliente(APP_ID, SECRET, timeout=1, endpoint="http://127.0.0.1:9/graphql", relogio=lambda: TS)
    assert c.link_afiliado(SHOP, ITEM) == (None, "api_indisponivel")


# --- SEG-01 (cliente) ---------------------------------------------------------------------------
def test_seg01_nenhuma_saida_tem_credencial_nem_assinatura(api, srv, capsys):
    c = api.Cliente(APP_ID, SECRET, timeout=0.3, endpoint=srv.url, relogio=lambda: TS)
    srv.respostas += [(200, ERRO_ASSINATURA), (200, ERRO_EXPIRADO), (500, b"x"), (200, b"lixo"),
                      (200, produto_ok()), (200, produto_ok(no()))]
    textos = []
    for _ in range(6):
        textos.append(repr(c.produto(SHOP, ITEM)))
        textos.append(c.detalhe or "")
    srv.atraso = 1
    textos.append(repr(c.link_afiliado(SHOP, ITEM)))
    textos.append(repr(c))
    textos.append(capsys.readouterr().out)
    assinaturas = [p["headers"]["Authorization"].rsplit("=", 1)[1] for p in srv.pedidos]
    tudo = "\n".join(textos)
    assert "shopee api: ok item=" in tudo
    for segredo in [APP_ID, SECRET, *assinaturas]:
        assert segredo not in tudo


# --- RES-01 / RES-02 ----------------------------------------------------------------------------
OPAANLP = f"https://shopee.com.br/opaanlp/{SHOP}/{ITEM}?gads_t_sig=REDACTED&utm_source=an_REDACTED&utm_medium=affiliates"


class Saltos:
    """`abrir` falso: url -> (status, Location); guarda os pedidos."""

    def __init__(self, mapa):
        self.mapa = mapa
        self.pedidos = []

    def __call__(self, url, timeout):
        self.pedidos.append(url)
        resposta = self.mapa[url]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def test_res01_link_curto_301_para_opaanlp(api):
    abrir = Saltos({CURTO: (301, OPAANLP)})
    assert api.resolver(CURTO, abrir=abrir) == ((SHOP, ITEM), None)
    assert abrir.pedidos == [CURTO]


@pytest.mark.parametrize("url", [
    f"https://shopee.com.br/Batom-Matte-REDACTED-i.{SHOP}.{ITEM}",
    f"https://shopee.com.br/Batom-Matte-REDACTED-i.{SHOP}.{ITEM}?sp_atk=REDACTED&utm_source=an_REDACTED",
    f"https://shopee.com.br/universal-link/Batom-Matte-REDACTED-i.{SHOP}.{ITEM}?utm_source=an_REDACTED",
    f"https://shopee.com.br/product/{SHOP}/{ITEM}",
    f"https://www.shopee.com.br/product/{SHOP}/{ITEM}?utm_source=an_REDACTED",
])
def test_res01_formatos_da_loja_sem_pedido(api, url):
    abrir = Saltos({})
    assert api.resolver(url, abrir=abrir) == ((SHOP, ITEM), None)
    assert abrir.pedidos == []


def test_res01_dois_e_tres_saltos(api):
    abrir = Saltos({CURTO: (302, "https://s.shopee.com.br/REDACTED3"),
                    "https://s.shopee.com.br/REDACTED3": (301, f"https://shopee.com.br/universal-link/x-i.{SHOP}.{ITEM}")})
    assert api.resolver(CURTO, abrir=abrir) == ((SHOP, ITEM), None)
    tres = Saltos({CURTO: (301, "https://s.shopee.com.br/b"), "https://s.shopee.com.br/b": (301, "https://s.shopee.com.br/c"),
                   "https://s.shopee.com.br/c": (301, OPAANLP)})
    assert api.resolver(CURTO, abrir=tres) == ((SHOP, ITEM), None)
    assert len(tres.pedidos) == 3


def test_res02_quatro_saltos_nao_reconhecida(api):
    abrir = Saltos({CURTO: (301, "https://s.shopee.com.br/b"), "https://s.shopee.com.br/b": (301, "https://s.shopee.com.br/c"),
                    "https://s.shopee.com.br/c": (301, "https://s.shopee.com.br/d"),
                    "https://s.shopee.com.br/d": (301, OPAANLP)})
    assert api.resolver(CURTO, abrir=abrir) == (None, "url_nao_reconhecida")
    assert len(abrir.pedidos) == 3


def test_res02_pagina_sem_ids_nao_reconhecida(api):
    abrir = Saltos({CURTO: (301, "https://shopee.com.br/m/campanha-REDACTED"),
                    "https://shopee.com.br/m/campanha-REDACTED": (200, None)})
    assert api.resolver(CURTO, abrir=abrir) == (None, "url_nao_reconhecida")


@pytest.mark.parametrize("url", [f"https://shopee.com.br/x/{SHOP}/abc", f"https://shopee.com.br/{ITEM}",
                                 f"https://exemplo.com.br/product/{SHOP}/{ITEM}"])
def test_res02_formato_estranho_nao_reconhecida(api, url):
    abrir = Saltos({url: (200, None)})
    assert api.resolver(url, abrir=abrir) == (None, "url_nao_reconhecida")


def test_res02_destino_fora_da_shopee_nao_e_pedido(api):
    abrir = Saltos({CURTO: (301, "https://golpe.exemplo.com/1/2")})
    assert api.resolver(CURTO, abrir=abrir) == (None, "url_nao_reconhecida")
    assert abrir.pedidos == [CURTO]


@pytest.mark.parametrize("resposta", [OSError("timed out"), (503, None), (429, None)])
def test_res_rede_ou_5xx_e_passageiro(api, resposta):
    abrir = Saltos({CURTO: resposta})
    assert api.resolver(CURTO, abrir=abrir) == (None, "api_indisponivel")


def test_res_404_nao_reconhecida(api):
    assert api.resolver(CURTO, abrir=Saltos({CURTO: (404, None)})) == (None, "url_nao_reconhecida")


def test_res01_pedido_real_nao_segue_redirect(api):
    vistos = []

    class H(BaseHTTPRequestHandler):
        def _responder(self):
            vistos.append((self.command, self.path))
            self.send_response(301)
            self.send_header("Location", "/destino-REDACTED")
            self.send_header("Content-Length", "0")
            self.end_headers()
        do_HEAD = do_GET = _responder

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/REDACTED1"
        assert api.abrir_sem_seguir(url, 2) == (301, "/destino-REDACTED")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert vistos == [("HEAD", "/REDACTED1")]
