import re

from core.base_store import BaseStore

# Caminho de pagina de PRODUTO (com o ASIN de 10 caracteres) -- ver
# AmazonStore.pagina_sem_produto.
_URL_PRODUTO = re.compile(r'/(?:dp|gp/product|gp/aw/d)/[A-Z0-9]{10}', re.IGNORECASE)

# Precos usam uniao (virgula) para cobrir os dois conteineres que a Amazon
# alterna por produto:
#   #corePriceDisplay_desktop_feature_div  e  #corePrice_feature_div
PRICE = '#corePriceDisplay_desktop_feature_div, #corePrice_feature_div'

# A Amazon usa classes semanticas "apex" estaveis para distinguir os 3 precos
# (validado ao vivo 2026-07-12):
#   apex-pricetopay-value    -> preco a pagar (atual)
#   apex-priceperunit-value  -> preco por unidade (ex.: "R$0,28"/ml) [tb tem a-text-price]
#   data-a-strike="true"     -> preco original riscado ("De: R$ X"); vem num blob ARIA
PAY = f'{PRICE} span.a-price.apex-pricetopay-value'
PER_UNIT = f'{PRICE} span.a-price.apex-priceperunit-value'
STRIKE = f'{PRICE} span.a-price[data-a-strike="true"] .a-offscreen'
# Extrai so o valor ("114,99") do blob do preco riscado (mesmo formato do preco_de da origem)
RE_DE = r'De:\s*R\$\s*([\d.,]+)'
# Guard: na variante "rica" a Amazon renderiza uma copia oculta onde varios
# precos colapsam num blob. So aceita o valor se o texto for UM preco limpo
# (ancorado), senao devolve vazio (produto sem aquele preco).
RE_PRECO = r'^(R\$\s?[\d.,]+)$'
# .a-price-whole engloba o .a-price-decimal, entao o inteiro vem com o separador
# colado ("27," / "1.234,"). Pega so os digitos do inteiro (com milhar): "27" / "1.234".
RE_INTEIRO = r'(\d[\d.]*\d|\d)'
# Nota de avaliacao vem "4,2 de 5 estrelas" -> extrai so "4,2".
RE_NOTA = r'([\d,]+)'
# pais_origem vem com o rotulo colado ("País de origem : Brasil") -> so o valor.
RE_PAIS = r'[:：]\s*(.+)$'


class AmazonStore(BaseStore):
    nome = 'amazon'
    nome_exibicao = 'Amazon'
    dominios = ['www.amazon.com.br', 'amazon.com.br', 'amzn.divulguei.app','link.amazon']

    categorias_selector = '#wayfinding-breadcrumbs_feature_div ul li'

    # "Sobre este item"
    lists = {
        'lst_detalhes_produtos': {'container': '#feature-bullets', 'item': '.a-list-item'},
    }

    # Cada campo tem uma CADEIA DE FALLBACK cobrindo os layouts da Amazon:
    #   Layout A (fixo):     #productDetails_techSpec_section_1 / #productDetails_detailBullets_sections1
    #   Layout B (expander): #prodDetails com tabelas .prodDetTable (colunas Left/Right)
    #   Layout C (nao-padrao / "Principais destaques"): tabela product-overview-classic
    #       em #topHighlight (ex.: ISDIN, Avene) — ultimo fallback das 3 colunas.
    TOP_HIGHLIGHT = '#topHighlight table.a-normal'
    tables = {
        'lst_Product_Detalhes_tecnicos': [
            '#productDetails_techSpec_section_1',
            '#productDetails_expanderTables_depthLeftSections table.prodDetTable',
            TOP_HIGHLIGHT,
        ],
        'lst_Product_Informacoes_adicionais': [
            '#productDetails_detailBullets_sections1',
            '#productDetails_expanderTables_depthRightSections table.prodDetTable',
            '#detailBullets_feature_div',
            TOP_HIGHLIGHT,
        ],
        # Tabela "glance" do topo (class a-normal a-spacing-micro): Marca/Peso/Forma...
        'lst_Product_Detalhes': [
            '#productOverview_feature_div',
            TOP_HIGHLIGHT,
        ],
    }

    baixar_imagens = True
    # Galeria por URL, sem clicar em nada (validado no HTML real em 2026-09-11,
    # amazon_dump_galeria.py -> destino/amazon_galeria_dump.html).
    #
    # O modo antigo clicava no <input> de cada miniatura p/ trocar a foto
    # grande. A Amazon trocou esse <input> por <button> (as miniaturas de hoje
    # tem input=0) e o clique passou a esperar o timeout inteiro sete vezes por
    # oferta: ~105s por pagina, zero imagem e nenhum aviso. Pior, quando
    # funcionava o mesmo laco rebaixava TODAS as fotos ja carregadas a cada
    # clique -- 27 arquivos para 6 imagens distintas.
    #
    # Dentro de #imageBlock cada foto da galeria traz suas resolucoes num JSON
    # no atributo data-a-dynamic-image; o escopo #imageBlock e essencial: o
    # mesmo atributo aparece nos carrosseis de "quem viu, viu" e traria fotos de
    # OUTROS produtos.
    img_urls_selector = '#imageBlock [data-a-dynamic-image]'
    img_urls_json_attr = 'data-a-dynamic-image'

    # A Amazon e renderizada no servidor: campo que nao esta no HTML ao fim do
    # post_load_wait nao vai aparecer depois. Os 4s do padrao viravam 28s por
    # oferta so em campos opcionais ausentes (parcelamento, assinatura,
    # "enviado por").
    SCAN_TIMEOUT = 1200

    def pagina_sem_produto(self, page):
        """Pagina de produto da Amazon sempre tem o ASIN no caminho (/dp/,
        /gp/product/, /gp/aw/d/). Qualquer outra coisa -- /promotion/psp/,
        /events/ofertasmensais, /megaofertaprime, /deals, /primeday, home --
        e vitrine de campanha: ate 2026-10-09 passava como 'ok', sem titulo
        nem preco, e virava PRODUTO/OFERTA vazios (102 no historico)."""
        return not _URL_PRODUTO.search(page.url or '')

    def normalizar_url_imagem(self, url):
        """Tira o recorte de tamanho do nome do arquivo e devolve a foto
        original:

            .../I/71zU53m4T9L._AC_SX466_.jpg  ->  .../I/71zU53m4T9L.jpg

        A maior resolucao anunciada no data-a-dynamic-image e pequena (466px,
        42 KB); a original do mesmo arquivo tem 2560px e 143 KB (medido em
        11/09/2026). Se a original nao existir, core/base_store._download_urls
        volta sozinho para a URL que estava na pagina."""
        if not url or 'amazon.com/images/' not in url:
            return url
        base, _, arquivo = url.rpartition('/')
        partes = arquivo.split('.')
        # ['71zU53m4T9L', '_AC_SX466_', 'jpg'] -> so o nome e a extensao.
        if len(partes) < 3:
            return url
        return f'{base}/{partes[0]}.{partes[-1]}'

    arr_items_scan = [
        {"key": "produto_titulo", "by": "CSS_SELECTOR", "value": '#productTitle'},
        {"key": "produto_descricao", "by": "CSS_SELECTOR", "value": '#productDescription span'},
        # pais de origem: casa a linha do detailBullets pelo rotulo e pega o valor
        {"key": "pais_origem", "by": "CSS_SELECTOR", "value": '#detailBullets_feature_div li:has-text("País de origem") span:last-child', "regex": RE_PAIS},
        {"key": "avaliacao_nota", "by": "CSS_SELECTOR", "value": '#acrPopover .a-icon-alt', "regex": RE_NOTA},
        {"key": "avaliacao_quantidade", "by": "CSS_SELECTOR", "value": '#acrCustomerReviewText'},
        # preco a pagar (atual) — ancorado na classe semantica apex-pricetopay-value
        {"key": "preco_com_desconto_inteiro", "by": "CSS_SELECTOR", "value": f'{PAY} .a-price-whole', "regex": RE_INTEIRO},
        {"key": "preco_com_desconto_fracao", "by": "CSS_SELECTOR", "value": f'{PAY} .a-price-fraction'},
        {"key": "preco_1", "by": "CSS_SELECTOR", "value": f'{PAY} .a-offscreen', "price": True},
        {"key": "preco_2", "by": "CSS_SELECTOR", "value": f'{PAY} .a-offscreen', "price": True},
        {"key": "preco_11", "by": "CSS_SELECTOR", "value": f'{PAY} .a-price-whole', "regex": RE_INTEIRO},
        {"key": "preco_12", "by": "CSS_SELECTOR", "value": f'{PAY} .a-price-whole', "regex": RE_INTEIRO},
        {"key": "preco_simbolo", "by": "CSS_SELECTOR", "value": f'{PAY} .a-price-symbol'},
        # preco original / riscado — discrimina por data-a-strike e extrai o valor do "De:"
        {"key": "preco_original", "by": "CSS_SELECTOR", "value": STRIKE, "regex": RE_DE, "price": True},
        {"key": "preco_sem_desconto", "by": "CSS_SELECTOR", "value": STRIKE, "regex": RE_DE, "price": True},
        # preco por unidade — classe semantica apex-priceperunit-value (nao contamina o original)
        {"key": "preco_por_unidade", "by": "CSS_SELECTOR", "value": f'{PER_UNIT} .a-offscreen', "regex": RE_PRECO, "price": True},
        {"key": "preco_tipo_unidade", "by": "CSS_SELECTOR", "value": f'{PRICE} .apex-priceperunit-accessibility-label'},
        # parcelamento
        {"key": "condicoes_1", "by": "CSS_SELECTOR", "value": '#installmentCalculator_feature_div .a-text-bold'},
        {"key": "condicoes_2", "by": "CSS_SELECTOR", "value": '#installmentCalculator_feature_div'},
        # assinatura (Programe e Poupe)
        {"key": "preco_recorrencia_inteiro", "by": "CSS_SELECTOR", "value": '#sns-base-price .a-price-whole', "regex": RE_INTEIRO},
        {"key": "preco_recorrencia_fracao", "by": "CSS_SELECTOR", "value": '#sns-base-price .a-price-fraction'},
        {"key": "recorrencia_quantidade_minima_descricao", "by": "CSS_SELECTOR", "value": '#trigger_popover'},
        # "Espere e economize" (2026-09-28): 2a linha do acordeao de opcoes de
        # compra (a 1a e "Compra unica") com preco menor por entrega mais
        # lenta. Identificado pelo TEXTO da legenda ("economize"), nao pelo
        # indice (data-csa-c-buying-option-idx varia conforme quantas opcoes o
        # produto tem) -- escopo #buybox pra nao pegar "economize" solto em
        # outro widget da pagina (ex. banners de recomendacao). Ausente na
        # maioria dos produtos -- so aparece quando a Amazon oferece a opcao.
        {"key": "espere_economize", "by": "CSS_SELECTOR",
         "value": '#buybox h5:has-text("economize") .apex-pricetopay-value .a-offscreen', "price": True},
        # enviado / vendido por
        {"key": "enviado_por", "by": "CSS_SELECTOR", "value": '#fulfillerInfoFeature_feature_div .offer-display-feature-text-message'},
        {"key": "vendido_por", "by": "CSS_SELECTOR", "value": '#merchantInfoFeature_feature_div .offer-display-feature-text-message'},
    ]
