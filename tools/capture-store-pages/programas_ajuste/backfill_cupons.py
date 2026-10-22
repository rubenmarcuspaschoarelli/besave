"""
Backfill de BESAVE.CUPOM a partir do historico ja capturado em
OFERTA_FILA_CAPTURA (linhas de antes de 2026-09-06, quando o cadastro passou
a rodar dentro do proprio main.py logo apos cada captura bem-sucedida).
Script SEPARADO do main.py -- so LE dado ja gravado.

Seleciona ST_CAPTURA='1' AND DS_CUPOM IS NOT NULL. Idempotente: pode rodar de
novo a qualquer momento -- STR_CUPOM_UPSERT acha-ou-atualiza pela chave
(CUPOM, DS_LOJA), nunca duplica.

Uso:
    .venv/Scripts/python.exe backfill_cupons.py --dry-run          # so mostra o que seria feito
    .venv/Scripts/python.exe backfill_cupons.py --limite 50        # processa so 50 (teste)
    .venv/Scripts/python.exe backfill_cupons.py                    # processa tudo
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core import registry
from core.cupons import publicar_cupom
from core.oracle_db import OracleDB


def _ler_pendentes(db, limite):
    cur = db._conn.cursor()
    cols = ", ".join(['DS_URL_FINAL'] + OracleDB.COLUNAS_PARA_CUPOM)
    sql = (f"SELECT {cols} FROM OFERTA_FILA_CAPTURA "
           f"WHERE ST_CAPTURA = '1' AND DS_CUPOM IS NOT NULL ORDER BY ID_OFERTA")
    if limite and limite > 0:
        sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :limite"
    try:
        cur.execute(sql, {'limite': limite} if limite and limite > 0 else {})
        nomes = [d[0] for d in cur.description]
        return [dict(zip(nomes, linha)) for linha in cur]
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                     help='So mostra quantos cupons seriam gravados, sem chamar a SP.')
    ap.add_argument('--limite', type=int, default=0,
                     help='Processa no maximo N ofertas pendentes (0 = todas).')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    linhas = _ler_pendentes(db, args.limite)
    print(f'{len(linhas)} oferta(s) com ST_CAPTURA=1 e DS_CUPOM preenchido.')

    if not args.dry_run:
        cur = db._conn.cursor()
        cur.execute('SELECT COUNT(*) FROM CUPOM')
        antes = cur.fetchone()[0]
        cur.close()

    processadas = 0
    total_codigos = 0
    for linha in linhas:
        id_oferta = linha['ID_OFERTA']
        if args.dry_run:
            loja = linha.get('DS_CUPOM_LOJA') or registry.nome_loja(
                registry.resolver_loja(linha.get('DS_URL_FINAL')))
            print(f'[oferta {id_oferta}] cupom={linha.get("DS_CUPOM")!r} loja={loja!r} -> seria gravado')
            processadas += 1
            continue
        loja_fallback = registry.nome_loja(registry.resolver_loja(linha.get('DS_URL_FINAL')))
        ids_cupom, erro = publicar_cupom(db, linha, loja_fallback)
        if ids_cupom:
            processadas += 1
            total_codigos += len(ids_cupom)
            print(f'[oferta {id_oferta}] cupom={linha.get("DS_CUPOM")!r} -> id_cupom {ids_cupom}')
        elif erro:
            print(f'[oferta {id_oferta}] erro ao publicar cupom: {erro}')

    if args.dry_run:
        print(f'\n[--dry-run] {processadas}/{len(linhas)} avaliada(s), nada gravado.')
    else:
        cur = db._conn.cursor()
        cur.execute('SELECT COUNT(*) FROM CUPOM')
        depois = cur.fetchone()[0]
        cur.close()
        print(f'\n{processadas}/{len(linhas)} oferta(s) processada(s), {total_codigos} codigo(s) '
              f'de cupom no total (>1 por oferta quando DS_CUPOM tinha "|").')
        print(f'CUPOM: {antes} -> {depois} linha(s) ({depois - antes} cupom(ns) novo(s), '
              f'{total_codigos - (depois - antes)} atualizacao(oes) de cupom existente).')

    db.desconectar()


if __name__ == '__main__':
    main()
