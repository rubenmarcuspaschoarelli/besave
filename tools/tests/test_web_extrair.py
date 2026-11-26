"""BSV-66 Saída 2: extração das fixtures reais e erro de estrutura."""

from decimal import Decimal

import pytest
from web_falso import fixture, pagina_pechinchou, pagina_pelando, pagina_promobit
from webapoio.extrair import (
    extrair_pechinchou,
    extrair_pelando,
    extrair_promobit,
    url_redirect_promobit,
)


def _validas(extr):
    assert extr.erro is None
    return [(o.id_origem, o.titulo, o.preco_por, o.preco_de, o.publicada.isoformat(), o.url, o.loja_origem,
             o.cupons) for o in extr.ofertas if not o.invalida]


def _d(v):
    return None if v is None else Decimal(v)


def test_pelando_astro_decodificado_e_validas():
    extr = extrair_pelando(fixture('pelando_lista.html'))
    validas = _validas(extr)
    shopee = validas[2]
    assert shopee[5].startswith('https://shopee.com.br/opaanlp/1599614108/58261587064?')
    validas[2] = shopee[:5] + ('<shopee>',) + shopee[6:]
    assert validas == [
        ('a561827e-a34b-450f-b007-2b917a3e8863', 'Fone Samsung Galaxy Buds Core sem fio', _d('181.00'), None,
         '2026-11-25T22:54:35.574000+00:00', 'https://www.amazon.com.br/dp/B0FP8KDP36', 'Amazon', []),
        ('b9f3f8f3-564c-4f93-bd33-afc33f88165f', 'NESTLÉ PRESTÍGIO Recheado 90g Tablete', _d('5.99'), None,
         '2026-11-25T22:48:08.133000+00:00',
         ('https://www.amazon.com.br/dp/B0FV52C6FM?lv=shuf&social_share=cm_sw_r_cso_cp_apan_dp_9RKT10SJ49B0DETJP9XR'
         '&channelId=704&ref_=cm_sw_r_cso_cp_apan_dp_9RKT10SJ49B0DETJP9XR&plpRedirect=mhFallback'), 'Amazon', []),
        ('c75ac6f4-0fca-4f9a-8a54-e6ed161ce7dd', 'Controle Xbox Forza Horizon 6 Edição Limitada', _d('570.00'),
         None, '2026-11-25T23:10:02.018000+00:00', '<shopee>', 'Shopee', []),
        ('2355d0a0-0f2d-4b39-b45f-88db6a865b59',
         "Parafusadeira Sem Fio Makita 3.6V, Torque De 5N.m, Mandril De 1/4'', Bateria De Li-ion", _d('105.41'),
         None, '2026-11-25T23:10:09.693000+00:00',
         ('https://www.magazineluiza.com.br/parafusadeira-eletrica-sem-fio-makita-3-6v-torque-de-5n-m-mandril-de-1'
         '-4-bateria-de-li-ion-de/p/hehcbe9438/fs/fura/?seller_id=aliexpress'), 'Magalu', []),
    ]


def test_pelando_expired_e_coupon_descartados():
    extr = extrair_pelando(fixture('pelando_lista.html'))
    invalidas = {o.id_origem: o.invalida for o in extr.ofertas if o.invalida}
    assert invalidas == {'4cd58b53-27fc-49c9-a805-b0273b72c731': 'status',
                         '791e3ee3-8937-4a62-a316-c3fc4a04691f': 'tipo'}
    assert len(extr.ofertas) == 6


def test_pelando_hide_in_feed_descarta_e_redirect_url_nao_usada():
    d = {'id': 'x1', 'title': 'T', 'price': 10, 'sourceUrl': 'https://www.amazon.com.br/dp/B000000001',
         'redirectUrl': 'https://dpl.pelando.com.br/r/abc', 'createdAt': '2026-11-25T22:00:00Z',
         'status': 'active', 'kind': 'promotion', 'hideInFeed': True}
    extr = extrair_pelando(pagina_pelando([d, dict(d, id='x2', hideInFeed=False)]))
    assert [(o.id_origem, o.invalida, o.url) for o in extr.ofertas] == [
        ('x1', 'oculta', 'https://www.amazon.com.br/dp/B000000001'),
        ('x2', None, 'https://www.amazon.com.br/dp/B000000001')]


def test_promobit_validas_com_cupom_e_preco_de():
    validas = _validas(extrair_promobit(fixture('promobit_lista.html')))
    assert validas == [
        ('3255118', 'Lava-Roupas Líquido Omo Lavagem Perfeita 1,8L', _d('19.69'), _d('23.99'),
         '2026-11-25T20:09:09-03:00', None, 'amazon.com.br', []),
        ('3255116', 'Carregador Ultra Rápido 50W Tipo C', _d('25.00'), _d('28.87'), '2026-11-25T20:08:10-03:00',
         None, 'amazon.com.br', []),
        ('3255208', 'Grand Theft Auto VI - PlayStation 5', _d('343.48'), _d('499.00'),
         '2026-11-25T20:37:04-03:00', None, 'mercadolivre.com.br', ['LIVREOFF']),
        ('3255106', 'Fralda Pampers Confort Sec Jumbo Plus M com 148un', _d('118.66'), _d('227.12'),
         '2026-11-25T20:07:17-03:00', None, 'shopee.com.br', ['25 Full']),
        ('3255098', 'Caixa de Som Torre Samsung Sound Tower MX-ST50F Bluetooth 240W RMS', _d('2279.05'),
         _d('2899.00'), '2026-11-25T20:06:43-03:00', None, 'magazineluiza.com.br', []),
    ]


def test_promobit_coupon_e_starting_at_descartados():
    extr = extrair_promobit(fixture('promobit_lista.html'))
    invalidas = {o.id_origem: o.invalida for o in extr.ofertas if o.invalida}
    assert invalidas == {'3249872': 'tipo_preco', '3252817': 'tipo_preco', '3222200': 'tipo_preco'}


@pytest.mark.parametrize('status,ok', [('RECENTS', True), ('APPROVED', True), ('TOP_OFFER', True),
                                       ('FINISHED', False), ('PENDING', False)])
def test_promobit_status(status, ok):
    item = {'offerId': 1, 'offerTitle': 'T', 'offerPrice': 10, 'offerOldPrice': 0.01, 'offerPriceType': 'NORMAL',
            'offerStatusName': status, 'offerPublished': '2026-11-25T20:00:00-0300',
            'storeDomain': 'amazon.com.br'}
    of = extrair_promobit(pagina_promobit([item])).ofertas[0]
    assert (of.invalida is None) is ok
    assert of.preco_de is None  # 0.01 = falso


def test_pechinchou_validas():
    validas = _validas(extrair_pechinchou(fixture('pechinchou_lista.html')))
    assert validas == [
        ('33300:lampada-inteligente-10w-smart-color-rgb-wifi-elgin-compativel-com-alexa-e-google-home',
         'Lâmpada Inteligente Smart Color 10w Elgin Rgb Wifi Compatível Com Alexa E Google Home', _d('23.97'),
         _d('29.90'), '2026-11-25T20:03:30.067903-03:00', 'https://www.amazon.com.br/dp/B088C4QZV2?tag=parceiropechi-20',
         'amazon.com.br', []),
        (('140513:hepta-world-ventilador-de-coluna-110v220v-resfriamento-silencioso-design-slim-para-casaescritorio-'
         '101-110v'),
         ('Hepta World Ventilador De Coluna, Resfriamento, Silencioso, Design Slim Para Casa Escritório (preto, 110v, '
         '1011)'), _d('79.19'), _d('99.90'), '2026-11-24T11:02:59.253426-03:00',
         'https://www.amazon.com.br/dp/B0GH2BTS86?tag=parceiropechi-20', 'amazon.com.br', ['15OFFCC']),
        ('152680:oculos-esportivo-pace-premium-protecao-uv400-baixa-ciclismo',
         'Óculos Esportivo Pace Premium Proteção Uv400 Baixa Ciclismo', _d('76.00'), _d('199.00'),
         '2026-11-25T20:02:54.793955-03:00', 'https://meli.la/29Szz1p', 'mercadolivre.com.br', ['FORTUNABLACK15']),
        ('150016:geladeirarefrigerador-brastemp-frost-free-duplex-385l-brm46mk',
         '[APP] Geladeira/Refrigerador Brastemp Frost Free Duplex 385L BRM46MK', _d('2549.00'), _d('3120.00'),
         '2026-11-25T19:51:20.147213-03:00',
         ('https://www.magazineluiza.com.br/geladeira-refrigerador-brastemp-frost-free-duplex-385l-brm46mk/'
         'divulgador/oferta/240972400/ed/refr/?promoter_id=76550&partner_id=3440'), 'magazineluiza.com.br',
         ['INFLUBLACK200']),
    ]


def test_pechinchou_closed_descartada():
    extr = extrair_pechinchou(fixture('pechinchou_lista.html'))
    invalidas = {o.id_origem: o.invalida for o in extr.ofertas if o.invalida}
    assert invalidas == {'137960:aparelho-de-jantar-magnolia-em-porcelana-decorada-20-pecas-tramontina-bv05':
                         'status'}


def test_pechinchou_preco_texto_e_preco_de_maior_que_por():
    base = {'id': 1, 'slug': 's', 'title': 'T', 'price': '10.00', 'old_price': '9.00', 'status': 'ACTIVE',
            'long_url': 'https://www.amazon.com.br/dp/B000000001', 'created_at': '2026-11-25T20:00:00-03:00',
            'coupons': []}
    ofs = extrair_pechinchou(pagina_pechinchou([base, dict(base, id=2, is_any_text_price=True)])).ofertas
    assert [(o.id_origem, o.invalida, o.preco_de) for o in ofs] == [('1:s', None, None), ('2:s', 'preco_texto',
                                                                                            None)]


def test_pechinchou_id_repetido_com_slug_diferente_sao_ofertas_diferentes():
    base = {'id': 7, 'slug': 'a', 'title': 'T', 'price': '10.00', 'status': 'ACTIVE',
            'long_url': 'https://www.amazon.com.br/dp/B000000001', 'created_at': '2026-11-25T20:00:00-03:00'}
    ofs = extrair_pechinchou(pagina_pechinchou([base, dict(base, slug='b')])).ofertas
    assert [o.chave_local for o in ofs] == ['PECHINCHOU:7:a', 'PECHINCHOU:7:b']


@pytest.mark.parametrize('extrator,pagina', [
    (extrair_pelando, '<html><body>sem ilha</body></html>'),
    (extrair_pelando, '<html><astro-island props="{&quot;outra&quot;:[0,1]}"></astro-island></html>'),
    (extrair_promobit, '<html><body>sem next</body></html>'),
    (extrair_promobit, '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'),
    (extrair_promobit, '<script id="__NEXT_DATA__" type="application/json">{nao e json</script>'),
    (extrair_pechinchou, '<html></html>'),
    (extrair_pechinchou, '<script id="__NEXT_DATA__">{"props":{"pageProps":{"promos":{}}}}</script>'),
    (extrair_pelando, ''),
    (extrair_pechinchou, None),
])
def test_estrutura_ausente_vira_erro_sem_excecao(extrator, pagina):
    extr = extrator(pagina)
    assert extr.erro
    assert extr.ofertas == []


def test_todos_os_itens_sem_campo_obrigatorio_e_erro_de_estrutura():
    extr = extrair_pechinchou(pagina_pechinchou([{'id': 1, 'title': 'sem o resto'}, {'id': 2}]))
    assert extr.erro
    extr = extrair_promobit(pagina_promobit([{'offerId': 1}]))
    assert extr.erro
    extr = extrair_pelando(pagina_pelando([{'id': 'a', 'title': 'T'}]))
    assert extr.erro


def test_so_parte_dos_itens_incompleta_nao_e_erro():
    ok = {'id': 1, 'slug': 's', 'title': 'T', 'price': '10.00', 'status': 'ACTIVE',
          'long_url': 'https://www.amazon.com.br/dp/B000000001', 'created_at': '2026-11-25T20:00:00-03:00'}
    extr = extrair_pechinchou(pagina_pechinchou([ok, {'id': 2}]))
    assert extr.erro is None
    assert [o.invalida for o in extr.ofertas] == [None, 'incompleta']


def test_lista_vazia_nao_e_erro():
    extr = extrair_promobit(pagina_promobit([]))
    assert (extr.erro, extr.ofertas) == (None, [])


def test_redirect_promobit_le_a_url_da_fixture():
    assert url_redirect_promobit(fixture('promobit_redirect.html')) == \
        'https://www.amazon.com.br/dp/B0GSBW1WV7?tag=promobit-d-20'


def test_redirect_promobit_so_com_o_link_do_p():
    pagina = '<p>Se isso não ocorrer, <a href="https://www.amazon.com.br/dp/B0000000AA?x=1&amp;y=2">clique</a></p>'
    assert url_redirect_promobit(pagina) == 'https://www.amazon.com.br/dp/B0000000AA?x=1&y=2'


@pytest.mark.parametrize('pagina', ['<html><body>nada</body></html>', '<p><a href="#">x</a></p>', '', None])
def test_redirect_promobit_sem_url(pagina):
    assert url_redirect_promobit(pagina) is None
