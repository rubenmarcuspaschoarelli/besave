"""
Publica ofertas aprovadas na tabela consolidada BESAVE.OFERTA -- ponto UNICO
chamado tanto pelo loop de captura ao vivo (main.py, logo apos o cadastro do
produto) quanto pelo backfill do historico (publicar_ofertas.py). "Aprovada" =
ST_CAPTURA='1' E loja com afiliado ativo em BESAVE.LOJA_AFILIADA (ver
core/afiliados.loja_ativa) -- essa checagem e feita pelo CHAMADOR, nao aqui.

Ver sql/STP_OFERTA_PUBLICAR.STP (insere-ou-atualiza via MERGE, ID_OFERTA
reaproveita o mesmo ID de OFERTA_FILA_CAPTURA).
"""

import oracledb

from core import duplicidade, validade
from core.oracle_db import erro_conexao
from core.precos import resolver_preco_por

# Duplicidade nao checada por falta de conexao (mesmo depois de reconectar): a
# oferta NAO e publicada e o chamador trava o ponteiro nela (BSV-52).
SEM_CONEXAO = 'sem conexao Oracle (duplicidade)'


def publicar_oferta(db, id_oferta, id_produto, loja_nome, linha, classificacao=None):
    """Publica 1 oferta em BESAVE.OFERTA. `linha` e um dict com as colunas de
    OracleDB.COLUNAS_PARA_OFERTA (a mesma linha JA GRAVADA em
    OFERTA_FILA_CAPTURA -- ver OracleDB.buscar_para_oferta). `classificacao`
    e o dict {'comunidade', 'publico'} ja calculado por
    core.produtos.cadastrar_produto (mesma chamada, mesmo resultado -- nao
    recalcula aqui) -- None so grava DS_COMUNIDADE/DS_PUBLICO NULL. Retorna
    (ok: bool, erro: str|None); nunca propaga excecao (best-effort, como o
    resto da gravacao no Oracle) -- falha aqui nao pode derrubar a captura
    nem o cadastro do produto, que ja foram bem-sucedidos."""
    classificacao = classificacao or {}
    # Cascata de preco (regras 1-3, ver core/precos.py) -- o mesmo valor final
    # tambem alimenta o minimo/maximo do produto em core/produtos.py.
    vl_preco_por = resolver_preco_por(linha)
    # Oferta mais velha que a validade (core/validade.py): nao publica nem
    # reativa -- se ja existir em OFERTA, fica inativa.
    if validade.vencida(linha.get('DT_OFERTA')):
        try:
            _desativar(db, id_oferta)
        except Exception as e:  # noqa: BLE001
            print(f'[ofertas] desativando vencida {id_oferta}: {e}')
        return False, validade.MOTIVO
    # Mesmo produto na janela de 24 h (core/duplicidade.py): se outra ganha
    # (menor preco; empate -> mais recente), nao publica, marca a fila e
    # devolve (False, 'duplicada de N').
    try:
        id_mantida = duplicidade.oferta_mantida(
            db, id_oferta, linha.get('DS_URL_FINAL'), vl_preco_por, linha.get('DT_OFERTA'),
            id_produto)
        if id_mantida is not None:
            duplicidade.marcar_duplicada(db, id_oferta, id_mantida)
            return False, f'{duplicidade.PREFIXO}{id_mantida}'
    except Exception as e:  # noqa: BLE001
        if erro_conexao(e):
            print(f'[ofertas] duplicidade sem conexao ({id_oferta}): {e} -- nao publicada.')
            return False, SEM_CONEXAO
        print(f'[ofertas] checagem de duplicidade falhou ({id_oferta}): {e} -- publicando.')
    params = {
        'P_ID_OFERTA': int(id_oferta),
        'P_ID_PRODUTO': int(id_produto),
        'P_DS_LOJA': loja_nome,
        'P_DS_TITULO': linha.get('DS_TITULO'),
        'P_DS_IMAGEM_OFERTA': linha.get('DS_IMAGEM_OFERTA'),
        'P_DS_URL_BESAVE': linha.get('DS_URL_BESAVE'),
        'P_DS_URL_FINAL': linha.get('DS_URL_FINAL'),
        'P_VL_PRECO_DE': linha.get('VL_PRECO_DE'),
        'P_VL_PRECO_POR': vl_preco_por,
        'P_VR_PRECO_1': linha.get('VR_PRECO_1'),
        'P_DS_CUPOM': linha.get('DS_CUPOM'),
        'P_DS_CUPOM_COMENTARIO': linha.get('DS_CUPOM_COMENTARIO'),
        'P_NR_NOTA_AVALIACAO': linha.get('NR_NOTA_AVALIACAO'),
        'P_QT_AVALIACAO': linha.get('QT_AVALIACAO'),
        'P_DT_OFERTA': linha.get('DT_OFERTA'),
        'P_DT_CAPTACAO': linha.get('DT_CAPTACAO'),
        # 'Outros' em vez de NULL quando nao ha classificacao/categoria
        # identificada (decisao do usuario, 2026-09-28).
        'P_DS_COMUNIDADE': classificacao.get('comunidade') or 'Outros',
        'P_DS_PUBLICO': classificacao.get('publico'),
        # Link oficial de afiliado + dados do mesmo widget: COPIADOS da fila
        # (capturados por core/link_afiliado.py na hora da captura). Vazio
        # quando a loja nao tem fluxo ou a sessao de afiliado estava fora.
        'P_DS_URL_AFILIADO': linha.get('DS_URL_AFILIADO'),
        'P_DS_CATEG_PROD_AFILIADO': linha.get('DS_CATEGORIA_PROD_AFILIADO') or 'Outros',
        'P_DS_TAXA_COM_PROD_AFILIADO': linha.get('DS_TAXA_COMISSAO_PROD_AFILIADO'),
        'P_DS_ID_PRODUTO_AFILIADO': linha.get('DS_ID_PRODUTO_AFILIADO'),
        # Recorrencia/espere-e-economize RAW (sem a cascata das regras 2/3 em
        # core/precos.py) -- informativo, mesmo papel do VR_PRECO_1. So a
        # Amazon preenche por ora.
        'P_VR_RECORRENCIA': linha.get('VR_RECORRENCIA'),
        'P_ST_RECORRENCIA': linha.get('ST_RECORRENCIA'),
        'P_QT_MINIMA_RECORRENCIA': linha.get('QT_MINIMA_RECORRENCIA'),
        'P_VR_ESPERE_ECONOMIZE': linha.get('VR_ESPERE_ECONOMIZE'),
        'P_ST_ESPERE_ECONOMIZE': linha.get('ST_ESPERE_ECONOMIZE'),
    }
    try:
        out = db.executar_stored_procedure(
            'STP_OFERTA_PUBLICAR', params,
            {'PV_RETORNO': oracledb.DB_TYPE_VARCHAR, 'PV_ERRO': oracledb.DB_TYPE_VARCHAR},
        )
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    ok = (out.get('PV_RETORNO') or '').upper() == 'TRUE'
    if ok:
        # Esta ganhou: as ofertas ativas da janela que ela vence saem do site.
        try:
            for id_perdedora in duplicidade.perdedoras(
                    db, id_oferta, linha.get('DS_URL_FINAL'), vl_preco_por,
                    linha.get('DT_OFERTA'), id_produto):
                duplicidade.marcar_duplicada(db, id_perdedora, id_oferta)
                print(f'[ofertas] {id_perdedora} desativada: {duplicidade.PREFIXO}{id_oferta}')
        except Exception as e:  # noqa: BLE001
            print(f'[ofertas] desativando concorrentes de {id_oferta}: {e}')
    return ok, (None if ok else out.get('PV_ERRO'))


def _desativar(db, id_oferta):
    def desativar(cur):
        cur.execute("UPDATE OFERTA SET ST_ATIVO = 0, DT_DESATIVACAO = NVL(DT_DESATIVACAO, SYSDATE) "
                    "WHERE ID_OFERTA = :id AND NVL(ST_ATIVO, 1) <> 0", id=int(id_oferta))

    db.transacao(desativar)
