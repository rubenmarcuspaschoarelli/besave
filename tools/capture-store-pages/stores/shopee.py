import os

from core.base_store import BaseStore
from core.images import download_image

# ATENCAO: a Shopee usa classes com hash (ex.: pyzxvq, FllsTu, k_fvNr, Ocv3B8)
# que MUDAM a cada deploy. Onde da, ancoramos em TEXTO (has-text "Avaliacoes",
# "Detalhes do Produto", "Descricao do produto", "Vendidos") ou em ids/classes
# semanticos (#sll2-normal-pdp-main, .page-product__breadcrumb) -- esses sobrevivem.
# Os seletores puramente por hash foram remapeados em 2026-07-23 (deploy anterior
# tinha quebrado preco/nota/avaliacoes/vendas/detalhes; titulo e breadcrumb ok).
# Fonte do remapeamento: destino/shopee_dump_635.html e _643.html (page.content()
# da sessao logada). REVALIDAR quando quebrar de novo -> rodar shopee_dump.py.
# Requer sessao logada (login manual no gate do main.py); sem login a Shopee
# redireciona para verify/traffic.


class ShopeeStore(BaseStore):
    nome = 'shopee'
    nome_exibicao = 'Shopee'
    dominios = ['s.shopee.com.br', 'www.shopee.com.br', 'shopee.com.br']

    # SPA: esperar o container do produto aparecer antes de capturar.
    ready_selector = '#sll2-normal-pdp-main'
    post_load_wait = 4000

    # Galeria (2026-10-08): cada miniatura e um bloco com um irmao
    # .thumbnail-selected-mask (classe semantica, sem hash). O item de VIDEO
    # (quando o anuncio tem, e sempre o 1o) traz o icone img[alt="icon video
    # play"] e a capa ..._cover -- pulado, senao a "1a foto" da oferta seria a
    # capa do video. O src da miniatura ja e a foto ORIGINAL (sem @resize).
    # Fonte: destino/shopee_dump_643.html.
    baixar_imagens = True
    img_urls_selector = ('#sll2-normal-pdp-main div:has(> .thumbnail-selected-mask)'
                         ':not(:has(img[alt*="video" i])) picture img')

    def get_images(self, page, folder):
        # A galeria da Shopee se redesenha sozinha (carrossel/lazyload): ler
        # item a item (.nth(i)) estoura timeout no meio. Le todos os src numa
        # chamada so e baixa na ordem, com o mesmo download/marca d'agua.
        os.makedirs(folder, exist_ok=True)
        try:
            page.wait_for_selector(self.img_urls_selector, timeout=10000)
        except Exception:  # noqa: BLE001
            return 0
        brutas = page.locator(self.img_urls_selector).evaluate_all(
            'els => els.map(e => e.getAttribute("src") || "")')
        vistos, counter = set(), 0
        for bruta in brutas:
            url = self.normalizar_url_imagem(bruta)
            limpo = url.split('?')[0]
            if not url or limpo.startswith('data:') or limpo in vistos:
                continue
            vistos.add(limpo)
            if download_image(url, os.path.join(folder, f'img_{counter + 1}.jpg')):
                counter += 1
        return counter

    def normalizar_url_imagem(self, url):
        # Segunda barreira contra o video: a capa (..._cover) ou o proprio
        # arquivo de midia (/mms/) nunca sao foto do produto. '' = pular.
        limpo = (url or '').split('?')[0]
        if limpo.endswith('_cover') or '/mms/' in limpo or '.mp4' in limpo:
            return ''
        return url

    # Breadcrumb: links + o <span> final (nome do produto). Semantico, estavel.
    categorias_selector = '.page-product__breadcrumb a, .page-product__breadcrumb span'

    # "Detalhes do Produto" -> lista chave/valor. Cada par e um bloco .c0ztn1 com
    # h3 = rotulo e um <div> = valor. Escopo pela seção cujo h2 = "Detalhes do
    # Produto" (has-text) p/ nao pegar a de "Descrição do produto" (mesmo .RNeUsI).
    pairs = {
        'lst_Product_Detalhes_tecnicos': {
            'container': '.cDKs6x:has(h2:has-text("Detalhes do Produto"))',
            'block': '.c0ztn1',
            'key': 'h3',
            # "Categoria" e um breadcrumb (varios <a> sem separador de texto ->
            # "ShopeeBeleza...") redundante com lst_categorias. Descartado.
            'skip': ['Categoria'],
        },
    }

    arr_items_scan = [
        {"key": "produto_titulo", "by": "CSS_SELECTOR", "value": '#sll2-normal-pdp-main h1'},
        # nota "4.8": 1o botao de avaliacao (a classe extra .JXtSdn.bv0Mz_ o
        # distingue do contador, que e so .FllsTu).
        {"key": "avaliacao_nota", "by": "CSS_SELECTOR", "value": '.FllsTu.JXtSdn.bv0Mz_'},
        # nº de avaliacoes "6,4mil": .FllsTu dentro do botao que contem "Avaliações".
        {"key": "avaliacao_quantidade", "by": "CSS_SELECTOR", "value": 'button:has-text("Avaliações") .FllsTu'},
        # preco "R$38,80" -> "38.80". Bloco aria-live do preco a pagar.
        {"key": "preco_1", "by": "CSS_SELECTOR", "value": '.pyzxvq.pw3J3G', "price": True},
        # descricao: conteudo (.RNeUsI) da seção cujo h2 = "Descrição do produto".
        {"key": "produto_descricao", "by": "CSS_SELECTOR", "value": '.cDKs6x:has(h2:has-text("Descrição do produto")) .RNeUsI'},
        # nº de vendas "5mil+" (Shopee-only): span dentro do bloco "... Vendidos".
        {"key": "quantidade_vendida", "by": "CSS_SELECTOR", "value": '.Ocv3B8 .PfWbfd'},
        # pais de origem: bloco de detalhe cujo h3 = "País de Origem".
        {"key": "pais_origem", "by": "CSS_SELECTOR", "value": '.c0ztn1:has(h3:has-text("País de Origem")) > div'},
    ]
