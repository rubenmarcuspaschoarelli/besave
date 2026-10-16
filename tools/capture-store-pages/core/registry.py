import unicodedata
from urllib.parse import urlparse

from core import estado
from stores.amazon import AmazonStore
from stores.shopee import ShopeeStore
from stores.mercadolivre import MercadoLivreStore
from stores.magazineluiza import MagazineLuizaStore
from stores.schemaorg import SchemaOrgStore

# Todas as lojas conhecidas. Amazon/Shopee/MercadoLivre e a SchemaOrgStore
# (e-commerces com JSON-LD: epoca, zzmall, belezanaweb) estao implementadas;
# MagazineLuiza segue placeholder e retorna "loja_nao_implementada".
_STORE_CLASSES = [AmazonStore, ShopeeStore, MercadoLivreStore, MagazineLuizaStore,
                  SchemaOrgStore]

# Instancia unica por loja (reaproveitada em todas as linhas do CSV).
_STORES = {cls.nome: cls() for cls in _STORE_CLASSES}

# de-para dominio -> nome da loja (montado a partir da config de cada loja).
_DOMAIN_TO_STORE = {}
for _cls in _STORE_CLASSES:
    for _dom in _cls.dominios:
        _DOMAIN_TO_STORE[_dom.strip().lower()] = _cls.nome


def _netloc(url):
    net = urlparse(url).netloc.lower()
    return net[4:] if net.startswith('www.') else net


def resolver_loja(url):
    # Retorna o nome da loja a partir do dominio da URL, ou None se desconhecida.
    if not url:
        return None
    net = urlparse(url).netloc.lower()
    if net in _DOMAIN_TO_STORE:
        return _DOMAIN_TO_STORE[net]
    net_sem_www = net[4:] if net.startswith('www.') else net
    return _DOMAIN_TO_STORE.get(net_sem_www)


def get_store(nome):
    # Retorna a instancia da loja SE ela estiver implementada (tem colunas de
    # saida). Placeholders retornam None.
    store = _STORES.get(nome)
    if store is None or not store.output_columns_implemented():
        return None
    return store


# --- lojas ativas (conf/config.json -> "lojas_ativas") -----------------------
# Lido UMA vez por execucao: o monitor fica horas no ar e o config.json e
# reescrito a cada gravacao (ponteiro de retomada). Para trocar a lista sem
# reiniciar, chame recarregar_lojas_ativas().
_LOJAS_ATIVAS = None


def _chave(nome):
    # Comparacao tolerante ao que o usuario digita no config.json: ignora caixa,
    # espacos extras e acentos ("Época Cosméticos" == "epoca cosmeticos").
    texto = unicodedata.normalize('NFKD', str(nome or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.lower().split())


def recarregar_lojas_ativas():
    """Rele "lojas_ativas" do config.json. Devolve a lista de nomes."""
    global _LOJAS_ATIVAS
    nomes = estado.ler_lojas_ativas()
    _LOJAS_ATIVAS = {_chave(n) for n in nomes}
    return nomes


def nome_loja(loja, url=None):
    """Nome COMERCIAL da loja ('Mercado Livre'), a partir do nome interno.

    A URL importa para as stores que atendem varias lojas (SchemaOrgStore).
    Loja desconhecida -> ''.
    """
    store = _STORES.get(loja)
    if store is None:
        return ''
    return store.nome_loja(url)


def loja_ativa(loja, url=None):
    """A oferta e de uma loja que entra em producao? (coluna ST_ATIVO)

    True somente para as lojas listadas em "lojas_ativas" no config.json. As
    demais continuam sendo capturadas e mapeadas -- nascem inativas para nao
    serem publicadas ainda. Loja desconhecida/nao implementada -> False.
    """
    if _LOJAS_ATIVAS is None:
        recarregar_lojas_ativas()
    nome = nome_loja(loja, url)
    return bool(nome) and _chave(nome) in _LOJAS_ATIVAS


def union_output_columns():
    # Uniao ordenada das colunas capturadas por todas as lojas implementadas.
    cols = []
    for nome in (c.nome for c in _STORE_CLASSES):
        store = _STORES[nome]
        if not store.output_columns_implemented():
            continue
        for col in store.output_columns():
            if col not in cols:
                cols.append(col)
    return cols
