"""
Backfill da copia de imagens por produto (`.webp`) no historico -- ver
core/imagens_produto.py e a secao "Copia de imagens por produto em .webp" do
resumo.md. Ate 22/09/2026 essa copia so passou a rodar para capturas NOVAS
(dentro do main.py); as ~22 mil ofertas ja capturadas antes disso nunca
tiveram suas fotos publicadas em
E:\\Work\\besave\\server\\s3\\produtos\\img\\<ID_PRODUTO>\\.

So le do Oracle (ID_OFERTA, ID_PRODUTO das ofertas com ST_CAPTURA='1' e
ID_PRODUTO preenchido) e do DISCO (destino/img/<ID_OFERTA>/, ja capturado).
NAO reabre pagina, NAO grava nada no Oracle -- so copia/converte arquivo.

Um mesmo ID_PRODUTO pode ter varias ofertas historicas (mesmo produto visto
em ofertas diferentes ao longo do tempo). Para reproduzir o que teria
acontecido se essa copia sempre tivesse existido -- a captura mais RECENTE
sobrescreve -- o script agrupa por ID_PRODUTO e usa a maior ID_OFERTA que
tiver fotos no disco (as mais novas sem foto na pasta sao ignoradas, nao
apagam o que uma oferta mais antiga tinha). So 1 conversao por produto, nao
1 por oferta.

Uso:
    python backfill_imagens_produto.py --listar          # so mostra o que faria
    python backfill_imagens_produto.py --limite 20        # ensaio curto (20 produtos)
    python backfill_imagens_produto.py --desde 100         # retomar a partir do ID_PRODUTO 100
    python backfill_imagens_produto.py                     # tudo

Retomavel/idempotente: pode parar (Ctrl+C) e rodar de novo com --desde no
maior ID_PRODUTO impresso -- refazer um produto ja feito so o regrava igual.
"""

import _raiz  # noqa: F401 -- raiz do projeto no sys.path e como cwd
import argparse
import os
import sys

from core.imagens_produto import publicar_imagens_produto
from core.oracle_db import OracleDB
from core.caminhos import IMG_DIR


def _pasta(id_oferta):
    return os.path.join(IMG_DIR, str(id_oferta))


def _tem_imagem_no_disco(id_oferta):
    p = _pasta(id_oferta)
    return os.path.isdir(p) and bool(os.listdir(p))


def _produtos_pendentes(desde):
    """{ID_PRODUTO: [ID_OFERTA, ...]} (ordem crescente), so ofertas com
    ST_CAPTURA='1' e ID_PRODUTO preenchido, ID_PRODUTO >= desde."""
    db = OracleDB()
    if not db.conectar():
        print('Sem conexao com o Oracle.')
        sys.exit(1)
    cur = db._conn.cursor()
    try:
        cur.execute(
            "SELECT ID_PRODUTO, ID_OFERTA FROM OFERTA_FILA_CAPTURA "
            " WHERE ST_CAPTURA = '1' AND ID_PRODUTO IS NOT NULL AND ID_PRODUTO >= :desde "
            " ORDER BY ID_PRODUTO, ID_OFERTA",
            {'desde': int(desde or 0)},
        )
        mapa = {}
        for id_produto, id_oferta in cur:
            mapa.setdefault(int(id_produto), []).append(int(id_oferta))
    finally:
        cur.close()
        db.desconectar()
    return mapa


def _escolher_oferta_com_foto(ids_oferta):
    """A maior ID_OFERTA (mais recente) que tiver fotos no disco. None se
    nenhuma das ofertas deste produto tiver foto."""
    for id_oferta in sorted(ids_oferta, reverse=True):
        if _tem_imagem_no_disco(id_oferta):
            return id_oferta
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--desde', type=int, default=0,
                    help='So produtos com ID_PRODUTO >= este valor (retomada).')
    ap.add_argument('--limite', type=int, default=0,
                    help='Maximo de PRODUTOS a processar (0 = todos).')
    ap.add_argument('--listar', action='store_true',
                    help='So mostra o que seria feito, sem converter nada.')
    args = ap.parse_args()

    mapa = _produtos_pendentes(args.desde)
    produtos = sorted(mapa)
    if args.limite:
        produtos = produtos[:args.limite]
    print(f'{len(produtos)} produto(s) a processar (de {len(mapa)} encontrado(s) no Oracle).')
    if not produtos:
        return

    if args.listar:
        for id_produto in produtos:
            escolhida = _escolher_oferta_com_foto(mapa[id_produto])
            situacao = f'oferta {escolhida}' if escolhida else 'SEM FOTO NO DISCO'
            print(f'  produto {id_produto} | {len(mapa[id_produto])} oferta(s) | {situacao}')
        return

    com_foto = sem_foto = total_imgs = 0
    for n, id_produto in enumerate(produtos, 1):
        id_oferta = _escolher_oferta_com_foto(mapa[id_produto])
        if id_oferta is None:
            sem_foto += 1
            print(f'[{n}/{len(produtos)}] produto {id_produto} | nenhuma das '
                  f'{len(mapa[id_produto])} oferta(s) tem foto no disco -- pulando.')
            continue
        n_imgs = publicar_imagens_produto(id_produto, _pasta(id_oferta))
        if n_imgs:
            com_foto += 1
            total_imgs += n_imgs
            print(f'[{n}/{len(produtos)}] produto {id_produto} <- oferta {id_oferta} | '
                  f'{n_imgs} imagem(ns)')
        else:
            sem_foto += 1
            print(f'[{n}/{len(produtos)}] produto {id_produto} <- oferta {id_oferta} | '
                  f'0 imagem(ns) (conversao falhou -- ver erro acima)')

    print(f'\nFim: {com_foto} produto(s) com foto publicada ({total_imgs} imagem(ns) no '
          f'total), {sem_foto} sem foto. Nada foi gravado no Oracle.')


if __name__ == '__main__':
    main()
