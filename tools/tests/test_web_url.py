"""BSV-66 Saída 4 (URL limpa, encurtadores), chave de produto e cupons (CONTRATO §4.3)."""

import logging

import pytest
from webapoio.cupons import ds_cupom, separar
from webapoio.url import chave_loja, eh_encurtador, limpar, resolver_encurtador

CASOS = [
    # Amazon
    ('https://www.amazon.com.br/dp/B0FP8KDP36?tag=promobit-d-20&linkCode=ll1',
     ('AMAZON', 'https://www.amazon.com.br/dp/B0FP8KDP36', None)),
    ('https://www.amazon.com.br/Fone-Samsung/dp/b0fp8kdp36/ref=sr_1_1?tag=parceiropechi-20',
     ('AMAZON', 'https://www.amazon.com.br/dp/B0FP8KDP36', None)),
    ('https://amazon.com.br/gp/product/B088C4QZV2?smid=A1&tag=x-20',
     ('AMAZON', 'https://www.amazon.com.br/dp/B088C4QZV2', None)),
    ('https://www.amazon.com.br/gp/aw/d/B0GH2BTS86/?th=1',
     ('AMAZON', 'https://www.amazon.com.br/dp/B0GH2BTS86', None)),
    ('https://www.amazon.com.br/s?k=fone&tag=x-20', (None, None, 'url_invalida')),
    ('https://www.amazon.com/dp/B0FP8KDP36', (None, None, 'loja_fora')),
    # Mercado Livre
    ('https://www.mercadolivre.com.br/grand-theft-auto-vi/p/MLB123456789?matt_tool=1&matt_word=x#reviews',
     ('MERCADO LIVRE', 'https://www.mercadolivre.com.br/grand-theft-auto-vi/p/MLB123456789', None)),
    ('https://produto.mercadolivre.com.br/MLB-3456789012-oculos-pace-_JM?utm_source=pechinchou#position=1',
     ('MERCADO LIVRE', 'https://produto.mercadolivre.com.br/MLB-3456789012-oculos-pace-_JM', None)),
    # Shopee, três formatos
    ('https://shopee.com.br/product/1599614108/58261587064?utm_source=an_1&mmp_pid=an_1',
     ('SHOPEE', 'https://shopee.com.br/product/1599614108/58261587064', None)),
    ('https://shopee.com.br/opaanlp/1599614108/58261587064?__mobile__=1&utm_campaign=id_x',
     ('SHOPEE', 'https://shopee.com.br/product/1599614108/58261587064', None)),
    ('https://shopee.com.br/Fralda-Pampers-Confort-Sec-i.123456.7890123?sp_atk=abc&utm_medium=affiliates',
     ('SHOPEE', 'https://shopee.com.br/product/123456/7890123', None)),
    ('https://shopee.com.br/search?keyword=fralda', (None, None, 'url_invalida')),
    # fora
    ('https://www.magazineluiza.com.br/parafusadeira/p/hehcbe9438/?seller_id=aliexpress',
     (None, None, 'loja_fora')),
    ('https://www.olympikus.com.br/tenis/p', (None, None, 'loja_fora')),
    ('https://evil.com/?u=amazon.com.br/dp/B0FP8KDP36', (None, None, 'loja_fora')),
    ('https://amazon.com.br.evil.com/dp/B0FP8KDP36', (None, None, 'loja_fora')),
    ('ftp://www.amazon.com.br/dp/B0FP8KDP36', (None, None, 'url_invalida')),
    ('', (None, None, 'url_invalida')),
    (None, (None, None, 'url_invalida')),
    # > 350
    ('https://www.mercadolivre.com.br/' + 'a' * 319 + '?x=1', (None, None, 'url_longa')),
]


@pytest.mark.parametrize('url,esperado', CASOS)
def test_url_limpa(url, esperado):
    assert limpar(url) == esperado


def test_url_limpa_no_limite_de_350_entra():
    url = 'https://www.mercadolivre.com.br/' + 'a' * 318
    assert len(url) == 350
    assert limpar(url + '?utm_source=x') == ('MERCADO LIVRE', url, None)


@pytest.mark.parametrize('url,sim', [
    ('https://meli.la/29Szz1p', True), ('https://amzn.to/3abc', True), ('https://s.shopee.com.br/AbC', True),
    ('https://mercadolivre.com/sec/1abc', True), ('https://www.mercadolivre.com/sec/1abc', True),
    ('https://www.mercadolivre.com.br/sec/1abc', False), ('https://www.amazon.com.br/dp/B0FP8KDP36', False),
    ('https://shopee.com.br/product/1/2', False), ('file:///amzn.to', False),
])
def test_encurtadores(url, sim):
    assert eh_encurtador(url) is sim


class Location:
    def __init__(self, mapa):
        self.mapa = mapa
        self.pedidos = []

    def __call__(self, url):
        self.pedidos.append(url)
        return self.mapa.get(url)


def test_encurtador_um_salto():
    loc = Location({'https://meli.la/29Szz1p':
                    'https://produto.mercadolivre.com.br/MLB-3456789012-oculos-_JM?matt_tool=9#x'})
    final = resolver_encurtador('https://meli.la/29Szz1p', loc)
    assert loc.pedidos == ['https://meli.la/29Szz1p']
    assert limpar(final) == ('MERCADO LIVRE', 'https://produto.mercadolivre.com.br/MLB-3456789012-oculos-_JM', None)


def test_encurtador_tres_saltos():
    loc = Location({'https://amzn.to/a': 'https://meli.la/b', 'https://meli.la/b': 'https://s.shopee.com.br/c',
                    'https://s.shopee.com.br/c': 'https://shopee.com.br/loja/11/22?utm_source=x'})
    final = resolver_encurtador('https://amzn.to/a', loc)
    assert loc.pedidos == ['https://amzn.to/a', 'https://meli.la/b', 'https://s.shopee.com.br/c']
    assert limpar(final) == ('SHOPEE', 'https://shopee.com.br/product/11/22', None)


def test_encurtador_quatro_saltos_nao_resolve():
    loc = Location({'https://amzn.to/a': 'https://meli.la/b', 'https://meli.la/b': 'https://amzn.to/c',
                    'https://amzn.to/c': 'https://meli.la/d', 'https://meli.la/d': 'https://www.amazon.com.br/dp/B0FP8KDP36'})
    assert resolver_encurtador('https://amzn.to/a', loc) is None
    assert len(loc.pedidos) == 3


def test_encurtador_sem_location_descarta():
    loc = Location({})
    assert resolver_encurtador('https://meli.la/zzz', loc) is None
    assert loc.pedidos == ['https://meli.la/zzz']


def test_encurtador_com_erro_descarta():
    def falha(url):
        raise OSError('rede')
    assert resolver_encurtador('https://amzn.to/a', falha) is None


def test_encurtador_location_relativo():
    loc = Location({'https://mercadolivre.com/sec/1abc': '/sec/2def',
                    'https://mercadolivre.com/sec/2def': 'https://www.mercadolivre.com.br/p/MLB1234567'})
    assert resolver_encurtador('https://mercadolivre.com/sec/1abc', loc) == \
        'https://www.mercadolivre.com.br/p/MLB1234567'


@pytest.mark.parametrize('url,chave', [
    ('https://www.amazon.com.br/dp/B0FP8KDP36', ('AMZ:B0FP8KDP36', 'B0FP8KDP36')),
    ('https://www.mercadolivre.com.br/x/p/MLB123456789', ('ML:123456789', '123456789')),
    ('https://produto.mercadolivre.com.br/MLB-3456789012-x', ('ML:3456789012', '3456789012')),
    ('https://shopee.com.br/product/1599614108/58261587064', ('SHP:1599614108/58261587064', '58261587064')),
    ('https://www.mercadolivre.com.br/social/abc', (None, None)),
])
def test_chave_de_produto(url, chave):
    assert chave_loja(url) == chave


def test_cupons_regra_4_3(caplog):
    with caplog.at_level(logging.WARNING, logger='captura_web'):
        assert separar('25 Full') == []
        assert separar(['livreoff ', 'LIVREOFF', 'A|b| c ']) == ['LIVREOFF', 'A', 'B', 'C']
        assert separar(['A1', 'A2', 'A3', 'A4', 'A5', 'A6']) == ['A1', 'A2', 'A3', 'A4', 'A5']
        assert separar(None) == []
        assert separar(['X' * 31, 'BE_SAVE-1']) == ['BE_SAVE-1']
    assert any('25 FULL' in r.getMessage() for r in caplog.records)
    assert any('A6' in r.getMessage() for r in caplog.records)


def test_ds_cupom():
    assert ds_cupom(['A', 'B']) == 'A|B'
    assert ds_cupom([]) is None
