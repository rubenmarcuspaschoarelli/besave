"""
Classifica um produto em Comunidade(s) e Publico a partir do path de
LS_CATEGORIA (breadcrumb "Departamento | Subcategoria | ... | Folha") +
DS_CATEGORIA_RANKING + titulo. Puro Python, sem dependencia de banco -- mesma
filosofia de core/produto_extrator.py (testavel isolado, chamado 1x por
produto em main.py/backfill antes de gravar).

Levantamento que fundamenta as regras (sessao 2026-09-04, ver conversa):
LS_CATEGORIA populado em 99,2% dos produtos (fonte primaria, presente nas 3
lojas ativas); DS_CATEGORIA_RANKING so tem cobertura real na Amazon (~75%),
usado aqui so como reforco de texto. Departamentos e decisoes de mapeamento
confirmadas com o usuario:
  - Joias -> Elas (puro). Relogios e Instrumentos Musicais -> Elas+Eles
    ponderado (nao da pra saber o genero so pelo departamento), publico
    Unisex por padrao.
  - Ferramentas/Construcao/Industria/Automotivo/Veiculos/Jardim/Piscina ->
    Meu Lar (nenhuma das 9 comunidades cobre "ferramentas" de forma nativa;
    decisao do usuario foi esticar Meu Lar pra cobrir).
"""
import re

PUBLICOS_VALIDOS = ('Masculino', 'Feminino', 'Unisex', 'Menino', 'Menina', 'Bebes', 'Infantil')

# -- produto de crianca (2026-10-08): fica em "Família & filhos" (nunca Elas/
# Eles) com publico Bebes/Menina/Menino ou, sem sinal, 'Infantil' -- ex. o
# perfume infantil do Cebolinha era Elas/Masculino. "baby" que NAO e de bebe
# (achados no catalogo): baby doll/"pijama baby" (lingerie), baby look
# (camiseta feminina), Giovanna Baby (marca adulta), essencia/lava-roupas
# "Baby Soft" (nome de fragrancia).
_BABY = (r'(?<!giovanna )(?<!pijama )(?<!essencia )(?<!essência )(?<!oh )'
         r'\bbaby\b(?![\s-]*(?:doll|dool|look|soft|tee?\b|hair|alive))')
_INFANTIL = re.compile(r'infantil|\bbeb[eê]s?\b|' + _BABY + r'|\bkids?\b|fralda|chupeta|'
                       r'mamadeira|\btalco\b|rec[eé]m.nascido|(?<!anti )(?<!anti-)assadura|'
                       r'pampers|huggies|babycreme', re.IGNORECASE)
# "Adulto Infantil" no titulo (elastico de cabelo, nebulizador): serve aos dois.
_ADULTO = re.compile(r'\badult', re.IGNORECASE)
# Produto p/ os PAIS (maternidade, amamentacao): Família & filhos, mas o
# publico continua o do genero (adulto).
_PAIS = re.compile(r'maternidade|amamenta', re.IGNORECASE)

_MODA = re.compile(r'cal[çc]ad|roupa|moda|vestu[aá]rio|bolsa|lingerie|sapato|t[eê]nis|sand[aá]lia|'
                   r'chinelo|\bmeias?\b', re.IGNORECASE)
# "roupa" que NAO e moda (2026-10-09): lavanderia/limpeza (Omo, Downy, Vanish,
# odorizador de roupas...) e roupa de cama -> Meu Lar, nunca Elas/Eles.
_NAO_MODA = re.compile(r'lava[\s-]*roupas?|amaciante|tira[\s-]*manchas?|alvejante|percarbonato|'
                       r'odorizador de roupas?|sab[aã]o (?:em p[oó]|l[ií]quido)|lavanderia|'
                       r'roupas? de cama', re.IGNORECASE)

_BELEZA = re.compile(r'beleza|perfum|cosm[eé]tic|dermocosm|cabelo|maquiag|skincare|'
                     r'shampoo|condicionador|creme|\bcream\b|s[eé]rum|lo[cç][aã]o|sabonete|batom|hidratante',
                     re.IGNORECASE)


# Itens de casa/lazer que a Shopee cataloga em "Mae e Bebe" (piscina de 7200 L,
# ofuro, umidificador) -- decisao do usuario 2026-10-08: nao sao Família &
# filhos, salvo se o TITULO disser "infantil"/"kids"/bolinhas/escorregador.
# "bebe" no titulo NAO basta: "Umidificador ... Quarto Bebe" e so o lugar de uso.
_CASA_NAO_INFANTIL = re.compile(r'\bpiscina|ofur[oô]|umidificador', re.IGNORECASE)
_LAZER_INFANTIL = re.compile(r'bolinhas?|escorregador|infantil|\bkids?\b', re.IGNORECASE)


def _casa_nao_infantil(titulo):
    return bool(_CASA_NAO_INFANTIL.search(titulo or '')
                and not _LAZER_INFANTIL.search(titulo or ''))


def _texto_infantil(titulo, texto_com_titulo):
    """Onde procurar sinal de crianca/bebe. Em BELEZA so o titulo vale: a
    Amazon cataloga muito shampoo adulto (Joico, Brae, Ricca...) em "Bebes |
    Higiene e Cuidados com o Bebe" -- achado em 2026-10-08. Idem p/ piscina/
    ofuro/umidificador (ver _CASA_NAO_INFANTIL)."""
    if _BELEZA.search(texto_com_titulo):
        return titulo or ''
    if _casa_nao_infantil(titulo):
        return ''
    return texto_com_titulo

# -- sinais de genero/idade: procurados no texto TODO (categoria + titulo) --
# checados nesta ordem -- infantil/bebe antes de feminino/masculino porque
# "moda infantil feminina" deve virar Menina, nao Feminino.
_SINAIS_PUBLICO = (
    ('Bebes', re.compile(r'\bbeb[eê]s?\b|' + _BABY + r'|rec[eé]m.nascido', re.IGNORECASE)),
    # \b: "femenino" (erro de digitacao comum) contem "menino".
    ('Menina', re.compile(r'\bmeninas?\b|infantil feminin', re.IGNORECASE)),
    ('Menino', re.compile(r'\bmeninos?\b|infantil masculin', re.IGNORECASE)),
    ('Feminino', re.compile(r'feminin|\bmulher', re.IGNORECASE)),
    ('Masculino', re.compile(r'masculin|\bhomem\b(?![\s-]*aranha)', re.IGNORECASE)),
)

# -- regras de comunidade: (padrao buscado no path+ranking, [(comunidade, peso), ...], publico_default) --
# publico_default = None quer dizer "so decide pelo sinal explicito acima";
# se nenhum sinal for achado, o fallback final e sempre Unisex.
_REGRAS = (
    (re.compile(r'\bjoia', re.IGNORECASE), (('Elas', 1.0),), 'Feminino'),
    (re.compile(r'rel[oó]gio', re.IGNORECASE), (('Elas', 0.5), ('Eles', 0.5)), 'Unisex'),
    (re.compile(r'instrumentos? music', re.IGNORECASE), (('Elas', 0.5), ('Eles', 0.5)), 'Unisex'),
    (_BELEZA, (('Elas', 1.0),), 'Feminino'),
    (_MODA, (('Elas', 0.6), ('Eles', 0.6)), None),
    (re.compile(r'\bcasa\b|m[oó]vei|cozinha|eletrodom[eé]stico|banheiro|aliment|bebida|decora|'
                r'armazenamento|organiza[çc][aã]o|lou[çc]a|utens[ií]lio|' + _NAO_MODA.pattern,
                re.IGNORECASE), (('Meu Lar', 1.0),), 'Unisex'),
    (re.compile(r'ferramenta|constru[cç][aã]o|ind[uú]stria|autom[oó]tiv|ve[ií]cul|jardim|piscina',
                re.IGNORECASE), (('Meu Lar', 1.0),), 'Unisex'),
    (re.compile(r'eletr[oô]nic|celular|telefone|inform[aá]tic|computador|c[aâ]mera|caixa.{0,15}som|dispositivo',
                re.IGNORECASE), (('Tech', 1.0),), 'Unisex'),
    (re.compile(r'\bgame\b|console', re.IGNORECASE), (('Players', 1.0),), 'Unisex'),
    (re.compile(r'\blivro|revista|comic', re.IGNORECASE), (('Cultura', 1.0),), 'Unisex'),
    (re.compile(r'sa[uú]de|suplement|esporte|fitness', re.IGNORECASE), (('Esporte & vida', 1.0),), 'Unisex'),
    # Infantil/bebe/maternidade entram em Família & filhos no classificar()
    # (precisa saber se e beleza -- ver _texto_infantil).
    (re.compile(r'brinquedo', re.IGNORECASE), (('Família & filhos', 1.0),), None),
    (re.compile(r'pet ?shop|\bpet\b|\bra[çc][aã]o\b|\banimal|\bgatos?\b|\bc[aã]es\b|cachorro',
                re.IGNORECASE), (('Pets', 1.0),), 'Unisex'),
)

_MAX_COMUNIDADES = 3

# -- genero adulto (2026-10-08): decide Elas x Eles e o publico Feminino/
# Masculino/Unisex. Antes o genero so ia p/ DS_PUBLICO e a comunidade nunca o
# via: beleza dava so Elas e moda/relogio empatavam Elas=Eles com o empate
# indo p/ Elas -- resultado: 0 ofertas "Eles" e ~740 "Elas"+"Masculino"
# (perfume masculino, jaqueta masculina...). Masculino ampliado p/ "homens",
# "men"/"men's" (NIVEA MEN), "homme", "barba".
_MASCULINO = re.compile(r'masculin|\bhom(em|ens)\b(?![\s-]*aranha)|\bmen\b|\bmen.?s\b|for men|\bhomme\b|\bbarba\b',
                        re.IGNORECASE)
_FEMININO = re.compile(r'feminin|\bmulher(es)?\b|\bwomen\b|\bfemme\b', re.IGNORECASE)


def _genero(titulo, texto_categoria):
    """'Masculino' / 'Feminino' / 'Unisex' (os dois citados) / None. O TITULO
    manda; a categoria so conta quando o titulo nao diz nada (breadcrumb de
    loja as vezes mistura, ex. "Moda Feminina" num produto masculino)."""
    for texto in (titulo or '', texto_categoria or ''):
        m, f = bool(_MASCULINO.search(texto)), bool(_FEMININO.search(texto))
        if m and f:
            return 'Unisex'
        if m:
            return 'Masculino'
        if f:
            return 'Feminino'
    return None


def limpar_path(ls_categoria, titulo=None):
    """Breadcrumb -> lista de segmentos limpos. Remove 2 artefatos conhecidos
    da Shopee: 1o segmento literal "Shopee" e o ultimo segmento quando repete
    o proprio titulo do produto (a Shopee inclui o titulo como se fosse
    categoria-folha)."""
    if not ls_categoria:
        return []
    segmentos = [s.strip() for s in ls_categoria.split('|') if s.strip()]
    if segmentos and segmentos[0].strip().lower() == 'shopee':
        segmentos = segmentos[1:]
    if segmentos and titulo and segmentos[-1].strip().lower() == titulo.strip().lower():
        segmentos = segmentos[:-1]
    return segmentos


def classificar(ls_categoria, titulo=None, ds_categoria_ranking=None):
    """Retorna (comunidades, publico):
      comunidades: lista [(nome, score), ...] ordenada desc por score, ate 3;
                   vazia se nada casou (nenhuma das regras bateu).
      publico: sempre 1 valor de PUBLICOS_VALIDOS (fallback 'Unisex')."""
    segmentos = limpar_path(ls_categoria, titulo)
    texto_categoria = ' | '.join(segmentos)
    if ds_categoria_ranking:
        texto_categoria = f'{texto_categoria} | {ds_categoria_ranking}'
    texto_com_titulo = f'{texto_categoria} | {titulo}' if titulo else texto_categoria

    # comunidade escaneia categoria+titulo -- necessario p/ lojas schemaorg
    # (epoca/zzmall/belezanaweb) cujo breadcrumb so tem a MARCA (ex.: "Dior |
    # Miss Dior"), sem nenhuma palavra de categoria; o titulo geralmente
    # compensa ("... Eau de Parfum - Perfume Feminino 50ml").
    scores = {}
    publico_default = None
    nao_moda = bool(_NAO_MODA.search(texto_com_titulo))
    for padrao, comunidades, publico in _REGRAS:
        # Lavanderia: nem moda ("roupa") nem beleza ("perfume" do odorizador).
        if nao_moda and (padrao is _MODA or padrao is _BELEZA):
            continue
        if padrao.search(texto_com_titulo):
            for nome, peso in comunidades:
                scores[nome] = scores.get(nome, 0.0) + peso
            if publico_default is None and publico is not None:
                publico_default = publico

    publico_sinalizado = None
    texto_infantil = _texto_infantil(titulo, texto_com_titulo)
    for nome, padrao in _SINAIS_PUBLICO:
        # Bebes/Menina/Menino olham o mesmo texto do sinal infantil.
        alvo = texto_infantil if nome in ('Bebes', 'Menina', 'Menino') else texto_com_titulo
        if padrao.search(alvo):
            publico_sinalizado = nome
            break

    # Genero adulto: troca Elas<->Eles conforme o genero (o produto fica com o
    # maior dos 2 scores) e corrige Feminino/Masculino/Unisex do publico.
    # Bebes/Menina/Menino continuam vencendo no publico (infantil primeiro).
    genero = _genero(titulo, texto_categoria)
    infantil = bool(_INFANTIL.search(texto_infantil)) and not _ADULTO.search(titulo or '')
    pais = bool(_PAIS.search(texto_com_titulo))
    if 'Pets' in scores or _casa_nao_infantil(titulo):
        # Fralda/brinquedo PARA cachorro: o "fralda"/"brinquedo" nao e de crianca.
        # Piscina/ofuro/umidificador em "Mae e Bebe | Brinquedos": idem.
        scores.pop('Família & filhos', None)
    elif infantil or pais:
        # Crianca/bebe (ou produto p/ os pais): Família & filhos e a principal
        # e Elas/Eles saem -- um perfume infantil nao e de adulto. As demais
        # (Meu Lar p/ cama infantil, Esporte p/ bicicleta) ficam secundarias.
        if infantil:
            scores.pop('Elas', None)
            scores.pop('Eles', None)
        scores['Família & filhos'] = max(scores.values(), default=0.0) + 1.0
        if infantil:
            if publico_sinalizado not in ('Bebes', 'Menina', 'Menino'):
                publico_sinalizado = 'Infantil'
            genero = None
    if genero in ('Masculino', 'Feminino') and ('Elas' in scores or 'Eles' in scores):
        score = max(scores.pop('Elas', 0.0), scores.pop('Eles', 0.0))
        scores['Eles' if genero == 'Masculino' else 'Elas'] = score
    if genero and publico_sinalizado in (None, 'Feminino', 'Masculino'):
        publico_sinalizado = genero

    publico = publico_sinalizado or publico_default or 'Unisex'
    comunidades = sorted(scores.items(), key=lambda kv: -kv[1])[:_MAX_COMUNIDADES]
    return comunidades, publico
