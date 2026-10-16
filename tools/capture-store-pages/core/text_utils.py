import re


# Marcas de formatacao invisiveis (bidi / zero-width / BOM) que a Amazon injeta
# em alguns campos, ex.: pais_origem vem com LRM/RLM em volta ("<LRM>China<RLM>").
# Nao aparecem no Excel mas sujam comparacoes/joins do CSV.
#   200B-200F: zero-width + LRM/RLM   202A-202E: embedding/override bidi
#   2066-2069: isolates bidi          FEFF: BOM / zero-width no-break space
_INVISIVEIS = re.compile('[​-‏‪-‮⁦-⁩﻿]')


def normalize_text(v):
    # Colapsa quebras de linha / espacos repetidos em um unico espaco e remove
    # o espaco antes de virgula/ponto (ex.: preco "57\n," -> "57,"). Tambem
    # remove marcas unicode invisiveis (LRM/RLM/zero-width/BOM).
    if not v:
        return v
    v = _INVISIVEIS.sub('', v)
    v = re.sub(r'\s+', ' ', v).strip()
    v = re.sub(r'\s+([,.])', r'\1', v)
    return v


def normalize_price(v):
    # Padroniza preco entre as lojas: remove "R$" e usa "." como separador
    # decimal (Amazon/Shopee vem "R$1.234,56"; Mercado Livre vem "1234.56").
    # Preserva faixas (ex.: "R$10,99 - R$11,99" -> "10.99 - 11.99").
    if not v:
        return v
    v = v.replace('R$', '')

    def conv(m):
        s = m.group(0)
        if '.' in s and ',' in s:      # BR: ponto=milhar, virgula=decimal
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:                 # so virgula: decimal
            s = s.replace(',', '.')
        return s                       # so ponto (ML) ou inteiro: mantem

    v = re.sub(r'\d[\d.,]*\d|\d', conv, v)
    return v.strip()


def extract_substrings(input_string, start_substring, end_substring):
    # Extrai todas as ocorrencias entre start_substring e end_substring (inclusive).
    substrings = []
    start_index = 0
    while True:
        start_index = input_string.find(start_substring, start_index)
        if start_index == -1:
            break
        end_index = input_string.find(end_substring, start_index + len(start_substring))
        if end_index != -1:
            substring = input_string[start_index + len(start_substring): end_index]
            substrings.append(start_substring + substring + end_substring)
            start_index = end_index + len(end_substring)
        else:
            break
    return substrings
