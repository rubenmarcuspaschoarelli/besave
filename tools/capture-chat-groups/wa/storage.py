"""
Persistencia: salva a imagem principal e grava a linha no CSV.

Imagem (ponto critico pedido pelo usuario): sempre na RESOLUCAO NATIVA.
  1) CANVAS: desenha a <img> num canvas em naturalWidth x naturalHeight e exporta
     -> pega o pixel REAL do blob (ex.: 1024x1024), sem depender do tamanho em
     que o WhatsApp desenhou a foto na tela.
  2) SCREENSHOT do elemento: so se o canvas falhar (ver _salvar_via_canvas).
  3) data URI do preview de link -> decodifica, se tiver resolucao suficiente.
Arquivo: ./captura/img/<numero_da_captura>_<nome_sanitizado>.jpeg
"""

import base64
import csv
import io
import json
import re
import time
from datetime import datetime
from pathlib import Path

try:                                 # Pillow so e necessario para a marca d'agua.
    from PIL import Image, ImageChops
except Exception:                    # noqa: BLE001 - sem Pillow, seguimos sem marca
    Image = None
    ImageChops = None

RAIZ_DIR = Path(__file__).resolve().parent.parent
CAPTURA_DIR = RAIZ_DIR / "captura"
IMG_DIR = CAPTURA_DIR / "img"        # imagens ficam separadas do CSV
CONF_DIR = RAIZ_DIR / "conf"         # config.json + arquivo da marca d'agua
CONFIG_PATH = CONF_DIR / "config.json"

# Pasta do site (bucket local) para onde a imagem final + miniatura de cada
# oferta sao publicadas, calibravel em config.json -> "publicacao_s3".
S3_IMG_DIR_PADRAO = r"E:\Work\besave\server\s3\ofertas\img"

# Nomes das colunas do CSV (nomes de saida; as chaves internas do dict `campos`
# do parser continuam com os nomes antigos). DS_TIPO_ORIGEM e uma constante fixa.
COLUNAS = [
    "DS_TIPO_ORIGEM",           # constante "WHATSAPP" (origem da captura)
    "DS_ORIGEM",                # <- nome_do_grupo_do_whatsapp
    "DS_TIPO_OFERTA",           # <- tipo_anuncio (PRODUTO ou CUPOM)
    "ID_OFERTA",                # <- numero_da_captura
    "DT_CAPTACAO",              # <- data_hora_captura
    "DT_OFERTA",                # <- data_hora_mensagem (horario REAL da msg)
    "DS_OFERTA",                # <- nome_do_produto
    "DS_IMAGEM_OFERTA",         # <- imagem_principal
    "DS_OFERTA_AVISO",          # <- msg_aviso
    "VL_PRECO_DE",              # <- preco_de
    "VL_PRECO_POR",             # <- preco_por
    "DS_DESCRICAO_PAGAMENTO",   # <- descricao_pagamento
    "DS_URL_ORIGEM",            # <- url
    "DS_MSG_FINAL",             # <- mensagem_final
    "DS_CUPOM",                 # <- cupom
    "DS_CUPOM_COMENTARIO",      # <- comentario_cupom (separadas por '|')
    "DS_CUPOM_LOJA",            # <- loja_cupom (loja DO CUPOM; so quando ha cupom)
    "DS_LOJA",                  # <- loja (marketplace DA OFERTA; sai em toda linha)
]


def _sanitizar(nome: str, limite: int = 60) -> str:
    """Transforma o nome do produto em algo seguro para nome de arquivo."""
    nome = nome.strip() or "sem_nome"
    nome = re.sub(r"[^\w\s-]", "", nome, flags=re.UNICODE)  # remove pontuacao
    nome = re.sub(r"\s+", "_", nome)
    return nome[:limite] or "sem_nome"


def novo_csv() -> Path:
    """Cria o CSV do run em ./captura/DD_MM_AAAA_HH_MM.csv e escreve o cabecalho."""
    CAPTURA_DIR.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime("%d_%m_%Y_%H_%M") + ".csv"
    caminho = CAPTURA_DIR / nome
    if not caminho.exists():
        # utf-8-sig para o Excel abrir emojis/acentos corretamente.
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=COLUNAS).writeheader()
    return caminho


# JS que escolhe, entre as imagens NAO-emoji da mensagem, a "foto do produto":
# a FOTO REAL (blob) de maior tamanho, ACEITANDO retrato/paisagem (nem todo grupo
# posta foto quadrada: @achadinhoscomcarol posta muitas fotos ALTAS, ex.: natural
# 1072x1600 / render 474x676). Preferimos a de maior naturalWidth (a foto real do
# blob e ~500-1600; o avatar e ~96 e o thumb do preview ~72), desempatando pela
# area renderizada. Ignoramos imagens data: (placeholder borrado / banner do
# preview de link -> tratados no fallback #3 de salvar_imagem).
#
# O CRITERIO E O TAMANHO NATIVO, NUNCA O RENDERIZADO. Uma versao anterior exigia
# clientWidth/Height >= 120 e descartava a foto quando o balao perdia o layout
# (a lista e virtualizada: fora da viewport a <img> fica 0x0 mesmo com o blob ja
# baixado). Isso derrubava ~45% das imagens do @achadinhoscomcarol no catch-up:
# diagnostico ao vivo mostrou 8/8 mensagens com blob nat 500-640 e clientWidth=0,
# constante desde t=0 (ou seja, esperar mais NAO resolvia -- o filtro e que estava
# errado). O filtro por render fazia sentido quando extraiamos por screenshot, que
# precisa do elemento desenhado; o canvas le de naturalWidth/naturalHeight e NAO
# precisa de layout nenhum.
_MIN_NATURAL_FOTO = 200      # exclui avatar (~96) e thumb do preview (~72)

_JS_IMG_QUADRADA = r"""
(el, minNat) => {
  const imgs = Array.from(el.querySelectorAll('img'))
    .filter(i => !(i.className || '').includes('emoji'));
  let best = -1, bestScore = -1;
  imgs.forEach((i, k) => {
    const src = i.src || '';
    if (src.startsWith('data:')) return;          // placeholder/banner -> fallback #3
    if (i.naturalWidth < minNat || i.naturalHeight < minNat) return;  // avatar/icone
    const w = i.clientWidth, h = i.clientHeight;  // pode ser 0x0 (fora da viewport)
    const score = i.naturalWidth * 100000 + w * h; // prefere a foto real (blob grande)
    if (score > bestScore) { bestScore = score; best = k; }
  });
  return best;
}
"""


# Ha alguma foto REAL (blob:/http) na mensagem, de qualquer tamanho? Distingue
# "a foto ainda nao layoutou" (vale esperar) de "esta mensagem so tem preview de
# link" (nao adianta esperar -> vai direto pro fallback). Sem isso, TODA mensagem
# de preview de link pagaria o periodo de graca inteiro a toa.
_JS_TEM_FOTO_REAL = r"""
(el) => Array.from(el.querySelectorAll('img'))
  .filter(i => !(i.className || '').includes('emoji'))
  .some(i => { const s = i.src || ''; return s && !s.startsWith('data:'); })
"""

# Espera MINIMA antes de confiar no _JS_TEM_FOTO_REAL: o WhatsApp monta o balao
# primeiro e so depois cria a <img> com o blob:, entao perguntar cedo demais da
# "nao tem foto" para mensagem que tem. So depois desse piso o atalho vale.
_GRACE_MIN_S = 3.0


def _imgs_nao_emoji(msg):
    """Lista de <img> da mensagem, excluindo emojis (mesma ordem do DOM/JS)."""
    return [
        i for i in msg.query_selector_all("img")
        if "emoji" not in (i.get_attribute("class") or "")
    ]


# Uma imagem "carregada de verdade" tem naturalWidth grande (a foto real do
# blob e ~1024). O placeholder borrado / com spinner tem naturalWidth pequeno,
# entao esperamos naturalWidth passar do limiar antes do screenshot.
_JS_IMG_CARREGADA = (
    "(i, m) => !!i && i.complete && i.naturalWidth >= m "
    "&& i.naturalWidth >= i.clientWidth"
)


def _melhor_img(msg):
    """Escolhe a img quadrada do produto e devolve (handle, carregada?)."""
    idx = msg.evaluate(_JS_IMG_QUADRADA, _MIN_NATURAL_FOTO)
    if not isinstance(idx, int) or idx < 0:
        return None, False
    imgs = _imgs_nao_emoji(msg)
    if idx >= len(imgs):
        return None, False
    handle = imgs[idx]
    try:
        # O limiar e o mesmo da selecao: o seletor ja garante nat >= _MIN_NATURAL_FOTO
        # e exclui os data: (placeholder borrado), entao aqui basta confirmar que a
        # decodificacao terminou. Usar um limiar maior (era 500) fazia uma foto
        # legitima de 450px nunca contar como "carregada" -> esperava o timeout todo.
        carregada = bool(handle.evaluate(_JS_IMG_CARREGADA, _MIN_NATURAL_FOTO))
    except Exception:  # noqa: BLE001
        carregada = False
    return handle, carregada


def _esperar_img_carregar(msg, timeout_s: float = 20.0, grace_sem_img_s: float = None):
    """
    Espera a imagem do produto terminar de carregar (naturalWidth grande) para
    evitar imagem borrada / com icone de loading. Re-seleciona a cada passo
    (a lista pode re-renderizar). Retorna o handle da melhor img (mesmo se
    estourar o timeout -> best-effort, nunca perde a imagem).

    Periodo de graca (grace_sem_img_s, config 'espera_imagem_s'): quando a foto
    AINDA nao aparece (idx<0 -> clientWidth<120), NAO desiste na hora. Durante o
    catch-up a lista e virtualizada e a foto blob: costuma nao ter layout no
    instante do processamento (rolagem rapida) -> aguarda ela "layoutar".

    Passado o piso _GRACE_MIN_S, a graca so continua sendo paga se a mensagem
    TEM uma foto real (blob:/http) esperando layout; mensagem que so tem preview
    de link nao tem o que esperar e vai direto ao fallback -> o catch-up nao
    perde tempo onde nao ha foto, mas nunca desiste antes da foto poder existir.
    """
    if grace_sem_img_s is None:
        grace_sem_img_s = float(_cfg_imagem().get("espera_imagem_s", 8.0))
    inicio = time.time()
    fim = inicio + timeout_s
    limite_sem_img = inicio + max(grace_sem_img_s, _GRACE_MIN_S)
    handle = None
    while time.time() < fim:
        handle, carregada = _melhor_img(msg)
        if handle is None:
            agora = time.time()
            if agora >= limite_sem_img:
                return None                    # sem foto mesmo -> fallback banner
            if agora >= inicio + _GRACE_MIN_S:
                try:
                    tem_foto = bool(msg.evaluate(_JS_TEM_FOTO_REAL))
                except Exception:  # noqa: BLE001
                    tem_foto = False
                if not tem_foto:
                    return None                # so preview de link -> nao espera
            time.sleep(0.4)                    # foto existe/pode existir: aguarda
            continue
        if carregada:
            return handle
        time.sleep(0.4)
    return handle


# --- Marca d'agua -----------------------------------------------------------
# Aplica, no CENTRO da imagem ja salva, a logo referida em conf/config.json
# ("imagem" -> "imagem_marca_dagua"), de forma suave. Parametros calibraveis no
# mesmo bloco do config.json (sem mexer no codigo):
#   marca_dagua_tecnica     : "keyed" (so a tinta da logo aparece; sem caixa
#                             branca) ou "flat" (logo inteira sobreposta fraca).
#   marca_dagua_opacidade   : 0..1 (forca; keyed ~0.30, flat ~0.10).
#   marca_dagua_largura_rel : largura da marca como fracao da largura da imagem.
#
# O mesmo bloco calibra a extracao da foto (a resolucao vem sempre da origem, nao
# de um tamanho fixo -- cada grupo posta na sua: 500, 640, 1024...):
#   qualidade_jpeg    : 0..1, qualidade do JPEG exportado do canvas.
#   resolucao_minima  : px do maior lado; abaixo disso o preview de link e
#                       descartado em vez de virar foto do produto.
#   espera_imagem_s   : quanto esperar a foto "layoutar" no catch-up antes de
#                       desistir (so conta quando ha foto real na mensagem).
#
# E a miniatura "_small" (ver gerar_thumbnail):
#   thumb_ativo       : true/false (desliga a geracao sem mexer no codigo).
#   thumb_max_px      : maior lado da miniatura (200 = padrao). NUNCA amplia:
#                       imagem menor que isso e copiada no tamanho que tem.
#   thumb_formato     : "webp" (padrao), "jpeg" ou "avif".
#   thumb_qualidade   : 1..100 do encoder escolhido.
_cfg_imagem_cache = None


def _cfg_imagem() -> dict:
    """Le (uma vez) o bloco 'imagem' do config.json. {} se ausente/erro."""
    global _cfg_imagem_cache
    if _cfg_imagem_cache is None:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _cfg_imagem_cache = (json.load(f).get("imagem") or {})
        except Exception:  # noqa: BLE001 - sem config valido -> sem marca
            _cfg_imagem_cache = {}
    return _cfg_imagem_cache


def _marca_escalada(cfg: dict, base_w: int):
    """Carrega e redimensiona a logo para ~largura_rel * largura da imagem."""
    nome = cfg.get("imagem_marca_dagua") or ""
    caminho = CONF_DIR / nome
    if not nome or not caminho.exists():
        return None
    largura_rel = float(cfg.get("marca_dagua_largura_rel", 0.35))
    wm = Image.open(caminho).convert("RGB")
    nova_w = max(1, int(base_w * largura_rel))
    nova_h = max(1, int(wm.height * nova_w / wm.width))
    return wm.resize((nova_w, nova_h), Image.LANCZOS)


def aplicar_marca_dagua(caminho_img: str) -> None:
    """
    Sobrepoe a marca d'agua no centro da imagem, IN-PLACE. Best-effort: qualquer
    falha (sem Pillow, sem logo, config ausente) apenas pula, sem quebrar a
    captura. Nao faz nada se opacidade <= 0 ou se nao houver logo configurada.
    """
    if Image is None or not caminho_img:
        return
    cfg = _cfg_imagem()
    opacidade = float(cfg.get("marca_dagua_opacidade", 0.30))
    if opacidade <= 0:
        return
    alvo = Path(caminho_img)
    if not alvo.exists():
        return
    try:
        base = Image.open(alvo).convert("RGBA")
        wm = _marca_escalada(cfg, base.width)
        if wm is None:
            return

        if (cfg.get("marca_dagua_tecnica") or "keyed") == "flat":
            # Logo inteira (com fundo) sobreposta com opacidade uniforme.
            camada_wm = wm.convert("RGBA")
            camada_wm.putalpha(int(255 * opacidade))
        else:
            # keyed: alpha por pixel = distancia do branco (branco->0, tinta->forte),
            # entao so a tinta da logo aparece, sem caixa branca sobre a foto.
            r, g, b = wm.split()
            minc = ImageChops.darker(ImageChops.darker(r, g), b)   # min(r,g,b) por pixel
            alpha = ImageChops.invert(minc).point(lambda v: int(v * opacidade))
            camada_wm = wm.convert("RGBA")
            camada_wm.putalpha(alpha)

        pos = ((base.width - camada_wm.width) // 2,
               (base.height - camada_wm.height) // 2)
        camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
        camada.paste(camada_wm, pos, camada_wm)
        final = Image.alpha_composite(base, camada).convert("RGB")
        final.save(alvo, quality=90)
    except Exception as e:  # noqa: BLE001
        print(f"[storage] Falha ao aplicar marca d'agua em {alvo.name}: {e}")


# --- Miniatura "_small" ------------------------------------------------------
# Para o site: a foto cheia (500-1254 px, 9-375 KB) e cara demais para uma
# listagem. A miniatura sai do MESMO arquivo ja com marca d'agua, com o mesmo
# nome + "_small" e a extensao do formato escolhido:
#     captura/img/29765_Perfume.jpeg  ->  captura/img/29765_Perfume_small.webp
#
# Formato: medido em 10 fotos reais deste projeto (200x200, total):
#     JPEG q85  70,9 KB   |  WEBP q80  41,4 KB (-42%)  |  AVIF q55  29,0 KB (-59%)
# WEBP e o padrao: menor que JPEG por larga margem, suportado por todos os
# navegadores atuais e ~23 ms por imagem. AVIF economiza mais, mas custa ~97 ms
# (4x) por imagem - vale a pena so se o volume do site pedir.
_FORMATOS_THUMB = {
    "webp": ("WEBP", ".webp", dict(method=6)),
    "jpeg": ("JPEG", ".jpeg", dict(optimize=True, progressive=True)),
    "jpg": ("JPEG", ".jpeg", dict(optimize=True, progressive=True)),
    "avif": ("AVIF", ".avif", {}),
}


def _cfg_thumb():
    """(ativo, max_px, formato_PIL, extensao, kwargs_do_encoder, qualidade)."""
    cfg = _cfg_imagem()
    ativo = bool(cfg.get("thumb_ativo", True))
    max_px = int(cfg.get("thumb_max_px", 200) or 200)
    nome = str(cfg.get("thumb_formato", "webp") or "webp").lower().lstrip(".")
    fmt, ext, extra = _FORMATOS_THUMB.get(nome, _FORMATOS_THUMB["webp"])
    qualidade = int(cfg.get("thumb_qualidade", 80) or 80)
    return ativo, max_px, fmt, ext, extra, qualidade


def caminho_thumbnail(caminho_img) -> Path:
    """Caminho da miniatura de uma imagem (nao verifica se existe)."""
    orig = Path(caminho_img)
    _, _, _, ext, _, _ = _cfg_thumb()
    return orig.with_name(orig.stem + "_small" + ext)


def gerar_thumbnail(caminho_img: str) -> str:
    """
    Gera a miniatura da imagem ja salva e devolve o caminho (str) ou "".

    Reduz mantendo a proporcao e NUNCA amplia (Image.thumbnail so encolhe): uma
    foto 150x150 vira uma miniatura 150x150, nao 200x200 borrada. Best-effort,
    igual a marca d'agua: qualquer falha e logada e a captura segue - a foto
    cheia, que e o dado, ja esta no disco.
    """
    if Image is None or not caminho_img:
        return ""
    ativo, max_px, fmt, _ext, extra, qualidade = _cfg_thumb()
    if not ativo:
        return ""
    origem = Path(caminho_img)
    if not origem.exists() or origem.stem.endswith("_small"):
        return ""
    destino = caminho_thumbnail(origem)
    try:
        with Image.open(origem) as im:
            im = im.convert("RGB")
            im.thumbnail((max_px, max_px), Image.LANCZOS)
            im.save(destino, format=fmt, quality=qualidade, **extra)
        return str(destino)
    except Exception as e:  # noqa: BLE001
        print(f"[storage] Falha ao gerar miniatura de {origem.name}: {e}")
        return ""


def apagar_thumbnail(caminho_img: str) -> None:
    """Remove a miniatura de uma imagem (usado quando a foto e descartada)."""
    if not caminho_img:
        return
    try:
        caminho_thumbnail(caminho_img).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


# --- Publicacao no site (bucket local) --------------------------------------
# Alem do arquivo definitivo em captura/img/ (que e o dado, nunca alterado),
# cada oferta e publicada tambem em <destino>/<id_oferta>/ com dois arquivos
# de nome fixo, os dois SEMPRE em WEBP:
#     <id_oferta>.webp         <- imagem principal, mesma resolucao do original
#     <id_oferta>-small.webp   <- a miniatura "_small" ja gerada
# Calibravel em config.json -> "publicacao_s3" (ativo, destino, qualidade),
# sem mexer no codigo; ausente = usa os padroes abaixo.
_cfg_s3_cache = None


def _cfg_s3() -> dict:
    """Le (uma vez) o bloco 'publicacao_s3' do config.json. {} se ausente/erro."""
    global _cfg_s3_cache
    if _cfg_s3_cache is None:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _cfg_s3_cache = (json.load(f).get("publicacao_s3") or {})
        except Exception:  # noqa: BLE001 - sem config valido -> usa padrao
            _cfg_s3_cache = {}
    return _cfg_s3_cache


def publicar_s3(caminho_img: str, numero) -> str:
    """
    Copia a imagem final (+ miniatura, se existir) para a pasta do site,
    convertendo para WEBP e renomeando para <id_oferta>.webp /
    <id_oferta>-small.webp em <destino>/<id_oferta>/. O arquivo original em
    captura/img/ nunca e tocado (so leitura). Best-effort, igual a marca
    d'agua e a miniatura: qualquer falha e logada e a captura segue - o dado
    (a foto em captura/img/) ja esta salvo.

    So publica com numero DEFINITIVO (nao 'tmp<N>' do catch-up).
    """
    if Image is None or not caminho_img or str(numero).startswith("tmp"):
        return ""
    cfg = _cfg_s3()
    if not bool(cfg.get("ativo", True)):
        return ""
    origem = Path(caminho_img)
    if not origem.exists():
        return ""
    qualidade = int(cfg.get("qualidade", 90) or 90)
    raiz = Path(cfg.get("destino") or S3_IMG_DIR_PADRAO)
    pasta = raiz / str(numero)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with Image.open(origem) as im:
            im.convert("RGB").save(
                pasta / f"{numero}.webp", format="WEBP", quality=qualidade, method=6
            )
        thumb = caminho_thumbnail(origem)
        if thumb.exists():
            with Image.open(thumb) as im:
                im.convert("RGB").save(
                    pasta / f"{numero}-small.webp", format="WEBP", quality=qualidade, method=6
                )
        return str(pasta)
    except Exception as e:  # noqa: BLE001
        print(f"[storage] Falha ao publicar imagem {numero} em {pasta}: {e}")
        return ""


def _finalizar_imagem(destino: Path, numero) -> str:
    """Marca d'agua + miniatura + publicacao no site. So roda no nome
    DEFINITIVO: as 'tmp<N>' do catch-up sao renomeadas (ou descartadas) depois
    e gerar miniatura/publicar para cada uma seria lixo no disco/na pasta do site."""
    aplicar_marca_dagua(str(destino))
    if not str(numero).startswith("tmp"):
        gerar_thumbnail(str(destino))
        publicar_s3(str(destino), numero)
    return str(destino)


# Desenha a <img> num canvas do tamanho NATIVO e exporta em JPEG. E assim que
# obtemos o pixel real do blob: o screenshot do elemento rasteriza a foto no
# tamanho em que ela esta DESENHADA na tela (ex.: 330x330 para uma foto de
# 1024x1024 -> reducao de 3x, irreversivel) e ainda herda o recorte do CSS.
# Canvas de imagem de origem cruzada fica "tainted" e toDataURL lanca; os blobs
# do WhatsApp sao da mesma origem (validado ao vivo: 6/6 sem taint), mas o
# try/catch mantem o screenshot como rede de seguranca se isso mudar.
_JS_CANVAS_NATIVO = r"""
(i, q) => {
  try {
    if (!i.naturalWidth || !i.naturalHeight) return null;
    const c = document.createElement('canvas');
    c.width = i.naturalWidth;
    c.height = i.naturalHeight;
    c.getContext('2d').drawImage(i, 0, 0);
    return c.toDataURL('image/jpeg', q);
  } catch (e) {
    return null;                       // tainted -> cai no screenshot
  }
}
"""


def _salvar_via_canvas(handle, destino: Path) -> bool:
    """Extrai a foto na resolucao nativa via canvas. False se nao der (-> screenshot)."""
    qualidade = float(_cfg_imagem().get("qualidade_jpeg", 0.95))
    try:
        url = handle.evaluate(_JS_CANVAS_NATIVO, qualidade)
    except Exception:  # noqa: BLE001 - elemento detachou / JS falhou
        return False
    if not url or not url.startswith("data:image"):
        return False
    try:
        destino.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[storage] Falha ao gravar imagem do canvas: {e}")
        return False


def _resolucao_ok(dados: bytes) -> bool:
    """
    True se a imagem tem resolucao util. O preview de link as vezes traz so um
    thumbnail minusculo (72x72): grava-lo como foto do produto e pior que nao ter
    imagem, porque a linha parece completa e nao da para saber que ficou ruim.
    Sem Pillow nao da para medir -> aceita (best-effort, nao quebra a captura).
    """
    if Image is None:
        return True
    minimo = int(_cfg_imagem().get("resolucao_minima", 400))
    try:
        with Image.open(io.BytesIO(dados)) as im:
            return max(im.size) >= minimo
    except Exception:  # noqa: BLE001
        return True


def _trazer_para_viewport(msg) -> None:
    """
    Leva a mensagem para a viewport antes de extrair a foto.

    O WhatsApp so carrega a foto (blob:) do que esta PERTO da tela. A lista
    virtualizada mantem renderizados varios baloes fora do viewport, e o sweep
    processa justamente esses: sem trazer o balao para a tela, a foto nunca chega
    a existir e a mensagem cai no thumbnail do preview (72x72). Best-effort: se o
    elemento detachar ou nao rolar, segue o fluxo normal.
    """
    try:
        msg.scroll_into_view_if_needed(timeout=3_000)
    except Exception:  # noqa: BLE001
        pass


def salvar_imagem(msg, bruto: dict, numero: int, nome_produto: str) -> str:
    """
    Salva a imagem principal e devolve o caminho (str) ou "" se nao houver.

    Ordem de preferencia:
      1) Foto do produto em RESOLUCAO NATIVA via canvas (blob: ou http).
      2) SCREENSHOT do elemento -> so se o canvas falhar (tainted/detachado).
      3) data URI do preview de link (banner) -> decode, se passar do piso.
    """
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    destino = IMG_DIR / f"{numero}_{_sanitizar(nome_produto)}.jpeg"

    # 1/2) Foto do produto. Espera a foto real carregar antes de extrair (evita
    #      imagem borrada/spinner). Re-seleciona e tenta 2x: a lista e virtualizada
    #      e o elemento pode "detachar" (Element is not attached to the DOM).
    for tentativa in range(2):
        _trazer_para_viewport(msg)                # senao a foto nem carrega
        handle = _esperar_img_carregar(msg)
        if handle is None:
            break
        if _salvar_via_canvas(handle, destino):
            return _finalizar_imagem(destino, numero)
        try:
            # element.screenshot ja rola o minimo para o elemento aparecer;
            # NAO usamos scroll_into_view explicito para nao atrapalhar o sweep.
            time.sleep(0.15)                      # pequeno settle
            handle.screenshot(path=str(destino))
            return _finalizar_imagem(destino, numero)
        except Exception as e:  # noqa: BLE001
            if tentativa == 0:
                time.sleep(0.4)                   # re-render -> tenta de novo
                continue
            print(f"[storage] Falha ao extrair a foto do produto: {e}")

    # 3) Fallback: data URI do preview (banner) -> decode base64.
    src = bruto.get("previewImg")
    if src and src.startswith("data:image"):
        try:
            dados = base64.b64decode(src.split(",", 1)[1])
            if _resolucao_ok(dados):
                destino.write_bytes(dados)
                return _finalizar_imagem(destino, numero)
            print(f"[storage] Preview de {numero} pequeno demais -> descartado.")
        except Exception as e:  # noqa: BLE001
            print(f"[storage] Falha ao decodificar data URI: {e}")

    return ""


def renomear_imagem(old_path: str, numero: int, nome_produto: str) -> str:
    """Renomeia a imagem (salva com nome temporario) para '<numero>_<nome>.jpeg'."""
    if not old_path:
        return ""
    old = Path(old_path)
    if not old.exists():
        return old_path
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    novo = IMG_DIR / f"{numero}_{_sanitizar(nome_produto)}.jpeg"
    try:
        old.replace(novo)                       # sobrescreve se ja existir
        apagar_thumbnail(str(old))              # miniatura do nome tmp, se houver
        gerar_thumbnail(str(novo))
        publicar_s3(str(novo), numero)
        return str(novo)
    except Exception as e:  # noqa: BLE001
        print(f"[storage] Falha ao renomear imagem: {e}")
        return old_path


def gravar_linha(caminho_csv: Path, linha: dict) -> None:
    """Anexa uma linha ao CSV do run."""
    with open(caminho_csv, "a", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=COLUNAS).writerow(linha)
