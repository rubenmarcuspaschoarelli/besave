"""BSV-66 Saídas 3 e 5: idade, loja, já vista (4 casos), preço; estado local de 7 dias."""

import copy
from datetime import timedelta
from decimal import Decimal

import pytest
from web_falso import (
    AGORA,
    AbrirFalso,
    BancoFalso,
    Resposta,
    deal_pelando,
    iso,
    oferta_promobit,
    pagina_pechinchou,
    pagina_pelando,
    pagina_promobit,
    promo_pechinchou,
    redirect_promobit,
)
from webapoio.banco import Banco
from webapoio.config import PADROES
from webapoio.estado import gravar_vistas, ler_vistas
from webapoio.http import Http
from webapoio.rodada import Rodada

PEL = 'https://www.pelando.com.br/recentes'
PRO = 'https://www.promobit.com.br/'
PEC = 'https://pechinchou.com.br/recentes'


def cfg(sites=('PELANDO',), por_menu=5, teto=30, menus=None):
    c = copy.deepcopy(PADROES)
    c['por_menu'], c['teto_rodada'] = por_menu, teto
    padrao = {'PELANDO': [PEL], 'PROMOBIT': [PRO], 'PECHINCHOU': [PEC]}
    for k in c['sites']:
        c['sites'][k]['habilitado'] = k in sites
        c['sites'][k]['menus'] = (menus or {}).get(k, padrao[k])
    return c


def rodar(rotas, c=None, banco=None, vistas=None, simular=False):
    abrir = AbrirFalso(rotas)
    http = Http('UA', (0, 0), abrir=abrir, dormir=lambda s: None)
    banco = BancoFalso() if banco is None else banco
    r = Rodada(c or cfg(), http, banco, lambda: AGORA, vistas or {}, simular=simular)
    res = r.executar()
    return res, r, abrir, banco


def _descartes(res):
    total = {}
    for resumo in res.resumo.values():
        for k, v in resumo.descartes.items():
            total[k] = total.get(k, 0) + v
    return total


@pytest.mark.parametrize('minutos,entra,motivo', [
    (-(23 * 60 + 59), True, None),
    (-(24 * 60 + 1), False, 'antiga'),
    (9, True, None),
    (11, False, 'futura'),
])
def test_idade(minutos, entra, motivo):
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1, criada=iso(minutos))]))})
    assert res.gravadas == (1 if entra else 0)
    assert _descartes(res) == ({} if entra else {motivo: 1})


def test_idade_configuravel():
    c = cfg()
    c['idade_max_horas'] = 2
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1, criada=iso(-121))]))}, c)
    assert _descartes(res) == {'antiga': 1}


def test_loja_fora_e_sem_preco_na_ordem():
    deals = [deal_pelando(1, url='https://www.magazineluiza.com.br/x/p/abc/'),
             deal_pelando(2, preco=None), deal_pelando(3, preco=0),
             deal_pelando(4, url='https://www.magazineluiza.com.br/y/p/def/', preco=None)]
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando(deals))})
    assert res.gravadas == 0
    assert _descartes(res) == {'loja_fora': 2, 'sem_preco': 2}


def test_promobit_filtra_dominio_antes_do_redirect():
    ofs = [oferta_promobit(1, dominio='magazineluiza.com.br'), oferta_promobit(2)]
    rotas = {PRO: Resposta(200, pagina_promobit(ofs)),
             'https://www.promobit.com.br/Redirect/to/2/': Resposta(200, redirect_promobit(
                 'https://www.amazon.com.br/dp/B0PROM0002?tag=promobit-d-20'))}
    res, _, abrir, banco = rodar(rotas, cfg(('PROMOBIT',)))
    assert abrir.urls == [PRO, 'https://www.promobit.com.br/Redirect/to/2/']
    assert [g['url'] for g in banco.gravadas] == ['https://www.amazon.com.br/dp/B0PROM0002']
    assert _descartes(res) == {'loja_fora': 1}


def test_promobit_redirect_sem_url_descarta():
    rotas = {PRO: Resposta(200, pagina_promobit([oferta_promobit(2)])),
             'https://www.promobit.com.br/Redirect/to/2/': Resposta(200, '<html>sem link</html>')}
    res, *_ = rodar(rotas, cfg(('PROMOBIT',)))
    assert (res.gravadas, _descartes(res)) == (0, {'sem_url': 1})


def test_encurtador_resolvido_e_nao_resolvido():
    promos = [promo_pechinchou(1, url='https://meli.la/abc'), promo_pechinchou(2, url='https://amzn.to/zzz')]
    rotas = {PEC: Resposta(200, pagina_pechinchou(promos)),
             'https://meli.la/abc': Resposta(302, location='https://www.mercadolivre.com.br/x/p/MLB99887766?matt_word=a'),
             'https://amzn.to/zzz': Resposta(200, 'sem location')}
    res, _, abrir, banco = rodar(rotas, cfg(('PECHINCHOU',)))
    assert [g['url'] for g in banco.gravadas] == ['https://www.mercadolivre.com.br/x/p/MLB99887766']
    assert _descartes(res) == {'encurtador_nao_resolvido': 1}
    assert [p[3] for p in abrir.pedidos[1:]] == [False, False]


# -- já vista -------------------------------------------------------------------------------------------

def test_vista_1_estado_local():
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1)]))},
                    vistas={'PELANDO:p1': iso(-60 * 24 * 3)})
    assert (res.gravadas, _descartes(res)) == (0, {'vista_local': 1})


def test_vista_2_mesma_rodada_menus_repetidos():
    c = cfg(menus={'PELANDO': [PEL, 'https://www.pelando.com.br/mais-quentes']})
    mesmo_produto = 'https://www.amazon.com.br/Outro-Nome/dp/B0PELA0001?ref=x'
    rotas = {PEL: Resposta(200, pagina_pelando([deal_pelando(1)])),
             'https://www.pelando.com.br/mais-quentes': Resposta(200, pagina_pelando(
                 [deal_pelando(9, url=mesmo_produto)]))}
    res, _, _, _banco = rodar(rotas, c)
    assert res.gravadas == 1
    assert _descartes(res) == {'vista_rodada': 1}


@pytest.mark.parametrize('motivo', ['vista_fila', 'vista_oferta'])
def test_vista_3_chave_no_banco(motivo):
    banco = BancoFalso(vistas={'B0PELA0001': motivo})
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1)]))}, banco=banco)
    assert (res.gravadas, _descartes(res)) == (0, {motivo: 1})
    assert banco.consultas == [('B0PELA0001', Decimal('10.50'), 'AMAZON', 'Produto Pelando 1')]


def test_vista_4_mesmo_titulo():
    banco = BancoFalso(vistas={'Produto Pelando 1': 'mesmo_titulo'})
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1)]))}, banco=banco)
    assert (res.gravadas, _descartes(res)) == (0, {'mesmo_titulo': 1})


class _Cur:
    """Cursor que aplica as regras da consulta de já vista sobre tabelas em memória."""

    def __init__(self, fila, ofertas):
        self.fila, self.ofertas, self.rows = fila, ofertas, []

    def execute(self, sql, b):
        self.rows = []
        if 'chave' in b:
            self.rows += [('F', None) for url, _l, _p, _t in self.fila if b['chave'] in url]
            self.rows += [('O', None) for url, preco, ativo in self.ofertas
                          if ativo == 1 and b['chave'] in url and preco <= b['preco']]
        self.rows += [('T', t) for _u, loja, preco, t in self.fila
                      if loja == b['loja'] and b['pmin'] <= preco <= b['pmax']]

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _Conn:
    def __init__(self, fila=(), ofertas=()):
        self.fila, self.ofertas = list(fila), list(ofertas)

    def cursor(self):
        return _Cur(self.fila, self.ofertas)


@pytest.mark.parametrize('preco_ativa,entra', [(Decimal('12.00'), True), (Decimal('10.50'), False),
                                               (Decimal('9.00'), False)])
def test_mais_barata_que_a_oferta_ativa_entra(preco_ativa, entra):
    conn = _Conn(ofertas=[('https://www.amazon.com.br/dp/B0PELA0001?tag=besave-20', preco_ativa, 1)])
    banco = Banco({}, conectar=lambda: conn)
    banco.abrir()
    banco.gravar = lambda linha: 77
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1, preco=10.5)]))}, banco=banco)
    assert res.gravadas == (1 if entra else 0)
    assert _descartes(res) == ({} if entra else {'vista_oferta': 1})


@pytest.mark.parametrize('loja,preco_fila,entra', [
    ('AMAZON', Decimal('10.60'), False),    # +0,95%
    ('AMAZON', Decimal('10.40'), False),    # -0,95%
    ('AMAZON', Decimal('10.65'), True),     # +1,4%
    ('AMAZON', Decimal('10.35'), True),     # -1,4%
    ('SHOPEE', Decimal('10.50'), True),     # outra loja
])
def test_mesmo_titulo_so_com_mesma_loja_e_preco_a_ate_1_porcento(loja, preco_fila, entra):
    conn = _Conn(fila=[('https://shopee.com.br/product/1/2', loja, preco_fila, 'PRODUTO pelando 1!')])
    banco = Banco({}, conectar=lambda: conn)
    banco.abrir()
    banco.gravar = lambda linha: 78
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1, preco=10.5)]))}, banco=banco)
    assert res.gravadas == (1 if entra else 0)
    assert _descartes(res) == ({} if entra else {'mesmo_titulo': 1})


def test_estado_local_de_8_dias_e_esquecido(tmp_path):
    caminho = str(tmp_path / 'vistas.json')
    gravar_vistas(caminho, {'PELANDO:p1': (AGORA - timedelta(days=8)).isoformat(),
                            'PELANDO:p2': (AGORA - timedelta(days=6)).isoformat()})
    vistas = ler_vistas(caminho, AGORA)
    assert list(vistas) == ['PELANDO:p2']
    res, *_ = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1), deal_pelando(2)]))}, vistas=vistas)
    assert res.gravadas == 1
    assert _descartes(res) == {'vista_local': 1}


def test_estado_local_ilegivel_comeca_vazio(tmp_path):
    caminho = tmp_path / 'vistas.json'
    caminho.write_text('{quebrado', encoding='utf-8')
    assert ler_vistas(str(caminho), AGORA) == {}


def test_titulo_com_trim_e_corte_em_350_no_insert():
    res, _, _, banco = rodar({PEL: Resposta(200, pagina_pelando([deal_pelando(1, title='  ' + 'x' * 400)]))})
    assert res.gravadas == 1
    assert banco.gravadas[0]['titulo'] == 'x' * 350


def test_descartes_transitorios_nao_entram_no_estado_local():
    deals = [deal_pelando(1, criada=iso(30)),                                       # futura
             deal_pelando(2, url='https://amzn.to/sem-location'),                    # encurtador_nao_resolvido
             deal_pelando(3, criada=iso(-60 * 25)),                                  # antiga
             deal_pelando(4, url='https://www.magazineluiza.com.br/x/p/abc/'),       # loja_fora
             deal_pelando(5)]                                                        # gravada
    rotas = {PEL: Resposta(200, pagina_pelando(deals)), 'https://amzn.to/sem-location': Resposta(200, '')}
    _, rodada, _, _ = rodar(rotas)
    assert sorted(rodada.novas_vistas) == ['PELANDO:p3', 'PELANDO:p4', 'PELANDO:p5']


def test_promobit_sem_url_nao_entra_no_estado_local():
    rotas = {PRO: Resposta(200, pagina_promobit([oferta_promobit(2)])),
             'https://www.promobit.com.br/Redirect/to/2/': Resposta(200, '<html>sem link</html>')}
    _, rodada, _, _ = rodar(rotas, cfg(('PROMOBIT',)))
    assert rodada.novas_vistas == {}
