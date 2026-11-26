"""Falsos da captura web (BSV-66): páginas sintéticas, `abrir` do urllib simulado e banco em memória."""

import html
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'web'
AGORA = datetime(2026, 11, 25, 23, 30, tzinfo=UTC)


def fixture(nome):
    return (FIXTURES / nome).read_text(encoding='utf-8')


def iso(delta_min=-30):
    return (AGORA + timedelta(minutes=delta_min)).isoformat().replace('+00:00', 'Z')


# -- páginas -------------------------------------------------------------------------------------------

def _astro(v):
    if isinstance(v, dict):
        return [0, {k: _astro(w) for k, w in v.items()}]
    if isinstance(v, list):
        return [1, [_astro(i) for i in v]]
    return [0, v]


def pagina_pelando(deals):
    props = {'initialDeals': _astro(deals), 'initialPageInfo': [0, {}]}
    return ('<html><body><astro-island uid="Z1" props="'
            + html.escape(json.dumps(props), quote=True) + '"></astro-island></body></html>')


def deal_pelando(n, url=None, preco=10.5, criada=None, **extra):
    d = {'id': f'p{n}', 'title': f'Produto Pelando {n}', 'price': preco,
         'sourceUrl': url or f'https://www.amazon.com.br/dp/B0PELA{n:04d}?tag=terceiro-20',
         'createdAt': criada or iso(), 'status': 'active', 'kind': 'promotion',
         'store': {'name': 'Amazon'}}
    d.update(extra)
    return d


def _next(dado):
    return ('<html><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(dado) + '</script></body></html>')


def pagina_promobit(ofertas):
    return _next({'props': {'pageProps': {'serverOffers': {'offers': ofertas}, 'cardsAds': [],
                                          'smallAds': []}}})


def oferta_promobit(n, dominio='amazon.com.br', preco=20.0, antigo=30.0, tipo='NORMAL',
                    status='RECENTS', publicada=None, cupom=None):
    return {'offerId': n, 'offerTitle': f'Produto Promobit {n}', 'offerPrice': preco,
            'offerOldPrice': antigo, 'offerPriceType': tipo, 'offerStatusName': status,
            'offerPublished': publicada or (AGORA - timedelta(minutes=30)).astimezone(
                timezone(timedelta(hours=-3))).strftime('%Y-%m-%dT%H:%M:%S-0300'),
            'storeDomain': dominio, 'offerCoupon': cupom}


def redirect_promobit(url):
    return (f"<html><script>function a(){{ var l = '{url}'; }}</script>"
            f'<p>Se isso não ocorrer, <a href="{url}">clique aqui.</a></p></html>')


def pagina_pechinchou(promos):
    return _next({'props': {'pageProps': {'promos': {'results': promos}}}})


def promo_pechinchou(n, url=None, preco='15.00', antigo='20.00', status='ACTIVE', criada=None,
                     cupons=None):
    return {'id': n, 'slug': f'produto-{n}', 'title': f'Produto Pechinchou {n}', 'price': preco,
            'old_price': antigo, 'is_any_text_price': False, 'status': status,
            'long_url': url or f'https://www.amazon.com.br/dp/B0PECH{n:04d}?tag=parceiropechi-20',
            'created_at': criada or (AGORA - timedelta(minutes=30)).isoformat(),
            'coupons': cupons or [], 'store': {'slug_url': 'amazon.com.br'}}


# -- urllib simulado ------------------------------------------------------------------------------------

class Resposta:
    def __init__(self, status=200, corpo='', location=None, erro=None):
        self.status, self.corpo, self.location, self.erro = status, corpo, location, erro


class AbrirFalso:
    """`abrir(req, timeout, seguir)` com respostas por URL; guarda cada requisição."""

    def __init__(self, rotas=None):
        self.rotas = dict(rotas or {})
        self.pedidos = []      # (url, headers, timeout, seguir)

    def __call__(self, req, timeout, seguir):
        url = req.full_url
        self.pedidos.append((url, dict(req.header_items()), timeout, seguir))
        r = self.rotas.get(url)
        if r is None:
            return 404, {}, b''
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        if r.erro is not None:
            raise r.erro
        headers = {'Location': r.location} if r.location else {}
        return r.status, headers, r.corpo.encode('utf-8')

    @property
    def urls(self):
        return [p[0] for p in self.pedidos]


# -- banco em memória ----------------------------------------------------------------------------------

class BancoFalso:
    """Mesma interface de webapoio.banco.Banco, sem SQL."""

    def __init__(self, vistas=None, conecta=True):
        self.vistas = vistas or {}   # trecho/titulo -> motivo
        self.conecta = conecta
        self.gravadas = []
        self.consultas = []
        self.proximo_id = 1000

    def abrir(self):
        return self.conecta

    def fechar(self):
        pass

    def ja_vista(self, trecho, preco, loja, titulo):
        self.consultas.append((trecho, preco, loja, titulo))
        return self.vistas.get(trecho) or self.vistas.get(titulo)

    def gravar(self, linha):
        self.proximo_id += 1
        self.gravadas.append(dict(linha))
        return self.proximo_id


class Avisos:
    def __init__(self):
        self.textos = []

    def avisar(self, texto):
        self.textos.append(texto)
