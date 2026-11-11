"""BSV-59 no lote real (_processar_lote): Shopee pela API de afiliados, sem navegador.

API falsa num servidor HTTP local; link curto resolvido por `abrir` falso; navegador e gerador
falsos que registram qualquer chamada. Credenciais ficticias e distintas de tudo (licao 11).
"""
import argparse
import json
import os
import time
from datetime import UTC, datetime, timedelta

import pytest
from conftest import Loja
from test_shopee_api import ERRO_ASSINATURA, ERRO_EXPIRADO, Servidor, no, produto_ok

APP_ID = "appid-lote-5150"
SECRET = "secret-lote-9086"
SHOP, ITEM = 300100200, 22334455667
CURTO = "https://s.shopee.com.br/REDACTED{}"
TERCEIRO = (f"https://shopee.com.br/opaanlp/{SHOP}/{{}}?gads_t_sig=REDACTED&utm_source=an_TERCEIRO"
            "&utm_medium=affiliates")
LINK = "https://s.shopee.com.br/NOSSO{}"
ALERTA = {"telegram_token": "123456:SEGREDO_REDACTED", "telegram_chat_id": "-100REDACTED"}
T0 = datetime(2026, 11, 10, 10, 0)


def item(i):
    return ITEM + i


class Relogio:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t

    def andar(self, **k):
        self.t += timedelta(**k)


class Pagina:
    url = ""

    def wait_for_timeout(self, ms):
        pass

    def is_closed(self):
        return False


class Db:
    sem_conexao = False

    def __init__(self):
        self.capturas, self.erros, self.ofertas = {}, [], []

    def atualizar_captura(self, id_oferta, out, ativo=False):
        self.capturas[id_oferta] = dict(out)
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


class ApiFalsa(Servidor):
    """Responde pelo tipo da query: produto do item pedido e link `LINK.format(item)`; `falhas` antes de tudo."""

    def __init__(self):
        super().__init__()
        self.falhas = []
        self.produtos = {}        # item -> resposta do productOfferV2
        dono = self
        H = self.httpd.RequestHandlerClass
        original = H.do_POST

        def do_POST(handler):
            corpo = handler.rfile.read(int(handler.headers["Content-Length"]))
            query = json.loads(corpo)["query"]
            if dono.falhas:
                dono.respostas.append(dono.falhas.pop(0))
            elif "generateShortLink" in query:
                it = int(query.split("/product/")[1].split("/")[1].split('"')[0])
                dono.respostas.append((200, {"data": {"generateShortLink": {"shortLink": LINK.format(it)}}}))
            else:
                it = int(query.split("itemId: ")[1].split(")")[0])
                dono.respostas.append((200, dono.produtos.get(it, produto_ok(no(item=it, shop=SHOP)))))
            handler.rfile = _Reler(corpo)
            original(handler)
        H.do_POST = do_POST


class _Reler:
    def __init__(self, dados):
        self.dados = dados

    def read(self, n):
        return self.dados

    def close(self):
        pass


@pytest.fixture
def amb(lojas, monkeypatch, tmp_path):
    api = ApiFalsa()
    rel = Relogio()
    enviados, navegou, gerador, baixadas = [], [], [], []
    cfg = {"shopee_afiliado": {"habilitado": True, "app_id": APP_ID, "app_secret": SECRET, "timeout_segundos": 2},
           "alerta": ALERTA, "bloqueio": {"pausa_minutos": 60}}
    monkeypatch.setattr(lojas.estado, "_ler_config", lambda *a, **k: cfg)
    monkeypatch.setattr(lojas.shopee_api, "ENDPOINT", api.url)
    redirects = {}

    def abrir(url, timeout):
        return 301, redirects[url]
    monkeypatch.setattr(lojas.shopee_api, "abrir_sem_seguir", abrir)
    por_dominio = {"shopee.com.br": "shopee", "amazon.com.br": "amazon", "mercadolivre.com.br": "mercadolivre"}
    monkeypatch.setattr(lojas.registry, "resolver_loja",
                        lambda url: next((v for k, v in por_dominio.items() if k in (url or "")), None))
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: Loja())
    monkeypatch.setattr(lojas.registry, "nome_loja",
                        lambda loja, url=None: {"shopee": "Shopee", "amazon": "Amazon",
                                                "mercadolivre": "Mercado Livre"}.get(loja, ""))
    monkeypatch.setattr(lojas.produtos, "cadastrar_produto", lambda db, i, linha: (900 + i, None, None))
    monkeypatch.setattr(lojas.imagens_produto, "publicar_imagens_produto", lambda *a: 0)
    monkeypatch.setattr(lojas.afiliados, "garantir_carregado", lambda db: True)
    monkeypatch.setattr(lojas.afiliados, "loja_ativa", lambda loja: True)

    def publicar(db, id_oferta, *a):
        db.ofertas.append(id_oferta)
        return True, None
    monkeypatch.setattr(lojas.ofertas, "publicar_oferta", publicar)

    def navegar(page, url, timeout=0):
        navegou.append(url)
        page.url = url
    monkeypatch.setattr(lojas, "_goto_robusto", navegar)
    def capturar(page, loja, url_final=""):
        gerador.append(loja)
        return {"url_afiliado": "https://link.amazon/REDACTED"} if loja != "shopee" else {}
    monkeypatch.setattr(lojas.link_afiliado, "capturar", capturar)
    monkeypatch.setattr(lojas.link_afiliado, "_shopee", lambda *a: gerador.append("_shopee"))
    monkeypatch.setattr(lojas.link_afiliado, "_aba_shopee", lambda *a: gerador.append("_aba_shopee"))
    monkeypatch.setattr(lojas.images, "download_image",
                        lambda url, destino, **k: baixadas.append((url, destino)) or True)

    pausa = lojas.bloqueio.PausaLojas(cfg, agora=rel, nome=lambda loja: lojas.registry.nome_loja(loja))
    pausa.avisar = lojas.bloqueio.Avisador(cfg, enviar=lambda t, c, m: enviados.append(m)).avisar

    def shopee(i):
        redirects[CURTO.format(i)] = TERCEIRO.format(item(i))
        return CURTO.format(i)

    def rodar(linhas, db=None):
        db = db or Db()
        rows = [{"ID_OFERTA": i, "url": u, "numero_da_captura": str(i), "DS_ORIGEM": "g"} for i, u in linhas]
        saidas, _, _ = lojas._processar_lote(Pagina(), rows, db, True, str(tmp_path), set(), pausa)
        return {o["ID_OFERTA"]: o for o in saidas}, db

    yield argparse.Namespace(api=api, rel=rel, cfg=cfg, enviados=enviados, navegou=navegou, gerador=gerador,
                             baixadas=baixadas, pausa=pausa, img=str(tmp_path), rodar=rodar, shopee=shopee, redirects=redirects)
    api.fechar()


def amz(i):
    return f"https://www.amazon.com.br/dp/B0REDACTED{i}"


def ml(i):
    return f"https://produto.mercadolivre.com.br/MLB-REDACTED{i}"


# --- PRO-01 / LNK-01 / NAV-01 -------------------------------------------------------------------
def test_pro01_linha_da_shopee_vira_ok_com_as_chaves_da_api(amb, lojas, capsys):
    saidas, db = amb.rodar([(1, amb.shopee(1))])
    out = saidas[1]
    assert out["status_captura"] == "ok" and 1 in db.capturas and db.ofertas == [1]
    gravado = db.capturas[1]
    assert gravado["produto_titulo"] == "Batom Matte REDACTED"
    assert gravado["preco_1"] == "19.93"
    assert gravado["avaliacao_nota"] == "4.6"
    assert gravado["quantidade_vendida"] == "1351"
    assert gravado["taxa_comissao_afiliado"] == "13%"
    assert gravado["id_produto_afiliado"] == f"{SHOP}.{item(1)}"
    assert gravado["url_afiliado"] == LINK.format(item(1))
    assert amb.baixadas == [("https://cf.shopee.com.br/file/REDACTED", os.path.join(amb.img, "1", "img_1.jpg"))]
    assert gravado["pasta_imagens"] == os.path.join(amb.img, "1")
    assert gravado["url_final"] == f"https://shopee.com.br/product/{SHOP}/{item(1)}"
    assert "oracle=ok" in capsys.readouterr().out
    assert lojas.ponteiro == [1]


@pytest.mark.parametrize("price, preco", [("89.99", "89.99"), ("19.9", "19.90")])
def test_pro01_preco_vr_preco_1(amb, price, preco):
    amb.api.produtos[item(1)] = produto_ok(no(item=item(1), price=price))
    _, db = amb.rodar([(1, amb.shopee(1))])
    assert db.capturas[1]["preco_1"] == preco


def test_lnk01_origin_url_limpa_mesmo_com_utm_de_terceiro(amb):
    _, db = amb.rodar([(1, amb.shopee(1))])
    queries = [json.loads(p["corpo"])["query"] for p in amb.api.pedidos]
    links = [q for q in queries if "generateShortLink" in q]
    assert len(links) == 1
    assert f'originUrl: "https://shopee.com.br/product/{SHOP}/{item(1)}"' in links[0]
    assert "TERCEIRO" not in "".join(queries) and "utm_" not in "".join(queries)
    assert db.capturas[1]["url_afiliado"] == LINK.format(item(1))
    assert "TERCEIRO" not in db.capturas[1]["url_afiliado"]


def test_nav01_ligado_nao_abre_a_shopee_nem_o_gerador(amb):
    amb.rodar([(1, amb.shopee(1)), (2, amz(2)), (3, amb.shopee(3))])
    assert not any("shopee" in u for u in amb.navegou)
    assert amb.navegou == [amz(2)]
    assert "shopee" not in amb.gerador and "_shopee" not in amb.gerador and "_aba_shopee" not in amb.gerador


# --- CFG-01 ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("bloco", [None, {"habilitado": False, "app_id": APP_ID, "app_secret": SECRET},
                                   {"app_id": APP_ID, "app_secret": SECRET}])
def test_cfg01_desligado_ou_ausente_e_o_navegador_de_hoje(amb, bloco):
    if bloco is None:
        del amb.cfg["shopee_afiliado"]
    else:
        amb.cfg["shopee_afiliado"] = bloco
    saidas, _ = amb.rodar([(1, amb.shopee(1))])
    assert amb.navegou == [CURTO.format(1)]
    assert amb.gerador == ["shopee"]
    assert amb.api.pedidos == []
    assert saidas[1]["status_captura"] == "ok"


# --- PRO-02 / RES-02: '9' com o motivo ------------------------------------------------------------
@pytest.mark.parametrize("resposta, motivo", [
    (produto_ok(), "fora_do_programa"),
    (produto_ok(no(item=ITEM + 999)), "item_divergente"),
    (produto_ok(*[no(item=ITEM + 1 + i) for i in range(20)], mais=True), "item_divergente"),
    (produto_ok(no(item=ITEM + 1, price="")), "item_divergente"),
])
def test_pro02_falha_do_item_vira_9_com_motivo(amb, lojas, resposta, motivo):
    amb.api.produtos[item(1)] = resposta
    _, db = amb.rodar([(1, amb.shopee(1)), (2, amz(2))])
    assert db.erros == [(1, motivo)] and 1 not in db.capturas and db.ofertas == [2]
    assert lojas.ponteiro == [2]


def test_res02_url_nao_reconhecida_vira_9(amb):
    amb.redirects[CURTO.format(1)] = "https://shopee.com.br/m/campanha-REDACTED"
    amb.redirects["https://shopee.com.br/m/campanha-REDACTED"] = None
    _, db = amb.rodar([(1, CURTO.format(1))])
    assert db.erros == [(1, "url_nao_reconhecida")] and amb.api.pedidos == []


# --- FAL-01 / ERR-01 ------------------------------------------------------------------------------
def test_fal01_timeout_retida_nada_gravado_ponteiro_travado(amb, lojas, capsys):
    amb.cfg["shopee_afiliado"]["timeout_segundos"] = 1     # piso do timeout (TIMEOUT_MIN)
    amb.api.atraso = 1.5
    saidas, db = amb.rodar([(1, amb.shopee(1))])
    amb.api.atraso = 0
    saidas2, _ = amb.rodar([(2, amz(2))], db=db)
    assert saidas2[2]["status_captura"] == "ok" and 2 in db.ofertas      # Amazon segue; ponteiro nao passa da 1
    assert saidas[1]["status_captura"] == "shopee_api_indisponivel"
    assert "oracle=retida(0)" in capsys.readouterr().out
    assert 1 not in db.capturas and db.erros == [] and 1 not in db.ofertas
    assert lojas.ponteiro == [] and db.trava_ponteiro == 1


@pytest.mark.parametrize("falha", [(200, ERRO_ASSINATURA), (200, ERRO_EXPIRADO), (500, b"x"),
                                   (200, {"errors": [{"message": "x", "extensions": {"code": 10030}}]}),
                                   (200, {"errors": [{"message": "x", "extensions": {"code": 11001}}]})])
def test_err01_falhas_da_api_retem_nunca_9(amb, falha):
    amb.api.falhas.append(falha)
    saidas, db = amb.rodar([(1, amb.shopee(1))])
    assert saidas[1]["status_captura"] == "shopee_api_indisponivel"
    assert db.erros == [] and db.capturas == {}


def test_err01_falha_no_link_tambem_retem(amb):
    amb.api.falhas += [(200, produto_ok(no(item=item(1)))), (200, ERRO_ASSINATURA)]
    saidas, db = amb.rodar([(1, amb.shopee(1))])
    assert saidas[1]["status_captura"] == "shopee_api_indisponivel" and db.capturas == {}


# --- PAU-01 ---------------------------------------------------------------------------------------
def test_pau01_tres_seguidas_pausam_a_shopee_avisam_uma_vez_e_voltam(amb):
    amb.api.falhas += [(200, ERRO_ASSINATURA)] * 3
    saidas, _ = amb.rodar([(1, amb.shopee(1)), (2, amz(2)), (3, amb.shopee(3)), (4, ml(4)),
                           (5, amb.shopee(5)), (6, amb.shopee(6)), (7, amz(7))])
    st = {i: o["status_captura"] for i, o in saidas.items()}
    assert st[1] == st[3] == st[5] == "shopee_api_indisponivel"
    assert st[6] == "loja_pausada"
    assert st[2] == st[4] == st[7] == "ok"
    assert amb.pausa.em_pausa("shopee") and not amb.pausa.em_pausa("amazon")
    assert len(amb.enviados) == 1
    aviso = amb.enviados[0]
    assert "Shopee" in aviso and "api_credencial" in aviso and "Invalid Signature" in aviso
    assert "conferir app_id/app_secret" in aviso
    pedidos = len(amb.api.pedidos)
    amb.rel.andar(minutes=61)
    saidas2, db2 = amb.rodar([(6, amb.shopee(6))])
    assert saidas2[6]["status_captura"] == "ok" and 6 in db2.ofertas
    assert len(amb.api.pedidos) == pedidos + 2
    assert len(amb.enviados) == 2 and "voltou" in amb.enviados[1] and "Shopee" in amb.enviados[1]


def test_pau01_indisponivel_avisa_sem_falar_de_credencial(amb):
    amb.api.falhas += [(503, b"x")] * 3
    amb.rodar([(1, amb.shopee(1)), (2, amb.shopee(2)), (3, amb.shopee(3))])
    assert len(amb.enviados) == 1
    assert "api_indisponivel" in amb.enviados[0] and "app_secret" not in amb.enviados[0]


def test_pau01_lembrete_mantem_o_motivo(amb):
    amb.api.falhas += [(200, ERRO_EXPIRADO)] * 3
    amb.rodar([(1, amb.shopee(1)), (2, amb.shopee(2)), (3, amb.shopee(3))])
    amb.rel.andar(hours=6)
    amb.pausa.lembrar()
    assert len(amb.enviados) == 2 and "Request Expired" in amb.enviados[1]


# --- SEG-01 ---------------------------------------------------------------------------------------
def test_seg01_credencial_nunca_sai(amb, lojas, capsys, monkeypatch):
    gravados = []
    monkeypatch.setattr(lojas.csv_io, "write_destino", lambda caminho, header, rows: gravados.append(rows))
    monkeypatch.setattr(lojas, "em_log", lambda nome: nome)
    amb.api.falhas += [(200, ERRO_ASSINATURA)] * 3 + [(200, ERRO_EXPIRADO), (500, b"x")]
    saidas, _ = amb.rodar([(i, amb.shopee(i)) for i in range(1, 4)])
    amb.rel.andar(minutes=61)
    saidas2, _ = amb.rodar([(4, amb.shopee(4)), (5, amb.shopee(5)), (6, amb.shopee(6))])
    amb.rel.andar(hours=7)
    amb.pausa.lembrar()
    lojas._gravar_csv(list(saidas.values()) + list(saidas2.values()), ["ID_OFERTA"], "teste")
    assinaturas = [p["headers"]["Authorization"].rsplit("=", 1)[1] for p in amb.api.pedidos]
    assert assinaturas and amb.enviados
    tudo = "\n".join([capsys.readouterr().out, repr(saidas), repr(saidas2), repr(gravados), *amb.enviados])
    for segredo in [APP_ID, SECRET, *assinaturas]:
        assert segredo not in tudo


# --- DOC-01 ---------------------------------------------------------------------------------------
def test_doc01_readme_exemplo_e_sql():
    from conftest import LOJAS
    leia = (LOJAS / "README.md").read_text(encoding="utf-8")
    secao = leia.split("## Shopee pela API de afiliados")[1]
    for termo in ("api_indisponivel", "api_credencial", "api_limite", "fora_do_programa", "item_divergente",
                  "url_nao_reconhecida", "habilitado", "conf/config.json", "O que se perdeu",
                  "conferir `app_id`/`app_secret`", "Request Expired"):
        assert termo in secao, termo
    exemplo = json.loads((LOJAS / "conf" / "config.example.json").read_text(encoding="utf-8"))
    bloco = exemplo["shopee_afiliado"]
    assert bloco["habilitado"] is False and bloco["timeout_segundos"] == 20 and "_obs" in bloco
    assert bloco["app_id"] == "<app_id>" and bloco["app_secret"] == "<app_secret>"
    sql = (LOJAS / "sql" / "BSV-59_retidas_shopee.sql").read_text(encoding="utf-8")
    assert ("UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '9', DS_CAPTURA = 'descartada_atraso_bsv'\n"
            " WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;") in sql


# --- BSV-57 x BSV-59: batimento no caminho da API e na pausa da Shopee ----------------------------
T_BAT = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)


@pytest.fixture
def batidas(lojas, monkeypatch):
    registro = []
    monkeypatch.setattr(lojas.batimento, "agora_utc", lambda: T_BAT)
    monkeypatch.setattr(lojas.batimento, "gravar_atomico", lambda caminho, dados: registro.append(dict(dados)) or True)
    return registro


def test_bat_api_cada_linha_da_shopee_pela_api_renova_o_batimento(amb, batidas):
    """Lote so de Shopee pela API (sem navegador): uma batida por linha, ok ou retida."""
    amb.api.falhas.append((503, b"x"))   # a 1a linha fica retida (passageiro), a 2a e a 3a vao ok
    saidas, _ = amb.rodar([(1, amb.shopee(1)), (2, amb.shopee(2)), (3, amb.shopee(3))])
    assert [saidas[i]["status_captura"] for i in (1, 2, 3)] == ["shopee_api_indisponivel", "ok", "ok"]
    assert amb.navegou == [] and len(amb.api.pedidos) == 5
    assert [b["fase"] for b in batidas] == ["linha"] * 3
    assert all(b["robo"] == "lojas" and b["prazo"] == "2026-11-10T13:10:00Z" for b in batidas)


def test_bat_api_linha_que_vira_9_pela_api_tambem_renova(amb, batidas):
    amb.api.produtos[item(1)] = produto_ok()
    _, db = amb.rodar([(1, amb.shopee(1))])
    assert db.erros == [(1, "fora_do_programa")]
    assert [b["fase"] for b in batidas] == ["linha"]


class _Tempo:
    """Proxy do `time` do robo com `monotonic` fixo; o resto delega ao `time` real."""

    def __init__(self, monotonic):
        self._mono = monotonic

    def monotonic(self):
        return self._mono

    def __getattr__(self, nome):
        return getattr(time, nome)


def _monitorar_com_pausa(lojas, monkeypatch, amb, batidas, filas):
    """Roda o `_monitorar` real com a pausa da Shopee do `amb`; cada espera registra a ultima batida.
    Acabadas as `filas`, a leitura seguinte (depois da batida 'varredura') encerra o monitor."""
    esperas = []
    respostas = iter(filas)

    def ler(*a, **k):
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None

    # monotonic fixo (> 1 h de uptime): a varredura de validade roda na 1a volta em qualquer maquina,
    # inclusive no runner do CI recem-ligado (licao 25: nada de depender do relogio real).
    monkeypatch.setattr(lojas, "time", _Tempo(10_000.0))
    monkeypatch.setattr(lojas, "_pausa_padrao", lambda: amb.pausa)
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", lambda s: esperas.append((s, dict(batidas[-1]) if batidas else None)))
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda *a: None)
    monkeypatch.setattr(lojas, "_gravar_csv", lambda *a, **k: None)
    monkeypatch.setattr(lojas, "_resumo_oracle", lambda *a, **k: None)
    lojas._monitorar(None, Pagina(), Db(), argparse.Namespace(desde=None, limite=0), [], amb.img, 3, None)
    return esperas


def test_bat_pausa_api_shopee_dorme_sempre_batendo_com_prazo_de_acordar(lojas, monkeypatch, amb, batidas):
    """Shopee pausada pela API e fila so de Shopee: o robo dorme, e toda espera vem depois de uma
    batida 'dormindo' com prazo = acordar + 10 min (regra da BSV-57)."""
    amb.api.falhas += [(200, ERRO_ASSINATURA)] * 3
    amb.rodar([(1, amb.shopee(1)), (2, amb.shopee(2)), (3, amb.shopee(3))])
    assert amb.pausa.em_pausa("shopee")
    batidas.clear()
    pedidos = len(amb.api.pedidos)
    fila = [{"ID_OFERTA": i, "url": amb.shopee(i), "numero_da_captura": str(i), "DS_ORIGEM": "g"} for i in (1, 2)]
    esperas = _monitorar_com_pausa(lojas, monkeypatch, amb, batidas, [fila, fila])
    assert len(amb.api.pedidos) == pedidos                     # em pausa: a API nao e chamada
    assert [s for s, _ in esperas] == [180, 180]
    for s, ultima in esperas:
        assert ultima is not None and ultima["fase"] == "dormindo"
        assert ultima["prazo"] == "2026-11-10T13:13:00Z"       # 13:00 + 3 min de sono + 10 min
    assert [b["fase"] for b in batidas] == ["varredura", "validade", "dormindo", "varredura", "dormindo", "varredura"]


def test_bat_retida_pela_api_antes_da_pausa_nao_espera_sem_bater(lojas, monkeypatch, amb, batidas):
    """1 falha da API (sem pausa ainda): a linha fica retida, o monitor rele na hora e bate na varredura."""
    amb.api.falhas.append((503, b"x"))
    fila = [{"ID_OFERTA": 1, "url": amb.shopee(1), "numero_da_captura": "1", "DS_ORIGEM": "g"}]
    esperas = _monitorar_com_pausa(lojas, monkeypatch, amb, batidas, [fila, []])
    fases = [b["fase"] for b in batidas]
    assert fases == ["varredura", "validade", "linha", "varredura", "dormindo", "varredura"]
    assert len(esperas) == 1 and esperas[0][1]["fase"] == "dormindo"


# --- Excecao inesperada no caminho da API (dono, 11/11): passageira, nunca '9' --------------------
def _produto_que_quebra(lojas, monkeypatch):
    assinatura = lojas.shopee_api.assinar(APP_ID, 1, "{}", SECRET)

    def quebra(self, shop_id, item_id):
        raise RuntimeError(f"bug com {APP_ID} {SECRET} Signature={assinatura} {assinatura}")
    monkeypatch.setattr(lojas.shopee_api.Cliente, "produto", quebra)
    return assinatura


def test_exc_excecao_inesperada_retem_a_linha_e_o_lote_segue(amb, lojas, monkeypatch, capsys):
    assinatura = _produto_que_quebra(lojas, monkeypatch)
    saidas, db = amb.rodar([(1, amb.shopee(1)), (2, amz(2))])
    assert saidas[1]["status_captura"] == "shopee_api_indisponivel"
    assert saidas[2]["status_captura"] == "ok" and 2 in db.ofertas            # o lote seguiu
    assert db.erros == [] and 1 not in db.capturas and 1 not in db.ofertas    # nada de '9'
    assert lojas.ponteiro == [] and db.trava_ponteiro == 1                    # retida em '0'
    saida = capsys.readouterr().out
    assert "oracle=retida(0)" in saida and "RuntimeError: bug com" in saida
    for segredo in (APP_ID, SECRET, assinatura):
        assert segredo not in saida


def test_exc_tres_excecoes_pausam_a_shopee_com_aviso_sem_segredo(amb, lojas, monkeypatch):
    assinatura = _produto_que_quebra(lojas, monkeypatch)
    saidas, _ = amb.rodar([(1, amb.shopee(1)), (2, amb.shopee(2)), (3, amb.shopee(3)), (4, amb.shopee(4))])
    assert [saidas[i]["status_captura"] for i in (1, 2, 3)] == ["shopee_api_indisponivel"] * 3
    assert saidas[4]["status_captura"] == "loja_pausada" and amb.pausa.em_pausa("shopee")
    assert len(amb.enviados) == 1 and "RuntimeError" in amb.enviados[0]
    for segredo in (APP_ID, SECRET, assinatura):
        assert segredo not in amb.enviados[0]
