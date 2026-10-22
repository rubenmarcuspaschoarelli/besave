def extract_substrings(input_string, start_substring, end_substring):
    # Lista para armazenar as substrings encontradas
    substrings = []

    # Começamos a busca a partir do índice 0
    start_index = 0

    while True:
        # Encontrar a primeira ocorrência de 'start_substring' a partir de start_index
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
            substrings.append(start_substring+substring+end_substring)

            # Atualiza o start_index para continuar a busca após o 'end_substring'
            start_index = end_index + len(end_substring)
        else:
            # Se não encontrar o 'end_substring', interrompe o loop
            break

    return substrings


# Exemplo de uso:
input_string = "Aqui está o exemplo: <item>valor1</item> e outro <item>valor2</item>"
start_substring = "<item>"
end_substring = "</item>"

html_string = '''
data-csa-c-action="image-block-main-image-hover" data-csa-c-element-type="navigational" data-csa-c-posy="1" data-csa-c-type="uxElement" class="image item itemNo0 maintain-height selected" style="cursor: pointer;" data-csa-c-id="9f70y-fsnpx2-j8kmws-cwk33a" rc="https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX425_.jpg" data-old-hires="https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SL1000_.jpg" onload="markFeatureRenderForImageBlock(); if(this.width/this.height > 1.0){this.className += ' a-stretch-horizontal'}else{this.className += ' a-stretch-vertical'};this.onload='';setCSMReq('af');if(typeof addlongPoleTag === 'function'){ addlongPoleTag('af','desktop-image-atf-marker');};setCSMReq('cf')" data-a-image-name="landingImage" class="a-dynamic-image a-stretch-vertical" id="landingImage" data-a-dynamic-image="{&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX522_.jpg&quot;:[522,522],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX425_.jpg&quot;:[425,425],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX679_.jpg&quot;:[679,679],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX466_.jpg&quot;:[466,466],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SY450_.jpg&quot;:[450,450],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SX569_.mpeg&quot;:[569,569],&quot;https://m.media-amazon.com/images/I/611Q+OwfS2L._AC_SY355_.gif&quot;:[355,355]}" style="max-width:679px;max-height:679px;" 
'''

start_substring = "https://"
end_substring = ".jpg"

result = extract_substrings(html_string, start_substring, end_substring)
print(result)  # Output esperado: ['valor1', 'valor2']