import html
import json
import os
import re
from urllib.parse import urlparse

from core.base_store import BaseStore
from core.text_utils import normalize_text, normalize_price
from core.images import download_image


class SchemaOrgStore(BaseStore):
    """Loja generica guiada por dados estruturados schema.org (JSON-LD + og meta).

    Serve qualquer e-commerce que publique um `<script type="application/ld+json">`
    com `@type: Product` (padrao em VTEX, SAP Hybris etc.) -- em vez de depender de
    classes CSS que variam por tema/loja. Cobre, hoje:
      - epocacosmeticos.com.br  (VTEX)
      - zzmall.com.br           (SAP Hybris -- NAO e VTEX, mas emite o mesmo JSON-LD)
      - belezanaweb.com.br      (via o encurtador blz.to)
      - minhaloja.natura.com    (Salesforce Commerce Cloud / demandware)

    A loja e resolvida na URL de ORIGEM (main.py, antes do goto); por isso o
    encurtador `blz.to` (-> belezanaweb) precisa estar mapeado aqui, igual ao
    `meli.la` do Mercado Livre.
    """

    nome = 'schemaorg'
    # Esta store atende VARIAS lojas de verdade, entao o nome comercial sai do
    # dominio (e nao de um `nome_exibicao` fixo) -- e esse nome que casa com
    # conf/config.json -> "lojas_ativas". Ver nome_loja(). Sem dominio conhecido
    # cai em 'schemaorg', que nunca estara na lista -> a oferta nasce inativa.
    _NOMES_POR_DOMINIO = {
        'epocacosmeticos': 'Época Cosméticos',
        'zzmall': 'ZZ Mall',
        'belezanaweb': 'Beleza na Web',
        'blz.to': 'Beleza na Web',
        'natura': 'Natura',
    }
    # @type que contam como "produto" no JSON-LD. ProductGroup e usado por lojas
    # com variacoes (ex.: belezanaweb num perfume com tamanhos) e traz name/offers/
    # image/aggregateRating no mesmo formato do Product.
    _TIPOS_PRODUTO = ('product', 'productgroup')
    # Rotulos genericos de "inicio" a descartar do breadcrumb (varia por loja).
    _CATEG_GENERICAS = ('home', 'inicio', 'início', 'página inicial', 'pagina inicial')

    dominios = [
        'zzmall.com.br', 'www.zzmall.com.br',
        'epocacosmeticos.com.br', 'www.epocacosmeticos.com.br',
        'belezanaweb.com.br', 'www.belezanaweb.com.br',
        'blz.to',  # encurtador oficial da belezanaweb
        'minhaloja.natura.com', 'www.minhaloja.natura.com',
    ]

    # Ficha tecnica / especificacoes: NAO vem no JSON-LD, entao e raspada do DOM.
    # A estrutura muda por loja (mas todas sao chave/valor -> get_pairs do BaseStore).
    # {substring do host: cfg do get_pairs}. 'skip' = rotulos a ignorar.
    _SPECS_POR_DOMINIO = {
        'epocacosmeticos': {'container': 'body', 'block': '[data-specification]',
                            'key': '[data-title]'},
        'belezanaweb': {'container': '.datasheet-characteristics', 'block': '.info-line',
                        'key': '.info-label', 'skip': ['Categorias']},
        'zzmall': {'container': '.product-features__list',
                   'block': '.product-features__list__item', 'key': 'span'},
        # Natura: acordeao "gota olfativa" (perfumes) / "caracteristicas" (demais).
        # Cada par e um <div class="relative flex"> com <span><span>rotulo</span>:
        # <span>valor</span></span>; o 'key' pega o primeiro span interno (o
        # .first do get_pairs), e o valor sobra como ": valor" -- o _specs limpa
        # o ":" da frente. Itens sem valor ("cruelty free") caem fora sozinhos.
        'natura.com': {'container': '[role="region"]', 'block': 'div.relative.flex',
                       'key': 'span > span'},
    }

    baixar_imagens = True
    post_load_wait = 2000
    # ready_selector fica None: a deteccao de "pagina sem produto" e feita pelo
    # hook pagina_sem_produto() (ausencia de Product no JSON-LD), nao por CSS.
    ready_selector = None

    # JS unico que extrai tudo que precisamos do DOM ja renderizado. Devolvido ao
    # Python, que faz o parse do JSON-LD (mais facil de manter que em JS).
    _JS = r"""
    () => {
      const out = { url: location.href, title: document.title };
      const ogType = document.querySelector('meta[property="og:type"]');
      out.ogType = ogType ? ogType.content : '';
      const mp = document.querySelector('meta[property="product:price:amount"]');
      out.metaPrice = mp ? mp.content : '';
      const ogImg = document.querySelector('meta[property="og:image"]');
      out.ogImage = ogImg ? ogImg.content : '';
      out.jsonld = [...document.querySelectorAll('script[type="application/ld+json"]')]
          .map(s => s.textContent);
      out.cssBreadcrumb = [...document.querySelectorAll(
          '[class*=readcrumb] a, [class*=readcrumb] span, nav[aria-label*=readcrumb] a')]
          .map(a => (a.textContent || '').trim()).filter(Boolean);
      // Galeria: <img> cujo src aponta para um repositorio de imagem de produto
      // (VTEX: /arquivos/ids/ ; Hybris: sys_master ; Salesforce/Natura:
      // demandware.static). Pega src / data-src / srcset. O filtro por SKU em
      // _urls_imagens e quem descarta recomendacoes/variantes.
      const urls = new Set();
      document.querySelectorAll('img').forEach(im => {
        const cand = [im.getAttribute('src'), im.getAttribute('data-src'),
                      im.getAttribute('data-zoom'),
                      (im.getAttribute('srcset') || '').split(',').pop().trim().split(' ')[0]];
        cand.forEach(u => {
          if (u && (u.includes('/arquivos/ids/') || u.includes('sys_master')
                    || u.includes('demandware.static'))) urls.add(u);
        });
      });
      out.gallery = [...urls];
      return out;
    }
    """

    # --- extracao / parse -------------------------------------------------
    def _dados(self, page):
        try:
            raw = page.evaluate(self._JS)
        except Exception:
            return {}
        produto, breadcrumb = None, []
        for bloco in raw.get('jsonld') or []:
            try:
                obj = json.loads(bloco)
            except Exception:
                continue
            for o in (obj if isinstance(obj, list) else [obj]):
                if not isinstance(o, dict):
                    continue
                tipo = str(o.get('@type', '')).lower()
                if tipo in self._TIPOS_PRODUTO and produto is None:
                    produto = o
                elif tipo == 'breadcrumblist' and not breadcrumb:
                    breadcrumb = [
                        (x.get('name') or (x.get('item') or {}).get('name') or '')
                        for x in (o.get('itemListElement') or [])
                    ]
        raw['produto'] = produto
        raw['breadcrumb'] = [b for b in breadcrumb if b]
        return raw

    @staticmethod
    def _tonum(x):
        try:
            return float(str(x).replace(',', '.'))
        except (TypeError, ValueError):
            return None

    def _precos(self, offers):
        # Percorre Offer / AggregateOffer (dict ou lista, aninhados) e devolve
        # (preco_a_pagar, preco_original). preco = menor price/lowPrice; original =
        # maior highPrice, so quando for de fato > preco (senao nao ha desconto).
        precos, highs = [], []

        def walk(o):
            if isinstance(o, list):
                for x in o:
                    walk(x)
                return
            if not isinstance(o, dict):
                return
            for chave in ('price', 'lowPrice'):
                if o.get(chave) not in (None, ''):
                    precos.append(o[chave])
            if o.get('highPrice') not in (None, ''):
                highs.append(o['highPrice'])
            if o.get('offers'):
                walk(o['offers'])
            # ProductGroup: os precos podem estar nas variacoes.
            for v in (o.get('hasVariant') or []):
                walk(v)

        walk(offers)
        pn = [n for n in (self._tonum(p) for p in precos) if n is not None]
        hn = [n for n in (self._tonum(h) for h in highs) if n is not None]
        preco = min(pn) if pn else None
        high = max(hn) if hn else None
        original = high if (high and preco and high > preco) else None
        return preco, original

    @staticmethod
    def _texto_limpo(valor):
        # Descricao/titulo do Product pode vir com HTML (ex.: "<Strong>...") e/ou
        # entidades (ex.: belezanaweb manda "L&#39;Oreal" no name/description).
        # Remove tags e decodifica entidades.
        if not valor:
            return ''
        return normalize_text(html.unescape(re.sub(r'<[^>]+>', ' ', str(valor))))

    @staticmethod
    def _marca(brand):
        if isinstance(brand, dict):
            return brand.get('name') or ''
        return brand or ''

    # --- hooks do fluxo ---------------------------------------------------
    def nome_loja(self, url=None):
        host = urlparse(url or '').netloc.lower()
        for sub, nome in self._NOMES_POR_DOMINIO.items():
            if sub in host:
                return nome
        return self.nome

    def prepare(self, page):
        # Rola ate o fim e volta ao topo antes de capturar. A epoca so RENDERIZA
        # a ficha tecnica ([data-specification]) quando o bloco entra na
        # viewport: sem a rolagem, lst_Product_Detalhes_tecnicos vinha vazio
        # (0 pares onde a pagina tem 6-11). Nas outras lojas da store a ficha ja
        # vem no HTML inicial, entao rolar e inofensivo (zzmall 2 e Natura 5
        # pares, iguais antes e depois). Best-effort: falha de rolagem nao
        # derruba a captura.
        try:
            page.wait_for_timeout(1200)   # deixa o layout inicial montar
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(1800)   # tempo do bloco lazy renderizar
            page.mouse.wheel(0, -6000)
            page.wait_for_timeout(300)
        except Exception:
            pass

    def pagina_sem_produto(self, page):
        # Sem Product no JSON-LD e sem og:type de produto -> nao e pagina de
        # produto (link de colecao/campanha, ou pagina bloqueada). main.py marca
        # 'pagina_sem_produto' em vez de gravar uma captura vazia como 'ok'.
        d = self._dados(page)
        if d.get('produto'):
            return False
        return 'product' not in str(d.get('ogType', '')).lower()

    def _specs(self, page, url):
        # Ficha tecnica do DOM (get_pairs) segundo a cfg do dominio. Limpa o ":"
        # final dos rotulos (epoca "Tipo De Pele:", zzmall "Marca:") para nao virar
        # "rotulo:: valor" na gravacao. Best-effort: sem cfg ou em erro -> [].
        host = urlparse(url).netloc.lower()
        cfg = next((c for sub, c in self._SPECS_POR_DOMINIO.items() if sub in host), None)
        if not cfg:
            return []
        try:
            pares = self.get_pairs(page, cfg)
        except Exception:
            return []
        limpos = []
        for par in pares:
            chave = (par.get('key') or '').rstrip(': ').strip()
            # O ":" pode ficar do lado do VALOR quando o separador esta solto
            # entre os spans (Natura: "<span>genero</span>: <span>feminino</span>").
            valor = (par.get('value') or '').lstrip(': ').strip()
            if chave and valor:
                limpos.append({'key': chave, 'value': valor})
        return limpos

    def capture(self, page):
        d = self._dados(page)
        p = d.get('produto') or {}

        preco, original = self._precos(p)
        if preco is None and d.get('metaPrice'):
            preco = self._tonum(d['metaPrice'])

        titulo = self._texto_limpo(p.get('name'))
        if not titulo:  # fallback: og:title sem o sufixo " | Loja"
            titulo = normalize_text(re.split(r'\s*[|–-]\s*', d.get('title') or '')[0])

        # Categorias: BreadcrumbList do JSON-LD (tira o ultimo = o proprio produto);
        # fallback no breadcrumb do DOM. Em ambos: decodifica entidades, descarta o
        # rotulo generico de "inicio" e remove qualquer item igual ao titulo (a
        # belezanaweb, num ProductGroup, poe o produto como ultimo item).
        categorias = d.get('breadcrumb') or []
        if categorias and p:
            categorias = categorias[:-1]  # ultimo item = nome do produto
        if not categorias:
            categorias = d.get('cssBreadcrumb') or []
        titulo_norm = titulo.lower()
        categorias = [
            html.unescape(c) for c in categorias
            if c and c.strip().lower() not in self._CATEG_GENERICAS
            and normalize_text(html.unescape(c)).lower() != titulo_norm
        ]

        rating = p.get('aggregateRating') or {}

        out = {
            'lst_categorias': categorias,
            'produto_titulo': normalize_text(titulo),
            'produto_descricao': self._texto_limpo(p.get('description')),
            'preco_1': normalize_price(str(preco)) if preco is not None else '',
            'preco_original': normalize_price(str(original)) if original is not None else '',
            'avaliacao_nota': str(rating.get('ratingValue') or '') if rating else '',
            'avaliacao_quantidade': str(
                rating.get('ratingCount') or rating.get('reviewCount') or '') if rating else '',
            'lst_Product_Detalhes_tecnicos': self._specs(page, d.get('url') or ''),
        }
        return out

    def _urls_imagens(self, page):
        d = self._dados(page)
        p = d.get('produto') or {}
        sku = str(p.get('sku') or '').strip()

        # Canonicas: a(s) imagem(ns) do Product no JSON-LD + og:image.
        urls = []
        img = p.get('image')
        if isinstance(img, list):
            urls += [u for u in img if isinstance(u, str)]
        elif isinstance(img, str):
            urls.append(img)
        if d.get('ogImage'):
            urls.append(d['ogImage'])

        # Galeria do DOM: SO as que contem o SKU do produto. Sem esse filtro o
        # scan traz thumbnails de recomendacoes (epoca) e de outras cores/variantes
        # (zzmall). Se o SKU nao aparece nas URLs da loja, a galeria e descartada
        # e ficamos apenas com as canonicas.
        if sku:
            urls += [u for u in (d.get('gallery') or []) if sku in u]
        # Dedup pela URL sem query string, preservando a ordem.
        vistos, out = set(), []
        for u in urls:
            base = u.split('?')[0]
            if base and not base.startswith('data:') and base not in vistos:
                vistos.add(base)
                out.append(u)
        return out

    def get_images(self, page, folder):
        urls = self._urls_imagens(page)
        if not urls:
            return 0
        os.makedirs(folder, exist_ok=True)
        contador = 0
        for u in urls:
            ext = u.split('?')[0].rsplit('.', 1)[-1][:4] or 'jpg'
            contador += 1
            download_image(u, os.path.join(folder, f'img_{contador}.{ext}'))
        return contador

    # --- contrato de colunas ---------------------------------------------
    def output_columns(self):
        return [
            'lst_categorias', 'produto_titulo', 'produto_descricao',
            'preco_1', 'preco_original', 'avaliacao_nota', 'avaliacao_quantidade',
            'lst_Product_Detalhes_tecnicos',
        ]

    def output_columns_implemented(self):
        return True
