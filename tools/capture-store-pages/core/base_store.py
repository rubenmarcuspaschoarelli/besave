import json
import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.text_utils import normalize_text, normalize_price
from core.images import download_image


class BaseStore:
    """Mecanica generica de scraping de uma pagina de produto.

    Cada loja herda desta classe e declara apenas a CONFIG (dominios, PRICE,
    arr_items_scan, seletores de categorias/listas/tabelas/imagens). Quando a
    pagina de uma loja for estruturalmente diferente, o metodo especifico pode
    ser sobrescrito na subclasse.
    """

    # --- CONFIG (sobrescrever na subclasse) -------------------------------
    nome = ''
    # Nome COMERCIAL da loja, como o usuario escreve em conf/config.json ->
    # "lojas_ativas" (ex.: 'Mercado Livre' para nome='mercadolivre'). Vazio ->
    # cai no `nome` interno. Ver nome_loja().
    nome_exibicao = ''
    dominios = []

    # Listas de chave/valor "planas" (cada item vira uma coluna no CSV de saida)
    arr_items_scan = []

    # Categorias do produto (breadcrumb)
    categorias_selector = None

    # Listas simples (ex.: "Sobre este item"): {coluna: {container, item}}
    lists = {}

    # Tabelas chave/valor com CADEIA DE FALLBACK: {coluna: [sel1, sel2, ...]}
    # O primeiro seletor da cadeia que retornar linhas vence.
    tables = {}

    # Pares chave/valor a partir de blocos <div> repetidos (sites que NAO usam
    # <table>, ex.: Shopee): {coluna: {container, block, key}}
    # key = seletor do rotulo dentro do bloco; valor = resto do texto do bloco.
    pairs = {}

    # Imagens
    baixar_imagens = False
    # (a) por clique nas miniaturas (Amazon): thumbs + container visivel
    img_thumbs_selector = None
    img_container_selector = None
    # (b) por URL direta da galeria (Mercado Livre, Amazon): seletor de <img> +
    #     atributo com a URL (ex.: 'data-zoom'); fallback p/ 'src'.
    img_urls_selector = None
    img_urls_attr = None
    # (b2) quando o atributo nao guarda UMA url e sim um JSON {url: [larg, alt]}
    #      com as resolucoes disponiveis (Amazon: data-a-dynamic-image), daqui
    #      sai a MAIOR delas. Preferir sempre (b)/(b2) a (a): ler URL nao
    #      depende de clique, e clique em galeria de loja grande e frageil --
    #      foi assim que a Amazon parou de baixar imagem em 10/09/2026.
    img_urls_json_attr = None

    # Espera pos-navegacao: seletor que indica que a pagina do produto carregou
    # (SPA), e um tempo extra fixo (ms). Amazon nao precisa; Shopee sim.
    ready_selector = None
    post_load_wait = 2000

    # Timeout (ms) por elemento no scan de campos "planos". Cada campo AUSENTE
    # custa esse tempo inteiro (e uma pagina de produto tem varios campos
    # opcionais), entao loja renderizada no servidor pode -- e deve -- baixar
    # esse valor na subclasse; quem monta a pagina em JavaScript precisa dele
    # generoso.
    SCAN_TIMEOUT = 4000

    # Timeout (ms) do clique em miniatura no modo (a). Curto de proposito: se a
    # galeria mudou, o certo e falhar rapido e avisar, nao segurar a captura.
    TIMEOUT_CLIQUE_MINIATURA = 3000

    # --- helpers ----------------------------------------------------------
    def nome_loja(self, url=None):
        # Nome comercial desta loja. Recebe a URL porque uma store pode atender
        # VARIAS lojas de verdade (a SchemaOrgStore cobre epoca, zzmall,
        # belezanaweb e Natura) e cada uma tem o seu nome na lista de ativas.
        return self.nome_exibicao or self.nome

    @staticmethod
    def to_selector(by_type, value):
        # Traduz o formato antigo (Selenium) para um seletor do Playwright.
        if by_type == 'ID':
            return f'#{value}'
        elif by_type == 'CLASS_NAME':
            return '.' + '.'.join(value.split())
        elif by_type == 'XPATH':
            return f'xpath={value}'
        elif by_type in ('TAG_NAME', 'CSS_SELECTOR'):
            return value
        return None

    # --- mecanica de captura ---------------------------------------------
    def get_categorias(self, page):
        if not self.categorias_selector:
            return []
        try:
            items = page.locator(self.categorias_selector)
            out = []
            for i in range(items.count()):
                t = normalize_text(items.nth(i).inner_text())
                if t and len(t) > 2:
                    out.append(t)
            return out
        except Exception:
            return []

    def get_list(self, page, container_sel, item_sel):
        try:
            cont = page.locator(container_sel).first
            if cont.count() == 0:
                return []
            items = cont.locator('ul').first.locator('li')
            out = []
            for i in range(items.count()):
                # item_sel None: o texto esta no proprio <li> (ex.: Mercado Livre).
                el = items.nth(i).locator(item_sel).first if item_sel else items.nth(i)
                if el.count() > 0:
                    t = normalize_text(el.inner_text())
                    if t:
                        out.append(t)
            return out
        except Exception:
            return []

    def prepare(self, page):
        # Hook chamado apos o goto e ANTES da captura. Padrao: nada. Lojas com
        # interstitial/popup sobrescrevem (ex.: Mercado Livre fecha o popup e
        # clica "Ir para produto").
        pass

    def pagina_sem_produto(self, page):
        # Hook: True quando a pagina navegada NAO e de produto (ex.: link de
        # colecao/campanha) mesmo tendo carregado sem erro. Padrao: False. Lojas
        # que so sabem disso apos inspecionar o DOM sobrescrevem (ex.: a store
        # schema.org marca True quando nao ha Product no JSON-LD). Complementa a
        # deteccao por ready_selector ausente feita no main.py.
        return False

    def status_descarte(self, page):
        # Hook: a pagina E de produto, mas a oferta nao serve -- devolve o
        # motivo (vira DS_CAPTURA com ST_CAPTURA='9' e o loop pula p/ a
        # proxima). Padrao: None. Diferente de pagina_sem_produto(), que diz
        # "isto nem e pagina de produto"; aqui o produto existe e foi o
        # ANUNCIO que saiu do ar (ex.: "Anuncio pausado" no Mercado Livre).
        return None

    def get_table(self, page, chain):
        # Percorre a cadeia de seletores; retorna as linhas do PRIMEIRO seletor
        # que produzir resultado (robusto p/ os varios layouts da Amazon).
        for sel in chain:
            try:
                container = page.locator(sel)
                if container.count() == 0:
                    continue
                rows = container.locator('tr')
                result = []
                for i in range(rows.count()):
                    cells = rows.nth(i).locator('th, td')
                    if cells.count() >= 2:
                        k = normalize_text(cells.nth(0).inner_text())
                        v = self._cell_value(cells.nth(1))
                        if k:
                            result.append({'key': k, 'value': v})
                if result:
                    return result
            except Exception:
                continue
        return []

    @staticmethod
    def _cell_value(cell):
        # Extrai o texto da celula de VALOR removendo <script>/<style> (a Amazon
        # injeta JS em algumas celulas, ex.: "Vantagens do produto",
        # "Avaliacoes de clientes") e preferindo o texto completo
        # (.a-truncate-full) quando o valor esta truncado ("Ver mais").
        try:
            txt = cell.evaluate(
                "el => { const c = el.cloneNode(true);"
                " c.querySelectorAll('script,style,noscript').forEach(n => n.remove());"
                " const full = c.querySelector('.a-truncate-full');"
                " return (full ? full.textContent : c.textContent) || ''; }"
            )
        except Exception:
            txt = cell.inner_text()
        return normalize_text(txt)

    def scan_elements(self, page):
        # Campos "planos" (arr_items_scan) -> dict {coluna: valor}. Campo ausente
        # fica string vazia (ausencia real, nao quebra o fluxo).
        res = {}
        for it in self.arr_items_scan:
            selector = self.to_selector(it['by'], it['value'])
            if selector is None:
                continue
            elem = page.locator(selector).first
            try:
                elem.wait_for(state='attached', timeout=self.SCAN_TIMEOUT)
            except PlaywrightTimeoutError:
                res.setdefault(it['key'], '')
                continue
            try:
                # 'attr' opcional: pega um atributo em vez do texto (ex.: preco do
                # Mercado Livre esta em <meta itemprop="price" content="29.90">).
                if it.get('attr'):
                    v = elem.get_attribute(it['attr']) or ''
                else:
                    v = elem.inner_text()
                    if not v:
                        v = elem.get_attribute('innerHTML') or ''
                v = normalize_text(v)
                # 'regex' opcional: extrai o grupo 1 do texto capturado. Serve p/
                # campos onde o elemento traz um blob (ex.: preco riscado da Amazon
                # vem "...De: R$ 114,99..." e queremos so "114,99").
                if it.get('regex'):
                    m = re.search(it['regex'], v)
                    v = m.group(1) if m else ''
                # 'price' opcional: padroniza (remove R$, decimal com ".").
                if it.get('price'):
                    v = normalize_price(v)
                res[it['key']] = v
            except Exception:
                res.setdefault(it['key'], '')
        return res

    def get_images(self, page, folder):
        # Modo (b): URLs diretas da galeria (Mercado Livre).
        if self.img_urls_selector:
            return self._download_urls(page, folder)
        # Modo (a): clique nas miniaturas (Amazon).
        if not self.img_thumbs_selector or not self.img_container_selector:
            return 0
        os.makedirs(folder, exist_ok=True)
        thumbs = page.locator(self.img_thumbs_selector).locator('li')
        counter = 0
        falhas = 0
        for index in range(thumbs.count()):
            thumb = thumbs.nth(index)
            try:
                # TIMEOUT_CLIQUE_MINIATURA, e nao o timeout padrao da pagina: em
                # 10/09/2026 a Amazon trocou o <input> da miniatura por <button>
                # e cada clique passou a esperar os 15s inteiros, sete vezes por
                # oferta, dentro do 'except' silencioso abaixo -- ~105s por
                # pagina e nenhuma imagem, sem uma linha de log.
                thumb.locator('input').first.click(
                    timeout=self.TIMEOUT_CLIQUE_MINIATURA)
                try:
                    container = page.locator(self.img_container_selector).first
                    container.wait_for(state='visible', timeout=20000)
                    images = container.locator('img')
                    for j in range(images.count()):
                        img_url = images.nth(j).get_attribute('src')
                        if not img_url:
                            continue
                        img_extension = img_url.split('?')[0].split('.')[-1]
                        counter += 1
                        filename = os.path.join(folder, f"img_{counter}.{img_extension}")
                        download_image(img_url, filename)
                except PlaywrightTimeoutError:
                    pass
            except Exception:
                falhas += 1
        if falhas:
            # Silencio aqui foi o que escondeu a quebra da Amazon por um dia:
            # agora a galeria que nao responde ao clique aparece no log.
            print(f'[{self.nome}] {falhas} de {thumbs.count()} miniatura(s) nao '
                  f'aceitaram clique ({self.img_thumbs_selector}) -- galeria '
                  f'mudou de marcacao?')
        return counter

    def normalizar_url_imagem(self, url):
        """Gancho por loja p/ trocar a URL lida na pagina pela versao que se
        quer baixar (a Amazon usa p/ tirar o recorte de tamanho e pegar a foto
        original). Por padrao, devolve a URL como veio."""
        return url

    @staticmethod
    def _maior_do_json(texto):
        """URL de maior area de um JSON {url: [largura, altura]} (Amazon
        data-a-dynamic-image). '' se o atributo nao for esse JSON."""
        try:
            mapa = json.loads(texto or '')
        except Exception:  # noqa: BLE001
            return ''
        if not isinstance(mapa, dict):
            return ''
        melhor, maior = '', -1
        for url, dim in mapa.items():
            try:
                area = int(dim[0]) * int(dim[1])
            except Exception:  # noqa: BLE001
                area = 0
            if area > maior:
                melhor, maior = url, area
        return melhor

    def _url_do_elemento(self, el):
        """URL da imagem de UM elemento da galeria, na ordem: JSON de
        resolucoes (b2) -> atributo declarado (b) -> src."""
        if self.img_urls_json_attr:
            url = self._maior_do_json(el.get_attribute(self.img_urls_json_attr))
            if url:
                return url
        if self.img_urls_attr:
            url = el.get_attribute(self.img_urls_attr)
            if url:
                return url
        return el.get_attribute('src') or ''

    def _download_urls(self, page, folder):
        # Baixa imagens pegando a URL de cada <img> da galeria. Deduplica pela
        # URL sem query string -- JA NORMALIZADA, senao duas resolucoes da mesma
        # foto passariam como imagens diferentes.
        os.makedirs(folder, exist_ok=True)
        imgs = page.locator(self.img_urls_selector)
        vistos = []
        counter = 0
        for i in range(imgs.count()):
            bruta = self._url_do_elemento(imgs.nth(i))
            url = self.normalizar_url_imagem(bruta)
            limpo = url.split('?')[0]
            if not url or limpo.startswith('data:') or limpo in vistos:
                continue
            vistos.append(limpo)
            # Sem extensao no ultimo trecho da URL (Shopee: .../file/<hash>)
            # -> 'jpg', senao o rsplit devolveria o proprio dominio.
            ultimo = limpo.rsplit('/', 1)[-1]
            ext = (ultimo.rsplit('.', 1)[-1][:4] if '.' in ultimo else '') or 'jpg'
            destino = os.path.join(folder, f'img_{counter + 1}.{ext}')
            # So conta o que virou arquivo: download_image recusa pixel
            # transparente, pagina de erro e HTTP != 200 (ver core/images.py).
            # Se a URL normalizada nao existir, a da propria pagina ainda vale:
            # melhor uma foto menor do que nenhuma.
            if (download_image(url, destino)
                    or (bruta != url and download_image(bruta, destino))):
                counter += 1
        return counter

    def get_pairs(self, page, cfg):
        # Extrai chave/valor de blocos <div> repetidos (Shopee nao usa <table>).
        # key = seletor do rotulo dentro do bloco; valor = resto do texto.
        # 'skip' (opcional): rotulos a IGNORAR (case-insensitive), ex.: "Categoria",
        # cujo valor e um breadcrumb redundante com lst_categorias.
        skip = {s.strip().lower() for s in cfg.get('skip', [])}
        try:
            blocks = page.locator(cfg['container']).locator(cfg['block'])
            out = []
            for i in range(blocks.count()):
                b = blocks.nth(i)
                kel = b.locator(cfg['key']).first
                if kel.count() == 0:
                    continue
                k = normalize_text(kel.inner_text())
                if k and k.lower() not in skip:
                    out.append({'key': k, 'value': self._pair_value(b, cfg['key'])})
            return out
        except Exception:
            return []

    @staticmethod
    def _pair_value(block, key_sel):
        # Valor = texto do bloco SEM o rotulo (remove o elemento da key) e sem
        # <script>/<style>.
        try:
            txt = block.evaluate(
                "(el, keySel) => { const c = el.cloneNode(true);"
                " c.querySelectorAll('script,style,noscript').forEach(n => n.remove());"
                " const k = c.querySelector(keySel); if (k) k.remove();"
                " return c.textContent || ''; }",
                key_sel,
            )
        except Exception:
            txt = block.inner_text()
        return normalize_text(txt)

    def capture(self, page):
        # Orquestra a captura e devolve um dict plano coluna -> valor.
        # Valores de lista/tabela sao serializados em JSON no csv_io.
        out = {'lst_categorias': self.get_categorias(page)}
        for coluna, cfg in self.lists.items():
            out[coluna] = self.get_list(page, cfg['container'], cfg['item'])
        for coluna, chain in self.tables.items():
            out[coluna] = self.get_table(page, chain)
        for coluna, cfg in self.pairs.items():
            out[coluna] = self.get_pairs(page, cfg)
        out.update(self.scan_elements(page))
        return out

    def output_columns(self):
        # Ordem das colunas capturadas por esta loja (para o cabecalho do CSV).
        cols = ['lst_categorias']
        cols += list(self.lists.keys())
        cols += list(self.tables.keys())
        for coluna in self.pairs.keys():
            if coluna not in cols:
                cols.append(coluna)
        for it in self.arr_items_scan:
            if it['key'] not in cols:
                cols.append(it['key'])
        return cols

    def output_columns_implemented(self):
        # Loja "implementada" = tem alguma config de captura (nao e placeholder).
        return bool(self.arr_items_scan or self.tables or self.lists or self.pairs)
