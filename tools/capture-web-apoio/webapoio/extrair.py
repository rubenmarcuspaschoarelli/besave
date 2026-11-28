"""Extração das ofertas do HTML da lista de cada site (BSV-66, Saída 2).

Cada extrator devolve `Extracao(ofertas, erro)`: `ofertas` tem todos os itens lidos, com `invalida`
preenchido nos que a tabela do site descarta; `erro` (texto) = estrutura mudou. Nunca levanta exceção.
"""

import html
import json
import re
from dataclasses import dataclass, field

from .oferta import PECHINCHOU, PELANDO, PROMOBIT, Oferta, data_iso, reais

PROMOBIT_STATUS = ('RECENTS', 'APPROVED', 'TOP_OFFER')
PRECO_FALSO = reais('0.01')


@dataclass
class Extracao:
    ofertas: list = field(default_factory=list)
    erro: str | None = None


def _texto(v):
    return v.strip() if isinstance(v, str) else ''


def _faltando(item, campos):
    return any(item.get(c) in (None, '') for c in campos)


def _montar(itens, campos, fazer):
    """Aplica `fazer` aos itens; item sem campo obrigatório vira `incompleta`. Todos incompletos = erro."""
    if not isinstance(itens, list):
        return Extracao(erro='lista ausente')
    ofertas, incompletas = [], 0
    for item in itens:
        if not isinstance(item, dict) or _faltando(item, campos):
            incompletas += 1
            ofertas.append(Oferta('', '', '', None, None, None, invalida='incompleta'))
            continue
        ofertas.append(fazer(item))
    if itens and incompletas == len(itens):
        return Extracao(ofertas=ofertas, erro='itens sem campo obrigatório')
    return Extracao(ofertas=ofertas)


# -- Pelando (Astro) ---------------------------------------------------------------------------------

_ILHA = re.compile(r'<astro-island\b[^>]*>', re.DOTALL)
_PROPS = re.compile(r'\bprops="([^"]*)"')


def _astro(v):
    """Serialização do Astro: `[0, valor]` (objeto: campos de novo `[tipo, valor]`), `[1, lista]`."""
    if not (isinstance(v, list) and len(v) == 2 and isinstance(v[0], int) and not isinstance(v[0], bool)):
        return v
    tipo, valor = v
    if tipo == 0:
        return {k: _astro(w) for k, w in valor.items()} if isinstance(valor, dict) else valor
    if tipo == 1:
        return [_astro(i) for i in valor] if isinstance(valor, list) else valor
    return valor


def _props_pelando(pagina):
    for tag in _ILHA.findall(pagina):
        m = _PROPS.search(tag)
        if m and 'initialDeals' in m.group(1):
            try:
                return json.loads(html.unescape(m.group(1)))
            except ValueError:
                return None
    return None


def _pelando(item):
    store = item.get('store') if isinstance(item.get('store'), dict) else {}
    of = Oferta(PELANDO, str(item['id']), _texto(item['title']), reais(item.get('price')), None,
                data_iso(item['createdAt']), url=_texto(item['sourceUrl']),
                loja_origem=_texto(store.get('name')))
    if item.get('status') != 'active':
        of.invalida = 'status'
    elif item.get('kind') != 'promotion':
        of.invalida = 'tipo'
    elif item.get('hideInFeed'):
        of.invalida = 'oculta'
    return of


def extrair_pelando(pagina):
    props = _props_pelando(pagina or '')
    if not isinstance(props, dict):
        return Extracao(erro='sem a ilha com initialDeals')
    deals = _astro(props.get('initialDeals'))
    if not isinstance(deals, list):
        return Extracao(erro='sem initialDeals')
    return _montar(deals, ('id', 'title', 'sourceUrl', 'createdAt', 'status', 'kind'), _pelando)


# -- Next.js (Promobit e Pechinchou) ------------------------------------------------------------------

_NEXT = re.compile(r'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def _next_data(pagina, caminho):
    m = _NEXT.search(pagina or '')
    if not m:
        return None, 'sem __NEXT_DATA__'
    try:
        dado = json.loads(m.group(1))
    except ValueError:
        return None, '__NEXT_DATA__ inválido'
    for chave in caminho:
        if not isinstance(dado, dict) or chave not in dado:
            return None, 'sem ' + '.'.join(caminho)
        dado = dado[chave]
    if not isinstance(dado, list):
        return None, 'sem ' + '.'.join(caminho)
    return dado, None


def _preco_de(de, por):
    if de is None or de <= PRECO_FALSO or (por is not None and de <= por):
        return None
    return de


def _promobit(item):
    tipo = item.get('offerPriceType')
    por = reais(item.get('offerPrice')) if tipo == 'NORMAL' else None
    cupom = _texto(item.get('offerCoupon'))
    of = Oferta(PROMOBIT, str(item['offerId']), _texto(item['offerTitle']), por,
                _preco_de(reais(item.get('offerOldPrice')), por), data_iso(item['offerPublished']),
                url=None, loja_origem=_texto(item['storeDomain']).lower(),
                cupons=[cupom] if cupom else [])
    if item.get('offerStatusName') not in PROMOBIT_STATUS:
        of.invalida = 'status'
    elif tipo != 'NORMAL':
        of.invalida = 'tipo_preco'
    return of


def extrair_promobit(pagina):
    itens, erro = _next_data(pagina, ('props', 'pageProps', 'serverOffers', 'offers'))
    if erro:
        return Extracao(erro=erro)
    return _montar(itens, ('offerId', 'offerTitle', 'offerPublished', 'offerStatusName', 'storeDomain'),
                   _promobit)


def _pechinchou(item):
    por = reais(item.get('price'))
    store = item.get('store') if isinstance(item.get('store'), dict) else {}
    cupons = item.get('coupons') if isinstance(item.get('coupons'), list) else []
    of = Oferta(PECHINCHOU, f"{item['id']}:{item['slug']}", _texto(item['title']), por,
                _preco_de(reais(item.get('old_price')), por), data_iso(item['created_at']),
                url=_texto(item['long_url']), loja_origem=_texto(store.get('slug_url')),
                cupons=[c for c in cupons if isinstance(c, str)])
    if item.get('status') != 'ACTIVE':
        of.invalida = 'status'
    elif item.get('is_any_text_price'):
        of.invalida = 'preco_texto'
    return of


def extrair_pechinchou(pagina):
    itens, erro = _next_data(pagina, ('props', 'pageProps', 'promos', 'results'))
    if erro:
        return Extracao(erro=erro)
    return _montar(itens, ('id', 'slug', 'title', 'created_at', 'status', 'long_url'), _pechinchou)


# -- Redirect do Promobit -----------------------------------------------------------------------------

_L_SCRIPT = re.compile(r"\bl\s*=\s*'([^']+)'")
_P_HREF = re.compile(r'<p\b[^>]*>.*?<a\b[^>]*?\bhref="([^"#][^"]*)"', re.DOTALL)


def url_redirect_promobit(pagina):
    """URL da loja na página `/Redirect/to/{id}/`: `l = '<url>'` do script, senão o `<a href>` do `<p>`."""
    for regex in (_L_SCRIPT, _P_HREF):
        m = regex.search(pagina or '')
        if m:
            url = html.unescape(m.group(1)).strip()
            if url.lower().startswith(('http://', 'https://')):
                return url
    return None


EXTRATORES = {PELANDO: extrair_pelando, PROMOBIT: extrair_promobit, PECHINCHOU: extrair_pechinchou}
