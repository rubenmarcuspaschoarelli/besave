"""API de afiliados da Shopee (BSV-59): produto e link de afiliado sem navegador.

GraphQL em ENDPOINT, assinado com SHA-256 de app_id + timestamp + corpo + app_secret.
Os erros vem com HTTP 200 no array `errors`: decide-se por ele, nunca pelo status.
Credencial e assinatura nunca vao para log, excecao ou retorno.
"""

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urljoin, urlsplit

ENDPOINT = 'https://open-api.affiliate.shopee.com.br/graphql'
TIMEOUT_PADRAO = 20

# Motivos. Os tres primeiros sao passageiros (linha retida); os outros viram '9'.
API_INDISPONIVEL = 'api_indisponivel'
API_CREDENCIAL = 'api_credencial'
API_LIMITE = 'api_limite'
FORA_DO_PROGRAMA = 'fora_do_programa'
ITEM_DIVERGENTE = 'item_divergente'
URL_NAO_RECONHECIDA = 'url_nao_reconhecida'
PASSAGEIROS = frozenset({API_INDISPONIVEL, API_CREDENCIAL, API_LIMITE})

_CODIGO_CREDENCIAL = 10020   # Invalid Signature / Request Expired
_CODIGO_LIMITE = 10030       # nao documentado; usado por cliente de terceiros (spec BSV-59)


def assinar(app_id, ts, payload, app_secret):
    """Hex do SHA-256 de app_id + ts + payload + app_secret."""
    return hashlib.sha256(f'{app_id}{ts}{payload}{app_secret}'.encode()).hexdigest()


class Config:
    def __init__(self, app_id, app_secret, timeout):
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout = timeout

    def __repr__(self):
        return f'shopee_api.Config(timeout={self.timeout})'


def ler_config(cfg):
    """Bloco `shopee_afiliado` com `habilitado: true` -> Config; ausente ou desligado -> None."""
    bloco = (cfg or {}).get('shopee_afiliado')
    if not isinstance(bloco, dict) or bloco.get('habilitado') is not True:
        return None
    try:
        timeout = float(bloco.get('timeout_segundos', TIMEOUT_PADRAO))
    except (TypeError, ValueError):
        timeout = TIMEOUT_PADRAO
    return Config(str(bloco.get('app_id') or ''), str(bloco.get('app_secret') or ''),
                  timeout if timeout > 0 else TIMEOUT_PADRAO)


def _preco(texto):
    try:
        valor = Decimal(str(texto).strip())
    except (InvalidOperation, ValueError):
        return None
    if not valor.is_finite() or valor <= 0:
        return None
    return str(valor.quantize(Decimal('0.01')))


def _comissao(texto):
    """"0.13" -> "13%"; "0.135" -> "13,5%". Vazio/invalido -> ''."""
    try:
        valor = Decimal(str(texto).strip()) * 100
    except (InvalidOperation, ValueError):
        return ''
    if not valor.is_finite():
        return ''
    valor = valor.normalize()
    texto = f'{valor:f}'
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto.replace('.', ',') + '%'


def _texto(valor):
    return '' if valor is None else str(valor).strip()


class Cliente:
    """Cliente da API. `detalhe` guarda a mensagem do ultimo erro (para o aviso), nunca credencial."""

    def __init__(self, app_id, app_secret, timeout=TIMEOUT_PADRAO, endpoint=ENDPOINT, relogio=time.time):
        self._app_id = app_id
        self._app_secret = app_secret
        self.timeout = timeout
        self.endpoint = endpoint
        self.relogio = relogio
        self.detalhe = ''

    @classmethod
    def de_config(cls, config):
        return cls(config.app_id, config.app_secret, config.timeout, endpoint=ENDPOINT)

    def __repr__(self):
        return f'shopee_api.Cliente(endpoint={self.endpoint!r})'

    def _falha(self, motivo, detalhe=''):
        self.detalhe = detalhe or motivo
        print(f'shopee api: {motivo}' + (f' ({detalhe})' if detalhe else ''))
        return None, motivo

    def _chamar(self, query):
        """POST assinado -> (data, None) ou (None, motivo)."""
        self.detalhe = ''
        payload = json.dumps({'query': query}, separators=(',', ':'))
        corpo = payload.encode('utf-8')
        ts = int(self.relogio())
        assinatura = assinar(self._app_id, ts, payload, self._app_secret)
        pedido = urllib.request.Request(self.endpoint, data=corpo, method='POST', headers={
            'Content-Type': 'application/json',
            'Authorization': f'SHA256 Credential={self._app_id}, Timestamp={ts}, Signature={assinatura}',
        })
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout) as resp:
                status = resp.status
                bruto = resp.read()
        except urllib.error.HTTPError as e:
            return self._falha(API_INDISPONIVEL, f'HTTP {e.code}')
        except (urllib.error.URLError, OSError, ValueError) as e:
            # So o tipo: a mensagem de rede nao carrega credencial, mas nao ha por que arriscar.
            return self._falha(API_INDISPONIVEL, type(e).__name__)
        if status != 200:
            return self._falha(API_INDISPONIVEL, f'HTTP {status}')
        try:
            resposta = json.loads(bruto)
        except ValueError:
            return self._falha(API_INDISPONIVEL, 'JSON ilegivel')
        if not isinstance(resposta, dict):
            return self._falha(API_INDISPONIVEL, 'JSON ilegivel')
        erros = resposta.get('errors')
        if erros:
            primeiro = erros[0] if isinstance(erros, list) and isinstance(erros[0], dict) else {}
            ext = primeiro.get('extensions') if isinstance(primeiro.get('extensions'), dict) else {}
            codigo = ext.get('code')
            if codigo == _CODIGO_CREDENCIAL:
                mensagem = _texto(ext.get('message')) or _texto(primeiro.get('message'))
                return self._falha(API_CREDENCIAL, f'codigo {codigo}: {mensagem[:120]}')
            if codigo == _CODIGO_LIMITE:
                return self._falha(API_LIMITE, f'codigo {codigo}')
            return self._falha(API_INDISPONIVEL, f'codigo {codigo}')
        data = resposta.get('data')
        if not isinstance(data, dict):
            return self._falha(API_INDISPONIVEL, 'sem data')
        return data, None

    def produto(self, shop_id, item_id):
        """productOfferV2 do item -> (chaves da captura + imagem_url, None) ou (None, motivo)."""
        shop_id, item_id = int(shop_id), int(item_id)
        data, motivo = self._chamar(
            f'{{ productOfferV2(shopId: {shop_id}, itemId: {item_id}) {{ nodes {{ itemId shopId '
            'productName price imageUrl ratingStar sales commissionRate } pageInfo { hasNextPage } } }')
        if motivo:
            return None, motivo
        nos = ((data.get('productOfferV2') or {}).get('nodes'))
        if not isinstance(nos, list):
            return self._falha(API_INDISPONIVEL, 'sem nodes')
        if not nos:
            return self._falha(FORA_DO_PROGRAMA, f'item={item_id}')
        if len(nos) != 1 or not isinstance(nos[0], dict) or _texto(nos[0].get('itemId')) != str(item_id):
            return self._falha(ITEM_DIVERGENTE, f'item={item_id} nos={len(nos)}')
        no = nos[0]
        preco = _preco(no.get('price'))
        if preco is None:
            return self._falha(ITEM_DIVERGENTE, f'item={item_id} sem preco')
        print(f'shopee api: ok item={item_id}')
        return {
            'produto_titulo': _texto(no.get('productName')),
            'preco_1': preco,
            'avaliacao_nota': _texto(no.get('ratingStar')),
            'quantidade_vendida': _texto(no.get('sales')),
            'taxa_comissao_afiliado': _comissao(no.get('commissionRate')),
            'id_produto_afiliado': f'{shop_id}.{item_id}',
            'imagem_url': _texto(no.get('imageUrl')),
        }, None

    def link_afiliado(self, shop_id, item_id):
        """generateShortLink da URL limpa do item -> (shortLink, None) ou (None, motivo)."""
        shop_id, item_id = int(shop_id), int(item_id)
        origem = f'https://shopee.com.br/product/{shop_id}/{item_id}'
        data, motivo = self._chamar(
            f'mutation {{ generateShortLink(input: {{originUrl: "{origem}"}}) {{ shortLink }} }}')
        if motivo:
            return None, motivo
        curto = _texto((data.get('generateShortLink') or {}).get('shortLink'))
        if not curto:
            return self._falha(API_INDISPONIVEL, 'sem shortLink')
        return curto, None


# --- Resolucao da URL do grupo -> (shopId, itemId) ------------------------------------------
MAX_PEDIDOS = 3
_RE_I = re.compile(r'-i\.(\d+)\.(\d+)(?:$|[/?#])')


class _SemSeguir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_ABRIDOR = urllib.request.build_opener(_SemSeguir)


def abrir_sem_seguir(url, timeout):
    """HEAD sem seguir redirect -> (status, Location ou None). Erro de rede levanta OSError."""
    pedido = urllib.request.Request(url, method='HEAD')
    try:
        with _ABRIDOR.open(pedido, timeout=timeout) as resp:
            return resp.status, resp.headers.get('Location')
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Location') if e.headers else None


def _host_shopee(host):
    host = (host or '').lower()
    return host == 'shopee.com.br' or host.endswith('.shopee.com.br')


def extrair_ids(url):
    """(shopId, itemId) de `/<x>/<shop>/<item>` ou `-i.<shop>.<item>` em shopee.com.br; senao None."""
    partes = urlsplit(url or '')
    if partes.hostname not in ('shopee.com.br', 'www.shopee.com.br'):
        return None
    caminho = unquote(partes.path)
    m = _RE_I.search(caminho)
    if m:
        return int(m.group(1)), int(m.group(2))
    segmentos = [s for s in caminho.split('/') if s]
    if len(segmentos) >= 3 and segmentos[-1].isdigit() and segmentos[-2].isdigit():
        return int(segmentos[-2]), int(segmentos[-1])
    return None


def resolver(url, abrir=None, timeout=TIMEOUT_PADRAO):
    """URL do grupo -> ((shopId, itemId), None) ou (None, motivo).

    Ate MAX_PEDIDOS pedidos sem seguir redirect, so a hosts da Shopee. Rede fora,
    5xx ou 429 -> API_INDISPONIVEL (passageiro); o resto -> URL_NAO_RECONHECIDA.
    """
    abrir = abrir or abrir_sem_seguir
    atual = (url or '').strip()
    for pedido in range(MAX_PEDIDOS + 1):
        ids = extrair_ids(atual)
        if ids:
            return ids, None
        if pedido == MAX_PEDIDOS or not _host_shopee(urlsplit(atual).hostname):
            break
        try:
            status, destino = abrir(atual, timeout)
        except (OSError, ValueError) as e:
            print(f'shopee api: {API_INDISPONIVEL} (resolver: {type(e).__name__})')
            return None, API_INDISPONIVEL
        if status >= 500 or status == 429:
            print(f'shopee api: {API_INDISPONIVEL} (resolver: HTTP {status})')
            return None, API_INDISPONIVEL
        if not (300 <= status < 400 and destino):
            break
        atual = urljoin(atual, destino)
    print(f'shopee api: {URL_NAO_RECONHECIDA}')
    return None, URL_NAO_RECONHECIDA
