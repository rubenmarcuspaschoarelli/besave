"""
Backfill de imagens de OFERTA no bucket do site (s3/ofertas/img) -- ver
DOCS/ESPEC_CONVERSAO_IMAGEM_S3_OFERTAS.md e core/imagens_oferta.py.

Para toda oferta JA CAPTURADA (ST_CAPTURA='1') cujo GRUPO de origem
(DS_ORIGEM) esteja marcado com "usa_imagem_loja": true em conf/config.json ->
"grupos", substitui a imagem original (enviada no WhatsApp) pela 1a foto
capturada na pagina do produto (destino/img/<ID_OFERTA>/, ja com marca
d'agua) -- SOBRESCREVE o que houver no S3 (decisao D1: a captura mais
recente sempre vence). So roda para quem TEM imagem em disco; sem ela,
pula (best-effort, nao e erro -- ~1% do historico nunca teve foto salva).

Script SEPARADO do main.py -- so LE dado ja gravado e arquivos ja em disco,
nao abre navegador. Puro I/O local (Oracle + Pillow), rapido.

Uso:
    .venv/Scripts/python.exe backfill_imagens_oferta.py --dry-run
    .venv/Scripts/python.exe backfill_imagens_oferta.py --limite 20 --raiz "C:\\rascunho"   # teste
    .venv/Scripts/python.exe backfill_imagens_oferta.py --aplicar                            # tudo, S3 real
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys

from core import imagens_oferta
from core.estado import grupos_com_imagem_loja
from core.oracle_db import OracleDB
from core.caminhos import IMG_DIR

DESTINO_ORIGEM = IMG_DIR


def _ler_pendentes(db, ds_origens, limite):
    if not ds_origens:
        return []
    cur = db._conn.cursor()
    try:
        marcadores = ', '.join(f':o{i}' for i in range(len(ds_origens)))
        binds = {f'o{i}': nome for i, nome in enumerate(ds_origens)}
        sql = (f"SELECT ID_OFERTA, DS_ORIGEM FROM OFERTA_FILA_CAPTURA "
               f"WHERE ST_CAPTURA = '1' AND DS_ORIGEM IN ({marcadores}) ORDER BY ID_OFERTA")
        if limite and limite > 0:
            sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :limite"
            binds['limite'] = limite
        cur.execute(sql, binds)
        return cur.fetchall()
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', help='So mostra o que seria feito (padrao).')
    ap.add_argument('--aplicar', action='store_true', help='Grava de verdade.')
    ap.add_argument('--limite', type=int, default=0, help='No maximo N ofertas (0 = todas).')
    ap.add_argument('--raiz', default=imagens_oferta.S3_OFERTAS_IMG_ROOT,
                    help='Pasta destino (padrao: o S3 real -- use uma pasta de '
                         'rascunho para testar antes).')
    args = ap.parse_args()
    aplicar = args.aplicar and not args.dry_run

    ds_origens = grupos_com_imagem_loja()
    print(f'Grupos marcados com usa_imagem_loja=true: {ds_origens or "nenhum"}')
    if not ds_origens:
        return

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    linhas = _ler_pendentes(db, ds_origens, args.limite)
    print(f'{len(linhas)} oferta(s) capturada(s) desses grupos.')
    print(f'Destino: {args.raiz}\n')

    publicadas = sem_imagem = falhas = 0
    for id_oferta, ds_origem in linhas:
        pasta_origem = os.path.join(DESTINO_ORIGEM, str(id_oferta))
        origem = imagens_oferta.primeira_imagem(pasta_origem)
        if not origem:
            sem_imagem += 1
            continue
        if not aplicar:
            publicadas += 1
            continue
        try:
            pasta = imagens_oferta.publicar_imagem_oferta(id_oferta, origem, raiz=args.raiz)
            if pasta:
                publicadas += 1
                print(f'[oferta {id_oferta}] {os.path.basename(origem)} -> {pasta}')
            else:
                falhas += 1
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f'[oferta {id_oferta}] ERRO: {type(e).__name__}: {e}')

    print(f'\n{publicadas} publicada(s), {sem_imagem} sem imagem em disco (pulada(s)), '
          f'{falhas} falha(s), de {len(linhas)} oferta(s).')
    if not aplicar:
        print('[--dry-run] nada foi gravado. Rode com --aplicar para gravar de verdade.')

    db.desconectar()


if __name__ == '__main__':
    main()
