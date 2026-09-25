"""
Extracao dos campos de uma mensagem promocional.

Fluxo:
  1. `extrair_bruto(msg)`  -> roda JS na mensagem e devolve um dicionario com
     o texto ja reconstruido (emoji trocado pelo alt), links, e a imagem
     (data URI do preview, quando houver).
  2. `parse_campos(bruto)` -> aplica regex/heuristicas sobre o texto e devolve
     os 7 campos pedidos.

Toda a extracao textual e feita por CONTEUDO (regex), nunca por classe CSS.
"""

import re
from datetime import datetime
from urllib.parse import urlparse

# JS injetado em cada mensagem. Recebe o elemento (data-id) como argumento.
_JS_EXTRAIR = r"""
(el) => {
  // Reconstroi o texto trocando <img> de emoji pelo seu alt/data-plain-text.
  function walk(node) {
    let s = '';
    node.childNodes.forEach(n => {
      if (n.nodeType === 3) {                      // texto puro
        s += n.nodeValue;
      } else if (n.tagName === 'IMG') {            // emoji
        const cls = n.className || '';
        if (cls.includes('emoji')) {
          s += (n.getAttribute('alt') || n.getAttribute('data-plain-text') || '');
        }
      } else if (n.tagName === 'BR') {
        s += '\n';
      } else {
        s += walk(n);
      }
    });
    return s;
  }

  // Autor da mensagem.
  const authorEl = el.querySelector('[data-testid="author"]');
  const author = authorEl ? authorEl.textContent.trim() : '';

  // Cabecalho "[hh:mm, dd/mm/aaaa] Autor:".
  const pre = el.querySelector('.copyable-text[data-pre-plain-text]');
  const prePlain = pre ? (pre.getAttribute('data-pre-plain-text') || '') : '';

  // Corpo: pega os spans selectable-text de mais alto nivel (evita duplicar
  // os <strong> internos, que tambem sao selectable-text).
  let bodyEls = Array.from(el.querySelectorAll('[data-testid~="selectable-text"]'))
    .filter(b => !b.parentElement || !b.parentElement.closest('[data-testid~="selectable-text"]'));

  let text = bodyEls.length ? bodyEls.map(walk).join('\n') : walk(el);

  // Links (na ordem em que aparecem).
  const links = Array.from(el.querySelectorAll('a[href]'))
    .map(a => a.getAttribute('href'))
    .filter(h => h && h.startsWith('http'));

  // Imagem principal: preferimos o data URI do preview de link.
  let previewImg = null;
  const p = el.querySelector('img[data-testid="link-preview-thumbnail-jpeg"]');
  if (p && (p.getAttribute('src') || '').startsWith('data:image')) {
    previewImg = p.getAttribute('src');
  }
  if (!previewImg) {
    // Qualquer imagem "grande" em data URI que nao seja emoji.
    const imgs = Array.from(el.querySelectorAll('img')).filter(i => {
      const c = i.className || '';
      const src = i.getAttribute('src') || '';
      return !c.includes('emoji') && src.startsWith('data:image') && src.length > 800;
    });
    if (imgs.length) previewImg = imgs[0].getAttribute('src');
  }

  // Sinaliza imagem enviada via blob (nao decodificavel -> screenshot).
  const temBlob = !!el.querySelector('[data-testid="image-thumb"] img, img[src^="blob:"]');

  // Titulo do card de link (quando a msg e um preview de link, nao imagem+legenda).
  // Usado como FALLBACK do nome quando a legenda nao tem o produto.
  let previewTitle = '';
  const tSel = [
    '[data-testid="link-preview-title"]',
    '[data-testid*="link-preview"] [role="button"] span',
  ];
  for (const s of tSel) {
    const t = el.querySelector(s);
    if (t && t.textContent.trim()) { previewTitle = t.textContent.trim(); break; }
  }

  return { author, prePlain, text, links, previewImg, temBlob, previewTitle };
}
"""

# ---------------------------------------------------------------------------
# Regex dos campos (aplicadas sobre o texto reconstruido)
# ---------------------------------------------------------------------------
_RE_PRECO_DE = re.compile(r"De\s*:?\s*R\$\s*([\d.,]+)", re.IGNORECASE)
_RE_PRECO_POR = re.compile(r"po+r\s*:?\s*R\$\s*([\d.,]+)", re.IGNORECASE)
# Preco "cru": qualquer 'R$ valor'. group(1)=valor, group(2)=resto da linha
# (usado p/ msgs que so tem o preco final, ex.: 'R$ 141,55 via Pix').
_RE_PRECO_GEN = re.compile(r"R\$\s*([\d.,]+)\s*(.*)$")
# A palavra 'cupom' e case-insensitive, mas o TOKEN fica case-sensitive (so
# MAIUSCULAS/digitos) -> evita 'podem', 'usar'. O lookahead (?![A-Za-zÀ-ÿ])
# garante token COMPLETO: 'CUPOM DISPONÍVEL' nao vira 'DISPON' (cortado no Í).
_RE_CUPOM = re.compile(r"(?i:cupom)\s*:?\s*\*?([A-Z0-9]{3,})(?![A-Za-zÀ-ÿ])")
# 'cupom <palavras>: CODE' — pega o codigo depois de ':' (ex.: 'CUPOM DISPONÍVEL: QUEROOFF').
_RE_CUPOM_COLON = re.compile(r"(?i:cupom)[^\n:]{0,25}:\s*\*?([A-Z0-9]{4,})(?![A-Za-zÀ-ÿ])")
# Palavras em caixa-alta que NAO sao cupom (aparecem logo depois de 'cupom').
_CUPOM_STOP = {
    "VAI", "COM", "ESSE", "ESSA", "AGORA", "PODE", "PODEM", "USE", "USAR",
    "USA", "PRA", "PARA", "HOJE", "AQUI", "SEU", "SUA", "DISPON", "DISPONIVEL",
    "DISPONÍVEL", "OFF", "APENAS", "GANHE", "TODOS", "TODAS", "TODA", "NELE",
    "NELA", "NAS", "NOS", "DESCONTO", "EXTRA", "VALIDO", "VÁLIDO",
    "LIMITADO", "LIMITADA", "NOVO", "NOVOS", "NOVA", "GRATIS", "GRÁTIS",
    "FRETE", "TEMPO", "EXCLUSIVO", "PRIMEIRA", "PRIMEIRO", "CLIENTE",
}
_RE_MSG_FINAL = re.compile(r"(Promo[cç][aã]o sujeita[^\n]*)", re.IGNORECASE)
_RE_HORA = re.compile(r"^\d{1,2}:\d{2}$")
# Selo de desconto ISOLADO (a linha e SO '34% OFF', '50% OFF!!' ...) — nao e
# nome. Se houver texto depois do selo (ex.: '34% OFF Cafeteira'), NAO filtra.
_RE_SELO_OFF = re.compile(r"^\d{1,3}\s*%\s*off\s*!*\.?\s*$", re.IGNORECASE)

# --- Anuncios de CUPOM (mensagens que so divulgam cupons) --------------------
# Entrada de cupom estruturada: 'Cupom: CODE' ou 'Código: CODE' (com ':').
# A palavra e case-insensitive, mas o CODE fica MAIUSCULO (evita pegar 'https'
# de 'resgate seu cupom: https://...'). Codigos reais: DECOR20, QUEROOFF, SURPR354.
_RE_CUPOM_ENTRY = re.compile(r"(?P<kw>(?i:cupom|c[óo]digo))\s*:\s*\*?(?P<code>[A-Z0-9]{3,})")
# Rotulos de link ('Resgate aqui:', 'Lista de produtos:') — nao sao comentario.
_RE_LINK_LABEL = re.compile(r"resgate|lista de produtos", re.IGNORECASE)
# Lojas conhecidas -> nome CANONICO. A ordem importa (mais especifico 1o).
_LOJAS = (
    ("MERCADO LIVRE", r"mercado\s*livre|mercadolivre|\bmeli\b|meli\.la"),
    ("SHOPEE",        r"shopee"),
    # "amaznlink.com" nao casa com "amzn" nem com "amazon" -- dai o 3o termo.
    ("AMAZON",        r"amazon|amzn|amaznlink"),
    ("MAGALU",        r"magalu|magazine\s*luiza|magazineluiza"),
    ("ALIEXPRESS",    r"aliexpress|aliexp"),
    ("NATURA",        r"natura"),
    # Lojas que so apareciam como DOMINIO CRU no campo (mapeadas em 22/09/2026,
    # a pedido do usuario). O dominio segue sendo o fallback de quem nao esta
    # aqui -- e o sinal de que falta mapear.
    ("BELEZA NA WEB", r"beleza\s*na\s*web|belezanaweb|blz\.to"),
    ("EPOCA COSMETICOS", r"epoca\s*cosmeticos|epocacosmeticos"),
    ("SHEIN",         r"\bshein\b"),
    ("ZZ MALL",       r"zzmall|\bzz\s*mall\b"),
    ("SKELT",         r"\bskelt\b"),
    ("ACHADINHOS COM CAROL", r"achadinhoscomcarol"),
    ("LTK",           r"\bltk\.com\b|\bon\.ltk\b"),
)

# Linhas que NAO sao nome de produto.
_LIXO_NOME = (
    "cupom", "compre aqui", "compre pelo", "compre pelo link", "resgate",
    "aproveite", "apenas", "promoç", "promoc", "insira", "link direto",
    "off acima", "dica especial", "código", "codigo", "de r$", "por r$",
    "@achados", "baixou", "corre que", "só hoje", "so hoje", "buggg",
    "promoção liberada", "de:", "por:",
    # Linhas de instrucao de compra que costumam ficar coladas no preco.
    "desconto aparece", "desconto entra", "última etapa", "ultima etapa",
    "etapa do pagamento", "selecionando", "recomendados", "menor valor",
    "no carrinho", "na finalização", "na finalizacao",
    # Linhas de selo/disclaimer que nao sao nome (ex.: "loja oficial ✅",
    # "Grandes marcas com loja oficial na Shopee", "é vendido e entregue pela Amazon").
    "loja oficial", "vendido e entregue",
)


def extrair_bruto(msg) -> dict:
    """Roda o JS na mensagem e devolve o dicionario bruto."""
    return msg.evaluate(_JS_EXTRAIR)


# Cabecalho copiavel de cada mensagem: "[HH:MM, DD/MM/AAAA] Autor:". E a fonte
# MAIS confiavel da data/hora (atributo data-pre-plain-text, nao depende das
# classes ofuscadas do span visivel nem de rastrear o separador 'Hoje/Ontem').
_RE_PRE_DATA = re.compile(r"\[(\d{1,2}):(\d{2}),\s*(\d{1,2})/(\d{1,2})/(\d{4})\]")


def extrair_data_hora(bruto: dict):
    """
    Data/hora em que a mensagem foi postada, como datetime (precisao de minuto),
    lida do cabecalho 'prePlain'. Retorna None se nao houver o atributo (raro).
    """
    m = _RE_PRE_DATA.search(bruto.get("prePlain") or "")
    if not m:
        return None
    hh, mm, dd, mo, yy = (int(g) for g in m.groups())
    try:
        return datetime(yy, mo, dd, hh, mm)
    except ValueError:
        return None


def _strip_emoji_inicial(s: str) -> str:
    """Remove emoji/simbolos/espacos no inicio, mantendo letras (com acento) e digitos."""
    return re.sub(r"^[^\w]+", "", s, flags=re.UNICODE).strip()


def _limpar_linhas(text: str):
    text = text.replace("\xa0", " ")
    linhas = []
    for ln in text.split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()   # colapsa espacos duplos
        if not ln or _RE_HORA.match(ln):
            continue
        linhas.append(ln)
    return linhas


def _eh_hype(ln: str) -> bool:
    """
    True se a linha for 'grito'/chamada (quase toda em MAIUSCULAS).
    Nomes de produto sao Title Case/mistos; frases de hype como
    'PEGA A DIFERENCA AMIGA' ou 'BAIXOU O PRECO' sao majoritariamente caixa-alta.
    """
    letras = [c for c in ln if c.isalpha()]
    if len(letras) < 5:
        return False
    razao_maiusc = sum(c.isupper() for c in letras) / len(letras)
    return razao_maiusc >= 0.7


def _achar_aviso(linhas):
    """Aviso = 1a linha 'hype' (maiuscula) ou curta terminando em '!'."""
    for ln in linhas:
        if _eh_hype(ln) or (len(ln) <= 40 and ln.endswith("!") and ln.upper() == ln):
            return ln
    return ""


def _limpar_desc_pagamento(s: str) -> str:
    """
    Extrai a condicao de pagamento que costuma vir depois do preco.
    Ex.: 'R$ 141,55 via Pix' -> 'via Pix'; 'R$ 67,99 à vista 👇' -> 'à vista'.
    Mantem so o trecho textual inicial (corta no 1o emoji/simbolo).
    """
    s = s.replace("\xa0", " ").strip()
    s = _strip_emoji_inicial(s)
    m = re.match(r"[\w ]+", s, flags=re.UNICODE)
    s = m.group(0).strip() if m else ""
    # Descricao de pagamento e curta ('via Pix', 'à vista', 'em até 12x').
    # Min. 3 chars descarta lixo tipo 'R' (sobra de 'R$' de outro valor na linha);
    # trecho longo (>30) provavelmente pegou outra coisa.
    return s if 3 <= len(s) <= 30 else ""


def _limpar_preco(s: str) -> str:
    """Remove pontuacao/espacos nas pontas do valor (ex.: '79,' -> '79')."""
    return s.strip(" .,\xa0")


def _analisar_precos(linhas):
    """
    Percorre as linhas e devolve (preco_de, preco_por, descricao_pagamento,
    idx_ancora) — idx_ancora e a linha do preco 'por' (ou 'de'), usada para
    ancorar o nome do produto logo acima dela.

    Regras:
      - 'De: R$ X'  -> preco_de
      - 'Por: R$ Y' -> preco_por (+ texto seguinte = descricao_pagamento)
      - Sem 'Por', usa o 1o 'R$' que nao seja o 'de' como preco_por
        (msgs que so tem o preco final, geralmente 'R$ Y via Pix / à vista').
    """
    preco_de = preco_por = desc_pag = ""
    idx_de = idx_por = -1
    for i, ln in enumerate(linhas):
        if _eh_hype(ln):        # 'POR MENOS DE R$70' etc. nao e linha de preco
            continue
        if not preco_de:
            m_de = _RE_PRECO_DE.search(ln)
            if m_de:
                preco_de, idx_de = _limpar_preco(m_de.group(1)), i
        if not preco_por:
            m_por = _RE_PRECO_POR.search(ln)
            if m_por:
                preco_por, idx_por = _limpar_preco(m_por.group(1)), i
                desc_pag = _limpar_desc_pagamento(ln[m_por.end():])

    if not preco_por:
        for i, ln in enumerate(linhas):
            if i == idx_de or _eh_hype(ln):   # nao reusar 'de' nem linha de hype
                continue
            m = _RE_PRECO_GEN.search(ln)
            if m:
                preco_por, idx_por = _limpar_preco(m.group(1)), i
                desc_pag = _limpar_desc_pagamento(m.group(2))
                break

    idx_ancora = idx_por if idx_por >= 0 else idx_de
    return preco_de, preco_por, desc_pag, idx_ancora


def _achar_cupom(text: str) -> str:
    """
    1o token de cupom valido: MAIUSCULO, completo, fora da lista de palavras
    comuns e 'codey' (>=4 chars ou com digito, ex.: FULL15, QUEROOFF).
    """
    for rx in (_RE_CUPOM, _RE_CUPOM_COLON):
        for m in rx.finditer(text):
            tok = m.group(1)
            if tok.upper() in _CUPOM_STOP:
                continue
            if len(tok) < 4 and not any(c.isdigit() for c in tok):
                continue
            return tok
    return ""


def _detectar_loja(*textos) -> str:
    """Nome CANONICO da loja a partir do texto e/ou URL (ex.: 'MERCADO LIVRE')."""
    hay = " ".join(t for t in textos if t).lower()
    for nome, pat in _LOJAS:
        if re.search(pat, hay):
            return nome
    return ""


def _dominio_da_url(url: str) -> str:
    """
    Host da URL, sem 'www.' e em minusculas (ex.: 'lojasrenner.com.br'). Usado
    como nome PROVISORIO da loja quando ela ainda nao esta em `_LOJAS`.
    """
    if not url:
        return ""
    if "//" not in url:                        # link sem esquema ('loja.com/x')
        url = "http://" + url
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    # Emoji/pontuacao colados no link vazam para o host ('🚨ga.ma' e 'ga.ma'
    # seriam 2 lojas). Descarta o lixo antes do 1o caractere valido de dominio.
    host = re.sub(r"^[^a-z0-9]+", "", host)
    return host[4:] if host.startswith("www.") else host


def _loja_do_campo(text: str, url: str) -> str:
    """
    Valor do campo de loja: nome CANONICO quando a loja e conhecida; senao o
    dominio do link, para a loja ficar registrada e ser mapeada depois.

    Separado de `_detectar_loja` de proposito: aquela alimenta a CLASSIFICACAO
    PRODUTO/CUPOM (`_tem_header_cupom`), onde um dominio solto faria qualquer
    linha com link parecer anuncio de loja.
    """
    return _detectar_loja(text, url) or _dominio_da_url(url)


def _tem_header_cupom(linha: str) -> bool:
    """
    True se a 1a linha e um cabecalho de anuncio de CUPOM: contem CUPOM/CUPONS
    E (NOVO/NOVOS/SAIU/+N ou nome de loja). Assim 'NOVO CUPOM SHOPEE' e cupom,
    mas 'BAIXOU 84% COM ESSE CUPOM' (produto) nao.
    """
    baixo = linha.lower()
    if not re.search(r"cupo(m|ns)", baixo):
        return False
    if re.search(r"\bnovo\b|\bnovos\b|\bsaiu\b|\+\s*\d", baixo):
        return True
    return bool(_detectar_loja(linha))


def _eh_anuncio_cupom(linhas) -> bool:
    """Classifica a mensagem como anuncio de CUPOM (vs. PRODUTO)."""
    if not linhas:
        return False
    if _tem_header_cupom(linhas[0]):
        return True
    # Sem header claro: 2+ entradas 'Cupom:/Código:' e nenhum preco De/Por.
    entradas = sum(1 for ln in linhas if _RE_CUPOM_ENTRY.search(ln))
    tem_preco = any(_RE_PRECO_DE.search(ln) or _RE_PRECO_POR.search(ln) for ln in linhas)
    return entradas >= 2 and not tem_preco


def _comentario_cupom(linhas, i: int, abaixo: bool) -> str:
    """
    Comentario/descricao de um cupom na linha i. 'Código:' -> comentario ABAIXO;
    'Cupom:' -> ACIMA. Pega a 1a linha textual adjacente (para antes de outro
    cupom ou de um link).
    """
    rng = range(i + 1, len(linhas)) if abaixo else range(i - 1, -1, -1)
    for j in rng:
        ln = linhas[j]
        if _RE_CUPOM_ENTRY.search(ln):        # bateu em outro cupom
            return ""
        if "http" in ln.lower() or _RE_LINK_LABEL.search(ln):
            return ""
        cand = _strip_emoji_inicial(ln).strip()
        if cand:
            return cand
    return ""


def _extrair_cupons(linhas):
    """
    Extrai (codigos, comentarios) de um anuncio de CUPOM, na ordem em que
    aparecem. Cada codigo tem seu comentario pareado (mesmo indice).
    """
    codigos, comentarios = [], []
    for i, ln in enumerate(linhas):
        m = _RE_CUPOM_ENTRY.search(ln)
        if not m:
            continue
        codigo = m.group("code").strip(" .,!¡")
        abaixo = "digo" in m.group("kw").lower()   # 'código' -> comentario abaixo
        codigos.append(codigo)
        comentarios.append(_comentario_cupom(linhas, i, abaixo))
    return codigos, comentarios


def _limpar_nome(s: str) -> str:
    """Limpa o nome: tira selo '% OFF' do inicio e pontuacao de 'grito' do fim."""
    s = re.sub(r"^\s*\d{1,3}\s*%\s*off\s*!*\s*", "", s, flags=re.IGNORECASE)
    return re.sub(r"[\s!¡?.…]+$", "", s).strip()


def _achar_nome_ancorado(linhas, idx_ancora, aviso):
    """
    Nome = linha qualificada mais PROXIMA acima da linha de preco.
    Sobe a partir do preco pulando hype/lixo/link/fragmentos. Isso resolve
    casos com varios comentarios antes do nome (o nome fica colado no preco).
    """
    if idx_ancora is None or idx_ancora < 1:
        return ""
    for i in range(idx_ancora - 1, -1, -1):
        ln = linhas[i]
        if ln == aviso:
            continue
        baixo = ln.lower()
        if "http" in baixo:
            continue
        if any(t in baixo for t in _LIXO_NOME):
            continue
        if _RE_SELO_OFF.match(ln):     # '34% OFF' nao e nome
            continue
        if _eh_hype(ln):
            continue
        if len(ln) < 6:
            continue
        return ln
    return ""


def _achar_nome(linhas, aviso):
    """Heuristica do nome: 1a linha 'substancial' que nao seja lixo/preco/hype."""
    for ln in linhas:
        if ln == aviso:
            continue
        baixo = ln.lower()
        if any(t in baixo for t in _LIXO_NOME):
            continue
        if "http" in baixo:
            continue
        if _RE_SELO_OFF.match(ln):     # '34% OFF' nao e nome
            continue
        if _eh_hype(ln):          # frases em maiuscula nao sao nome de produto
            continue
        if len(ln) < 10:
            continue
        return ln
    # Fallback: maior linha nao-lixo e nao-hype.
    candidatas = [
        ln for ln in linhas
        if "http" not in ln.lower()
        and not any(t in ln.lower() for t in _LIXO_NOME)
        and not _RE_SELO_OFF.match(ln)
        and not _eh_hype(ln)
    ]
    return max(candidatas, key=len) if candidatas else ""


def _campos_vazios() -> dict:
    """Dicionario base com todos os campos vazios (garante colunas consistentes)."""
    return {
        "tipo_anuncio": "PRODUTO",
        "nome_do_produto": "",
        "msg_aviso": "",
        "preco_de": "",
        "preco_por": "",
        "descricao_pagamento": "",
        "url": "",
        "mensagem_final": "",
        "cupom": "",
        "comentario_cupom": "",
        "loja_cupom": "",
        "loja": "",
    }


def parse_campos(bruto: dict) -> dict:
    """Classifica a mensagem (PRODUTO/CUPOM) e extrai os campos."""
    text = bruto.get("text", "") or ""
    linhas = _limpar_linhas(text)
    links = bruto.get("links") or []
    url = links[0] if links else ""          # 1o link (decisao do usuario)

    campos = _campos_vazios()
    campos["url"] = url

    # --- Anuncio so de CUPOM (1+ cupons, sem produto) ---
    if _eh_anuncio_cupom(linhas):
        codigos, comentarios = _extrair_cupons(linhas)
        campos["tipo_anuncio"] = "CUPOM"
        campos["msg_aviso"] = _strip_emoji_inicial(linhas[0]) if linhas else ""
        campos["cupom"] = " | ".join(codigos)
        campos["comentario_cupom"] = " | ".join(comentarios)
        campos["loja_cupom"] = _loja_do_campo(text, url)
        campos["loja"] = campos["loja_cupom"]
        return campos

    # --- Anuncio de PRODUTO (fluxo padrao) ---
    aviso = _achar_aviso(linhas)
    preco_de, preco_por, desc_pag, idx_ancora = _analisar_precos(linhas)

    # Nome: 1o ancora no preco; senao heuristica antiga; senao titulo do link
    # preview (mensagens cujo nome so aparece no card do link, nao na legenda).
    nome = _achar_nome_ancorado(linhas, idx_ancora, aviso)
    if not nome:
        nome = _achar_nome(linhas, aviso)
    if not nome:
        nome = (bruto.get("previewTitle") or "").strip()

    cupom = _achar_cupom(text)
    m_final = _RE_MSG_FINAL.search(text)

    campos["nome_do_produto"] = _limpar_nome(_strip_emoji_inicial(nome))
    campos["msg_aviso"] = _strip_emoji_inicial(aviso)
    campos["preco_de"] = preco_de
    campos["preco_por"] = preco_por
    campos["descricao_pagamento"] = desc_pag
    campos["mensagem_final"] = m_final.group(1).strip() if m_final else ""
    campos["cupom"] = cupom
    # "loja_cupom" e a loja DO CUPOM (so existe quando ha cupom); "loja" e a
    # loja DA OFERTA e sai em toda linha -- antes de 22/09/2026 o marketplace
    # ficava sem registro em 2 de cada 3 ofertas, mesmo com a URL dizendo qual.
    loja = _loja_do_campo(text, url)
    campos["loja_cupom"] = loja if cupom else ""
    campos["loja"] = loja
    return campos
