from core.base_store import BaseStore

# Mercado Livre: links de afiliado (meli.la) caem numa PAGINA DE PREVIA (social)
# com o botao "Ir para produto"; prepare() clica nele e (se houver) fecha o
# popup "Entendi". Depois captura a pagina do produto (ui-pdp-*).


class MercadoLivreStore(BaseStore):
    nome = 'mercadolivre'
    nome_exibicao = 'Mercado Livre'
    dominios = ['meli.la', 'www.mercadolivre.com.br', 'mercadolivre.com.br',
                'produto.mercadolivre.com.br',
                # encurtador oficial (mercadolivre.com/sec/<hash>), sem o .br
                'mercadolivre.com', 'www.mercadolivre.com']

    ready_selector = 'h1.ui-pdp-title'
    post_load_wait = 2500

    categorias_selector = '.andes-breadcrumb .andes-breadcrumb__link'

    # "Caracteristicas principais" (quando existe): cada <li> ja e o texto.
    lists = {
        'lst_detalhes_produtos': {'container': '#ui-vpp-highlighted-specs', 'item': None},
    }

    # Duas tabelas andes-table em #highlighted_specs_attrs: 1a = tecnicos, 2a =
    # informacoes adicionais. get_table usa th (rotulo) / td (valor).
    tables = {
        'lst_Product_Detalhes_tecnicos': ['#highlighted_specs_attrs table.andes-table >> nth=0'],
        'lst_Product_Informacoes_adicionais': ['#highlighted_specs_attrs table.andes-table >> nth=1'],
    }

    baixar_imagens = True
    img_urls_selector = '.ui-pdp-gallery__figure__image'
    img_urls_attr = 'data-zoom'

    arr_items_scan = [
        {"key": "produto_titulo", "by": "CSS_SELECTOR", "value": 'h1.ui-pdp-title'},
        {"key": "avaliacao_nota", "by": "CSS_SELECTOR", "value": '.ui-pdp-review__rating'},
        {"key": "avaliacao_quantidade", "by": "CSS_SELECTOR", "value": '.ui-pdp-review__amount'},
        # preco no atributo content do <meta> (ex.: "29.90")
        {"key": "preco_1", "by": "CSS_SELECTOR", "value": 'meta[itemprop="price"]', "attr": "content", "price": True},
        # Especificos do ML (colunas QT_OPINIOES/DS_AVALIACAO_GERAL, 2026-09-02).
        # So aparecem quando o produto tem opinioes suficientes p/ o resumo de IA
        # do ML gerar o widget -- ausente em produtos com poucas avaliacoes
        # (validado ao vivo: sem scroll, nao e lazy-render).
        {"key": "quantidade_opinioes", "by": "CSS_SELECTOR", "value": '.total-opinion'},
        {"key": "avaliacao_geral", "by": "CSS_SELECTOR",
         "value": '.ui-review-capability__summary__plain_text__summary_container'},
    ]

    # Anuncio que o vendedor tirou do ar: a pagina do produto CARREGA normal
    # (tem titulo, tem preco), mas exibe a tarja "Anúncio pausado" e nao da
    # para comprar. Capturar isso como oferta boa poluiria o feed -- vira
    # 'anuncio_pausado' (ST_CAPTURA='9') e o loop segue. ":has-text" e
    # case-insensitive e casa por trecho, entao "pausado" basta e evita
    # depender do acento.
    MSG_PAUSADO = '.andes-message__text:has-text("pausado")'

    def status_descarte(self, page):
        try:
            if page.locator(self.MSG_PAUSADO).count():
                return 'anuncio_pausado'
        except Exception:
            pass
        return None

    def prepare(self, page):
        # 1) fecha o popup "Entendi" se aparecer (so na 1a pagina, geralmente)
        try:
            pop = page.locator('button:has-text("Entendi"), .andes-button__content:has-text("Entendi")').first
            if pop.count():
                pop.click(timeout=3000)
                page.wait_for_timeout(500)
        except Exception:
            pass
        # 2) pagina de previa -> clica "Ir para produto" e espera o PDP
        try:
            if page.locator(self.ready_selector).count() == 0:
                link = page.locator('a:has-text("Ir para produto")').first
                if link.count():
                    link.click()
                    page.wait_for_selector(self.ready_selector, timeout=25000)
                    page.wait_for_timeout(1500)
        except Exception:
            pass
