"""
Cadastro/atualizacao de cupons (BESAVE.CUPOM) -- ponto UNICO chamado tanto
pelo loop de captura ao vivo (main.py, logo apos uma captura bem-sucedida)
quanto pelo backfill do historico (backfill_cupons.py). So grava quando a
linha JA CAPTURADA de OFERTA_FILA_CAPTURA tem DS_CUPOM preenchido -- sem
cupom, nada a fazer.

DS_LOJA vem de OFERTA_FILA_CAPTURA.DS_CUPOM_LOJA (a loja ASSOCIADA AO CUPOM
propriamente dito, ja gravada na fila antes da captura -- nao vem do
scraping). Quando DS_CUPOM_LOJA vier vazio (raro, ~11 linhas no historico
inteiro) cai para o nome comercial resolvido pelo Python (registry.nome_loja),
mesmo padrao ja usado por BESAVE.OFERTA.DS_LOJA.

Chave de upsert = (CUPOM, DS_LOJA) -- o MESMO codigo de cupom se repete em
lojas diferentes com condicoes diferentes (confirmado no historico: ex.
"EUCERIN20" em 4 lojas, "RESGATE" em 3) -- checar so por CUPOM juntaria
cupons de lojas diferentes numa unica linha. Ver sql/STR_CUPOM_UPSERT.STP.

Cupom fora do padrao (2026-09-28): a origem as vezes manda mais de 1 codigo no
MESMO campo DS_CUPOM, unidos por " | " (ex. oferta 30303: "MODA2309 |
LOJASOFICIAIS"). Cada codigo separado por "|" vira SUA PROPRIA linha em
CUPOM (mesma DS_LOJA/DS_CUPOM/datas, CUPOM diferente, ID_CUPOM novo) -- ver
_separar_codigos().
"""

import oracledb


def _separar_codigos(cupom_bruto):
    """"MODA2309 | LOJASOFICIAIS" -> ["MODA2309", "LOJASOFICIAIS"]. Sem "|" ->
    1 item (caminho normal). Remove espacos e tokens vazios (ex. "A | | B")."""
    return [c.strip() for c in cupom_bruto.split('|') if c.strip()]


def publicar_cupom(db, linha, loja_fallback=None):
    """Cadastra/atualiza em BESAVE.CUPOM a partir de `linha` (dict com as
    chaves de OracleDB.COLUNAS_PARA_CUPOM -- a mesma linha JA GRAVADA em
    OFERTA_FILA_CAPTURA, incluindo ID_OFERTA -> grava em CUPOM.ID_ULT_OFERTA).
    `loja_fallback` e o nome comercial ja resolvido (registry.nome_loja) usado
    quando DS_CUPOM_LOJA vier vazio. Retorna (ids, erro):
      - (None, None): linha sem cupom, nada a gravar (nao e erro);
      - (lista de id_cupom, None): todos os codigos gravados com sucesso (1
        item na lista no caminho normal, >1 quando DS_CUPOM tinha "|");
      - (lista parcial ou None, str): algum codigo falhou -- a lista traz os
        que JA tinham sido gravados com sucesso antes da falha.
    Nunca propaga excecao (best-effort, como o resto da gravacao no Oracle) --
    falha aqui nao pode derrubar a captura, que ja foi bem-sucedida."""
    cupom_bruto = (linha.get('DS_CUPOM') or '').strip()
    if not cupom_bruto:
        return None, None
    id_oferta = linha.get('ID_OFERTA')
    id_ult_oferta = int(id_oferta) if id_oferta is not None else None
    ds_loja = linha.get('DS_CUPOM_LOJA') or loja_fallback
    ds_cupom_comentario = linha.get('DS_CUPOM_COMENTARIO')

    ids = []
    for codigo in _separar_codigos(cupom_bruto):
        params = {
            'P_CUPOM': codigo,
            'P_DS_CUPOM': ds_cupom_comentario,
            'P_DS_LOJA': ds_loja,
            'P_ID_ULT_OFERTA': id_ult_oferta,
        }
        try:
            out = db.executar_stored_procedure(
                'STR_CUPOM_UPSERT', params,
                {'P_ID_CUPOM': oracledb.DB_TYPE_NUMBER,
                 'PV_RETORNO': oracledb.DB_TYPE_VARCHAR,
                 'PV_ERRO': oracledb.DB_TYPE_VARCHAR},
            )
        except Exception as e:  # noqa: BLE001
            return (ids or None), str(e)
        ok = (out.get('PV_RETORNO') or '').upper() == 'TRUE'
        if not ok:
            return (ids or None), out.get('PV_ERRO')
        ids.append(out.get('P_ID_CUPOM'))
    return ids, None
