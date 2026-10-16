"""
Publica as fotos de UMA oferta ja capturada (destino/img/<ID_OFERTA>/) na pasta
do PRODUTO correspondente, convertidas para .webp:

    E:\\Work\\besave\\server\\s3\\produtos\\img\\<ID_PRODUTO>\\<ID_PRODUTO>_<seq>.webp

O original capturado (destino/img/<ID_OFERTA>/img_N.<ext>, com a marca d'agua
ja aplicada -- ver core/images.py) NUNCA e alterado ou removido; isto so LE de
la e GRAVA uma copia convertida em outro lugar. Se o produto ja tinha fotos
publicadas (outra oferta da mesma familia capturada antes), a pasta e
esvaziada primeiro -- a captura mais recente sempre vence.

Chamado por main.py logo apos o cadastro do produto (core/produtos.py) dar
ID_PRODUTO, best-effort: falha aqui nunca derruba a captura, que ja foi
gravada com sucesso.
"""

import os
import re

try:
    from PIL import Image
except Exception:  # noqa: BLE001 - sem Pillow -> nao publica, so avisa
    Image = None

from core.estado import ler_raiz_s3

# conf/config.json -> s3.raiz (padrao E:\Work\besave\server\s3)
S3_PRODUTOS_IMG_ROOT = os.path.join(ler_raiz_s3(), 'produtos', 'img')

QUALIDADE_WEBP = 90

_NUM_RE = re.compile(r'(\d+)')


def _chave_ordem(nome):
    # 'img_2.jpg' antes de 'img_10.jpg' -- ordem numerica, nao alfabetica.
    m = _NUM_RE.search(nome)
    return (int(m.group(1)) if m else 0, nome)


def _limpar_pasta(pasta):
    for antigo in os.listdir(pasta):
        caminho = os.path.join(pasta, antigo)
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
        except OSError as e:
            print(f'[imagens_produto] falha ao remover {caminho}: {e}')


def publicar_imagens_produto(id_produto, pasta_origem):
    """Converte e copia as imagens de `pasta_origem` (destino/img/<ID_OFERTA>)
    para a pasta do produto no S3, sobrepondo o que houver la. Devolve o
    numero de imagens publicadas (0 se nao houver nada a fazer ou em erro)."""
    if not id_produto or not pasta_origem or not os.path.isdir(pasta_origem):
        return 0
    if Image is None:
        print('[imagens_produto] Pillow indisponivel -- imagens do produto nao publicadas.')
        return 0

    arquivos = sorted(
        (f for f in os.listdir(pasta_origem)
         if os.path.isfile(os.path.join(pasta_origem, f))),
        key=_chave_ordem,
    )
    if not arquivos:
        return 0

    pasta_destino = os.path.join(S3_PRODUTOS_IMG_ROOT, str(id_produto))
    if os.path.isdir(pasta_destino):
        _limpar_pasta(pasta_destino)
    else:
        os.makedirs(pasta_destino, exist_ok=True)

    publicadas = 0
    for i, nome in enumerate(arquivos, start=1):
        origem = os.path.join(pasta_origem, nome)
        alvo = os.path.join(pasta_destino, f'{id_produto}_{i}.webp')
        try:
            with Image.open(origem) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')
                # Sem resize: o .webp sai na MESMA resolucao do original.
                img.save(alvo, 'WEBP', quality=QUALIDADE_WEBP)
            publicadas += 1
        except Exception as e:  # noqa: BLE001
            print(f'[imagens_produto] falha ao converter {origem}: {e}')
    return publicadas
