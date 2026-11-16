"""Foto do post (BSV-63): a da oferta, publicada no site, em quadrado 800x800 JPEG de fundo branco.

JPEG e nao WebP: WebP anexado no WhatsApp pode virar figurinha. Sem foto da oferta (404, timeout,
imagem invalida) -> placeholder da area, igual ao Telegram. Sem os dois -> None: o post nao sai sem foto.
"""

import io
import urllib.request
from collections.abc import Callable
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SITE = "https://besave.com.br"
LADO = 800
QUALIDADE = 90
TIMEOUT_S = 20
MAX_BYTES = 10 * 1024 * 1024


def url_oferta(id_oferta: int) -> str:
    return f"{SITE}/img/ofertas/{int(id_oferta)}.webp"


def url_placeholder(area_slug: str) -> str:
    return f"{SITE}/img/placeholder/{area_slug}.webp"


def baixar(url: str, timeout: float = TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "besave-publicador"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dados = r.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError("imagem maior que o limite")
    return dados


def quadrado(dados: bytes) -> bytes:
    """Imagem inteira, proporcao preservada, centralizada num quadrado branco LADO x LADO, em JPEG."""
    with Image.open(io.BytesIO(dados)) as im:
        im.load()
        if im.width < 1 or im.height < 1:
            raise ValueError("imagem vazia")
        im = im.convert("RGBA")
    escala = LADO / max(im.width, im.height)
    w, h = max(1, round(im.width * escala)), max(1, round(im.height * escala))
    im = im.resize((w, h), Image.Resampling.LANCZOS)
    fundo = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    fundo.paste(im, ((LADO - w) // 2, (LADO - h) // 2), im)
    saida = io.BytesIO()
    fundo.save(saida, format="JPEG", quality=QUALIDADE)
    return saida.getvalue()


def preparar(id_oferta: int, area_slug: str, destino: Path,
             obter: Callable[[str], bytes] = baixar, log: Callable[[str], None] = print) -> Path | None:
    """Grava o JPEG em `destino` e devolve o caminho; None se nem a oferta nem o placeholder servirem."""
    for url, rotulo in ((url_oferta(id_oferta), "oferta"), (url_placeholder(area_slug), "placeholder")):
        try:
            jpeg = quadrado(obter(url))
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as e:
            # OSError cobre HTTPError (404), URLError e timeout.
            log(f"[foto] WARN oferta {id_oferta}: {rotulo} indisponivel ({type(e).__name__})")
            continue
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(jpeg)
        if rotulo == "placeholder":
            log(f"[foto] WARN oferta {id_oferta}: sem foto propria, usando o placeholder de {area_slug}")
        return destino
    return None
