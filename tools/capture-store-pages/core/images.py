"""
Download das imagens do produto e aplicacao da marca d'agua.

A marca d'agua e portada do AgenteCapturaWhatsapp (wa/storage.py): sobrepoe no
CENTRO da imagem a logo indicada em conf/config.json ("imagem" ->
"imagem_marca_dagua", procurada em conf/). Parametros calibraveis no mesmo bloco,
sem mexer no codigo:
  marca_dagua_tecnica     : "keyed" (so a tinta da logo aparece, sem caixa branca
                            sobre a foto) ou "flat" (logo inteira, opacidade
                            uniforme).
  marca_dagua_opacidade   : 0..1 (forca; keyed ~0.30-0.40, flat ~0.10). <= 0
                            desliga a marca d'agua.
  marca_dagua_largura_rel : largura da marca como fracao da largura da imagem.
  qualidade_jpeg          : 0..1, qualidade do JPEG regravado apos a marca.

Tudo e best-effort: sem Pillow, sem logo ou com config invalido as imagens sao
baixadas normalmente, apenas sem marca.
"""

import json
import os

import requests

try:
    from PIL import Image, ImageChops
except Exception:  # noqa: BLE001 - sem Pillow -> baixa sem marca d'agua
    Image = None
    ImageChops = None

CONF_DIR = 'conf'
CONFIG_PATH = os.path.join(CONF_DIR, 'config.json')

_cfg_imagem_cache = None


def _cfg_imagem():
    """Le (uma vez) o bloco 'imagem' do config.json. {} se ausente/erro."""
    global _cfg_imagem_cache
    if _cfg_imagem_cache is None:
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                _cfg_imagem_cache = (json.load(f).get('imagem') or {})
        except Exception:  # noqa: BLE001 - sem config valido -> sem marca
            _cfg_imagem_cache = {}
    return _cfg_imagem_cache


def _marca_escalada(cfg, base_w):
    """Carrega e redimensiona a logo para ~largura_rel * largura da imagem."""
    nome = cfg.get('imagem_marca_dagua') or ''
    caminho = os.path.join(CONF_DIR, nome)
    if not nome or not os.path.exists(caminho):
        return None
    largura_rel = float(cfg.get('marca_dagua_largura_rel', 0.35))
    wm = Image.open(caminho).convert('RGB')
    nova_w = max(1, int(base_w * largura_rel))
    nova_h = max(1, int(wm.height * nova_w / wm.width))
    return wm.resize((nova_w, nova_h), Image.LANCZOS)


def aplicar_marca_dagua(caminho_img):
    """
    Sobrepoe a marca d'agua no centro da imagem, IN-PLACE. Best-effort: qualquer
    falha (sem Pillow, sem logo, arquivo corrompido) apenas pula, sem quebrar a
    captura. Nao faz nada se opacidade <= 0 ou se nao houver logo configurada.
    """
    if Image is None or not caminho_img:
        return
    cfg = _cfg_imagem()
    opacidade = float(cfg.get('marca_dagua_opacidade', 0.30))
    if opacidade <= 0 or not os.path.exists(caminho_img):
        return
    try:
        base = Image.open(caminho_img).convert('RGBA')
        wm = _marca_escalada(cfg, base.width)
        if wm is None:
            return

        if (cfg.get('marca_dagua_tecnica') or 'keyed') == 'flat':
            # Logo inteira (com fundo) sobreposta com opacidade uniforme.
            camada_wm = wm.convert('RGBA')
            camada_wm.putalpha(int(255 * opacidade))
        else:
            # keyed: alpha por pixel = distancia do branco (branco->0, tinta->forte),
            # entao so a tinta da logo aparece, sem caixa branca sobre a foto.
            r, g, b = wm.split()
            minc = ImageChops.darker(ImageChops.darker(r, g), b)   # min(r,g,b) por pixel
            alpha = ImageChops.invert(minc).point(lambda v: int(v * opacidade))
            camada_wm = wm.convert('RGBA')
            camada_wm.putalpha(alpha)

        pos = ((base.width - camada_wm.width) // 2,
               (base.height - camada_wm.height) // 2)
        camada = Image.new('RGBA', base.size, (0, 0, 0, 0))
        camada.paste(camada_wm, pos, camada_wm)
        final = Image.alpha_composite(base, camada).convert('RGB')
        qualidade = int(float(cfg.get('qualidade_jpeg', 0.95)) * 100)
        final.save(caminho_img, quality=max(1, min(100, qualidade)))
    except Exception as e:  # noqa: BLE001
        print(f"Erro ao aplicar marca d'agua em {caminho_img}: {e}")


# Menor arquivo aceito como foto de produto. Existe por causa de um caso real:
# a Amazon usa um GIF transparente de 43 bytes (grey-pixel.gif) como espaco
# reservado enquanto a imagem de verdade nao carrega -- e ate 11/09/2026 ele era
# gravado como se fosse foto (6 dos 27 arquivos de uma captura). O mesmo corte
# barra pagina de erro devolvida com 200.
MIN_BYTES_IMAGEM = 1024


def download_image(img_url, filename, marca_dagua=True):
    """Baixa a imagem e grava em `filename`. Devolve True se gravou algo que
    parece uma imagem de verdade -- assim quem chamou pode tentar outra URL.
    Erro nunca interrompe o lote."""
    try:
        resp = requests.get(img_url, timeout=30)
        if resp.status_code != 200:
            print(f"Imagem {img_url[:70]}: HTTP {resp.status_code}, ignorada.")
            return False
        tipo = (resp.headers.get('Content-Type') or '').lower()
        img_data = resp.content
        if tipo and not tipo.startswith('image/'):
            print(f"Imagem {img_url[:70]}: veio '{tipo}', ignorada.")
            return False
        if len(img_data) < MIN_BYTES_IMAGEM:
            # Espaco reservado / pixel transparente: nao e foto do produto.
            return False
        with open(filename, 'wb') as file:
            file.write(img_data)
    except Exception as e:
        print(f"Erro ao salvar a imagem {filename}: {e}")
        return False
    if marca_dagua:
        aplicar_marca_dagua(filename)
    return True
