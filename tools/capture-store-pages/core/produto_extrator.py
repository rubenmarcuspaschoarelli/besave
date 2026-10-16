"""
Extrai atributos estruturados (marca, modelo, dimensoes, avaliacao, etc.) dos 4
campos de texto livre capturados pelas stores (LS_DETALHES_PRODUTO/_TECNICOS/
_INFO_ADICIONAIS/_COMPLEMENTO_PRODUTO em OFERTA_FILA_CAPTURA), para popular o
cadastro consolidado BESAVE.PRODUTO (cadastrar_produtos.py + STP_PRODUTO_UPSERT).

Os 4 campos sao texto "rotulo: valor | rotulo2: valor2 | frase solta sem rotulo"
(formato produzido por core/oracle_db.py:_texto/_item_texto na captura). Este
modulo NAO toca no fluxo de captura -- opera em cima do texto ja gravado no
banco, isolado do resto do programa.

Mecanismo (mineracao de texto, nao NLP): junta os 4 campos numa lista unica de
"pares" (rotulo normalizado -> valor), na ordem TECNICOS -> INFO_ADICIONAIS ->
COMPLEMENTO_PRODUTO -> DETALHES_PRODUTO (do mais estruturado ao mais "prosa";
1a ocorrencia de cada rotulo vence). Cada campo-alvo tem uma lista de rotulos
candidatos (sinonimos observados nos exemplos reais); o 1o candidato presente
vence. Peso/volume/dimensao tem fallback por regex sobre o texto corrido para
os casos em prosa (ex.: "Pesa 4.3kg.", "28.2cm de largura").
"""

import re
import unicodedata


# --- normalizacao basica --------------------------------------------------
def _sem_acento(s):
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c))


def _norm_rotulo(s):
    # minusculo, sem acento, espacos colapsados -- chave de busca nos MAPAs.
    return ' '.join(_sem_acento(s).lower().strip().split())


def _norm_numero(s):
    # "17,5" -> "17.5" (decimal); "1.234,56" -> "1234.56" (milhar+decimal).
    s = s.strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    return s


# --- unidades: sinonimo (sem acento/caixa) -> forma padronizada ----------
_UNID_PESO = {
    'g': 'g', 'g.': 'g', 'grama': 'g', 'gramas': 'g', 'gram(s)': 'g', 'grama(s)': 'g',
    'kg': 'kg', 'kg.': 'kg', 'quilograma': 'kg', 'quilogramas': 'kg', 'quilograma(s)': 'kg',
}
_UNID_VOLUME = {
    'ml': 'ml', 'ml.': 'ml', 'mililitro': 'ml', 'mililitros': 'ml', 'mililitro(s)': 'ml',
    'l': 'l', 'l.': 'l', 'litro': 'l', 'litros': 'l', 'litro(s)': 'l',
}
_UNID_COMPRIMENTO = {
    'cm': 'cm', 'cm.': 'cm', 'centimetro': 'cm', 'centimetros': 'cm', 'centimetro(s)': 'cm',
    'mm': 'mm', 'mm.': 'mm', 'milimetro': 'mm', 'milimetros': 'mm', 'milimetro(s)': 'mm',
    'm': 'm', 'm.': 'm', 'metro': 'm', 'metros': 'm',
}

# Unidade: qualquer sequencia sem digito/espaco (cobre acentos - "mililitro(s)",
# "milímetros" - sem depender de uma lista fixa de letras acentuadas).
_RE_NUM_UNIDADE = re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*([^\d\s]+)\s*$')


def _normalizar_medida(valor, tabela_unidades):
    """"236 Gramas" -> "236 g" | "17,5 cm" -> "17.5 cm" | "1,9 kg" -> "1.9 kg".
    Unidade fora da tabela: mantem como veio (minusculo, sem ponto final) --
    melhor guardar o dado bruto do que descartar."""
    if not valor:
        return None
    m = _RE_NUM_UNIDADE.match(valor)
    if not m:
        return valor.strip() or None
    numero = _norm_numero(m.group(1))
    unidade_raw = m.group(2).strip().rstrip('.')
    unidade = tabela_unidades.get(_sem_acento(unidade_raw).lower(), unidade_raw.lower())
    return f'{numero} {unidade}'


# --- rotulos candidatos por campo-alvo (normalizados) ---------------------
# Ordem importa: o 1o encontrado vence (ex.: "modelo" antes de "modelo
# detalhado", que costuma repetir o mesmo valor).
_CANDIDATOS = {
    'DS_MARCA':          ['marca', 'nome da marca'],
    'DS_MODELO':         ['modelo', 'modelo detalhado', 'nome do modelo'],
    'DS_FABRICANTE':     ['fabricante'],
    'DS_PESO_LIQUIDO':   ['peso liquido', 'peso do conteudo liquido'],
    'DS_PESO':           ['peso', 'peso da unidade', 'peso do produto', 'peso do item'],
    'DS_VOLUME':         ['volume liquido', 'volume do conteudo liquido',
                          'volume da unidade', 'volume do produto'],
    'DS_PAIS_ORIGEM':    ['pais de origem'],
    'DS_GENERO':         ['genero'],
    'ID_COD_ASIN':       ['asin'],
    # UPC nao e EAN, mas cumpre o mesmo papel de codigo de barras nos exemplos
    # (nenhum "EAN:" apareceu) -- unico candidato observado p/ ID_COD_EAN.
    'ID_COD_EAN':        ['upc'],
    'DS_FAIXA_ETARIA':   ['descricao da faixa etaria', 'faixa etaria (descricao)', 'idade'],
    'DS_LINHA':          ['linha'],
    'DS_ALTURA':         ['altura'],
    'DS_LARGURA':        ['largura'],
    'DS_COMPRIMENTO':    ['comprimento', 'profundidade'],
    'DS_UNIDADES':       ['unidades por embalagem', 'unidades por kit',
                          'contagem de unidades', 'quantidade de unidades'],
}

_CAMPOS_MEDIDA = {
    'DS_PESO_LIQUIDO': _UNID_PESO, 'DS_PESO': _UNID_PESO, 'DS_VOLUME': _UNID_VOLUME,
    'DS_ALTURA': _UNID_COMPRIMENTO, 'DS_LARGURA': _UNID_COMPRIMENTO,
    'DS_COMPRIMENTO': _UNID_COMPRIMENTO,
}

# Ordem de prioridade das 4 origens: mais estruturada (tabela de specs) ->
# mais "prosa" (bullets). A 1a ocorrencia de um rotulo, na ordem abaixo, vence.
_ORDEM_CAMPOS = ('tecnicos', 'info_adicionais', 'complemento', 'detalhes_produto')


def _dividir_pares(texto):
    """Um campo LS_* (texto "rotulo: valor | rotulo2: valor2 | frase solta")
    -> (pares normalizados {rotulo: valor}, lista de frases sem rotulo)."""
    pares, soltas = {}, []
    if not texto:
        return pares, soltas
    for segmento in texto.split(' | '):
        segmento = segmento.strip()
        if not segmento:
            continue
        rotulo, sep, valor = segmento.partition(':')
        if sep and 2 <= len(rotulo) <= 45:
            pares[_norm_rotulo(rotulo)] = valor.strip()
        else:
            soltas.append(segmento)
    return pares, soltas


def _primeiro(pares, candidatos):
    for c in candidatos:
        if c in pares and pares[c]:
            return pares[c]
    return None


# --- avaliacao / ranking: parsing do VALOR de 1 par especifico ------------
_RE_NOTA = re.compile(r'(\d+[,.]\d+)\s*de\s*5\s*estrelas', re.IGNORECASE)
_RE_QTD_AVAL = re.compile(r'\((\d[\d.]*)\)')
_RE_RANKING = re.compile(r'N[ºo]\s*([\d.]+)\s+em\s+(.+?)(?:\s*\(|\s+N[ºo]\s|$)', re.IGNORECASE)


def _extrair_avaliacao(pares):
    valor = pares.get('avaliacoes de clientes')
    nota = qtd = None
    if valor:
        m = _RE_NOTA.search(valor)
        if m:
            nota = float(_norm_numero(m.group(1)))
        m = _RE_QTD_AVAL.search(valor)
        if m:
            qtd = int(m.group(1).replace('.', ''))
    return nota, qtd


def _extrair_ranking(pares):
    valor = pares.get('ranking dos mais vendidos')
    if not valor:
        return None, None
    m = _RE_RANKING.search(valor)
    if not m:
        return None, None
    numero = m.group(1).replace('.', '')
    categoria = m.group(2).strip()
    return numero, categoria


# --- dimensoes: "C x L x A" e prosa com rotulo por numero -----------------
_RE_TRIPLA = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*'
    r'([^\d\s]+)'
)
# "comprimento de 39 cm" (rotulo antes do numero)
_RE_PROSA_A = re.compile(
    r'\b(largura|altura|comprimento)\s+de\s+(\d+(?:[.,]\d+)?)\s*(cm|mm|m)\b', re.IGNORECASE)
# "28.2cm de largura" (numero antes do rotulo)
_RE_PROSA_B = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(cm|mm|m)\s+de\s+\b(largura|altura|comprimento)\b', re.IGNORECASE)


def _extrair_dimensoes(pares, soltas, resultado):
    # 1) rotulos diretos (Altura:/Largura:/Comprimento:/Profundidade:) --
    #    ja aplicados em _extrair_campos_simples antes desta funcao rodar;
    #    aqui so completamos o que ainda faltar.
    if all(resultado.get(c) for c in ('DS_ALTURA', 'DS_LARGURA', 'DS_COMPRIMENTO')):
        return

    texto_completo = ' | '.join(
        [f'{k}: {v}' for k, v in pares.items()] + soltas
    )

    # 2) segmentos rotulados "dimens..." com padrao "N x N x N unidade" --
    #    assume-se Comprimento x Largura x Altura (convencao Amazon/e-commerce
    #    BR quando o rotulo nao especifica a ordem).
    for rotulo, valor in pares.items():
        if 'dimens' not in rotulo:
            continue
        m = _RE_TRIPLA.search(valor)
        if m:
            unid_raw = m.group(4).rstrip('.')
            unidade = _UNID_COMPRIMENTO.get(_sem_acento(unid_raw).lower(), unid_raw.lower())
            resultado.setdefault('DS_COMPRIMENTO', f'{_norm_numero(m.group(1))} {unidade}')
            resultado.setdefault('DS_LARGURA', f'{_norm_numero(m.group(2))} {unidade}')
            resultado.setdefault('DS_ALTURA', f'{_norm_numero(m.group(3))} {unidade}')
            continue
        # prosa dentro do proprio valor "dimensoes" (ex.: "28.2cm de largura, ...")
        for regex in (_RE_PROSA_A, _RE_PROSA_B):
            for mm in regex.finditer(valor):
                grupos = mm.groups()
                if regex is _RE_PROSA_A:
                    campo, numero, unidade = grupos
                else:
                    numero, unidade, campo = grupos
                chave = {'largura': 'DS_LARGURA', 'altura': 'DS_ALTURA',
                         'comprimento': 'DS_COMPRIMENTO'}[campo.lower()]
                resultado.setdefault(chave, f'{_norm_numero(numero)} {unidade.lower()}')

    # 3) prosa solta em qualquer lugar do texto (ex.: bullet sem rotulo
    #    "Cabides com comprimento de 39 cm, altura de 19,5 cm...").
    for regex in (_RE_PROSA_A, _RE_PROSA_B):
        for mm in regex.finditer(texto_completo):
            grupos = mm.groups()
            if regex is _RE_PROSA_A:
                campo, numero, unidade = grupos
            else:
                numero, unidade, campo = grupos
            chave = {'largura': 'DS_LARGURA', 'altura': 'DS_ALTURA',
                     'comprimento': 'DS_COMPRIMENTO'}[campo.lower()]
            resultado.setdefault(chave, f'{_norm_numero(numero)} {unidade.lower()}')


# --- peso: fallback de prosa ("Pesa 4.3kg.") ------------------------------
_RE_PESA = re.compile(r'\bpesa\s+(\d+(?:[.,]\d+)?)\s*(kg|g)\b', re.IGNORECASE)


def _extrair_peso_prosa(soltas, resultado):
    if resultado.get('DS_PESO'):
        return
    for frase in soltas:
        m = _RE_PESA.search(frase)
        if m:
            unidade = _UNID_PESO.get(m.group(2).lower(), m.group(2).lower())
            resultado['DS_PESO'] = f'{_norm_numero(m.group(1))} {unidade}'
            return


# --- entrada principal -----------------------------------------------------
def extrair_atributos(ls_detalhes_produto, ls_detalhes_tecnicos,
                       ls_info_adicionais, ls_complemento_produto):
    """4 campos LS_* (texto, como gravados em OFERTA_FILA_CAPTURA) -> dict com
    as colunas de BESAVE.PRODUTO que deu pra extrair (chave ausente = nao
    encontrado, nunca string vazia)."""
    textos = {
        'tecnicos': ls_detalhes_tecnicos,
        'info_adicionais': ls_info_adicionais,
        'complemento': ls_complemento_produto,
        'detalhes_produto': ls_detalhes_produto,
    }
    pares_geral, soltas_geral = {}, []
    for nome in _ORDEM_CAMPOS:
        pares, soltas = _dividir_pares(textos[nome])
        for k, v in pares.items():
            pares_geral.setdefault(k, v)  # 1a origem (mais estruturada) vence
        soltas_geral.extend(soltas)

    resultado = {}
    for campo, candidatos in _CANDIDATOS.items():
        valor = _primeiro(pares_geral, candidatos)
        if valor:
            if campo in _CAMPOS_MEDIDA:
                valor = _normalizar_medida(valor, _CAMPOS_MEDIDA[campo])
            else:
                # LS_DETALHES_PRODUTO vem em frases (Amazon "Sobre este item"),
                # entao um par que só aparece la carrega o ponto final da
                # frase (ex.: "Unidades por kit: 1." -> valor "1."). Tira 1
                # ponto final se sobrar; nao mexe em pontos NO MEIO do valor
                # (rstrip so afeta o final da string).
                valor = valor.strip().rstrip('.').strip()
            if valor:
                resultado[campo] = valor

    nota, qtd = _extrair_avaliacao(pares_geral)
    if nota is not None:
        resultado['NR_NOTA_AVALIACAO'] = nota
    if qtd is not None:
        resultado['QT_AVALIACAO'] = qtd

    ranking, categoria = _extrair_ranking(pares_geral)
    if ranking:
        resultado['NR_RANKING'] = ranking
    if categoria:
        resultado['DS_CATEGORIA_RANKING'] = categoria

    _extrair_dimensoes(pares_geral, soltas_geral, resultado)
    _extrair_peso_prosa(soltas_geral, resultado)

    return resultado


def resolver_titulo(ds_titulo, ds_oferta):
    # Preferencia explicita do usuario: DS_TITULO (vem da pagina da loja,
    # mais preciso) sobre DS_OFERTA (texto de origem do WhatsApp).
    # Titulo sem nenhuma letra/numero ("-", ".") conta como vazio: o produto e
    # achado pelo TITULO, e mensagens do WhatsApp so com "-" juntavam ofertas
    # Shopee sem titulo num produto unico "-" (o 294, ate 2026-10-09).
    for candidato in (ds_titulo, ds_oferta):
        candidato = (candidato or '').strip()
        if any(ch.isalnum() for ch in candidato):
            return candidato
    return ''
