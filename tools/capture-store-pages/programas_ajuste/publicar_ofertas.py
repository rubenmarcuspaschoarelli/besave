"""
Backfill de BESAVE.OFERTA a partir do historico ja capturado em
OFERTA_FILA_CAPTURA (antes de 2026-09-02, quando a publicacao passou a rodar
dentro do proprio main.py logo apos o cadastro do produto). Script SEPARADO
do main.py -- so LE dado ja gravado.

Seleciona ST_CAPTURA='1' AND ID_PRODUTO IS NOT NULL (precisa ter passado pelo
cadastro de produto primeiro -- rodar cadastrar_produtos.py antes se sobrar
alguma linha sem produto) E cuja loja tenha afiliado ATIVO em
BESAVE.LOJA_AFILIADA (core/afiliados.loja_ativa) -- a loja e resolvida a
partir de DS_URL_FINAL (mesma tecnica do backfill_url_besave.py), ja que
OFERTA_FILA_CAPTURA nao guarda o nome da loja.

Idempotente e retomavel: so processa quem ainda nao esta em OFERTA (LEFT JOIN
... IS NULL) -- rodar de novo a qualquer momento e seguro.

Uso:
    .venv/Scripts/python.exe publicar_ofertas.py --dry-run
    .venv/Scripts/python.exe publicar_ofertas.py --limite 50
    .venv/Scripts/python.exe publicar_ofertas.py
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

from core.oracle_db import OracleDB
from core import afiliados, registry
from core.ofertas import publicar_oferta


def _ler_pendentes(db, limite):
    cur = db._conn.cursor()
    cols = ", ".join(['f.ID_OFERTA', 'f.ID_PRODUTO', 'f.DS_URL_FINAL'] +
                      [f'f.{c}' for c in OracleDB.COLUNAS_PARA_OFERTA if c != 'DS_URL_FINAL'])
    sql = (f"SELECT {cols} FROM OFERTA_FILA_CAPTURA f "
           f"LEFT JOIN OFERTA o ON o.ID_OFERTA = f.ID_OFERTA "
           f"WHERE f.ST_CAPTURA = '1' AND f.ID_PRODUTO IS NOT NULL AND o.ID_OFERTA IS NULL "
           f"ORDER BY f.ID_OFERTA")
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
                     help='So mostra quantas linhas seriam publicadas, por loja.')
    ap.add_argument('--limite', type=int, default=0,
                     help='Processa no maximo N ofertas pendentes (0 = todas).')
    args = ap.parse_args()

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)
    afiliados.carregar(db)

    linhas = _ler_pendentes(db, args.limite)
    print(f'{len(linhas)} oferta(s) com produto cadastrado e ainda fora de OFERTA.')

    publicadas = 0
    fora_loja_ativa = 0
    for linha in linhas:
        id_oferta = linha['ID_OFERTA']
        loja = registry.resolver_loja(linha.get('DS_URL_FINAL'))
        if not afiliados.loja_ativa(loja):
            fora_loja_ativa += 1
            continue
        if args.dry_run:
            print(f'[oferta {id_oferta}] loja={loja} -> seria publicada')
            publicadas += 1
            continue
        ok, erro = publicar_oferta(
            db, id_oferta, linha['ID_PRODUTO'], registry.nome_loja(loja), linha)
        if ok:
            publicadas += 1
            print(f'[oferta {id_oferta}] loja={loja} -> publicada')
        else:
            print(f'[oferta {id_oferta}] erro ao publicar: {erro}')

    if args.dry_run:
        print(f'\n[--dry-run] {publicadas} seria(m) publicada(s); '
              f'{fora_loja_ativa} fora (loja sem afiliado ativo); nada gravado.')
    else:
        print(f'\n{publicadas}/{len(linhas)} oferta(s) publicada(s) em OFERTA; '
              f'{fora_loja_ativa} fora (loja sem afiliado ativo).')

    db.desconectar()


if __name__ == '__main__':
    main()
