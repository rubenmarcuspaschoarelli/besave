"""
Cadastro consolidado de produtos (BESAVE.PRODUTO) a partir das ofertas ja
capturadas em OFERTA_FILA_CAPTURA (ST_CAPTURA='1'). Script SEPARADO do
main.py -- so serve para o BACKFILL do historico (linhas capturadas antes de
2026-09-02, quando o cadastro passou a rodar dentro do proprio main.py logo
apos cada captura bem-sucedida). Nao ha mais motivo para uso continuo, mas
continua idempotente/retomavel se sobrar alguma linha p/ qualquer motivo
(ex.: falha pontual do cadastro dentro do main.py -- ver core/produtos.py).

Usa a mesma logica de main.py (core/produtos.cadastrar_produto): so muda a
FONTE das linhas (aqui, uma consulta em lote em vez de 1 linha por vez logo
apos a captura).

Uso:
    .venv/Scripts/python.exe cadastrar_produtos.py --dry-run          # so mostra o que seria feito
    .venv/Scripts/python.exe cadastrar_produtos.py --limite 50        # processa so 50 (teste)
    .venv/Scripts/python.exe cadastrar_produtos.py                    # processa tudo
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB
from core.produto_extrator import extrair_atributos, resolver_titulo
from core.produtos import cadastrar_produto, clob_para_texto


def _ler_pendentes(db, limite):
    cur = db._conn.cursor()
    cols = ', '.join(['ID_OFERTA'] + OracleDB.COLUNAS_PARA_PRODUTO)
    sql = (f"SELECT {cols} FROM OFERTA_FILA_CAPTURA "
           f"WHERE ST_CAPTURA = '1' AND ID_PRODUTO IS NULL ORDER BY ID_OFERTA")
    if limite and limite > 0:
        sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :limite"
    try:
        cur.execute(sql, {'limite': limite} if limite and limite > 0 else {})
        nomes = [d[0] for d in cur.description]
        return [dict(zip(nomes, linha)) for linha in cur]
    finally:
        cur.close()


def _processar_linha(linha, dry_run):
    if not dry_run:
        return None
    # --dry-run: so mostra titulo + atributos extraidos, sem chamar a SP.
    titulo = resolver_titulo(linha.get('DS_TITULO'), linha.get('DS_OFERTA'))
    if not titulo:
        print(f'[oferta {linha["ID_OFERTA"]}] sem titulo -- pulando.')
        return None
    extraidos = extrair_atributos(
        clob_para_texto(linha.get('LS_DETALHES_PRODUTO')),
        clob_para_texto(linha.get('LS_DETALHES_TECNICOS')),
        clob_para_texto(linha.get('LS_INFO_ADICIONAIS')),
        clob_para_texto(linha.get('LS_COMPLEMENTO_PRODUTO')),
    )
    print(f'[oferta {linha["ID_OFERTA"]}] titulo={titulo[:70]!r} extraidos={extraidos}')
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                     help='So mostra titulo/atributos extraidos, sem gravar no Oracle.')
    ap.add_argument('--limite', type=int, default=0,
                     help='Processa no maximo N ofertas pendentes (0 = todas).')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    linhas = _ler_pendentes(db, args.limite)
    print(f'{len(linhas)} oferta(s) com ST_CAPTURA=1 e ID_PRODUTO ainda vazio.')

    if not args.dry_run:
        cur = db._conn.cursor()
        cur.execute('SELECT COUNT(*) FROM PRODUTO')
        antes = cur.fetchone()[0]
        cur.close()

    processadas = 0
    for linha in linhas:
        if args.dry_run:
            _processar_linha(linha, dry_run=True)
            continue
        id_produto, _classificacao, erro = cadastrar_produto(db, linha['ID_OFERTA'], linha)
        if id_produto is None:
            print(f'[oferta {linha["ID_OFERTA"]}] {erro}')
            continue
        processadas += 1
        titulo = resolver_titulo(linha.get('DS_TITULO'), linha.get('DS_OFERTA'))
        print(f'[oferta {linha["ID_OFERTA"]}] -> produto {id_produto} | {titulo[:70]!r}')

    if args.dry_run:
        print(f'\n[--dry-run] {len(linhas)} avaliada(s), nada gravado.')
    else:
        cur = db._conn.cursor()
        cur.execute('SELECT COUNT(*) FROM PRODUTO')
        depois = cur.fetchone()[0]
        cur.close()
        print(f'\n{processadas}/{len(linhas)} oferta(s) vinculada(s) a um produto.')
        print(f'PRODUTO: {antes} -> {depois} linha(s) ({depois - antes} produto(s) novo(s), '
              f'{processadas - (depois - antes)} atualizacao(oes) de produto existente).')

    db.desconectar()


if __name__ == '__main__':
    main()
