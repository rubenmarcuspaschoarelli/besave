"""BSV-66 Saída 1: requisição (cabeçalhos, pausa, repetição, 403/429, sem redirect)."""

import urllib.error
import urllib.request

import pytest
from web_falso import AbrirFalso, Resposta
from webapoio import http as mod
from webapoio.http import Bloqueado, Http, SemResposta

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0'


def _http(rotas, pausas=None):
    abrir = AbrirFalso(rotas)
    dormidas = [] if pausas is None else pausas
    h = Http(UA, (3, 6), abrir=abrir, dormir=dormidas.append, sortear=lambda a, b: (a, b))
    return h, abrir, dormidas


def test_cabecalhos_e_timeout():
    h, abrir, _ = _http({'https://x.com.br/a': Resposta(200, 'ok')})
    assert h.get('https://x.com.br/a') == 'ok'
    _url, headers, timeout, seguir = abrir.pedidos[0]
    assert headers == {'User-agent': UA, 'Accept-language': 'pt-BR'}
    assert timeout == 20
    assert seguir is True


def test_pausa_aleatoria_entre_todas_as_requisicoes():
    h, _abrir, dormidas = _http({'https://x.com.br/a': Resposta(200, 'a'),
                                'https://amzn.to/b': Resposta(302, location='https://www.amazon.com.br/dp/B0')})
    h.get('https://x.com.br/a')
    h.location('https://amzn.to/b')
    h.get('https://x.com.br/a')
    assert dormidas == [(3, 6), (3, 6)]
    assert h.requisicoes == 3


def test_uma_repeticao_em_timeout_e_5xx():
    h, abrir, dormidas = _http({'https://x.com.br/a': [Resposta(erro=TimeoutError('t')), Resposta(200, 'ok')],
                                'https://x.com.br/b': [Resposta(503), Resposta(200, 'b')]})
    assert h.get('https://x.com.br/a') == 'ok'
    assert h.get('https://x.com.br/b') == 'b'
    assert abrir.urls == ['https://x.com.br/a'] * 2 + ['https://x.com.br/b'] * 2
    assert len(dormidas) == 3


@pytest.mark.parametrize('respostas', [
    [Resposta(erro=urllib.error.URLError('x')), Resposta(erro=TimeoutError())],
    [Resposta(500), Resposta(502)],
])
def test_duas_falhas_viram_sem_resposta(respostas):
    h, abrir, _ = _http({'https://x.com.br/a': respostas})
    with pytest.raises(SemResposta):
        h.get('https://x.com.br/a')
    assert len(abrir.pedidos) == 2


@pytest.mark.parametrize('codigo', [403, 429])
def test_403_429_bloqueado_sem_repetir(codigo):
    h, abrir, _ = _http({'https://x.com.br/a': Resposta(codigo)})
    with pytest.raises(Bloqueado) as e:
        h.get('https://x.com.br/a')
    assert e.value.codigo == codigo
    assert len(abrir.pedidos) == 1


def test_404_sem_resposta_sem_repetir():
    h, abrir, _ = _http({})
    with pytest.raises(SemResposta):
        h.get('https://x.com.br/nada')
    assert len(abrir.pedidos) == 1


def test_location_sem_seguir_redirect():
    h, abrir, _ = _http({'https://meli.la/a': Resposta(301, location='https://www.mercadolivre.com.br/p/MLB1'),
                         'https://meli.la/b': Resposta(200, 'sem redirect')})
    assert h.location('https://meli.la/a') == 'https://www.mercadolivre.com.br/p/MLB1'
    assert h.location('https://meli.la/b') is None
    assert [p[3] for p in abrir.pedidos] == [False, False]


def test_abrir_urllib_sem_redirect_sem_cookies(monkeypatch):
    usados = []

    class Opener:
        def __init__(self, handlers):
            usados.append(handlers)

        def open(self, req, timeout):
            raise urllib.error.HTTPError(req.full_url, 302, 'Found', {'Location': 'https://destino'}, None)

    monkeypatch.setattr(urllib.request, 'build_opener', lambda *hs: Opener(hs))
    req = urllib.request.Request('https://amzn.to/x')
    status, headers, _ = mod.abrir_urllib(req, 20, False)
    assert (status, headers['Location']) == (302, 'https://destino')
    (handlers,) = usados
    assert len(handlers) == 1 and isinstance(handlers[0], urllib.request.HTTPRedirectHandler)
    assert handlers[0].redirect_request(req, None, 302, 'Found', {}, 'https://destino') is None
    mod.abrir_urllib(req, 20, True)
    assert usados[1] == ()  # opener padrão: sem HTTPCookieProcessor


def test_request_padrao_sem_accept_encoding():
    capturado = []
    h = Http(UA, (0, 0), abrir=lambda req, t, s: capturado.append(req) or (200, {}, b''), dormir=lambda s: None)
    h.get('https://x.com.br/a')
    nomes = {k.lower() for k, _ in capturado[0].header_items()}
    assert 'accept-encoding' not in nomes and 'cookie' not in nomes
