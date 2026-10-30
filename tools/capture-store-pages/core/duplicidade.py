"""
Oferta DUPLICADA (regra do usuario; criada 2026-10-09, revista 2026-10-13):
o mesmo produto repostado -- no mesmo grupo do WhatsApp ou em outro -- fica
com UMA so oferta ativa por janela de 24 h: a de MENOR preco; empate de preco
-> a MAIS RECENTE (DT_OFERTA, depois ID_OFERTA). As demais ficam inativas.

"Mesmo produto" = mesmo PRODUTO cadastrado (ID_PRODUTO -- o cadastro agrupa
pelo titulo, cobre variante/cor/tamanho com outro ASIN e anuncio/catalogo do
ML) OU mesmo codigo da loja na DS_URL_FINAL (ASIN Amazon, MLB Mercado Livre,
item Shopee). A janela vale para OS DOIS LADOS (+-24 h de DT_OFERTA): a
captura pode sair fora de ordem (ex. 35006/35008 em 13/10).

Ao publicar uma oferta (core/ofertas.publicar_oferta):
  * existe ativa na janela que GANHA dela -> nao publica, vira duplicada
    (oferta_mantida + marcar_duplicada);
  * senao publica e DESATIVA as ativas da janela que ela vence
    (perdedoras + marcar_duplicada) -- antes de 13/10 a anterior mais cara
    continuava no site.
Sem preco -> nunca entra na disputa (na duvida, publica).

Chamado de dentro de core/ofertas.publicar_oferta -- assim vale para o main.py
e para todos os backfills que republicam (senao a STP_OFERTA_PUBLICAR, que
grava ST_ATIVO=1, reativaria a duplicada).
"""

import re
from datetime import timedelta

JANELA = timedelta(hours=24)
PREFIXO = 'duplicada de '

_AMAZON = re.compile(r'/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})', re.IGNORECASE)
_ML = re.compile(r'MLB-?(\d{6,})', re.IGNORECASE)
_SHOPEE = re.compile(r'shopee\.com\.br/(?:product/(\d+)/(\d+)|.*?-i\.(\d+)\.(\d+))', re.IGNORECASE)


def chave_loja(url):
    """(chave, trecho p/ LIKE) do produto na loja, ou (None, None)."""
    url = url or ''
    m = _AMAZON.search(url)
    if m:
        asin = m.group(1).upper()
        return f'AMZ:{asin}', asin
    m = _ML.search(url)
    if m:
        return f'ML:{m.group(1)}', m.group(1)
    m = _SHOPEE.search(url)
    if m:
        loja, item = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return f'SHP:{loja}/{item}', item
    return None, None


def vence(preco_a, dt_a, id_a, preco_b, dt_b, id_b):
    """A oferta A fica no lugar da B? Menor preco; empate -> mais recente."""
    pa, pb = round(float(preco_a), 2), round(float(preco_b), 2)
    if pa != pb:
        return pa < pb
    return (dt_a, int(id_a)) > (dt_b, int(id_b))


def _concorrentes(db, id_oferta, url_final, dt_oferta, id_produto):
    """Ofertas ATIVAS do mesmo produto com DT_OFERTA a ate 24 h (antes ou
    depois) desta: [(id, preco, dt)]."""
    chave, trecho = chave_loja(url_final)
    filtros = []
    binds = {'id': int(id_oferta), 'ini': dt_oferta - JANELA, 'fim': dt_oferta + JANELA}
    if chave:
        filtros.append('DS_URL_FINAL LIKE :trecho')
        binds['trecho'] = f'%{trecho}%'
    if id_produto is not None:
        filtros.append('ID_PRODUTO = :prod')
        binds['prod'] = int(id_produto)
    if not filtros:
        return []
    def consultar(cur):
        cur.execute(
            "SELECT ID_OFERTA, VL_PRECO_POR, DT_OFERTA, DS_URL_FINAL, ID_PRODUTO FROM OFERTA "
            " WHERE ST_ATIVO = 1 AND ID_OFERTA <> :id AND VL_PRECO_POR IS NOT NULL "
            "   AND DT_OFERTA BETWEEN :ini AND :fim "
            f"  AND ({' OR '.join(filtros)}) "
            " ORDER BY VL_PRECO_POR, DT_OFERTA DESC, ID_OFERTA DESC", binds)
        out = []
        for id_outra, preco_outra, dt_outra, url_outra, prod_outra in cur:
            mesmo = ((chave and chave_loja(url_outra)[0] == chave)
                     or (id_produto is not None and prod_outra is not None
                         and int(prod_outra) == int(id_produto)))
            if mesmo:
                out.append((int(id_outra), preco_outra, dt_outra))
        return out

    return db.transacao(consultar, commit=False)


def oferta_mantida(db, id_oferta, url_final, preco, dt_oferta, id_produto=None):
    """ID da oferta ativa da janela que fica no lugar desta, ou None."""
    if preco is None or dt_oferta is None:
        return None
    for id_outra, preco_outra, dt_outra in _concorrentes(db, id_oferta, url_final,
                                                         dt_oferta, id_produto):
        if vence(preco_outra, dt_outra, id_outra, preco, dt_oferta, id_oferta):
            return id_outra
    return None


def perdedoras(db, id_oferta, url_final, preco, dt_oferta, id_produto=None):
    """IDs das ofertas ativas da janela que esta oferta vence (a desativar)."""
    if preco is None or dt_oferta is None:
        return []
    return [id_outra for id_outra, preco_outra, dt_outra
            in _concorrentes(db, id_oferta, url_final, dt_oferta, id_produto)
            if vence(preco, dt_oferta, id_oferta, preco_outra, dt_outra, id_outra)]


def marcar_duplicada(db, id_oferta, id_mantida):
    """Fila: ST_CAPTURA='9' + DS_CAPTURA='duplicada de N'. OFERTA (se a linha
    ja existir, ex. republicacao por backfill): desativada."""
    def marcar(cur):
        cur.execute("UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '9', DS_CAPTURA = :d "
                    "WHERE ID_OFERTA = :id", d=f'{PREFIXO}{id_mantida}', id=int(id_oferta))
        cur.execute("UPDATE OFERTA SET ST_ATIVO = 0, DT_DESATIVACAO = NVL(DT_DESATIVACAO, SYSDATE) "
                    "WHERE ID_OFERTA = :id AND NVL(ST_ATIVO, 1) <> 0", id=int(id_oferta))

    db.transacao(marcar)
