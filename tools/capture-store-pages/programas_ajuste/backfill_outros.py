"""
Backfill de 'Outros' (2026-09-28) nos registros HISTORICOS que ficaram NULL
antes da mudanca em core/ofertas.py / core/produtos.py (que agora grava
'Outros' em vez de NULL quando o classificador/widget nao identifica nada).
Ver [[captureamazon-recorrencia-amazon]] na memoria.

So toca OFERTA.DS_COMUNIDADE, OFERTA.DS_CATEGORIA_PROD_AFILIADO e
PRODUTO.DS_COMUNIDADE -- os 3 campos que o codigo ao vivo passou a defaultar.
Nao toca PRODUTO_COMUNIDADE (N:N): 'Outros' nao e uma das 9 comunidades reais
de BESAVE.COMUNIDADE, o codigo ao vivo tambem nao cria entrada la pra ele.
Nao toca OFERTA_FILA_CAPTURA.DS_CATEGORIA_PROD_AFILIADO (captura RAW do
widget, semantica diferente -- continua NULL quando o widget nao trouxe nada,
preservado por NVL na SP, exatamente como hoje).

UPDATE puro (sem SP), idempotente -- so mexe em quem esta NULL.

Uso:
    .venv/Scripts/python.exe backfill_outros.py --dry-run
    .venv/Scripts/python.exe backfill_outros.py --aplicar
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB

ALVOS = [
    ('OFERTA', 'DS_COMUNIDADE'),
    ('OFERTA', 'DS_CATEGORIA_PROD_AFILIADO'),
    ('PRODUTO', 'DS_COMUNIDADE'),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='So mostra quantas linhas seriam afetadas (padrao).')
    ap.add_argument('--aplicar', action='store_true', help='Grava de verdade.')
    args = ap.parse_args()
    aplicar = args.aplicar and not args.dry_run

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    cur = db._conn.cursor()
    for tabela, coluna in ALVOS:
        cur.execute(f'SELECT COUNT(*) FROM {tabela} WHERE {coluna} IS NULL')
        (qtde,) = cur.fetchone()
        print(f'{tabela}.{coluna} IS NULL: {qtde} linha(s)')
        if aplicar and qtde:
            cur.execute(f"UPDATE {tabela} SET {coluna} = 'Outros' WHERE {coluna} IS NULL")
            print(f'  -> {cur.rowcount} linha(s) atualizada(s).')
            db._conn.commit()
    cur.close()

    if not aplicar:
        print('\n[--dry-run] nada foi gravado. Rode com --aplicar para gravar de verdade.')

    db.desconectar()


if __name__ == '__main__':
    main()
