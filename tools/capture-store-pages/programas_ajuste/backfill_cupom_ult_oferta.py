"""
Backfill de BESAVE.CUPOM.ID_ULT_OFERTA (coluna criada pelo usuario,
2026-09-28) no historico. So preenche o FACIL: CUPOM.ID_ULT_OFERTA IS NULL e
existe em OFERTA uma linha com o MESMO codigo (OFERTA.DS_CUPOM, sem
diferenciar caixa) e a MESMA loja (DS_LOJA, NULL tratado como uma loja "*") --
pega a oferta mais RECENTE (maior DT_CAPTACAO, empate por ID_OFERTA) entre as
que baterem.

NAO tenta casar os cupons "fora do padrao" (que tinham "|" e foram separados
por backfill_cupom_split.py) contra o DS_CUPOM ainda unido de OFERTA -- essa
comparacao exata nunca bate para eles, de propos ito (ver pedido do usuario:
"so fazer o backfill se for facil"). Esses continuam sem ID_ULT_OFERTA.

UPDATE puro (sem SP), idempotente -- so mexe em quem esta NULL.

Uso:
    .venv/Scripts/python.exe backfill_cupom_ult_oferta.py --dry-run
    .venv/Scripts/python.exe backfill_cupom_ult_oferta.py --aplicar
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB

# Correlacionar 2 niveis de subquery (p/ aplicar ROWNUM=1 DEPOIS do ORDER BY)
# num scalar subquery do SELECT list nao funciona neste Oracle 11g (ORA-00904
# -- a correlacao com o alias da query externa nao atravessa o 2o nivel de
# aninhamento). Por isso 1 SELECT por linha em Python em vez de 1 UPDATE so.
SQL_PENDENTES = "SELECT ID_CUPOM, CUPOM, DS_LOJA FROM CUPOM WHERE ID_ULT_OFERTA IS NULL"

SQL_MATCH = """
    SELECT ID_OFERTA FROM (
      SELECT ID_OFERTA FROM OFERTA
      WHERE UPPER(DS_CUPOM) = UPPER(:cupom)
        AND NVL(UPPER(DS_LOJA), '*') = NVL(UPPER(:loja), '*')
      ORDER BY DT_CAPTACAO DESC, ID_OFERTA DESC
    ) WHERE ROWNUM = 1
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='So mostra o que seria feito (padrao).')
    ap.add_argument('--aplicar', action='store_true', help='Grava de verdade.')
    args = ap.parse_args()
    aplicar = args.aplicar and not args.dry_run

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    cur = db._conn.cursor()
    cur.execute(SQL_PENDENTES)
    pendentes = [{'ID_CUPOM': r[0], 'CUPOM': r[1], 'DS_LOJA': r[2]} for r in cur]

    linhas = []
    for p in pendentes:
        cur.execute(SQL_MATCH, {'cupom': p['CUPOM'], 'loja': p['DS_LOJA']})
        row = cur.fetchone()
        linhas.append({**p, 'ID_OFERTA_ACHADA': row[0] if row else None})

    sem_ult_oferta = len(linhas)
    achadas = [l for l in linhas if l['ID_OFERTA_ACHADA'] is not None]
    print(f'{sem_ult_oferta} cupom(ns) sem ID_ULT_OFERTA; {len(achadas)} com match facil '
          f'(mesmo codigo + mesma loja em OFERTA).')

    for linha in achadas:
        print(f"[cupom {linha['ID_CUPOM']}] {linha['CUPOM']!r} (loja={linha['DS_LOJA']!r}) "
              f"-> ID_ULT_OFERTA={linha['ID_OFERTA_ACHADA']}"
              + ('' if aplicar else ' (dry-run)'))
        if aplicar:
            cur.execute(
                'UPDATE CUPOM SET ID_ULT_OFERTA = :oferta WHERE ID_CUPOM = :id',
                {'oferta': linha['ID_OFERTA_ACHADA'], 'id': linha['ID_CUPOM']},
            )
    if aplicar:
        db._conn.commit()
    cur.close()

    print(f'\n{len(linhas) - len(achadas)} cupom(ns) sem match facil -- ficam sem ID_ULT_OFERTA '
          f'(nao e erro, so nao deu pra achar com seguranca).')
    if not aplicar:
        print('[--dry-run] nada foi gravado. Rode com --aplicar para gravar de verdade.')

    db.desconectar()


if __name__ == '__main__':
    main()
