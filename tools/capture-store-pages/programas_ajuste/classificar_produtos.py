"""
Backfill de classificacao (BESAVE.PRODUTO.DS_COMUNIDADE/DS_PUBLICO +
PRODUTO_COMUNIDADE/PRODUTO_PUBLICO) para produtos cadastrados ANTES de
2026-09-04, quando core.produtos.cadastrar_produto passou a classificar
junto do cadastro (ver core/classificador.py). Roda DIRETO em cima de
BESAVE.PRODUTO -- LS_CATEGORIA/DS_CATEGORIA_RANKING/DS_PRODUTO ja estao
consolidados ali, nao precisa voltar em OFERTA_FILA_CAPTURA. Idempotente/
retomavel: filtra DS_COMUNIDADE IS NULL, sem ponteiro.

Uso:
    .venv/Scripts/python.exe classificar_produtos.py --dry-run          # so mostra o que seria feito
    .venv/Scripts/python.exe classificar_produtos.py --limite 50        # processa so 50 (teste)
    .venv/Scripts/python.exe classificar_produtos.py                    # processa tudo
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.classificador import classificar
from core.oracle_db import OracleDB
from core.produtos import clob_para_texto, gravar_classificacao


def _ler_pendentes(db, limite):
    cur = db._conn.cursor()
    sql = ('SELECT ID_PRODUTO, DS_PRODUTO, LS_CATEGORIA, DS_CATEGORIA_RANKING '
           'FROM BESAVE.PRODUTO WHERE DS_COMUNIDADE IS NULL ORDER BY ID_PRODUTO')
    if limite and limite > 0:
        sql = f'SELECT * FROM ({sql}) WHERE ROWNUM <= :limite'
    try:
        cur.execute(sql, {'limite': limite} if limite and limite > 0 else {})
        return cur.fetchall()
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                     help='So mostra a classificacao calculada, sem gravar no Oracle.')
    ap.add_argument('--limite', type=int, default=0,
                     help='Processa no maximo N produtos pendentes (0 = todos).')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    linhas = _ler_pendentes(db, args.limite)
    print(f'{len(linhas)} produto(s) com DS_COMUNIDADE ainda vazio.')

    sem_match = 0
    processados = 0
    cur = db._conn.cursor()
    try:
        for id_produto, titulo, ls_categoria_clob, ranking in linhas:
            ls_categoria = clob_para_texto(ls_categoria_clob)
            comunidades, publico = classificar(ls_categoria, titulo, ranking)
            principal = comunidades[0][0] if comunidades else None
            if not comunidades:
                sem_match += 1

            if args.dry_run:
                print(f'[produto {id_produto}] comunidade={principal!r} publico={publico!r} '
                      f'todas={comunidades} titulo={(titulo or "")[:60]!r}')
                continue

            cur.execute(
                'UPDATE BESAVE.PRODUTO SET DS_COMUNIDADE = :c, DS_PUBLICO = :p WHERE ID_PRODUTO = :id',
                {'c': principal, 'p': publico, 'id': id_produto},
            )
            db._conn.commit()
            gravar_classificacao(db, id_produto, comunidades, publico)
            processados += 1
            if processados % 500 == 0:
                print(f'... {processados}/{len(linhas)}')
    finally:
        cur.close()

    if args.dry_run:
        print(f'\n[--dry-run] {len(linhas)} avaliado(s), nada gravado. '
              f'Sem nenhuma comunidade: {sem_match}.')
    else:
        print(f'\n{processados}/{len(linhas)} produto(s) classificado(s). '
              f'Sem nenhuma comunidade: {sem_match}.')

    db.desconectar()


if __name__ == '__main__':
    main()
