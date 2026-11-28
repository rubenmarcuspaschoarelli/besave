"""URL limpa por loja, chave de produto e encurtadores (BSV-66, Saídas 4 e 5).

A URL de origem pode ter marca de afiliado de terceiro (`tag=`, `matt_`, `utm_`...): só a URL limpa vai
para log, banco ou comparação.
"""

import re
from urllib.parse import urljoin, urlsplit

AMAZON, MERCADO_LIVRE, SHOPEE = 'AMAZON', 'MERCADO LIVRE', 'SHOPEE'
URL_MAX = 350
SALTOS_MAX = 3

_ASIN = re.compile(r'/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?=[/?#]|$)', re.IGNORECASE)
_SHP_PRODUCT = re.compile(r'^/product/(\d+)/(\d+)/?$')
_SHP_I = re.compile(r'^/[^/]*-i\.(\d+)\.(\d+)/?$')
_SHP_GERAL = re.compile(r'^/[^/]+/(\d+)/(\d+)/?$')


def _partes(url):
    try:
        p = urlsplit((url or '').strip())
    except ValueError:
        return None
    if p.scheme.lower() not in ('http', 'https') or not p.hostname:
        return None
    return p


def _dominio(host, dominio):
    return host == dominio or host.endswith('.' + dominio)


def eh_encurtador(url):
    p = _partes(url)
    if p is None:
        return False
    host = p.hostname.lower()
    if host in ('meli.la', 'amzn.to', 's.shopee.com.br'):
        return True
    return host in ('mercadolivre.com', 'www.mercadolivre.com') and p.path.startswith('/sec/')


def limpar(url):
    """-> (loja, url_limpa, None) ou (None, None, motivo) com motivo loja_fora|url_invalida|url_longa."""
    p = _partes(url)
    if p is None:
        return None, None, 'url_invalida'
    host = p.hostname.lower()
    if _dominio(host, 'amazon.com.br'):
        m = _ASIN.search(p.path)
        if not m:
            return None, None, 'url_invalida'
        loja, limpa = AMAZON, f'https://www.amazon.com.br/dp/{m.group(1).upper()}'
    elif _dominio(host, 'mercadolivre.com.br'):
        loja, limpa = MERCADO_LIVRE, f'{p.scheme.lower()}://{host}{p.path or "/"}'
    elif host in ('shopee.com.br', 'www.shopee.com.br'):
        m = _SHP_PRODUCT.match(p.path) or _SHP_I.match(p.path) or _SHP_GERAL.match(p.path)
        if not m:
            return None, None, 'url_invalida'
        loja, limpa = SHOPEE, f'https://shopee.com.br/product/{m.group(1)}/{m.group(2)}'
    else:
        return None, None, 'loja_fora'
    if len(limpa) > URL_MAX:
        return None, None, 'url_longa'
    return loja, limpa, None


def host(url):
    p = _partes(url)
    return p.hostname.lower() if p else '?'


def resolver_encurtador(url, location):
    """Segue até 3 saltos com `location(url) -> str | None` (uma requisição sem seguir redirect cada).

    Devolve a URL final (fora de encurtador) ou None se não resolveu.
    """
    atual = url
    for _ in range(SALTOS_MAX):
        if not eh_encurtador(atual):
            return atual
        try:
            destino = location(atual)
        except Exception:  # noqa: BLE001 - qualquer falha = não resolveu
            return None
        if not destino:
            return None
        atual = urljoin(atual, destino.strip())
        if _partes(atual) is None:
            return None
    return None if eh_encurtador(atual) else atual


# Mesma regra de capture-store-pages/core/duplicidade.chave_loja, reimplementada (regra 3 da spec).
_AMZ = re.compile(r'/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})', re.IGNORECASE)
_ML = re.compile(r'MLB-?(\d{6,})', re.IGNORECASE)
_SHP = re.compile(r'shopee\.com\.br/(?:product/(\d+)/(\d+)|.*?-i\.(\d+)\.(\d+))', re.IGNORECASE)


def chave_loja(url):
    """(chave, trecho para LIKE) do produto na loja, ou (None, None)."""
    url = url or ''
    m = _AMZ.search(url)
    if m:
        asin = m.group(1).upper()
        return f'AMZ:{asin}', asin
    m = _ML.search(url)
    if m:
        return f'ML:{m.group(1)}', m.group(1)
    m = _SHP.search(url)
    if m:
        loja, item = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return f'SHP:{loja}/{item}', item
    return None, None
