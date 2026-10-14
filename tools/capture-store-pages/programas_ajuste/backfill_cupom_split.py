"""
Corrige, no historico, os cupons gravados ERRADOS antes da mudanca de
2026-09-28 em core/cupons.py: quando a origem manda mais de 1 codigo no
mesmo campo unidos por " | " (ex.: "MODA2309 | LOJASOFICIAIS"), o codigo
inteiro (com o "|") tinha sido gravado como se fosse 1 unico CUPOM.

Para cada linha de BESAVE.CUPOM com "|" no CUPOM: separa em N codigos, faz
find-or-create (STR_CUPOM_UPSERT) de cada um com a MESMA DS_CUPOM/DS_LOJA/
ID_ULT_OFERTA da linha antiga, e por fim APAGA a linha antiga (errada).

ATENCAO: alguns desses valores ja chegam TRUNCADOS na origem -- a coluna
OFERTA_FILA_CAPTURA.DS_CUPOM e VARCHAR2(30 BYTE) e varias amostras batem
exatamente nesse limite (ex. "CUPONSAUTO | CONSTRUIRML | USA", o ultimo
codigo cortado no meio). Nao ha como recuperar o texto perdido aqui -- o
corte aconteceu antes deste programa ver o dado. O script separa o que
sobrou mesmo assim.

Idempotente: se rodar de novo, as linhas antigas com "|" ja terao sido
apagadas na rodada anterior (nada a fazer).

Uso:
    .venv/Scripts/python.exe backfill_cupom_split.py --dry-run
    .venv/Scripts/python.exe backfill_cupom_split.py --aplicar
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import sys

import oracledb

from core.oracle_db import OracleDB


def _ler_cupons_com_pipe(db):
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT ID_CUPOM, CUPOM, DS_CUPOM, DS_LOJA, ID_ULT_OFERTA FROM CUPOM "
            "WHERE CUPOM LIKE '%|%' ORDER BY ID_CUPOM"
        )
        nomes = [d[0] for d in cur.description]
        return [dict(zip(nomes, linha)) for linha in cur]
    finally:
        cur.close()


def _upsert_codigo(db, codigo, ds_cupom, ds_loja, id_ult_oferta):
    out = db.executar_stored_procedure(
        'STR_CUPOM_UPSERT',
        {'P_CUPOM': codigo, 'P_DS_CUPOM': ds_cupom, 'P_DS_LOJA': ds_loja,
         'P_ID_ULT_OFERTA': id_ult_oferta},
        {'P_ID_CUPOM': oracledb.DB_TYPE_NUMBER,
         'PV_RETORNO': oracledb.DB_TYPE_VARCHAR,
         'PV_ERRO': oracledb.DB_TYPE_VARCHAR},
    )
    ok = (out.get('PV_RETORNO') or '').upper() == 'TRUE'
    return (out.get('P_ID_CUPOM'), None) if ok else (None, out.get('PV_ERRO'))


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

    linhas = _ler_cupons_com_pipe(db)
    print(f'{len(linhas)} linha(s) de CUPOM com "|" no CUPOM (gravadas erradas antes da correcao).')

    for linha in linhas:
        codigos = [c.strip() for c in linha['CUPOM'].split('|') if c.strip()]
        print(f"\n[cupom {linha['ID_CUPOM']}] {linha['CUPOM']!r} (loja={linha['DS_LOJA']!r}) "
              f"-> {len(codigos)} codigo(s): {codigos}")
        if not aplicar:
            continue

        novos_ids = []
        erro_algum = None
        for codigo in codigos:
            novo_id, erro = _upsert_codigo(
                db, codigo, linha['DS_CUPOM'], linha['DS_LOJA'], linha['ID_ULT_OFERTA'])
            if erro:
                erro_algum = erro
                break
            novos_ids.append(novo_id)
        if erro_algum:
            db._conn.rollback()
            print(f'  ERRO: {erro_algum} -- linha antiga NAO apagada.')
            continue

        cur = db._conn.cursor()
        cur.execute('DELETE FROM CUPOM WHERE ID_CUPOM = :id', {'id': linha['ID_CUPOM']})
        db._conn.commit()
        cur.close()
        print(f'  -> id_cupom novo(s) {novos_ids}; linha antiga {linha["ID_CUPOM"]} apagada.')

    if not aplicar:
        print('\n[--dry-run] nada foi gravado. Rode com --aplicar para gravar de verdade.')

    db.desconectar()


if __name__ == '__main__':
    main()
