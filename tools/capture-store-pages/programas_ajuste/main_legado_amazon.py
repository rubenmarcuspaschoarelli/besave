import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
import requests
import re

# N O T A S
# API para produtos da amazon
#  Exemplo: https://graphql.canopyapi.co/?query=query+amazonProduct+%7B%0A++amazonProduct%28input%3A+%7BasinLookup%3A+%7Basin%3A+%22B0D1XD1ZV3%22%7D%7D%29+%7B%0A++++title%0A++++brand%0A++++mainImageUrl%0A++++ratingsTotal%0A++++rating%0A++++price+%7B%0A++++++display%0A++++++currency%0A++++++symbol%0A++++++value%0A++++%7D%0A++++isPrime%0A++++isNew%0A++++countryOfOrigin%0A++++packageWeight%0A++++optimizedTitle%0A++++optimizedDescription%0A++++url%0A++++subtitle%0A++%7D%0A++amazonProductCategory%28input%3A+%7BcategoryId%3A+%22%22%7D%29+%7B%0A++++name%0A++++subcategories+%7B%0A++++++name%0A++++%7D%0A++%7D%0A%7D
#  api developer da aws: https://developer.amazonservices.com/index.html
# http://api-doc.axesso.de/


# Traduz o "ByType" do formato antigo (Selenium) para um seletor do Playwright.
# Mantido para nao precisar reescrever as listas de arrItemsScan.
def to_selector(by_type, value):
    if by_type == 'ID':
        return f'#{value}'
    elif by_type == 'CLASS_NAME':
        # Playwright usa "." para classe; troca espacos por "." para classes compostas
        return '.' + '.'.join(value.split())
    elif by_type == 'XPATH':
        return f'xpath={value}'
    elif by_type == 'TAG_NAME':
        return value
    elif by_type == 'CSS_SELECTOR':
        return value
    else:
        return None


# Função para baixar as imagens
def download_image(img_url, filename):
    try:
        img_data = requests.get(img_url, timeout=30).content
        with open(filename, 'wb') as file:
            file.write(img_data)
    except Exception as e:
        print(f"Erro ao salvar a imagem {filename}: {e}")


def extract_substrings(input_string, start_substring, end_substring):
    # Lista para armazenar as substrings encontradas
    substrings = []

    # Começamos a busca a partir do índice 0
    start_index = 0

    while True:
        # Encontra a primeira ocorrência de 'start_substring' a partir de start_index
        start_index = input_string.find(start_substring, start_index)

        # Se não encontrar mais o 'start_substring', interrompe o loop
        if start_index == -1:
            break

        # Encontrar a ocorrência de 'end_substring' após o 'start_substring'
        end_index = input_string.find(end_substring, start_index + len(start_substring))

        # Se encontrar a 'end_substring', extraímos a substring
        if end_index != -1:
            # Substring incluindo o 'start_substring' até o 'end_substring'
            substring = input_string[start_index + len(start_substring): end_index]
            substrings.append(start_substring + substring + end_substring)

            # Atualiza o start_index para continuar a busca após o 'end_substring'
            start_index = end_index + len(end_substring)
        else:
            # Se não encontrar o 'end_substring', interrompe o loop
            break

    return substrings


def get_amazon_images(page, folder_path):
    # Cria o diretório para salvar as imagens
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    thumbs = page.locator('#altImages ul').locator('li')

    img_counter = 0
    for index in range(thumbs.count()):
        thumb = thumbs.nth(index)
        try:
            button = thumb.locator('input').first
            button.click()

            try:
                # ":visible" ignora o <ul> template oculto (main-image-container
                # tem 2 <ul>: um template escondido e o visivel com as imagens)
                container = page.locator('#main-image-container > ul:visible').first
                container.wait_for(state='visible', timeout=20000)

                images = container.locator('img')
                for j in range(images.count()):
                    img_url = images.nth(j).get_attribute('src')
                    if not img_url:
                        continue
                    # Remove eventual query string antes de deduzir a extensao
                    clean_url = img_url.split('?')[0]
                    img_extension = clean_url.split('.')[-1]
                    img_counter += 1
                    filename = os.path.join(folder_path, f"img_{img_counter}.{img_extension}")
                    download_image(img_url, filename)

            except PlaywrightTimeoutError:
                print('nao encontrou a imagem')

        except Exception:
            print('nao encontrou o botao')


def normalize_text(v):
    # Colapsa quebras de linha / espacos repetidos em um unico espaco e remove
    # o espaco antes de virgula/ponto (ex.: preco "57\n," -> "57,").
    if not v:
        return v
    v = re.sub(r'\s+', ' ', v).strip()
    v = re.sub(r'\s+([,.])', r'\1', v)
    return v


def scanElements(page, arrItemsScan):
    lst = []
    for i in arrItemsScan:
        selector = to_selector(i['by'], i['value'])
        if selector is None:
            continue

        elem = page.locator(selector).first
        try:
            elem.wait_for(state='attached', timeout=5000)
        except PlaywrightTimeoutError:
            print(f'Nao achou {i["key"]} com o valor {i["value"]}')
            continue

        try:
            v = elem.inner_text()
            if not v:
                v = elem.get_attribute('innerHTML')

            r = {'key': i['key'], 'value': normalize_text(v)}
            lst.append(r)
        except Exception:
            print(f'Achou o elemento porem nao conseguiu pegar o valor: {i["key"]} com o valor {i["value"]}')
    return lst


def get_tables_amazon(page, elementId, ByType, elementKey, elementValue):
    lstResult = []

    selector = to_selector(ByType, elementId)
    if selector is None:
        return []

    try:
        elemTable = page.locator(selector).first
        rows = elemTable.locator('tr')

        for idx in range(rows.count()):
            row = rows.nth(idx)
            titulo = normalize_text(row.locator(elementKey).first.inner_text())
            valor = normalize_text(row.locator(elementValue).first.inner_text())
            r = {'key': titulo, 'value': valor}
            lstResult.append(r)
    except Exception:
        print('linha da tabela não encontrada')
    return lstResult


def get_list_item_amazon(page, elementId, ByType, idContent):
    lstResult = []

    selector = to_selector(ByType, elementId)
    if selector is None:
        return []

    try:
        elem_origem = page.locator(selector).first
        items = elem_origem.locator('ul').first.locator('li')

        for idx in range(items.count()):
            valor = items.nth(idx).locator('.' + idContent).first
            lstResult.append(normalize_text(valor.inner_text()))
    except Exception:
        print('linha da tabela não encontrada')

    return lstResult


folder_path_img = "amazon_1234/img"
folder_path_html = "amazon_1234/html"

with sync_playwright() as p:
    # headless=False abre o navegador (equivalente ao comportamento atual sem --headless)
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-gpu", "--no-sandbox"],
    )
    page = browser.new_page()
    # Timeout padrao para find/wait (equivalente ao implicitly_wait, mas em ms)
    page.set_default_timeout(15000)

    page.goto("https://www.amazon.com.br/gp/product/B0D8YZZ8Z4/ref=ewc_pr_img_1?smid=A2XNLIR2U695JM&psc=1")

    page_source = page.content()

    #  categorias do produto
    ul_element = page.locator('#wayfinding-breadcrumbs_feature_div ul')
    list_items = ul_element.locator('li')

    lstCategorias = []
    for idx in range(list_items.count()):
        texto = list_items.nth(idx).inner_text()
        if len(texto) > 2:
            lstCategorias.append(texto)

    print('lstCategorias -> ')
    print(lstCategorias)

    element_by_id = page.locator('#productTitle').first
    print(f" element_by_id.text: {element_by_id.inner_text()}")

    # Titulo (usa o #productTitle, que e estavel; o XPath absoluto antigo
    # quebrava a cada mudanca de layout da Amazon)
    try:
        element = page.locator('#productTitle').first
        element_text = element.inner_text(timeout=5000)
        print(f"Valor do elemento: {element_text}")
    except PlaywrightTimeoutError:
        print("Titulo (#productTitle) nao encontrado")

    # prime
    primes = page.locator('#prime-badge')
    for idx in range(primes.count()):
        print('prime---->')
        px = primes.nth(idx).get_attribute('innerHTML')
        print('prime---->')
        print(px)

    lst_detalhes_produtos = get_list_item_amazon(page, 'feature-bullets', 'ID', 'a-list-item')
    print('lst_detalhes_produtos---------------------->>>')
    print(lst_detalhes_produtos)

    lst_Product_Detalhes_tecnicos = get_tables_amazon(page, 'productDetails_techSpec_section_1', 'ID', 'th', 'td')
    print('lst_Product_Details---------------------->>>')
    print(lst_Product_Detalhes_tecnicos)

    lst_Product_Informacoes_adicionais = get_tables_amazon(page, 'productDetails_detailBullets_sections1', 'ID', 'th', 'td')
    print('lst_Product_Informacoes_adicionais---------------------->>>')
    print(lst_Product_Informacoes_adicionais)

    # <table class="a-normal a-spacing-micro">
    lst_Product_Detalhes = get_tables_amazon(page, 'productDetails_detailBullets_sections1', 'ID', 'th', 'td')
    print('lst_Product_Informacoes_adicionais---------------------->>>')
    print(lst_Product_Detalhes)

    # ----------------------------------------------------------------------------------------------------------------------
    #  P R O D U T O
    # ----------------------------------------------------------------------------------------------------------------------
    # Seletores robustos: ancorados em IDs/classes estaveis da Amazon em vez de
    # caminhos posicionais (div[1]/span[3]/...). Os precos usam uniao (virgula)
    # para cobrir os dois conteineres que a Amazon alterna por produto:
    #   #corePriceDisplay_desktop_feature_div  e  #corePrice_feature_div
    PRICE = '#corePriceDisplay_desktop_feature_div, #corePrice_feature_div'
    arrItemsScan = [
        {"key": "produto_descricao", "by": "CSS_SELECTOR", "value": '#productDescription span'},
        # país de origem: casa a linha do detailBullets pelo rótulo e pega o valor
        {"key": "pais_origem", "by": "CSS_SELECTOR", "value": '#detailBullets_feature_div li:has-text("País de origem") span:last-child'},
        {"key": "avaliacao_nota", "by": "CSS_SELECTOR", "value": '#acrPopover .a-icon-alt'},
        {"key": "avaliacao_quantidade", "by": "CSS_SELECTOR", "value": '#acrCustomerReviewText'},
        # preço a pagar (com desconto) — inteiro/fração/símbolo/valor completo
        {"key": "preco_com_desconto_inteiro", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-price-whole'},
        {"key": "preco_com_desconto_fracao", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-price-fraction'},
        {"key": "preco_1", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-offscreen'},
        {"key": "preco_2", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-offscreen'},
        {"key": "preco_11", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-price-whole'},
        {"key": "preco_12", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-price-whole'},
        {"key": "preco_simbolo", "by": "CSS_SELECTOR", "value": f'{PRICE} span.a-price:not(.a-text-price) .a-price-symbol'},
        # preço original / riscado (a-text-price)
        {"key": "preco_original", "by": "CSS_SELECTOR", "value": '#corePriceDisplay_desktop_feature_div span.a-price.a-text-price .a-offscreen'},
        {"key": "preco_sem_desconto", "by": "CSS_SELECTOR", "value": '#corePriceDisplay_desktop_feature_div span.a-price.a-text-price .a-offscreen'},
        # preço por unidade
        {"key": "preco_por_unidade", "by": "CSS_SELECTOR", "value": '#corePriceDisplay_desktop_feature_div .a-price[data-a-size="mini"] .a-offscreen'},
        {"key": "preco_tipo_unidade", "by": "CSS_SELECTOR", "value": '#corePriceDisplay_desktop_feature_div .pricePerUnit'},
        # parcelamento
        {"key": "condicoes_1", "by": "CSS_SELECTOR", "value": '#installmentCalculator_feature_div .a-text-bold'},
        {"key": "condicoes_2", "by": "CSS_SELECTOR", "value": '#installmentCalculator_feature_div'},
        # assinatura (Programe e Poupe)
        {"key": "preco_recorrencia_inteiro", "by": "CSS_SELECTOR", "value": '#sns-base-price .a-price-whole'},
        {"key": "preco_recorrencia_fracao", "by": "CSS_SELECTOR", "value": '#sns-base-price .a-price-fraction'},
        {"key": "recorrencia_quantidade_minima_descricao", "by": "CSS_SELECTOR", "value": '#trigger_popover'},
        {"key": "recorrencia_quantidade_minima", "by": "CSS_SELECTOR", "value": '#trigger_popover'},
        # enviado / vendido por
        {"key": "enviado_por", "by": "CSS_SELECTOR", "value": '#fulfillerInfoFeature_feature_div .offer-display-feature-text-message'},
        {"key": "vendido_por", "by": "CSS_SELECTOR", "value": '#merchantInfoFeature_feature_div .offer-display-feature-text-message'},
    ]

    lst = scanElements(page, arrItemsScan)
    print('lst -----> ')
    print(lst)

    # Imagens
    get_amazon_images(page, folder_path_img)

    # Imprimir o título da página
    print(page.title())

    # Abre o arquivo em modo de escrita ('w') e escreve o código-fonte nele
    if not os.path.exists(folder_path_html):
        os.makedirs(folder_path_html)

    file_name = folder_path_html + '/1234.html'
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(page_source)

    # Status prime: procura o marcador "icon-prime" no HTML da pagina
    nFind = page_source.find('icon-prime', 0)

    print('Inicio')
    current_dateTime = datetime.now()
    print(current_dateTime.now())

    print('st_prime-----------------> ')
    print(nFind)

    st_prime = (nFind > 0)
    print(st_prime)

    print('Fim')
    print(current_dateTime.now())

    # Fechar o navegador
    browser.close()
