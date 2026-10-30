"""
Gera a URL_BESAVE (link do produto com o NOSSO codigo de afiliado no lugar do
divulgador que originou a oferta), a partir da url_final capturada da pagina.

Le BESAVE.LOJA_AFILIADA (ST_ATIVO = 1) UMA vez por execucao e guarda em
memoria: {nome_interno_da_store: {id_afiliado, id_ref_afiliado}}. Cada loja
tem sua propria regra de troca de parametros de tracking (ver
_regra_amazon/_regra_mercadolivre/_regra_shopee). Loja sem afiliado ativo na
tabela ou sem regra implementada aqui -> gerar_url() devolve None (o campo
fica NULL no banco, sem quebrar a captura).
"""

import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# DS_LOJA (tabela LOJA_AFILIADA) -> nome interno da store (stores/*.py -> nome)
_DS_LOJA_PARA_STORE = {
    'AMAZON': 'amazon',
    'MERCADO LIVRE': 'mercadolivre',
    'SHOPEE': 'shopee',
}

# Releitura de LOJA_AFILIADA quando o cache nao carregou: no maximo 1x por minuto.
INTERVALO_RETENTATIVA_S = 60

_afiliados = {}
_carregado = False
_falhou = False
_ultima_tentativa = None
_relogio = time.monotonic


def carregar(db):
    """Le LOJA_AFILIADA (ST_ATIVO=1) e guarda em memoria. Falha de leitura NAO
    marca o cache como carregado (ver garantir_carregado): sem ele nenhuma loja
    e ativa e a oferta nao entra em OFERTA. Nunca derruba a captura."""
    global _afiliados, _carregado, _falhou, _ultima_tentativa
    _ultima_tentativa = _relogio()
    if db is None:
        print('[afiliados] sem conexao Oracle; DS_URL_BESAVE nao sera gerado.')
        _afiliados, _carregado = {}, True
        return dict(_afiliados)

    def ler(cur):
        cur.execute(
            "SELECT DS_LOJA, ID_AFILIADO, ID_REF_AFILIADO "
            "FROM BESAVE.LOJA_AFILIADA WHERE ST_ATIVO = 1"
        )
        return list(cur)

    try:
        linhas = db.transacao(ler, commit=False)
    except Exception as e:  # noqa: BLE001
        if not _falhou:
            print(f'[afiliados] cache não carregado: {e}')
        _falhou = True
        return dict(_afiliados)
    novos = {}
    for ds_loja, id_afiliado, id_ref_afiliado in linhas:
        nome = _DS_LOJA_PARA_STORE.get((ds_loja or '').strip().upper())
        if nome:
            novos[nome] = {
                'id_afiliado': (id_afiliado or '').strip(),
                'id_ref_afiliado': (id_ref_afiliado or '').strip(),
            }
    _afiliados, _carregado = novos, True
    if _falhou:
        print('[afiliados] cache carregado (banco voltou).')
    _falhou = False
    print(f'[afiliados] {len(_afiliados)} loja(s) com afiliado ativo: '
          f'{", ".join(sorted(_afiliados)) or "-"}.')
    return dict(_afiliados)


def garantir_carregado(db):
    """True se o cache esta carregado. Se nao, tenta de novo (no maximo 1x por
    INTERVALO_RETENTATIVA_S). Quem recebe False nao pode publicar a linha."""
    if _carregado:
        return True
    if (_ultima_tentativa is not None
            and _relogio() - _ultima_tentativa < INTERVALO_RETENTATIVA_S):
        return False
    carregar(db)
    return _carregado


def _set_query_param(url, key, value):
    """Troca (ou acrescenta, se ausente) 1 parametro de query, preservando os
    demais parametros e a ordem original."""
    partes = urlsplit(url)
    pares = parse_qsl(partes.query, keep_blank_values=True)
    achou = False
    novos = []
    for k, v in pares:
        if k == key:
            novos.append((key, value))
            achou = True
        else:
            novos.append((k, v))
    if not achou:
        novos.append((key, value))
    query = urlencode(novos)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, query, ''))


def _regra_amazon(url, afiliado):
    # Troca so o parametro tag= (rastreio do divulgador) pelo NOSSO id de
    # afiliado; resto da URL (path/ref, demais params) fica intacto.
    return _set_query_param(url, 'tag', afiliado['id_afiliado'])


def _regra_mercadolivre(url, afiliado):
    # Descarta TUDO depois do "?" (rastreio do divulgador, inclusive a
    # #fragment de recomendacoes) e poe so os 2 parametros do NOSSO afiliado.
    partes = urlsplit(url)
    base = urlunsplit((partes.scheme, partes.netloc, partes.path, '', ''))
    return (f"{base}?matt_word={afiliado['id_afiliado']}"
            f"&matt_d2id={afiliado['id_ref_afiliado']}")


def _regra_shopee(url, afiliado):
    # Remove o gads_t_sig do divulgador (mantendo os demais params, ex.
    # exp_group) e acrescenta os parametros do NOSSO programa de afiliados.
    partes = urlsplit(url)
    pares = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
             if k != 'gads_t_sig']
    id_af = afiliado['id_afiliado']
    pares += [
        ('mmp_pid', f'an_{id_af}'),
        ('utm_content', '----'),
        ('utm_medium', 'affiliates'),
        ('utm_source', f'an_{id_af}'),
    ]
    query = urlencode(pares)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, query, ''))


_REGRAS = {
    'amazon': _regra_amazon,
    'mercadolivre': _regra_mercadolivre,
    'shopee': _regra_shopee,
}


def gerar_url(loja, url_final):
    """URL do produto com o NOSSO codigo de afiliado, a partir da url_final
    capturada. None se a loja nao tiver afiliado ativo (LOJA_AFILIADA) ou
    regra implementada -- nesse caso DS_URL_BESAVE fica NULL."""
    if not loja or not url_final or not _carregado:
        return None
    afiliado = _afiliados.get(loja)
    regra = _REGRAS.get(loja)
    if not afiliado or not regra:
        return None
    try:
        return regra(url_final, afiliado)
    except Exception:  # noqa: BLE001
        return None


def loja_ativa(loja):
    """A loja tem afiliado ativo em BESAVE.LOJA_AFILIADA (ST_ATIVO=1)? Usado
    p/ decidir o que entra na tabela OFERTA (2026-09-02) -- CONCEITO DIFERENTE
    de registry.loja_ativa() (que le conf/config.json -> "lojas_ativas" p/ a
    coluna ST_ATIVO de OFERTA_FILA_CAPTURA). Hoje as duas dao o mesmo
    resultado (Amazon/ML/Shopee), mas sao fontes distintas."""
    return bool(loja) and loja in _afiliados
