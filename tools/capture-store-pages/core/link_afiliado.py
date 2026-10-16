"""
Captura o LINK OFICIAL de afiliado de cada loja -- o link que o PROPRIO
programa de afiliados gera (e nao o que o Python calcula em core/afiliados.py).

    core/afiliados.py  -> DS_URL_BESAVE   (CALCULADO: troca o parametro de
                          rastreio do divulgador pelo nosso, na DS_URL_FINAL)
    core/link_afiliado -> DS_URL_AFILIADO (OFICIAL: clicado no widget da loja,
                          ex. https://link.amazon/B0eZOeQAV)

As duas convivem, mas so a OFICIAL e o link de afiliado confiavel (decisao
do usuario, 2026-09-24): e ela que vai p/ PRODUTO.DS_ULT_URL, e o historico
sem ela e completado por backfill_url_afiliado.py. A calculada fica gravada
so como referencia e NAO entra em nenhum fluxo daqui.

Cada loja tem um caminho diferente:
  * Amazon ......... SiteStripe na propria pagina do produto: le categoria e
                     taxa de comissao, clica "Obter link" e depois "Copiar
                     link de associado".
  * Mercado Livre .. barra de afiliado no topo da pagina do produto: le
                     "GANHOS x%", clica "Compartilhar" e LE OS CAMPOS do menu
                     que abre (link e ID do produto). Os campos tem
                     data-testid proprio e demoram alguns segundos p/ serem
                     preenchidos -- ver _valor_campo().
  * Shopee ......... nao tem widget na pagina: usa o gerador em
                     affiliate.shopee.com.br/offer/custom_link, NUMA ABA
                     SEPARADA (a aba do produto fica intacta), colando a URL
                     e clicando "Obter link" -> "Copiar Link".

TODAS as lojas dependem de SESSAO LOGADA no respectivo programa de afiliados
(os gates de login no arranque do main.py). Sem login o widget simplesmente
nao existe na pagina -> os campos ficam vazios (NULL no banco) e a captura do
produto, que ja deu certo, NAO e afetada: este modulo e best-effort e nunca
propaga excecao.

Leitura do link -- dois caminhos, sempre: (1) o valor que a propria loja
mostra no campo/dialogo e (2) o clique no botao "copiar" + leitura da AREA DE
TRANSFERENCIA (navigator.clipboard, com permissao concedida em
preparar_contexto()). Qual vem primeiro depende da loja: no Mercado Livre o
campo e a fonte principal (o clipboard exige foco da janela e falha em
silencio); na Amazon e na Shopee o clipboard vem primeiro, com o dialogo como
reserva. Em qualquer caso o valor so e aceito se casar com o FORMATO esperado
da loja -- assim um clipboard velho (de outra oferta) nunca vira dado bom -- e
a area de transferencia e zerada antes de cada clique.
"""

import re

# Campos produzidos aqui -> colunas DS_*_AFILIADO (ver core/oracle_db.MAPA_CAMPOS).
CAMPOS = ('url_afiliado', 'categoria_afiliado', 'taxa_comissao_afiliado',
          'id_produto_afiliado')

# Lojas com fluxo implementado (as demais devolvem tudo vazio).
LOJAS = ('amazon', 'mercadolivre', 'shopee')

_habilitado = True

# Corta-circuito: loja com LIMITE_FALHAS ofertas seguidas sem link sai do ar
# ate o proximo arranque (ver _desistir_da_loja).
LIMITE_FALHAS = 5
_falhas_seguidas = {}
_desistidas = set()

# --- formatos aceitos por loja ------------------------------------------------
# Amazon: link curto do SiteStripe; a URL longa com tag= serve de 2a opcao.
_RE_AMAZON_CURTO = re.compile(r'https?://(?:link\.amazon|amzn\.to)/\S+')
_RE_AMAZON_LONGO = re.compile(r'https?://(?:www\.)?amazon\.com\.br/\S*[?&]tag=\S+')
_RE_MELI = re.compile(r'https?://(?:meli\.la|(?:\w+\.)?mercadolivre\.com(?:\.br)?)/\S+')
_RE_SHOPEE = re.compile(r'https?://(?:s\.shopee\.com\.br|shopee\.com\.br)/\S+')
# Codigo do produto no ML: "JD7H7W-PS9Y". Basta nao ser URL -- o valor vem do
# CAMPO do menu (ou da area de transferencia logo apos o clique no copiar),
# nunca de uma varredura de texto solto da pagina.
_RE_ID_ML = re.compile(r'^[A-Z0-9][A-Z0-9-]{3,29}$')
# "13,00%" / "GANHOS 16%" -> so o percentual. No Mercado Livre a barra tem mais
# texto em volta, entao o rotulo "GANHOS" vem primeiro na fila: sem ele, um
# "-20%" de desconto que aparecesse na mesma barra seria lido como comissao.
_RE_PERCENTUAL = re.compile(r'(\d+(?:[.,]\d+)?\s*%)')
# O que separa o rotulo do numero varia ("GANHOS 16%", "GANHOS: 16%",
# "GANHOS ATE 16%") -> aceita qualquer coisa que nao seja digito no meio.
_RE_GANHOS = re.compile(r'GANHOS[^\d%]{0,12}(\d+(?:[.,]\d+)?\s*%)', re.IGNORECASE)


def configurar(habilitado=True):
    """Liga/desliga a captura (conf/config.json -> link_afiliado.habilitado ou
    --sem-link-afiliado). Desligada, capturar() devolve tudo vazio sem tocar na
    pagina -- util p/ rodar a fila sem depender dos 3 logins de afiliado."""
    global _habilitado
    _habilitado = bool(habilitado)
    _falhas_seguidas.clear()
    _desistidas.clear()


def habilitado():
    return _habilitado


def vazio():
    return {campo: '' for campo in CAMPOS}


def preparar_contexto(context):
    """Concede permissao de leitura/escrita da area de transferencia ao
    contexto do navegador. Sem isso navigator.clipboard.readText() dispara o
    prompt de permissao (que ninguem responde numa automacao) e falha.
    Best-effort: negado, os fluxos caem na leitura pelo DOM."""
    try:
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        return True
    except Exception as e:  # noqa: BLE001
        print(f'[link_afiliado] sem permissao de area de transferencia: {e}')
        return False


# --- area de transferencia ----------------------------------------------------
def _limpar_clipboard(page):
    # Zera antes de clicar: sem isso um clique que nao copiou nada deixaria a
    # gente ler o link da oferta ANTERIOR e grava-lo como se fosse desta.
    try:
        page.evaluate("() => navigator.clipboard.writeText('')")
    except Exception:  # noqa: BLE001
        pass


def _ler_clipboard(page):
    for tentativa in (1, 2):
        try:
            return (page.evaluate("() => navigator.clipboard.readText()") or '').strip()
        except Exception as e:  # noqa: BLE001
            # "Document is not focused": o Chrome so libera o clipboard p/ a aba
            # em primeiro plano. Traz a aba e tenta mais uma vez.
            if tentativa == 1 and 'focus' in str(e).lower():
                try:
                    page.bring_to_front()
                except Exception:  # noqa: BLE001
                    pass
                continue
            return ''
    return ''


def _loc(page, alvo):
    """Aceita seletor (str) ou Locator ja pronto -- a barra do Mercado Livre e
    resolvida subindo a partir do botao, entao chega aqui como Locator."""
    return page.locator(alvo).first if isinstance(alvo, str) else alvo


def _texto_do_bloco(page, alvo):
    """Texto visivel + valor dos inputs/textareas de um bloco (o link gerado
    costuma estar num <input readonly> que innerText nao alcanca)."""
    try:
        bloco = _loc(page, alvo)
        if bloco.count() == 0:
            return ''
        return bloco.evaluate(
            "el => { const v = [...el.querySelectorAll('input,textarea')]"
            ".map(i => i.value || '').join('\\n');"
            " return (el.innerText || '') + '\\n' + v; }"
        ) or ''
    except Exception:  # noqa: BLE001
        return ''


def _copiar_e_ler(page, botao, validar, tentativas=3, espera=400):
    """Clica no botao de copiar da loja e devolve o que caiu na area de
    transferencia, ja validado pelo formato da loja ('' se nao veio nada
    aceitavel). Fecha aba que o clique porventura abra (botoes de compartilhar
    ficam ao lado dos de copiar no Mercado Livre)."""
    contexto = page.context
    abas_antes = len(contexto.pages)
    _limpar_clipboard(page)
    try:
        botao.click(timeout=10000)
    except Exception as e:  # noqa: BLE001
        print(f'[link_afiliado] clique no copiar: {e}')
        return ''
    valor = ''
    for _ in range(tentativas):
        page.wait_for_timeout(espera)
        valor = validar(_ler_clipboard(page))
        if valor:
            break
    for aba in contexto.pages[abas_antes:]:
        try:
            aba.close()
        except Exception:  # noqa: BLE001
            pass
    return valor


def _primeiro(*valores):
    for v in valores:
        if v:
            return v
    return ''


def _texto(page, alvo):
    try:
        el = _loc(page, alvo)
        if el.count() == 0:
            return ''
        return (el.inner_text() or '').strip()
    except Exception:  # noqa: BLE001
        return ''


def _esperar_visivel(page, seletor, espera_ms):
    """True se o elemento aparecer dentro do prazo. Nada aqui pode ser checado
    "na hora": tanto a barra de afiliado quanto o menu que ela abre sao
    montados em JavaScript alguns segundos depois -- conferir cedo demais
    devolve "ausente" para coisa que estava a caminho (aconteceu duas vezes na
    validacao de 11/09, com a barra e depois com o menu)."""
    try:
        page.locator(seletor).first.wait_for(state='visible', timeout=espera_ms)
        return True
    except Exception:  # noqa: BLE001
        return False


def _esperar_widget(page, seletor, espera_ms, loja):
    """Como _esperar_visivel, mas para o widget que depende de LOGIN -- por
    isso a mensagem aponta a sessao de afiliado como causa provavel."""
    if _esperar_visivel(page, seletor, espera_ms):
        return True
    print(f'[link_afiliado] {loja}: widget de afiliado nao apareceu em '
          f'{espera_ms / 1000:g}s (sessao de afiliado nao logada?).')
    return False


def _percentual(texto, rotulado=None, so_rotulado=False):
    """Percentual de um texto. `rotulado` (regex) tem prioridade: casando, e
    dele que sai o valor; so entao cai no "qualquer percentual do texto".
    `so_rotulado` desliga essa queda -- usado onde o escopo lido pode conter
    outros percentuais (um "-20% OFF" do produto viraria taxa de comissao)."""
    for regex in (rotulado, None if so_rotulado else _RE_PERCENTUAL):
        m = regex.search(texto or '') if regex else None
        if m:
            return m.group(1).replace(' ', '')
    return ''


def _casa(regex):
    def validar(texto):
        m = regex.search(texto or '')
        return m.group(0).rstrip('.,;)') if m else ''
    return validar


# --- Amazon (SiteStripe, na propria pagina do produto) ------------------------
AMZ_CATEGORIA = '#amzn-ss-category-content'
AMZ_COMISSAO = '#amzn-ss-commission-rate-content'
AMZ_BOTAO_LINK = '#amzn-ss-get-link-button'
AMZ_BOTAO_COPIAR = ('#amzn-ss-copy-affiliate-link-btn-announce, '
                    '#amzn-ss-copy-affiliate-link-btn, '
                    'button:has-text("Copiar link de associado")')
# Caixas onde o proprio dialogo mostra o link (2a via, se o clipboard falhar).
AMZ_CAIXA_LINK = ('#amzn-ss-text-shortlink-textarea, '
                  'textarea[id*="amzn-ss"], input[id*="amzn-ss"]')
# 15s: o SiteStripe normalmente vem junto com a pagina, mas em produca (11/09)
# a PRIMEIRA oferta Amazon da execucao perdeu o widget com 10s -- a barra so
# assenta depois que a aba termina de se acomodar no arranque.
AMZ_ESPERA_MS = 15000


def _valida_amazon(texto):
    return _primeiro(_casa(_RE_AMAZON_CURTO)(texto), _casa(_RE_AMAZON_LONGO)(texto))


def _amazon(page, url_final):
    # O SiteStripe vem junto com a pagina, mas nao custa esperar um pouco: se
    # ja estiver la, o wait retorna na hora.
    if not _esperar_widget(page, AMZ_BOTAO_LINK, AMZ_ESPERA_MS, 'amazon'):
        return {}
    out = {
        'categoria_afiliado': _texto(page, AMZ_CATEGORIA),
        'taxa_comissao_afiliado': _percentual(_texto(page, AMZ_COMISSAO)),
    }
    page.locator(AMZ_BOTAO_LINK).first.click(timeout=10000)
    copiar = page.locator(AMZ_BOTAO_COPIAR).first
    try:
        copiar.wait_for(state='visible', timeout=15000)
    except Exception:  # noqa: BLE001
        print('[link_afiliado] amazon: dialogo do "Obter link" nao abriu.')
        return out
    out['url_afiliado'] = _primeiro(
        _copiar_e_ler(page, copiar, _valida_amazon),
        _valida_amazon(_texto_do_bloco(page, AMZ_CAIXA_LINK)),
    )
    try:                                   # fecha o dialogo p/ nao atrapalhar
        page.keyboard.press('Escape')
    except Exception:  # noqa: BLE001
        pass
    return out


# --- Mercado Livre (barra de afiliado, na propria pagina do produto) ----------
ML_BOTAO = '[data-testid="generate_link_button"]'
# Campos e botoes do menu "Compartilhar", mapeados no HTML real em 2026-09-11
# (ml_dump_barra.py -> destino/ml_barra_dump.html). Todos tem data-testid
# proprio: nao dependem das classes "andes-*", que mudam a cada deploy.
ML_CAMPO_LINK = 'textarea[data-testid="text-field__label_link"]'
ML_CAMPO_ID = 'textarea[data-testid="text-field__label_id"]'
ML_COPIAR_LINK = 'button[data-testid="copy-button__label_link"]'
ML_COPIAR_ID = 'button[data-testid="copy-button__label_id"]'
# Onde mora o "GANHOS x%" (a barra do app de afiliados, fora do menu).
ML_ESCOPO_TAXA = '.toolbar__actions, nav.stripe, #stripe'
# A barra so e INJETADA alguns segundos depois de a pagina do produto carregar
# (validado ao vivo em 2026-09-10: checar na hora dava "barra ausente" com a
# barra a caminho). Ela e generosa de proposito -- quem nao tem sessao de
# afiliado paga essa espera uma vez por oferta.
ML_ESPERA_MS = 20000
# Tempo para o menu "Compartilhar" se montar depois do clique.
ML_MENU_ESPERA_MS = 12000


def _valida_meli_link(texto):
    return _casa(_RE_MELI)(texto)


def _valida_meli_id(texto):
    texto = (texto or '').strip()
    if not texto or _RE_MELI.search(texto) or texto.startswith('http'):
        return ''
    return texto if _RE_ID_ML.match(texto) else ''


def _ancestral(botao, nivel):
    """N-esimo ancestral do botao ([1] = pai: o eixo ancestor do XPath e
    reverso). Subir a partir do botao e mais estavel que ter um seletor
    proprio p/ cada pedaco da barra -- as classes "andes-*" do Mercado Livre
    mudam a cada deploy, o data-testid do botao nao."""
    return botao.locator(f'xpath=ancestor::*[{nivel}]')


def _valor_campo(page, seletor, validar, tentativas=20, espera=500):
    """Espera um campo do menu ser PREENCHIDO e devolve o valor ja validado.

    O Mercado Livre gera link e ID de forma ASSINCRONA depois que o menu abre:
    no HTML capturado 2,5s apos o clique os dois <textarea> ainda estavam
    vazios (ml_dump_barra.py, 11/09). Ler na hora devolve string vazia -- foi
    o que fez as ofertas do ML sairem sem link em producao."""
    campo = page.locator(seletor).first
    for tentativa in range(tentativas):
        try:
            if campo.count():
                valor = validar((campo.input_value() or '').strip())
                if valor:
                    return valor
        except Exception:  # noqa: BLE001
            pass
        if tentativa < tentativas - 1:
            page.wait_for_timeout(espera)
    return ''


def _taxa_ml(page, escopos, tentativas=6, espera=400):
    """"GANHOS 16%" -> "16%", insistindo um pouco: a barra aparece ANTES de
    terminar de calcular a comissao do produto (validado ao vivo em
    2026-09-11: link e codigo vinham, taxa vinha vazia). `escopos` sao os
    ancestrais candidatos a "barra" -- so vale o percentual que vier com o
    rotulo GANHOS (o escopo ainda pode pegar um "-20% OFF" da pagina).
    Desistindo, imprime o que leu: e o unico jeito de descobrir, sem
    reproduzir a mao, se o rotulo mudou ou se o produto nao mostra comissao."""
    texto = ''
    for tentativa in range(tentativas):
        for escopo in escopos:
            texto = _texto(page, escopo)
            taxa = _percentual(texto, _RE_GANHOS, so_rotulado=True)
            if taxa:
                return taxa
        if tentativa < tentativas - 1:
            page.wait_for_timeout(espera)
    print('[link_afiliado] mercadolivre: taxa de comissao nao achada na barra '
          f'(texto lido: {" ".join(texto.split())[:120]!r})')
    return ''


def _mercadolivre(page, url_final):
    out = {}
    if not _esperar_widget(page, ML_BOTAO, ML_ESPERA_MS, 'mercadolivre'):
        return out
    botao = page.locator(ML_BOTAO).first
    botao.click(timeout=10000)
    # O menu e um tooltip montado depois do clique (no HTML capturado ele so
    # existia ~2,5s depois) -- esperar o CAMPO e o jeito certo de saber que
    # abriu; conferir logo apos o clique acusa "nao abriu" com o menu vindo.
    if not _esperar_visivel(page, ML_CAMPO_LINK, ML_MENU_ESPERA_MS):
        print('[link_afiliado] mercadolivre: o menu "Compartilhar" nao abriu em '
              f'{ML_MENU_ESPERA_MS / 1000:g}s (campo do link ausente).')
        return out

    # 1a via: o VALOR do campo. E o proprio link que o ML acabou de gerar --
    # nada de clicar as cegas nem depender da area de transferencia.
    link = _valor_campo(page, ML_CAMPO_LINK, _valida_meli_link)
    # 2a via: o botao de copiar do campo (alvo exato, pelo data-testid).
    if not link and page.locator(ML_COPIAR_LINK).count():
        link = _copiar_e_ler(page, page.locator(ML_COPIAR_LINK).first, _valida_meli_link)
    # O ID enche junto com o link: se o link ja veio, aqui a espera e curta.
    id_produto = _valor_campo(page, ML_CAMPO_ID, _valida_meli_id,
                              tentativas=6, espera=300)
    if not id_produto and page.locator(ML_COPIAR_ID).count():
        id_produto = _copiar_e_ler(page, page.locator(ML_COPIAR_ID).first, _valida_meli_id)

    out['url_afiliado'] = link
    out['id_produto_afiliado'] = id_produto
    # O "GANHOS x%" fica na barra, FORA do menu (.toolbar__actions); os
    # ancestrais entram como reserva caso essas classes mudem.
    out['taxa_comissao_afiliado'] = _taxa_ml(
        page, [page.locator(ML_ESCOPO_TAXA).first, _ancestral(botao, 3),
               _ancestral(botao, 4)])
    try:                                   # fecha o menu
        page.keyboard.press('Escape')
    except Exception:  # noqa: BLE001
        pass
    return out


# --- Shopee (gerador em affiliate.shopee.com.br, em aba separada) -------------
SHP_URL = 'https://affiliate.shopee.com.br/offer/custom_link'
SHP_TEXTAREA = 'form textarea.ant-input, form textarea'
SHP_SUBMIT = ('form button[type="submit"]:has-text("Obter link"), '
              'button.mkt-btn:has-text("Obter link")')
SHP_COPIAR = 'button:has-text("Copiar Link")'
SHP_MODAL = '.ant-modal-content, .ant-modal, [role="dialog"]'


def _aba_shopee(page):
    """Aba dedicada ao painel de afiliados da Shopee, reaproveitada entre as
    ofertas (o login mora nela; abrir uma aba por oferta so faria a Shopee ver
    mais trafego). A aba do produto nunca sai do lugar."""
    contexto = page.context
    for aba in contexto.pages:
        if aba is not page and not aba.is_closed() and 'affiliate.shopee' in (aba.url or ''):
            return aba
    nova = contexto.new_page()
    nova.set_default_timeout(15000)
    return nova


def _shopee(page, url_final):
    # A URL colada no gerador e a DS_URL_FINAL (a pagina real do produto), SEM
    # passar pela DS_URL_BESAVE: o gerador so precisa reconhecer o produto e
    # ele proprio poe o nosso codigo no link. Decisao do usuario (2026-09-24):
    # o link de afiliado nao pode depender da troca de parametros por regex
    # de core/afiliados.py.
    alvo = (url_final or '').strip()
    if not alvo:
        return {}
    aba = _aba_shopee(page)
    try:
        aba.bring_to_front()
        aba.goto(SHP_URL, wait_until='domcontentloaded', timeout=60000)
        campo = aba.locator(SHP_TEXTAREA).first
        try:
            campo.wait_for(state='visible', timeout=20000)
        except Exception:  # noqa: BLE001
            print('[link_afiliado] shopee: formulario do custom_link nao abriu '
                  f'(sessao de afiliado nao logada? url={aba.url[:70]}).')
            return {}
        campo.fill(alvo)
        aba.locator(SHP_SUBMIT).first.click(timeout=10000)
        copiar = aba.locator(SHP_COPIAR).first
        try:
            copiar.wait_for(state='visible', timeout=30000)
        except Exception:  # noqa: BLE001
            print('[link_afiliado] shopee: o gerador nao devolveu link p/ esta URL.')
            return {}
        return {'url_afiliado': _primeiro(
            _copiar_e_ler(aba, copiar, _casa(_RE_SHOPEE)),
            _casa(_RE_SHOPEE)(_texto_do_bloco(aba, SHP_MODAL)),
        )}
    finally:
        try:                               # devolve o foco p/ a aba do produto
            page.bring_to_front()
        except Exception:  # noqa: BLE001
            pass


_FLUXOS = {
    'amazon': _amazon,
    'mercadolivre': _mercadolivre,
    'shopee': _shopee,
}


def _desistir_da_loja(loja, veio_link):
    """Corta-circuito por loja. Sessao de afiliado que cai no meio de uma
    execucao longa faria TODA oferta daquela loja pagar a espera do widget
    (ate 20s no ML) sem chance de sucesso. Depois de LIMITE_FALHAS ofertas
    seguidas sem link, o fluxo daquela loja para ate o proximo arranque (que e
    quando os gates de login rodam de novo). Sucesso zera a contagem."""
    if veio_link:
        _falhas_seguidas[loja] = 0
        return
    _falhas_seguidas[loja] = _falhas_seguidas.get(loja, 0) + 1
    if _falhas_seguidas[loja] >= LIMITE_FALHAS and loja not in _desistidas:
        _desistidas.add(loja)
        print(f'[link_afiliado] {loja}: {LIMITE_FALHAS} ofertas seguidas sem '
              'link -- DESLIGANDO a captura do link nesta loja ate reiniciar o '
              'programa (sessao de afiliado provavelmente caiu).')


def capturar(page, loja, url_final=''):
    """Link oficial de afiliado (+ categoria/taxa/codigo, quando a loja
    entrega) da oferta que ESTA ABERTA em `page`. Chamar DEPOIS da captura do
    produto e do download das imagens -- o fluxo clica em botoes e, na Shopee,
    usa outra aba.

    Devolve sempre um dict com todas as chaves de CAMPOS ('' quando nao veio).
    Nunca levanta excecao: loja sem fluxo, sessao deslogada ou layout mudado
    resultam em campos vazios (NULL no banco), nunca em captura perdida."""
    resultado = vazio()
    fluxo = _FLUXOS.get(loja)
    if not _habilitado or fluxo is None or loja in _desistidas:
        return resultado
    try:
        resultado.update({k: v for k, v in (fluxo(page, url_final) or {}).items()
                          if k in CAMPOS and v})
    except Exception as e:  # noqa: BLE001
        print(f'[link_afiliado] {loja}: {type(e).__name__}: {str(e).splitlines()[0]}')
    _desistir_da_loja(loja, bool(resultado['url_afiliado']))
    return resultado
