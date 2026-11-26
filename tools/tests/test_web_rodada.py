"""BSV-66 Saída 7: cotas com rodízio, avisos (texto inteiro), --simular, trava; fixtures de ponta a ponta."""

import json
from decimal import Decimal

import pytest
from test_web_filtros import PEC, PEL, PRO, cfg, rodar
from web_falso import (
    AGORA,
    AbrirFalso,
    Avisos,
    BancoFalso,
    Resposta,
    deal_pelando,
    fixture,
    oferta_promobit,
    pagina_pechinchou,
    pagina_pelando,
    pagina_promobit,
    promo_pechinchou,
    redirect_promobit,
)
from webapoio import cli
from webapoio.banco import BancoFora
from webapoio.estado import Trava
from webapoio.http import Http
from webapoio.rodada import mensagem

PEL2 = 'https://www.pelando.com.br/mais-quentes'
PRO2 = 'https://www.promobit.com.br/promocoes/recentes/'
PEC2 = 'https://pechinchou.com.br/destaques'
RED = 'https://www.promobit.com.br/Redirect/to/{}/'
TRES = ('PELANDO', 'PROMOBIT', 'PECHINCHOU')


def _rotas_tres_sites(n=4):
    rotas = {}
    for menu, base in ((PEL, 100), (PEL2, 200)):
        rotas[menu] = Resposta(200, pagina_pelando([deal_pelando(base + i) for i in range(n)]))
    for menu, base in ((PRO, 300), (PRO2, 400)):
        rotas[menu] = Resposta(200, pagina_promobit([oferta_promobit(base + i) for i in range(n)]))
        for i in range(n):
            rotas[RED.format(base + i)] = Resposta(200, redirect_promobit(
                f'https://www.amazon.com.br/dp/B0PROM{base + i:04d}?tag=promobit-d-20'))
    for menu, base in ((PEC, 500), (PEC2, 600)):
        rotas[menu] = Resposta(200, pagina_pechinchou([promo_pechinchou(base + i) for i in range(n)]))
    return rotas


MENUS2 = {'PELANDO': [PEL, PEL2], 'PROMOBIT': [PRO, PRO2], 'PECHINCHOU': [PEC, PEC2]}


def test_rodizio_entre_sites_e_menus_com_teto():
    res, _, abrir, banco = rodar(_rotas_tres_sites(), cfg(TRES, por_menu=2, teto=7, menus=MENUS2))
    assert [g['url'] for g in banco.gravadas] == [
        'https://www.amazon.com.br/dp/B0PELA0100',
        'https://www.amazon.com.br/dp/B0PROM0300',
        'https://www.amazon.com.br/dp/B0PECH0500',
        'https://www.amazon.com.br/dp/B0PELA0200',
        'https://www.amazon.com.br/dp/B0PROM0400',
        'https://www.amazon.com.br/dp/B0PECH0600',
        'https://www.amazon.com.br/dp/B0PELA0101',
    ]
    # teto atingido: nenhuma requisição depois da 7ª gravação
    assert abrir.urls == [PEL, PRO, RED.format(300), PEC, PEL2, PRO2, RED.format(400), PEC2]
    assert res.gravadas == 7


def test_por_menu_limita_cada_menu():
    res, _, abrir, banco = rodar(_rotas_tres_sites(), cfg(('PELANDO',), por_menu=2, teto=30, menus=MENUS2))
    assert [g['url'] for g in banco.gravadas] == [
        'https://www.amazon.com.br/dp/B0PELA0100', 'https://www.amazon.com.br/dp/B0PELA0200',
        'https://www.amazon.com.br/dp/B0PELA0101', 'https://www.amazon.com.br/dp/B0PELA0201']
    assert abrir.urls == [PEL, PEL2]
    assert [r.gravadas for r in res.resumo.values()] == [2, 2]


def test_teto_30_divide_os_tres_sites():
    rotas = _rotas_tres_sites(n=6)
    _res, _, _, banco = rodar(rotas, cfg(TRES, por_menu=5, teto=30, menus=MENUS2))
    origens = [g['origem'] for g in banco.gravadas]
    assert len(origens) == 30
    assert {o: origens.count(o) for o in set(origens)} == {'PELANDO': 10, 'PROMOBIT': 10, 'PECHINCHOU': 10}


def test_menu_esgotado_passa_ao_proximo_no_mesmo_turno():
    rotas = _rotas_tres_sites()
    rotas[PEL] = Resposta(200, pagina_pelando([deal_pelando(1, status='expired')]))
    _res, _, _abrir, banco = rodar(rotas, cfg(('PELANDO',), por_menu=1, teto=30, menus=MENUS2))
    assert [g['url'] for g in banco.gravadas] == ['https://www.amazon.com.br/dp/B0PELA0200']


# -- avisos ---------------------------------------------------------------------------------------------

def test_403_para_o_site_os_outros_seguem_e_uma_mensagem():
    rotas = _rotas_tres_sites()
    rotas[PRO] = Resposta(403)
    res, _, abrir, banco = rodar(rotas, cfg(TRES, por_menu=1, teto=30, menus=MENUS2))
    assert PRO2 not in abrir.urls and abrir.urls.count(PRO) == 1
    assert {g['origem'] for g in banco.gravadas} == {'PELANDO', 'PECHINCHOU'}
    assert mensagem(res) == 'Captura web: Promobit bloqueado (HTTP 403). Gravadas 4 oferta(s).'


def test_429_no_redirect_tambem_para_o_site():
    rotas = _rotas_tres_sites()
    rotas[RED.format(300)] = Resposta(429)
    res, _, abrir, _ = rodar(rotas, cfg(('PROMOBIT',), menus=MENUS2))
    assert abrir.urls == [PRO, RED.format(300)]
    assert mensagem(res) == 'Captura web: Promobit bloqueado (HTTP 429). Gravadas 0 oferta(s).'


def test_estrutura_mudou_e_sem_resposta_numa_mensagem():
    rotas = _rotas_tres_sites()
    rotas[PEL2] = Resposta(200, '<html>layout novo</html>')
    rotas[PEC] = Resposta(503)
    res, *_ = rodar(rotas, cfg(TRES, por_menu=1, teto=30, menus=MENUS2))
    assert mensagem(res) == ('Captura web: Pelando estrutura mudou em /mais-quentes; Pechinchou sem resposta. '
                             'Gravadas 4 oferta(s).')


def test_tudo_ok_sem_mensagem_e_site_sem_oferta_valida_nao_e_problema():
    rotas = _rotas_tres_sites()
    rotas[PEL] = Resposta(200, pagina_pelando([deal_pelando(1, status='expired')]))
    rotas[PEL2] = Resposta(200, pagina_pelando([]))
    res, *_ = rodar(rotas, cfg(TRES, menus=MENUS2))
    assert res.problemas == []
    assert mensagem(res) is None


def test_banco_fora_no_meio_para_a_rodada():
    class Cai(BancoFalso):
        def gravar(self, linha):
            if self.gravadas:
                raise BancoFora('ORA-03113')
            return super().gravar(linha)

    res, _, abrir, _banco = rodar(_rotas_tres_sites(), cfg(TRES, menus=MENUS2), banco=Cai())
    assert res.banco_fora and res.gravadas == 1
    assert abrir.urls == [PEL, PRO, RED.format(300)]
    assert mensagem(res) == 'Captura web: banco fora do ar; gravadas 1 oferta(s) antes da falha.'


# -- ponta a ponta sobre as fixtures reais ----------------------------------------------------------------

def test_fixtures_reais_ponta_a_ponta():
    rotas = {PEL: Resposta(200, fixture('pelando_lista.html')),
             PRO: Resposta(200, fixture('promobit_lista.html')),
             PEC: Resposta(200, fixture('pechinchou_lista.html')),
             RED.format(3255118): Resposta(200, fixture('promobit_redirect.html')),
             RED.format(3255116): Resposta(200, redirect_promobit(
                 'https://www.amazon.com.br/dp/B0CARREG01?tag=promobit-d-20')),
             RED.format(3255208): Resposta(200, redirect_promobit(
                 'https://www.mercadolivre.com.br/gta-vi/p/MLB55443322?matt_tool=promobit#reviews')),
             RED.format(3255106): Resposta(200, redirect_promobit(
                 'https://shopee.com.br/Fralda-Pampers-i.11111.22222?utm_source=promobit')),
             'https://meli.la/29Szz1p': Resposta(302, location=(
                 'https://produto.mercadolivre.com.br/MLB-3456789012-oculos-pace-_JM?matt_word=pechinchou'))}
    res, _, _, banco = rodar(rotas, cfg(TRES))
    # rodízio: 140513 (antiga) e 137960 (CLOSED) passam no mesmo turno do Pechinchou; Magalu nunca entra
    linhas = [(g['origem'], g['loja'], g['url'], g['preco_por'], g['preco_de'], g['cupom'], g['cupom_loja'])
              for g in banco.gravadas]
    assert linhas == [
        ('PELANDO', 'AMAZON', 'https://www.amazon.com.br/dp/B0FP8KDP36', Decimal('181.00'), None, None, None),
        ('PROMOBIT', 'AMAZON', 'https://www.amazon.com.br/dp/B0GSBW1WV7', Decimal('19.69'), Decimal('23.99'),
         None, None),
        ('PECHINCHOU', 'AMAZON', 'https://www.amazon.com.br/dp/B088C4QZV2', Decimal('23.97'), Decimal('29.90'),
         None, None),
        ('PELANDO', 'AMAZON', 'https://www.amazon.com.br/dp/B0FV52C6FM', Decimal('5.99'), None, None, None),
        ('PROMOBIT', 'AMAZON', 'https://www.amazon.com.br/dp/B0CARREG01', Decimal('25.00'), Decimal('28.87'),
         None, None),
        ('PECHINCHOU', 'MERCADO LIVRE', 'https://produto.mercadolivre.com.br/MLB-3456789012-oculos-pace-_JM',
         Decimal('76.00'), Decimal('199.00'), 'FORTUNABLACK15', 'MERCADO LIVRE'),
        ('PELANDO', 'SHOPEE', 'https://shopee.com.br/product/1599614108/58261587064', Decimal('570.00'), None,
         None, None),
        ('PROMOBIT', 'MERCADO LIVRE', 'https://www.mercadolivre.com.br/gta-vi/p/MLB55443322', Decimal('343.48'),
         Decimal('499.00'), 'LIVREOFF', 'MERCADO LIVRE'),
        ('PROMOBIT', 'SHOPEE', 'https://shopee.com.br/product/11111/22222', Decimal('118.66'), Decimal('227.12'),
         None, None),
    ]
    assert banco.gravadas[0]['titulo'] == 'Fone Samsung Galaxy Buds Core sem fio'
    # 140513 (Pechinchou) foi publicada há 33 h: antiga
    assert res.resumo[('Pechinchou', '/recentes')].descartes['antiga'] == 1
    assert mensagem(res) is None
    # nada com marca de terceiro
    texto = json.dumps([g['url'] for g in banco.gravadas])
    for marca in ('tag=', 'utm_', 'matt_', 'meli.la', 'amzn.to'):
        assert marca not in texto


def test_so_paginas_da_spec_sao_pedidas():
    import re
    _res, _, abrir, _ = rodar(_rotas_tres_sites(n=6), cfg(TRES, menus=MENUS2))
    permitidas = {u for menus in MENUS2.values() for u in menus}
    for url in abrir.urls:
        assert url in permitidas or re.fullmatch(r'https://www\.promobit\.com\.br/Redirect/to/\d+/', url), url
        assert '/api/' not in url


def test_log_sem_url_de_terceiro(caplog):
    test_fixtures_reais_ponta_a_ponta()
    texto = caplog.text
    for marca in ('tag=', 'utm_', 'matt_', 'mmp_pid', 'seller_id', 'promoter_id'):
        assert marca not in texto


# -- CLI: --simular, estado local, trava ----------------------------------------------------------------

def _cli(tmp_path, argv, banco, avisos, rotas=None):
    rotas = rotas if rotas is not None else _rotas_tres_sites()
    conf = tmp_path / 'conf'
    conf.mkdir(exist_ok=True)
    (conf / 'config.json').write_text(json.dumps({
        'pausa_s': [0, 0], 'sites': {k: {'habilitado': True, 'menus': v} for k, v in MENUS2.items()}}),
        encoding='utf-8')
    abrir = AbrirFalso(rotas)
    codigo = cli.main(argv, base=str(tmp_path), configurar=False, avisador=avisos, agora=lambda: AGORA,
                      fazer_http=lambda ua, p: Http(ua, p, abrir=abrir, dormir=lambda s: None),
                      fazer_banco=lambda c: banco)
    return codigo, abrir


def test_simular_nao_grava_nem_atualiza_estado(tmp_path):
    banco, avisos = BancoFalso(), Avisos()
    codigo, _abrir = _cli(tmp_path, ['--simular'], banco, avisos)
    assert codigo == 0
    assert banco.gravadas == []
    assert banco.consultas  # as consultas de já vista rodam
    assert not (tmp_path / 'estado' / 'vistas.json').exists()
    assert avisos.textos == []


def test_simular_respeita_cotas():
    res, _, _, banco = rodar(_rotas_tres_sites(), cfg(TRES, por_menu=2, teto=7, menus=MENUS2), simular=True)
    assert res.gravadas == 7 and banco.gravadas == []
    assert [linha['url'] for linha in res.linhas][:3] == ['https://www.amazon.com.br/dp/B0PELA0100',
                                                          'https://www.amazon.com.br/dp/B0PROM0300',
                                                          'https://www.amazon.com.br/dp/B0PECH0500']


def test_segunda_rodada_pula_as_ja_gravadas(tmp_path):
    banco = BancoFalso()
    codigo, _ = _cli(tmp_path, [], banco, Avisos())
    assert codigo == 0 and len(banco.gravadas) == 24
    vistas = json.loads((tmp_path / 'estado' / 'vistas.json').read_text(encoding='utf-8'))
    assert 'PELANDO:p100' in vistas and 'PROMOBIT:300' in vistas and 'PECHINCHOU:500:produto-500' in vistas
    banco2 = BancoFalso()
    _, abrir2 = _cli(tmp_path, [], banco2, Avisos())
    assert banco2.gravadas == []
    # Promobit: já vista no estado local não gasta o redirect
    assert not any('/Redirect/to/' in u for u in abrir2.urls)


def test_banco_fora_no_inicio_avisa_e_nao_le_sites(tmp_path):
    avisos = Avisos()
    codigo, abrir = _cli(tmp_path, [], BancoFalso(conecta=False), avisos)
    assert codigo == 1
    assert abrir.urls == []
    assert avisos.textos == ['Captura web: banco fora do ar; gravadas 0 oferta(s) antes da falha.']


def test_mensagem_vai_ao_avisador_uma_vez(tmp_path):
    rotas = _rotas_tres_sites()
    rotas[PRO] = Resposta(403)
    rotas[PEC2] = Resposta(200, '<html/>')
    avisos = Avisos()
    _cli(tmp_path, [], BancoFalso(), avisos, rotas)
    assert avisos.textos == [('Captura web: Promobit bloqueado (HTTP 403); Pechinchou estrutura mudou em '
                             '/destaques. Gravadas 12 oferta(s).')]


def test_segunda_instancia_sai_com_codigo_2(tmp_path):
    banco = BancoFalso()
    with Trava(str(tmp_path / 'estado' / 'rodada.lock')):
        codigo, abrir = _cli(tmp_path, [], banco, Avisos())
    assert codigo == 2
    assert abrir.urls == [] and banco.gravadas == []
    codigo, _ = _cli(tmp_path, ['--simular'], BancoFalso(), Avisos())
    assert codigo == 0  # trava liberada


@pytest.mark.parametrize('argv', [['--simular'], []])
def test_log_de_arquivo_com_rotacao_14_dias(tmp_path, argv):
    import logging
    cli.configurar_log(str(tmp_path))
    try:
        (h,) = [h for h in logging.getLogger('captura_web').handlers if hasattr(h, 'backupCount')]
        assert (h.backupCount, h.when) == (14, 'MIDNIGHT')
        assert h.baseFilename == str(tmp_path / 'log' / 'captura_web.log')
    finally:
        for h in list(logging.getLogger('captura_web').handlers):
            logging.getLogger('captura_web').removeHandler(h)
            h.close()
        logging.getLogger('captura_web').propagate = True
