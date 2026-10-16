"""
Paginas-ponte (vitrines de divulgador / links de afiliado).

Nao sao lojas: a pagina so exibe a oferta e leva para a loja de verdade
(Amazon, Mercado Livre, Shopee...). Sao geradas por plataformas white-label
(ex.: divulgadorinteligente.com), entao CADA divulgador usa o seu proprio
dominio (achadinhoscomcarol.com.br, ...) — mapear dominio a dominio no
registry nao daria conta. Por isso a deteccao aqui e pela ESTRUTURA da pagina,
nao pelo dominio: o main.py so chama este modulo quando a loja da URL de origem
e desconhecida, como ultima tentativa antes de marcar 'loja_desconhecida'.

Formato reconhecido hoje: o <script id="__NEXT_DATA__"> do Next.js, onde a
plataforma guarda a oferta e o link ORIGINAL da loja em
props.pageProps.product.originalValues.url.
"""

import json

from core import registry

# Marcas na URL de uma pagina-ponte cuja oferta saiu do ar. A vitrine responde,
# mas redireciona para um aviso ("Promocao encerrada") e o __NEXT_DATA__ nao tem
# mais produto -- sem isso o caso viraria 'loja_desconhecida', motivo enganoso:
# o problema nao e o dominio ser desconhecido, e a oferta ter expirado. Essas
# vitrines duram poucos dias, entao o caso e comum em fila atrasada.
MARCAS_EXPIRADA = ('promocao-encerrada', 'promocao_encerrada', 'oferta-encerrada')


def oferta_expirada(page):
    """True se a pagina-ponte ABERTA em `page` avisa que a promocao acabou."""
    try:
        url = (page.url or '').lower()
    except Exception:
        return False
    return any(marca in url for marca in MARCAS_EXPIRADA)


def _next_data(page):
    # JSON do <script id="__NEXT_DATA__"> (estado da pagina no Next.js).
    try:
        bruto = page.evaluate(
            "() => { const e = document.getElementById('__NEXT_DATA__');"
            " return e ? e.textContent : ''; }")
        return json.loads(bruto) if bruto else None
    except Exception:
        return None


def _urls(no, achadas):
    # Recolhe, na ordem em que aparecem, todas as strings http(s) de um no.
    if isinstance(no, dict):
        for valor in no.values():
            _urls(valor, achadas)
    elif isinstance(no, list):
        for valor in no:
            _urls(valor, achadas)
    elif isinstance(no, str) and no.strip().startswith(('http://', 'https://')):
        achadas.append(no.strip())


def resolver_destino(page):
    """URL da loja real de uma pagina-ponte JA ABERTA em `page`.

    Retorna (url, nome_da_loja), ou (None, None) se a pagina nao for uma ponte
    reconhecida ou se nenhum link dela cair numa loja do registry.
    """
    dados = _next_data(page)
    if not dados:
        return None, None
    produto = ((dados.get('props') or {}).get('pageProps') or {}).get('product')
    if not isinstance(produto, dict):
        return None, None
    originais = produto.get('originalValues')
    originais = originais if isinstance(originais, dict) else {}

    # A ordem importa: originalValues.url e o link ORIGINAL da loja (o mais
    # confiavel, e o unico que aponta direto para a pagina do produto). Os
    # outros campos entram so como reserva, porque o layout desse JSON muda
    # entre versoes da plataforma; product.link, por exemplo, e um encurtador
    # (link.amazon/...) que funciona mas gasta um redirect a mais.
    candidatos = []
    if isinstance(originais.get('url'), str):
        candidatos.append(originais['url'].strip())
    _urls(originais, candidatos)
    _urls(produto, candidatos)

    for url in candidatos:
        loja = registry.resolver_loja(url)
        if loja:
            return url, loja
    return None, None