"""
Preenche ST_ATIVO nas linhas que ja estavam na OFERTA_FILA_CAPTURA quando a
coluna foi criada (2026-07-31) -- elas ficaram NULL.

Classifica pelo MESMO criterio do programa (core.registry.loja_ativa lendo
conf/config.json -> "lojas_ativas"), para nao existir uma segunda regra em SQL
que possa divergir do capturador:
  - loja resolvida pela URL de ORIGEM; se desconhecida, tenta a URL FINAL
    (as paginas-ponte de divulgador so revelam a loja depois de navegar, e a
    DS_URL_FINAL guarda o destino);
  - loja em "lojas_ativas" -> '1'; qualquer outro caso (inclusive loja
    desconhecida) -> '0'.

NAO toca em ST_CAPTURA nem em nenhuma outra coluna, e so mexe onde ST_ATIVO
esta NULL -- rodar de novo depois de uma captura nao desfaz nada.

Alcance: apenas as linhas JA PROCESSADAS (ST_CAPTURA <> '0'). As pendentes
ficam NULL de proposito, porque a loja delas pode so aparecer depois de navegar
(pagina-ponte de divulgador: a origem e um dominio desconhecido e o destino real
so sai do __NEXT_DATA__) -- classifica-las aqui marcaria como inativa uma oferta
que a captura vai descobrir ser da Amazon.

Uso:
    .venv\\Scripts\\python.exe backfill_st_ativo.py            # simulacao
    .venv\\Scripts\\python.exe backfill_st_ativo.py --aplicar  # grava

Desfazer: UPDATE OFERTA_FILA_CAPTURA SET ST_ATIVO = NULL;
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
from collections import Counter

from core import registry
from core.oracle_db import OracleDB, ST_ATIVO_SIM, ST_ATIVO_NAO

SQL_LER = ("SELECT ID_OFERTA, DS_URL_ORIGEM, DS_URL_FINAL FROM OFERTA_FILA_CAPTURA "
           "WHERE ST_ATIVO IS NULL AND ST_CAPTURA <> '0' ORDER BY ID_OFERTA")
SQL_GRAVAR = "UPDATE OFERTA_FILA_CAPTURA SET ST_ATIVO = :st WHERE ID_OFERTA = :id"


def classificar(url_origem, url_final):
    """(st_ativo, loja, url_usada) para uma linha da fila."""
    for url in ((url_origem or '').strip(), (url_final or '').strip()):
        loja = registry.resolver_loja(url) if url else None
        if loja:
            ativo = registry.loja_ativa(loja, url)
            return (ST_ATIVO_SIM if ativo else ST_ATIVO_NAO,
                    registry.nome_loja(loja, url), url)
    return ST_ATIVO_NAO, '(loja desconhecida)', ''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--aplicar', action='store_true',
                    help='grava de fato (sem esta flag e so simulacao)')
    args = ap.parse_args()

    print(f'lojas ativas: {registry.recarregar_lojas_ativas()}')
    db = OracleDB()
    if not db.conectar():
        raise SystemExit(1)
    cur = db._conn.cursor()
    linhas = cur.execute(SQL_LER).fetchall()
    pendentes = cur.execute(
        "SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA "
        "WHERE ST_ATIVO IS NULL AND ST_CAPTURA = '0'").fetchone()[0]
    print(f'{len(linhas)} linhas ja processadas com ST_ATIVO nulo')
    print(f'{pendentes} pendentes ficam NULL (a captura preenche)\n')

    por_loja = Counter()
    atualizacoes = []
    for id_oferta, url_origem, url_final in linhas:
        st, loja, _ = classificar(url_origem, url_final)
        por_loja[(st, loja)] += 1
        atualizacoes.append({'st': st, 'id': int(id_oferta)})

    for (st, loja), qtd in sorted(por_loja.items(), key=lambda kv: (-kv[1], kv[0][1])):
        print(f'  ST_ATIVO={st}  {loja:22s} {qtd:5d}')
    ativas = sum(q for (st, _), q in por_loja.items() if st == ST_ATIVO_SIM)
    print(f'\ntotal: {ativas} ativas / {len(linhas) - ativas} inativas')

    if not args.aplicar:
        print('\n(simulacao -- rode com --aplicar para gravar)')
    else:
        cur.executemany(SQL_GRAVAR, atualizacoes)
        db._conn.commit()
        print(f'\n{cur.rowcount} linhas atualizadas e commitadas.')
    db.desconectar()


if __name__ == '__main__':
    main()
