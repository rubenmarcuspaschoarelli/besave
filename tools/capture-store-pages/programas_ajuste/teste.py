from html.parser import HTMLParser

# Exemplo de string fornecida
html_string = '''
data-csa-c-action="image-block-main-image-hover" data-csa-c-element-type="navigational" data-csa-c-posy="1" data-csa-c-type="uxElement" class="image item itemNo0 maintain-height selected" style="cursor: pointer;" data-csa-c-id="9f70y-fsnpx2-j8kmws-cwk33a" rc="https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX425_.jpg" data-old-hires="https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SL1000_.jpeg" onload="markFeatureRenderForImageBlock(); if(this.width/this.height > 1.0){this.className += ' a-stretch-horizontal'}else{this.className += ' a-stretch-vertical'};this.onload='';setCSMReq('af');if(typeof addlongPoleTag === 'function'){ addlongPoleTag('af','desktop-image-atf-marker');};setCSMReq('cf')" data-a-image-name="landingImage" class="a-dynamic-image a-stretch-vertical" id="landingImage" data-a-dynamic-image="{&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX522_.jpg&quot;:[522,522],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX425_.jpg&quot;:[425,425],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX679_.jpg&quot;:[679,679],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX466_.jpg&quot;:[466,466],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SY450_.jpg&quot;:[450,450],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX569_.mpeg&quot;:[569,569],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SY355_.gif&quot;:[355,355]}" style="max-width:679px;max-height:679px;" 
'''


# Função para extrair as URLs das imagens
def extract_image_urls(html_string):
    # Definindo as extensões de imagem válidas
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']

    # Lista de URLs encontradas
    image_urls = []

    # Procurando por todas as ocorrências de URLs na string
    parts = html_string.split('"')

    for part in parts:
        if any(part.endswith(ext) for ext in image_extensions):  # Verifica se termina com uma extensão de imagem
            image_urls.append(part)

    return image_urls


# Chamando a função para extrair as URLs das imagens
image_urls = extract_image_urls(html_string)

# Exibindo as URLs encontradas
print(image_urls)
