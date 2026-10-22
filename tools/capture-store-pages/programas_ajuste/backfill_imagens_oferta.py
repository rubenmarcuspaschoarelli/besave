"""
Backfill de imagens de OFERTA no bucket do site (s3/ofertas/img) -- ver
DOCS/ESPEC_CONVERSAO_IMAGEM_S3_OFERTAS.md e core/imagens_oferta.py.

Para toda oferta JA CAPTURADA (ST_CAPTURA='1') cujo GRUPO de origem
(DS_ORIGEM) esteja marcado com "usa_imagem_loja": true em conf/config.json ->
"grupos" (ou nos grupos passados em --origem), substitui a imagem original
(enviada no WhatsApp) pela 1a foto capturada na pagina do produto
(destino/img/<ID_OFERTA>/, ja com marca d'agua) -- SOBRESCREVE o que
houver no S3 (decisao D1: a captura mais recente sempre vence). So roda para
quem TEM imagem em disco; sem ela, pula (best-effort, nao e erro -- ~1% do
historico nunca teve foto salva).

Script SEPARADO do main.py -- so LE dado ja gravado e arquivos ja em disco,
nao abre navegador. Puro I/O local (Oracle + Pillow), rapido.

--origem e --id-min/--id-max recortam o lote (virada por grupo, a partir de
um ID): sem eles o alvo e TODO o historico dos grupos marcados, o que
sobrescreve milhares de imagens do WhatsApp -- confira a faixa de IDs que o
script imprime antes de rodar com --aplicar.

Uso:
    .venv/Scripts/python.exe backfill_imagens_oferta.py --dry-run
    .venv/Scripts/python.exe backfill_imagens_oferta.py --limite 20 --raiz "C:\\rascunho"   # teste
    .venv/Scripts/python.exe backfill_imagens_oferta.py --aplicar                            # tudo, S3 real
    # so um grupo, a partir de um ID (virada da diaenoite, 2026-10-19 10:30):
    .venv/Scripts/python.exe backfill_imagens_oferta.py \
        --origem "Achadinhos diaenoite #03" --id-min 37274 --aplicar
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


def _ler_pendentes(db, ds_origens, limite, id_min=0, id_max=0):
    if not ds_origens:
        return []
    cur = db._conn.cursor()
    try:
        marcadores = ', '.join(f':o{i}' for i in range(len(ds_origens)))
        binds = {f'o{i}': nome for i, nome in enumerate(ds_origens)}
        faixa = ''
        if id_min and id_min > 0:
            faixa += ' AND ID_OFERTA >= :id_min'
            binds['id_min'] = id_min
        if id_max and id_max > 0:
            faixa += ' AND ID_OFERTA <= :id_max'
            binds['id_max'] = id_max
        sql = (f"SELECT ID_OFERTA, DS_ORIGEM FROM OFERTA_FILA_CAPTURA "
               f"WHERE ST_CAPTURA = '1' AND DS_ORIGEM IN ({marcadores}){faixa} "
               f"ORDER BY ID_OFERTA")
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
    ap.add_argument('--origem', action='append', metavar='DS_ORIGEM',
                    help='So este grupo (repetivel). Padrao: os grupos marcados '
                         'com usa_imagem_loja=true no config.json.')
    ap.add_argument('--id-min', type=int, default=0,
                    help='So ID_OFERTA >= N (0 = sem minimo).')
    ap.add_argument('--id-max', type=int, default=0,
                    help='So ID_OFERTA <= N (0 = sem maximo).')
    ap.add_argument('--raiz', default=imagens_oferta.S3_OFERTAS_IMG_ROOT,
                    help='Pasta destino (padrao: o S3 real -- use uma pasta de '
                         'rascunho para testar antes).')
    args = ap.parse_args()
    aplicar = args.aplicar and not args.dry_run

    if args.origem:
        ds_origens = args.origem
        print(f'Grupos pedidos em --origem: {ds_origens}')
    else:
        ds_origens = grupos_com_imagem_loja()
        print(f'Grupos marcados com usa_imagem_loja=true: {ds_origens or "nenhum"}')
    if not ds_origens:
        return
    print(f'Faixa de ID_OFERTA: {args.id_min or "sem minimo"} .. {args.id_max or "sem maximo"}')

    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)

    linhas = _ler_pendentes(db, ds_origens, args.limite, args.id_min, args.id_max)
    print(f'{len(linhas)} oferta(s) capturada(s) desses grupos.')
    if linhas:
        print(f'IDs de {linhas[0][0]} a {linhas[-1][0]}.')
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
