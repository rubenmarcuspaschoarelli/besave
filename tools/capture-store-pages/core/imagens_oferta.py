"""
Publica a imagem de UMA oferta no bucket do site (BESAVE.OFERTA, s3/ofertas/img),
no MESMO padrao do AgenteCapturaWhatsapp (wa/storage.py) -- ver especificacao
em DOCS/ESPEC_CONVERSAO_IMAGEM_S3_OFERTAS.md (2026-09-28):

    <destino>\\<ID_OFERTA>\\<ID_OFERTA>.webp        principal, ate 480x480 (fundo branco), <= 200 KB
    <destino>\\<ID_OFERTA>\\<ID_OFERTA>-small.webp  miniatura, maior lado 200, sem preencher

So roda para ofertas cujo GRUPO de origem (OFERTA_FILA_CAPTURA.DS_ORIGEM) esta
marcado com "usa_imagem_loja" em conf/config.json -> "grupos" (ver
core/estado.usa_imagem_loja) -- decisao POR GRUPO do WhatsApp, nao por loja:
so os grupos marcados tem a foto original (enviada no WhatsApp) substituida
pela foto capturada na pagina do produto. Usa so a 1a foto da oferta
(`primeira_imagem`); a origem (destino/img/<ID_OFERTA>/, com marca d'agua)
nunca e alterada. SOBRESCREVE o que houver no S3 -- a captura mais recente
sempre vence (decisao D1 da especificacao).
"""

import io
import os
import re
from pathlib import Path

try:
    from PIL import Image
except Exception:  # noqa: BLE001 - sem Pillow -> nao publica, so avisa
    Image = None

from core.estado import ler_raiz_s3

# conf/config.json -> s3.raiz (padrao E:\Work\besave\server\s3)
S3_OFERTAS_IMG_ROOT = os.path.join(ler_raiz_s3(), 'ofertas', 'img')
MAX_PX = 480
MAX_BYTES = 200 * 1024
QUALIDADE = 90
QUALIDADE_MIN = 60
THUMB_MAX_PX = 200
THUMB_QUALIDADE = 80

_NUM_RE = re.compile(r'(\d+)')


def _chave_ordem(nome):
    # 'img_2.webp' antes de 'img_10.webp' -- ordem numerica, nao alfabetica.
    m = _NUM_RE.search(nome)
    return (int(m.group(1)) if m else 0, nome)


_EXT_VIDEO = {'mp4', 'webm', 'mov', 'm4v', 'avi', 'mkv', 'm3u8', 'ts'}


def _e_foto(caminho):
    """Arquivo que o Pillow abre como imagem PARADA (video e GIF animado nao)."""
    if caminho.rsplit('.', 1)[-1].lower() in _EXT_VIDEO or Image is None:
        return False
    try:
        with Image.open(caminho) as im:
            return getattr(im, 'n_frames', 1) <= 1
    except Exception:  # noqa: BLE001
        return False


def primeira_imagem(pasta_origem):
    """1a FOTO (ordem numerica) de destino/img/<ID_OFERTA>/, ou '' se a pasta
    nao existir ou nao tiver nenhuma. Pula o que nao for foto parada (video,
    GIF animado, arquivo que nao abre) e tenta a 2a, a 3a... (2026-10-08)."""
    if not pasta_origem or not os.path.isdir(pasta_origem):
        return ''
    arquivos = sorted(
        (f for f in os.listdir(pasta_origem)
         if os.path.isfile(os.path.join(pasta_origem, f))),
        key=_chave_ordem,
    )
    for f in arquivos:
        caminho = os.path.join(pasta_origem, f)
        if _e_foto(caminho):
            return caminho
    return ''


def tem_imagem_publicada(id_oferta, raiz=S3_OFERTAS_IMG_ROOT):
    """O site ja tem imagem para esta oferta (<raiz>/<id>/<id>.webp)?"""
    return os.path.isfile(os.path.join(raiz, str(id_oferta), f'{id_oferta}.webp'))


def _webp_principal(im, qualidade=QUALIDADE, max_px=MAX_PX, max_bytes=MAX_BYTES):
    """> max_px: reduz + completa com branco ate max_px x max_px (centralizado).
    <= max_px: mantem a resolucao original. Garante <= max_bytes."""
    im = im.convert('RGB')
    if max(im.size) > max_px:
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        if im.size != (max_px, max_px):
            fundo = Image.new('RGB', (max_px, max_px), (255, 255, 255))
            fundo.paste(im, ((max_px - im.width) // 2, (max_px - im.height) // 2))
            im = fundo
    while True:
        q = qualidade
        while True:
            buf = io.BytesIO()
            im.save(buf, format='WEBP', quality=q, method=6)
            dados = buf.getvalue()
            if len(dados) <= max_bytes or q <= QUALIDADE_MIN:
                break
            q = max(QUALIDADE_MIN, q - 5)
        if len(dados) <= max_bytes or min(im.size) <= 16:
            return dados
        im = im.resize((max(1, int(im.width * 0.9)), max(1, int(im.height * 0.9))),
                       Image.LANCZOS)


def _webp_miniatura(im, max_px=THUMB_MAX_PX, qualidade=THUMB_QUALIDADE):
    """Maior lado max_px, mantendo a proporcao; nunca amplia; sem preenchimento."""
    im = im.convert('RGB')
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format='WEBP', quality=qualidade)
    return buf.getvalue()


def _gravar_atomico(destino, dados):
    tmp = destino.with_name(destino.name + '.tmp')
    tmp.write_bytes(dados)
    os.replace(tmp, destino)


def publicar_imagem_oferta(id_oferta, caminho_origem, raiz=S3_OFERTAS_IMG_ROOT):
    """Gera <id>.webp e <id>-small.webp a partir de UMA imagem de origem (a 1a
    foto da oferta, ja com marca d'agua). Cria a pasta se nao existir;
    SOBRESCREVE os 2 arquivos se ja existirem (decisao D1: a captura mais
    recente sempre vence). Devolve a pasta, ou '' se nao houver origem/Pillow.
    Best-effort: quem chama trata a excecao."""
    if Image is None:
        print('[imagens_oferta] Pillow indisponivel -- imagem da oferta nao publicada.')
        return ''
    if not id_oferta or not caminho_origem or not os.path.isfile(caminho_origem):
        return ''
    pasta = Path(raiz) / str(id_oferta)
    pasta.mkdir(parents=True, exist_ok=True)
    with Image.open(caminho_origem) as im:
        im.load()
        dados_principal = _webp_principal(im)
        dados_small = _webp_miniatura(im)
    _gravar_atomico(pasta / f'{id_oferta}.webp', dados_principal)
    _gravar_atomico(pasta / f'{id_oferta}-small.webp', dados_small)
    return str(pasta)
