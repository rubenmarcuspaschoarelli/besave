"""`conf/config.json` (BSV-66, Saída 10): padrões da spec; chave inválida -> padrão com WARN."""

import copy
import json
import logging
import os
from urllib.parse import urlsplit

from .oferta import PECHINCHOU, PELANDO, PROMOBIT

log = logging.getLogger('captura_web')

UA_PADRAO = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
             'Chrome/131.0.0.0 Safari/537.36')

HOSTS = {PELANDO: 'www.pelando.com.br', PROMOBIT: 'www.promobit.com.br', PECHINCHOU: 'pechinchou.com.br'}

PADROES = {
    'db': {},
    'alerta': {},
    'user_agent': UA_PADRAO,
    'pausa_s': [3, 6],
    'por_menu': 5,
    'teto_rodada': 30,
    'idade_max_horas': 24,
    'sites': {
        PELANDO: {'habilitado': True, 'menus': [
            'https://www.pelando.com.br/recentes',
            'https://www.pelando.com.br/mais-baratos',
            'https://www.pelando.com.br/mais-quentes',
        ]},
        PROMOBIT: {'habilitado': True, 'menus': [
            'https://www.promobit.com.br/',
            'https://www.promobit.com.br/promocoes/recentes/',
            'https://www.promobit.com.br/promocoes/em-alta/',
            'https://www.promobit.com.br/promocoes/menor-preco/',
        ]},
        PECHINCHOU: {'habilitado': True, 'menus': [
            'https://pechinchou.com.br/recentes',
            'https://pechinchou.com.br/destaques',
            'https://pechinchou.com.br/menor-preco',
            'https://pechinchou.com.br/mais-pontuados',
            'https://pechinchou.com.br/pechinchas',
        ]},
    },
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _inteiro_positivo(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


VALIDADORES = {
    'db': lambda v: isinstance(v, dict),
    'alerta': lambda v: isinstance(v, dict),
    'user_agent': lambda v: isinstance(v, str) and bool(v.strip()),
    'pausa_s': lambda v: (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)
                          and 0 <= v[0] <= v[1]),
    'por_menu': _inteiro_positivo,
    'teto_rodada': _inteiro_positivo,
    'idade_max_horas': lambda v: _num(v) and v > 0,
}
SECRETOS = ('db', 'alerta')


def menu_permitido(site, url):
    """Só páginas do próprio site, em https, fora de `/api/` (regra 2 da spec)."""
    if not isinstance(url, str):
        return False
    p = urlsplit(url.strip())
    caminho = (p.path or '/').lower()
    return (p.scheme == 'https' and (p.hostname or '').lower() == HOSTS[site]
            and not (caminho == '/api' or caminho.startswith('/api/')))


def _sites(bruto):
    sites = copy.deepcopy(PADROES['sites'])
    if bruto is None:
        return sites
    if not isinstance(bruto, dict):
        log.warning('config: sites invalido; usando o padrao')
        return sites
    for chave in sites:
        s = bruto.get(chave)
        if s is None:
            continue
        if not isinstance(s, dict):
            log.warning('config: sites.%s invalido; usando o padrao', chave)
            continue
        if 'habilitado' in s:
            if isinstance(s['habilitado'], bool):
                sites[chave]['habilitado'] = s['habilitado']
            else:
                log.warning('config: sites.%s.habilitado invalido; usando o padrao', chave)
        if 'menus' not in s:
            continue
        menus = s['menus']
        if not isinstance(menus, list):
            log.warning('config: sites.%s.menus invalido; usando o padrao', chave)
            continue
        ok = []
        for u in menus:
            if menu_permitido(chave, u):
                ok.append(u.strip())
            else:
                log.warning('config: menu fora do site ou em /api/ ignorado em %s: %r', chave, u)
        if ok:
            sites[chave]['menus'] = ok
        else:
            log.warning('config: sites.%s.menus sem menu valido; usando o padrao', chave)
    return sites


def carregar(caminho, ambiente=None):
    ambiente = os.environ if ambiente is None else ambiente
    bruto = {}
    try:
        with open(caminho, encoding='utf-8') as f:
            bruto = json.load(f)
    except FileNotFoundError:
        log.warning('config: %s ausente; usando os padroes', os.path.basename(caminho))
    except (OSError, ValueError) as e:
        log.warning('config: %s ilegivel (%s); usando os padroes', os.path.basename(caminho),
                    type(e).__name__)
    if not isinstance(bruto, dict):
        log.warning('config: raiz nao e objeto; usando os padroes')
        bruto = {}
    cfg = {}
    for chave, validar in VALIDADORES.items():
        if chave in bruto and validar(bruto[chave]):
            cfg[chave] = copy.deepcopy(bruto[chave])
            continue
        if chave in bruto:
            padrao = 'vazio' if chave in SECRETOS else repr(PADROES[chave])
            log.warning('config: %s invalido; usando o padrao %s', chave, padrao)
        cfg[chave] = copy.deepcopy(PADROES[chave])
    cfg['pausa_s'] = tuple(cfg['pausa_s'])
    cfg['sites'] = _sites(bruto.get('sites'))
    senha = ambiente.get('BESAVE_WEB_SENHA')
    if senha:
        cfg['db']['senha'] = senha
    return cfg
