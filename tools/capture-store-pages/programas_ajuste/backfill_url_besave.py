"""
Backfill de DS_URL_BESAVE para ofertas ja capturadas (ST_CAPTURA='1') ANTES da
funcionalidade existir. Nao reabre o navegador: recalcula a URL a partir da
DS_URL_FINAL ja gravada, usando as mesmas regras de core/afiliados.py.

So mexe em DS_URL_BESAVE (UPDATE direto, sem passar pela stored procedure) --
nenhuma outra coluna e tocada. Roda uma vez; reprocessar e seguro (idempotente,
sempre recalcula a partir da DS_URL_FINAL atual).

Uso:
    .venv/Scripts/python.exe backfill_url_besave.py --dry-run   # so mostra contagens
    .venv/Scripts/python.exe backfill_url_besave.py             # aplica
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB
from core import afiliados, registry

LOTE_COMMIT = 500


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true',
                     help='So mostra quantas linhas seriam atualizadas por loja.')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)
    afiliados.carregar(db)

    cur = db._conn.cursor()
    cur.execute(
        "SELECT ID_OFERTA, DS_URL_FINAL FROM OFERTA_FILA_CAPTURA "
        "WHERE ST_CAPTURA = '1' AND DS_URL_FINAL IS NOT NULL "
        "AND DS_URL_BESAVE IS NULL"
    )
    linhas = cur.fetchall()
    print(f'{len(linhas)} linha(s) com ST_CAPTURA=1, DS_URL_FINAL preenchida e '
          f'DS_URL_BESAVE ainda vazia.')

    por_loja = {}
    atualiza = cur.connection.cursor()
    pendentes = 0
    for id_oferta, url_final in linhas:
        loja = registry.resolver_loja(url_final)
        url_besave = afiliados.gerar_url(loja, url_final) if loja else None
        chave = loja or '(sem loja/afiliado)'
        por_loja[chave] = por_loja.get(chave, 0) + (1 if url_besave else 0)
        if url_besave and not args.dry_run:
            atualiza.execute(
                "UPDATE OFERTA_FILA_CAPTURA SET DS_URL_BESAVE = :url "
                "WHERE ID_OFERTA = :id",
                {'url': url_besave, 'id': id_oferta},
            )
            pendentes += 1
            if pendentes % LOTE_COMMIT == 0:
                db._conn.commit()
                print(f'  ...{pendentes} gravada(s).')

    if not args.dry_run:
        db._conn.commit()

    print('\nPor loja (linhas com url_besave gerada):')
    for loja, qtd in sorted(por_loja.items(), key=lambda x: -x[1]):
        print(f'  {loja}: {qtd}')
    if args.dry_run:
        print('\n[--dry-run] nada foi gravado.')
    else:
        print(f'\n{pendentes} linha(s) gravada(s) em DS_URL_BESAVE.')

    atualiza.close()
    cur.close()
    db.desconectar()


if __name__ == '__main__':
    main()
