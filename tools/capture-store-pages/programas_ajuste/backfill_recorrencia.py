"""
Backfill de VR_RECORRENCIA/ST_RECORRENCIA/QT_MINIMA_RECORRENCIA (2026-09-28),
em duas fases independentes -- SEM reabrir navegador, o dado cru
(VR_PRECO_RECORRENCIA_INTEIRO/FRACAO, QT_MINIMA_RECORRENCIA) ja esta gravado em
OFERTA_FILA_CAPTURA desde antes desta mudanca.

Fase 1 (colunas) -- SEMPRE roda:
  * OFERTA_FILA_CAPTURA: VR_RECORRENCIA = INTEIRO + FRACAO/100 (NULL se sem
    INTEIRO); ST_RECORRENCIA = 1/0. So ST_CAPTURA='1' (as demais nunca tiveram
    esses campos capturados).
  * OFERTA: espelha VR_RECORRENCIA/ST_RECORRENCIA/QT_MINIMA_RECORRENCIA da
    FILA para as ofertas ja publicadas.
  UPDATE puro (sem SP), idempotente -- pode rodar de novo a qualquer momento.

Fase 2 (preco), com --tambem-preco: para ofertas Amazon onde a recorrencia
(ST_RECORRENCIA=1) e MENOR que o VL_PRECO_POR hoje publicado em OFERTA, corrige
OFERTA.VL_PRECO_POR para o valor da recorrencia (regra 2, ver core/ofertas.py)
e RECALCULA (do zero, MIN/MAX agregado sobre as ofertas atuais do produto --
nao incrementalmente, para poder tambem DIMINUIR um maximo que so existia por
causa do preco antigo, mais caro) PRODUTO.VR_PRECO_MINIMO/MAXIMO dos produtos
afetados. Mexe em dado JA PUBLICADO -- roda so com --dry-run ate confirmar.

Uso:
    .venv/Scripts/python.exe backfill_recorrencia.py --dry-run
    .venv/Scripts/python.exe backfill_recorrencia.py --aplicar
    .venv/Scripts/python.exe backfill_recorrencia.py --aplicar --tambem-preco
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB

SQL_FILA_CONTAGEM = """
    SELECT
      COUNT(*) total,
      SUM(CASE WHEN VR_PRECO_RECORRENCIA_INTEIRO IS NOT NULL THEN 1 ELSE 0 END) com_recorrencia,
      SUM(CASE WHEN NVL(ST_RECORRENCIA, -1) !=
               (CASE WHEN VR_PRECO_RECORRENCIA_INTEIRO IS NOT NULL THEN 1 ELSE 0 END) THEN 1 ELSE 0 END) pendentes
    FROM OFERTA_FILA_CAPTURA
    WHERE ST_CAPTURA = '1'
"""

SQL_FILA_UPDATE = """
    UPDATE OFERTA_FILA_CAPTURA
    SET VR_RECORRENCIA = CASE WHEN VR_PRECO_RECORRENCIA_INTEIRO IS NOT NULL
                               THEN VR_PRECO_RECORRENCIA_INTEIRO + NVL(VR_PRECO_RECORRENCIA_FRACAO, 0) / 100
                               ELSE NULL END,
        ST_RECORRENCIA = CASE WHEN VR_PRECO_RECORRENCIA_INTEIRO IS NOT NULL THEN 1 ELSE 0 END
    WHERE ST_CAPTURA = '1'
"""

SQL_OFERTA_CONTAGEM = """
    SELECT COUNT(*) FROM OFERTA o
    WHERE EXISTS (SELECT 1 FROM OFERTA_FILA_CAPTURA f WHERE f.ID_OFERTA = o.ID_OFERTA)
"""

SQL_OFERTA_UPDATE = """
    UPDATE OFERTA o
    SET (VR_RECORRENCIA, ST_RECORRENCIA, QT_MINIMA_RECORRENCIA) = (
      SELECT f.VR_RECORRENCIA, f.ST_RECORRENCIA, f.QT_MINIMA_RECORRENCIA
      FROM OFERTA_FILA_CAPTURA f WHERE f.ID_OFERTA = o.ID_OFERTA
    )
    WHERE EXISTS (SELECT 1 FROM OFERTA_FILA_CAPTURA f WHERE f.ID_OFERTA = o.ID_OFERTA)
"""

SQL_CANDIDATOS_PRECO = """
    SELECT ID_OFERTA, ID_PRODUTO, VL_PRECO_POR, VR_RECORRENCIA
    FROM OFERTA
    WHERE ST_RECORRENCIA = 1 AND VR_RECORRENCIA > 0
      AND (VL_PRECO_POR IS NULL OR VR_RECORRENCIA < VL_PRECO_POR)
    ORDER BY ID_OFERTA
"""


def _fase1(db, aplicar):
    cur = db._conn.cursor()
    try:
        cur.execute(SQL_FILA_CONTAGEM)
        total, com_recorrencia, pendentes = cur.fetchone()
        print(f'OFERTA_FILA_CAPTURA (ST_CAPTURA=1): {total} linha(s), '
              f'{com_recorrencia} com recorrencia capturada, {pendentes} com '
              f'VR_RECORRENCIA/ST_RECORRENCIA a atualizar.')
        if aplicar and pendentes:
            cur.execute(SQL_FILA_UPDATE)
            print(f'  -> {cur.rowcount} linha(s) atualizada(s) em OFERTA_FILA_CAPTURA.')
            db._conn.commit()

        cur.execute(SQL_OFERTA_CONTAGEM)
        (total_oferta,) = cur.fetchone()
        print(f'OFERTA publicada (com par na fila): {total_oferta} linha(s).')
        if aplicar and total_oferta:
            cur.execute(SQL_OFERTA_UPDATE)
            print(f'  -> {cur.rowcount} linha(s) atualizada(s) em OFERTA.')
            db._conn.commit()
    finally:
        cur.close()


def _fase2(db, aplicar, limite):
    cur = db._conn.cursor()
    try:
        cur.execute(SQL_CANDIDATOS_PRECO)
        nomes = [d[0] for d in cur.description]
        linhas = [dict(zip(nomes, linha)) for linha in cur]
    finally:
        cur.close()

    if limite and limite > 0:
        linhas = linhas[:limite]

    print(f'\n{len(linhas)} oferta(s) onde VR_RECORRENCIA < VL_PRECO_POR publicado '
          f'(preco cairia com a regra 2).')
    if not linhas:
        return

    produtos_afetados = set()
    for linha in linhas:
        antes = linha['VL_PRECO_POR']
        depois = linha['VR_RECORRENCIA']
        print(f"[oferta {linha['ID_OFERTA']}] produto {linha['ID_PRODUTO']}: "
              f"VL_PRECO_POR {antes} -> {depois}"
              + ('' if aplicar else ' (dry-run)'))
        produtos_afetados.add(linha['ID_PRODUTO'])
        if aplicar:
            cur = db._conn.cursor()
            try:
                cur.execute(
                    'UPDATE OFERTA SET VL_PRECO_POR = :novo WHERE ID_OFERTA = :id',
                    {'novo': depois, 'id': linha['ID_OFERTA']},
                )
            finally:
                cur.close()

    if not aplicar:
        print(f'\n[--dry-run] {len(produtos_afetados)} produto(s) teriam '
              f'VR_PRECO_MINIMO/MAXIMO recalculados do zero.')
        return

    db._conn.commit()

    print(f'\nRecalculando VR_PRECO_MINIMO/MAXIMO do zero para '
          f'{len(produtos_afetados)} produto(s) afetado(s)...')
    cur = db._conn.cursor()
    try:
        for id_produto in sorted(produtos_afetados):
            cur.execute(
                'SELECT MIN(VL_PRECO_POR), MAX(VL_PRECO_POR) FROM OFERTA '
                'WHERE ID_PRODUTO = :id AND VL_PRECO_POR IS NOT NULL',
                {'id': id_produto},
            )
            minimo, maximo = cur.fetchone()
            cur.execute(
                'UPDATE PRODUTO SET VR_PRECO_MINIMO = :minimo, VR_PRECO_MAXIMO = :maximo '
                'WHERE ID_PRODUTO = :id',
                {'minimo': minimo, 'maximo': maximo, 'id': id_produto},
            )
            print(f'  produto {id_produto}: VR_PRECO_MINIMO={minimo} VR_PRECO_MAXIMO={maximo}')
        db._conn.commit()
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='So mostra o que seria feito (padrao).')
    ap.add_argument('--aplicar', action='store_true', help='Grava de verdade.')
    ap.add_argument('--tambem-preco', action='store_true',
                     help='Fase 2: tambem corrige VL_PRECO_POR (OFERTA) e VR_PRECO_MINIMO/'
                          'MAXIMO (PRODUTO) onde a recorrencia e menor que o preco publicado.')
    ap.add_argument('--limite', type=int, default=0,
                     help='Fase 2: processa no maximo N ofertas candidatas (0 = todas).')
    args = ap.parse_args()
    aplicar = args.aplicar and not args.dry_run

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    print('=== Fase 1: VR_RECORRENCIA / ST_RECORRENCIA / QT_MINIMA_RECORRENCIA ===')
    _fase1(db, aplicar)

    if args.tambem_preco:
        print('\n=== Fase 2: VL_PRECO_POR (OFERTA) + VR_PRECO_MINIMO/MAXIMO (PRODUTO) ===')
        _fase2(db, aplicar, args.limite)

    if not aplicar:
        print('\n[--dry-run] nada foi gravado. Rode com --aplicar para gravar de verdade.')

    db.desconectar()


if __name__ == '__main__':
    main()
