"""
Cadastro consolidado de produtos (BESAVE.PRODUTO) -- ponto UNICO chamado tanto
pelo loop de captura ao vivo (main.py, logo apos uma gravacao bem-sucedida em
OFERTA_FILA_CAPTURA) quanto pelo backfill do historico (cadastrar_produtos.py).
Ambos os chamadores leem a linha JA GRAVADA (via OracleDB.buscar_para_produto)
antes de chamar cadastrar_produto() aqui -- garante que os dois caminhos vejam
exatamente o mesmo texto/numero que esta no banco, sem duplicar a logica de
conversao de tipo do core/oracle_db.py.

Extracao dos atributos (marca/modelo/dimensoes/...) em core/produto_extrator.py
(mineracao dos 4 campos LS_*). Busca/insert-or-update/sequence/write-back em
sql/STP_PRODUTO_UPSERT.STP.
"""

import oracledb

from core import classificador
from core.precos import resolver_preco_por
from core.produto_extrator import extrair_atributos, resolver_titulo

_comunidades_cache = None


def _mapa_comunidades(db):
    """ID_COMUNIDADE por nome (BESAVE.COMUNIDADE), lido 1x e cacheado em
    memoria -- mesmo padrao de core/afiliados.py p/ LOJA_AFILIADA. Recarrega
    se a 1a leitura falhar/vier vazia (ex.: banco ainda nao tinha a tabela no
    boot do processo)."""
    global _comunidades_cache
    if _comunidades_cache:
        return _comunidades_cache
    mapa = {}
    try:
        cur = db._conn.cursor()
        try:
            cur.execute('SELECT DS_COMUNIDADE, ID_COMUNIDADE FROM BESAVE.COMUNIDADE')
            mapa = {nome: id_ for nome, id_ in cur}
        finally:
            cur.close()
    except Exception as e:  # noqa: BLE001
        print(f'[produtos] falha ao ler COMUNIDADE: {e}')
        return {}
    _comunidades_cache = mapa
    return mapa


def gravar_classificacao(db, id_produto, comunidades, publico):
    """Grava as linhas N:N de PRODUTO_COMUNIDADE/PRODUTO_PUBLICO (DELETE +
    INSERT, idempotente). Best-effort: nunca propaga excecao -- o ID_PRODUTO
    ja foi obtido com sucesso antes de chamar isto, essa gravacao e so
    enriquecimento."""
    try:
        mapa = _mapa_comunidades(db)
        cur = db._conn.cursor()
        try:
            cur.execute('DELETE FROM BESAVE.PRODUTO_COMUNIDADE WHERE ID_PRODUTO = :id', {'id': id_produto})
            for ordem, (nome, score) in enumerate(comunidades, start=1):
                id_comunidade = mapa.get(nome)
                if id_comunidade is None:
                    continue
                cur.execute(
                    'INSERT INTO BESAVE.PRODUTO_COMUNIDADE (ID_PRODUTO, ID_COMUNIDADE, NR_ORDEM, NR_SCORE) '
                    'VALUES (:id_produto, :id_comunidade, :ordem, :score)',
                    {'id_produto': id_produto, 'id_comunidade': id_comunidade, 'ordem': ordem, 'score': score},
                )
            cur.execute('DELETE FROM BESAVE.PRODUTO_PUBLICO WHERE ID_PRODUTO = :id', {'id': id_produto})
            if publico:
                cur.execute(
                    'INSERT INTO BESAVE.PRODUTO_PUBLICO (ID_PRODUTO, DS_PUBLICO, NR_ORDEM) '
                    'VALUES (:id_produto, :publico, 1)',
                    {'id_produto': id_produto, 'publico': publico},
                )
            db._conn.commit()
        finally:
            cur.close()
    except Exception as e:  # noqa: BLE001
        print(f'[produtos] falha ao gravar PRODUTO_COMUNIDADE/PRODUTO_PUBLICO ({id_produto}): {e}')

_CLOB_PARAMS = [
    'P_LS_CATEGORIA', 'P_DS_AVALIACAO_GERAL', 'P_LS_DETALHES_PRODUTO',
    'P_LS_DETALHES_TECNICOS', 'P_LS_INFO_ADICIONAIS', 'P_LS_COMPLEMENTO_PRODUTO',
]

# Campos extraidos (core/produto_extrator.extrair_atributos) -> parametro da SP.
_MAPA_EXTRAIDOS = {
    'ID_COD_EAN': 'P_ID_COD_EAN', 'ID_COD_ASIN': 'P_ID_COD_ASIN',
    'DS_PAIS_ORIGEM': 'P_DS_PAIS_ORIGEM', 'DS_MARCA': 'P_DS_MARCA',
    'DS_FABRICANTE': 'P_DS_FABRICANTE', 'DS_MODELO': 'P_DS_MODELO',
    'DS_PESO_LIQUIDO': 'P_DS_PESO_LIQUIDO', 'DS_PESO': 'P_DS_PESO',
    'DS_VOLUME': 'P_DS_VOLUME', 'DS_GENERO': 'P_DS_GENERO',
    'NR_NOTA_AVALIACAO': 'P_NR_NOTA_AVALIACAO', 'QT_AVALIACAO': 'P_QT_AVALIACAO',
    'NR_RANKING': 'P_NR_RANKING', 'DS_CATEGORIA_RANKING': 'P_DS_CATEGORIA_RANKING',
    'DS_FAIXA_ETARIA': 'P_DS_FAIXA_ETARIA', 'DS_LINHA': 'P_DS_LINHA',
    'DS_ALTURA': 'P_DS_ALTURA', 'DS_LARGURA': 'P_DS_LARGURA',
    'DS_COMPRIMENTO': 'P_DS_COMPRIMENTO', 'DS_UNIDADES': 'P_DS_UNIDADES',
}


def clob_para_texto(v):
    # oracledb devolve LOB objects por padrao para colunas CLOB; le como texto
    # (ou None/str, se ja vier assim -- ex. de um dict montado a mao em teste).
    if v is None:
        return None
    try:
        return v.read()
    except AttributeError:
        return v


def cadastrar_produto(db, id_oferta, linha):
    """Acha/cadastra o produto (STP_PRODUTO_UPSERT) a partir de UMA linha JA
    GRAVADA de OFERTA_FILA_CAPTURA (dict com as chaves de
    OracleDB.COLUNAS_PARA_PRODUTO -- ver OracleDB.buscar_para_produto) e grava
    ID_PRODUTO de volta na propria linha. Tambem classifica o produto em
    comunidade(s)/publico (core/classificador.py, a partir de LS_CATEGORIA)
    e grava em PRODUTO.DS_COMUNIDADE/DS_PUBLICO + PRODUTO_COMUNIDADE/
    PRODUTO_PUBLICO (N:N). Retorna (id_produto, classificacao, erro) --
    classificacao e {'comunidade': str|None, 'publico': str} ou None em erro.
    NUNCA propaga excecao (best-effort, como o resto da gravacao no Oracle) --
    falha aqui nao pode derrubar a captura, que ja foi bem-sucedida.
    """
    titulo = resolver_titulo(linha.get('DS_TITULO'), linha.get('DS_OFERTA'))
    if not titulo:
        return None, None, 'sem titulo (DS_TITULO e DS_OFERTA vazios)'

    ls_detalhes_produto = clob_para_texto(linha.get('LS_DETALHES_PRODUTO'))
    ls_detalhes_tecnicos = clob_para_texto(linha.get('LS_DETALHES_TECNICOS'))
    ls_info_adicionais = clob_para_texto(linha.get('LS_INFO_ADICIONAIS'))
    ls_complemento_produto = clob_para_texto(linha.get('LS_COMPLEMENTO_PRODUTO'))
    ls_categoria = clob_para_texto(linha.get('LS_CATEGORIA'))
    avaliacao_geral = clob_para_texto(linha.get('DS_AVALIACAO_GERAL'))

    extraidos = extrair_atributos(
        ls_detalhes_produto, ls_detalhes_tecnicos, ls_info_adicionais, ls_complemento_produto)

    # Cascata de preco (regras 1-3, ver core/precos.py) -- o mesmo valor final
    # tambem alimenta OFERTA.VL_PRECO_POR em core/ofertas.py.
    vl_preco_por = resolver_preco_por(linha)

    params = {
        'P_ID_OFERTA': int(id_oferta),
        'P_DS_PRODUTO': titulo,
        'P_DS_DESCRICAO_PRODUTO': linha.get('DS_PRODUTO'),
        'P_VL_PRECO_POR': vl_preco_por,
        'P_DS_URL_AFILIADO': linha.get('DS_URL_AFILIADO'),
        'P_LS_CATEGORIA': ls_categoria,
        'P_QT_OPINIOES': linha.get('QT_OPINIOES'),
        'P_DS_AVALIACAO_GERAL': avaliacao_geral,
        'P_LS_DETALHES_PRODUTO': ls_detalhes_produto,
        'P_LS_DETALHES_TECNICOS': ls_detalhes_tecnicos,
        'P_LS_INFO_ADICIONAIS': ls_info_adicionais,
        'P_LS_COMPLEMENTO_PRODUTO': ls_complemento_produto,
    }
    for campo, param in _MAPA_EXTRAIDOS.items():
        params[param] = extraidos.get(campo)

    comunidades, publico = classificador.classificar(
        ls_categoria, titulo, extraidos.get('DS_CATEGORIA_RANKING'))
    # 'Outros' em vez de NULL quando nenhuma regra do classificador bateu
    # (decisao do usuario, 2026-09-28). Nao entra em PRODUTO_COMUNIDADE (N:N,
    # gravar_classificacao) porque 'Outros' nao e uma das 9 comunidades reais
    # de BESAVE.COMUNIDADE -- so a coluna escalar DS_COMUNIDADE reflete isso.
    comunidade_principal = comunidades[0][0] if comunidades else 'Outros'
    params['P_DS_COMUNIDADE'] = comunidade_principal
    params['P_DS_PUBLICO'] = publico

    try:
        out = db.executar_stored_procedure(
            'STP_PRODUTO_UPSERT', params,
            {'P_ID_PRODUTO': oracledb.DB_TYPE_NUMBER,
             'PV_RETORNO': oracledb.DB_TYPE_VARCHAR,
             'PV_ERRO': oracledb.DB_TYPE_VARCHAR},
            clob_params=_CLOB_PARAMS,
        )
    except Exception as e:  # noqa: BLE001
        return None, None, str(e)

    ok = (out.get('PV_RETORNO') or '').upper() == 'TRUE'
    if not ok:
        return None, None, out.get('PV_ERRO')

    id_produto = out.get('P_ID_PRODUTO')
    gravar_classificacao(db, id_produto, comunidades, publico)
    return id_produto, {'comunidade': comunidade_principal, 'publico': publico}, None
