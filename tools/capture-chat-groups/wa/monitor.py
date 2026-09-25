"""
Loop de monitoramento por polling.

- Le periodicamente as mensagens do painel (#main).
- Deduplica por data-id (id unico de cada mensagem no WhatsApp) DENTRO da execucao
  e, ENTRE execucoes, pelo estado salvo por grupo (wa/estado.py): retoma desde a
  ultima mensagem lida (data/hora + data-id), sem repetir nem perder mensagens.
- Ignora notificacoes do sistema (fixou mensagem, mudou imagem, separadores de
  data), processando apenas balões reais (que contem [data-testid="msg-container"]).

Ordem de decisao no arranque de cada grupo:
  1. --max N  -> SWEEP das ultimas ~N msgs (IGNORA o controle de data).
  2. --force-capture-today -> captura tudo desde 00:00 de hoje.
  3. estado salvo do grupo -> retoma desde a ultima mensagem lida.
  4. sem estado -> baseline (so mensagens novas dali pra frente).
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import browser, estado as estado_mod, oracle_db, parser, storage

SELETOR_MENSAGENS = '#main [data-testid="conversation-panel-messages"] div[data-id]'

# Teto de seguranca de itens coletados no catch-up (evita varrer historico
# gigante se o estado salvo for muito antigo).
#
# Subiu de 2000 para 6000 em 02/08/2026: bater no teto PARA A SUBIDA, ou seja,
# perde justamente a parte mais ANTIGA do atraso — o oposto do que se quer num
# catch-up longo. Com ~600 ofertas/dia nos 3 grupos, 2000 nao cobria nem um
# atraso de 2 dias. Quando o teto dispara, ele avisa no log.
TETO_ITENS = 6000

# Limiar de "lacuna" no rodizio ao vivo (Fase 2).
#
# Uma volta completa nos 3 grupos leva ~20s. Passar disso so acontece se o
# processo CONGELOU (stand by da maquina) ou se a pagina morreu e todos os
# grupos cairam no timeout. Ver _recuperar_lacuna.
LACUNA_RECAPTURA_S = 10 * 60

# Voltas seguidas em que TODOS os grupos falharam ao abrir antes de forcar o
# catch-up.
#
# O LACUNA_RECAPTURA_S acima nao cobre este caso: ele mede o relogio de parede
# entre voltas, e existe uma falha em que as voltas continuam girando NA HORA
# CERTA e mesmo assim nada e capturado. Medido em 03/08/2026: um dialogo modal
# do WhatsApp Web ('role=dialog aria-modal=true') ficou aberto das 12:36 as
# 13:24 e interceptou o clique na lista de conversas — 83 erros consecutivos,
# nos 3 grupos, 48 min sem abrir grupo nenhum. Como cada volta terminava em
# ~105s, o relogio nunca saltou e a guarda de lacuna nunca disparou.
#
# Naquele dia nao houve perda (48 min de atraso ainda cabiam na viewport
# renderizada, e a leitura ao vivo recolheu tudo ao destravar), mas um bloqueio
# de algumas horas jogaria o atraso para fora da viewport — e o rodizio nao
# volta no historico. Dai a guarda.
#
# 5 voltas cegas ~= 9 min de bloqueio, no mesmo espirito do limiar acima.
# Enquanto o bloqueio durar, o proprio catch-up tambem falha (ele clica); o
# ganho e que o resgate fica PENDENTE e dispara sozinho assim que a pagina
# destravar, em vez de o atraso se perder em silencio.
VOLTAS_CEGAS_RESGATE = 5

# Espera normal entre um scroll para cima e o proximo.
ESPERA_SCROLL_MS = 650

# Fracao da viewport que a subida avanca por iteracao.
#
# Medido em 28/07: com o passo antigo (0.85 da viewport) a subida colhia UMA
# janela renderizada (~6-15 baloes) e SALTAVA ~2,5h de historico — o CSV saia em
# blocos contiguos de 7-15 ofertas separados por buracos de 1,8-2,8h, e tres runs
# sobre a mesma janela devolveram conjuntos quase DISJUNTOS (65, 53 e 57 ofertas,
# intersecao 1-2). O passo precisa ser MENOR que a janela renderizada para que
# duas iteracoes consecutivas se sobreponham; a sobreposicao e verificada de fato
# em _coletar_subindo (ids_antes & ids_depois).
PASSO_SUBIDA = 0.25

# ASSENTAMENTO: quantas vezes recoletar NA MESMA REGIAO antes de avancar.
#
# Medido em 28/07: um minuto denso pode ter 35 mensagens (28/07 13:18) e o DOM
# comporta as 35 AO MESMO TEMPO (pico renderizado = 35) — mas uma passagem so
# colhe ~8, porque no instante em que amostramos a lista virtualizada renderizou
# apenas parte do lote. Duas varreduras do MESMO minuto no mesmo dia contaram 35
# e 8. Dai quatro runs sobre a mesma janela sairem com conjuntos DISJUNTOS.
#
# As quatro correcoes anteriores mexiam em COMO CAMINHAR; a perda vem de NAO
# PARAR. Aqui a subida recoleta no lugar (com um micro-movimento que forca a
# lista a re-renderizar a regiao sem sair dela) ate duas passadas seguidas nao
# trazerem nenhum data-id novo.
ASSENTAMENTO_MAX = 6
ASSENTAMENTO_VAZIAS = 2
ASSENTAMENTO_NUDGE = 0.35
ASSENTAMENTO_ESPERA_MS = 300

# Backoff de quando a subida ENCOSTA no topo sem o historico crescer.
#
# Medido em 28/07: com nao-lidas, o salto ao fim (_ir_ao_fim) faz a lista
# virtualizada DESCARTAR o historico ja carregado (ex.: 54 baloes/34848px ->
# 1 balao/922px). Nesse estado o scrollTop ja nasce em ~0, entao "estou no topo"
# fica trivialmente verdadeiro e a parada dispara quase de imediato. Como o
# WhatsApp devolve o historico em RAJADAS de ~5000px a cada ~5s, os 3 x 650ms
# fixos de antes davam so ~2s para distinguir "fim do chat" de "servidor ainda
# respondendo" — e a subida encerrava em 7s tendo lido 1 mensagem.
#
# Agora cada tentativa no topo espera um pouco mais; so depois de esgotar a
# lista (~15s de espera acumulada) declaramos inicio do chat. O custo so existe
# no fim REAL do historico: uma vez por grupo, por execucao.
ESPERA_TOPO_MS = (1_000, 2_000, 3_000, 4_000, 5_000)

# Acha o container rolavel das mensagens (o WhatsApp virtualiza a lista: so o
# que esta renderizado existe no DOM) e executa um comando de scroll, sempre
# re-achando o elemento (evita handle "stale" quando a lista re-renderiza).
# cmd: 'info' (so le), 'bottom', 'up', 'down'. Retorna {top, h, c} ou None.
_JS_SCROLL = r"""
([cmd, frac]) => {
  const panel = document.querySelector('#main [data-testid="conversation-panel-messages"]');
  let el = panel;
  while (el && el !== document.body) {
    const st = getComputedStyle(el);
    if ((st.overflowY === 'auto' || st.overflowY === 'scroll')
        && el.scrollHeight > el.clientHeight + 50) { break; }
    el = el.parentElement;
  }
  if (!el) el = panel;
  if (!el) return null;
  const f = frac || 0.85;
  if (cmd === 'bottom')    el.scrollTop = el.scrollHeight;
  else if (cmd === 'up')   el.scrollTop -= el.clientHeight * f;
  else if (cmd === 'down') el.scrollTop += el.clientHeight * f;
  return {top: Math.round(el.scrollTop),
          h:   Math.round(el.scrollHeight),
          c:   Math.round(el.clientHeight)};
}
"""


def _scroll(page, cmd: str, frac: float = 0.85):
    """Executa um comando de scroll no painel de mensagens. Ver _JS_SCROLL."""
    return page.evaluate(_JS_SCROLL, [cmd, frac])


def _ids_renderizados(page) -> set:
    """
    data-ids de TUDO que esta renderizado agora (inclusive notificacoes e
    separadores). E o retrato da "janela" atual da lista virtualizada, usado
    para exigir SOBREPOSICAO entre uma iteracao e a seguinte.
    """
    return {i for i, _hid in page.evaluate(_JS_INVENTARIO)}


def _seletor_do_id(data_id: str) -> str:
    """Seletor CSS de um balao especifico. json.dumps cuida das aspas."""
    return (f'#main [data-testid="conversation-panel-messages"] '
            f'div[data-id={json.dumps(data_id)}]')


def _achar_balao(page, data_id: str):
    """
    ElementHandle do balao com esse data-id, se ainda estiver renderizado.

    Busca DIRETA pelo seletor: a versao antiga varria `query_selector_all` e
    comparava `get_attribute` um a um, ou seja um round-trip por balao
    renderizado para achar UM. Como isto e chamado dentro de lacos (coleta e
    reaproximacao), era custo multiplicado.
    """
    return page.query_selector(_seletor_do_id(data_id))


def _dbg_subida() -> bool:
    """
    Instrumentacao da subida do catch-up/sweep (WA_DEBUG_SUBIDA=1).

    Desligada por padrao: em producao a subida ja imprime uma linha por captura,
    e o log por iteracao so interessa quando se esta medindo ONDE a subida para.
    """
    return os.environ.get("WA_DEBUG_SUBIDA", "") == "1"


def _ancora_mais_antiga(page):
    """
    (ElementHandle, data-id) do balao MAIS ANTIGO renderizado agora.

    E a ancora da subida e tambem o medidor de progresso: se depois de rolar o
    balao mais antigo continua sendo o mesmo, nenhum historico novo chegou.
    Ordem do DOM na lista de mensagens e cronologica, entao o primeiro e o mais
    antigo. Aqui NAO se filtra por msg-container: notificacoes de sistema e
    separadores tambem servem de ancora (o que importa e a borda do renderizado).
    """
    inv = page.evaluate(_JS_INVENTARIO)
    if not inv:
        return None, None
    data_id = inv[0][0]
    return _achar_balao(page, data_id), data_id


def _elts_baloes(page):
    """ElementHandles das mensagens (baloes reais) renderizadas agora, ordem DOM."""
    out = []
    for m in page.query_selector_all(SELETOR_MENSAGENS):
        if m.get_attribute("data-id") and m.query_selector('[data-testid="msg-container"]') is not None:
            out.append(m)
    return out


def _ids_baloes(page):
    """data-ids das mensagens (baloes reais) renderizadas agora, em ordem DOM."""
    return [i for i, hidratado in page.evaluate(_JS_INVENTARIO) if hidratado]


def _ir_ao_fim(page):
    """Salta para a mensagem mais recente (fim do chat)."""
    # Atalho: o botao de "descer" (aparece quando ha nao-lidas) salta pro fim.
    chevron = page.locator('[data-testid="ic-chevron-down-wide"]')
    try:
        if chevron.count() > 0:
            chevron.first.click(timeout=3_000)
            page.wait_for_timeout(800)
    except Exception:  # noqa: BLE001
        pass
    # Garante o fim mesmo sem o botao (ou se ele nao levou 100% ao fundo).
    for _ in range(40):
        _scroll(page, "bottom")
        page.wait_for_timeout(350)
        info = _scroll(page, "info")
        if not info or info["top"] + info["c"] >= info["h"] - 8:
            break


def _reaproximar(page, data_id: str, tentativas: int = 12) -> bool:
    """
    Continuidade perdida: desce ate o balao 'data_id' voltar a estar renderizado.

    Chamado quando a janela renderizada nova nao toca a anterior — sinal de que a
    lista pulou um trecho. Sem isso o trecho pulado nunca entra no DOM enquanto
    amostramos e as mensagens dele se perdem EM SILENCIO (foi o que produziu os
    buracos de ~2,5h medidos em 28/07). Retorna True se reencontrou a ancora.
    """
    for _ in range(tentativas):
        el = _achar_balao(page, data_id)
        if el is not None:
            try:
                el.scroll_into_view_if_needed(timeout=5_000)
            except Exception:  # noqa: BLE001
                pass
            return True
        _scroll(page, "down", PASSO_SUBIDA)
        page.wait_for_timeout(ESPERA_SCROLL_MS)
    return False


def _esperar_painel_estavel(page, *, timeout_s: float = 5.0, leituras_iguais: int = 2) -> None:
    """
    Espera o painel parar de mudar depois do salto ao fim, ANTES da 1a coleta.

    O _ir_ao_fim reposiciona a lista e o WhatsApp leva um tempo re-renderizando
    em volta do fim; coletar em cima dessa transicao le um DOM pela metade.

    PASSIVO de proposito: aqui NAO se rola. Rolar antes da primeira coleta
    arriscaria virtualizar para fora justamente as mensagens MAIS NOVAS (que no
    catch-up ficam abaixo do divisor de nao-lidas) antes de a subida te-las lido.
    Quem cuida do painel degenerado e a espera com backoff da subida
    (ESPERA_TOPO_MS) — ali ja e seguro, porque a coleta acontece a cada volta.
    """
    t0 = time.monotonic()
    anterior = None
    iguais = 0
    while time.monotonic() - t0 < timeout_s:
        info = _scroll(page, "info")
        atual = (info["h"], info["top"]) if info else None
        if atual is not None and atual == anterior:
            iguais += 1
            if iguais >= leituras_iguais:
                return
        else:
            iguais = 0
        anterior = atual
        page.wait_for_timeout(300)


# Inventario da janela renderizada em UMA ida ao browser: [[data-id, hidratado]].
# 'hidratado' = ja tem [msg-container], isto e, o conteudo do balao foi montado.
_JS_INVENTARIO = r"""
() => {
  const sel = '#main [data-testid="conversation-panel-messages"] div[data-id]';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const id = el.getAttribute('data-id');
    if (!id) continue;
    out.push([id, !!el.querySelector('[data-testid="msg-container"]')]);
  }
  return out;
}
"""

# Quantas vezes insistir em hidratar um data-id antes de aceitar que ele e mesmo
# notificacao do sistema (separador de data, "fulano entrou", etc.).
HIDRATACAO_TENTATIVAS = 3

# Teto de pendentes hidratados por passada.
HIDRATACAO_POR_PASSADA = 40
HIDRATACAO_ESPERA_MS = 150

# Pausa entre um scrollIntoView e o proximo, DENTRO do browser (ver _JS_HIDRATAR).
HIDRATACAO_PASSO_MS = 60

# Hidrata varios pendentes em UMA ida ao browser.
#
# Medido em 29/07 (sweep de 60 no #03): a hidratacao era 78,9s de 97,7s = 81%
# do run, em 156 scrolls a ~0,5s cada. O custo NAO era rolar — era usar
# `scroll_into_view_if_needed` por elemento, que faz as checagens de
# actionability do Playwright (espera visivel + estavel) e gasta um round-trip
# por chamada. Para montar o balao nada disso e necessario: basta o
# scrollIntoView nativo, que dispara o mesmo observer de viewport.
_JS_HIDRATAR = r"""
async ([ids, passoMs]) => {
  const base = '#main [data-testid="conversation-panel-messages"] div[data-id=';
  let tocados = 0;
  for (const id of ids) {
    const el = document.querySelector(base + JSON.stringify(id) + ']');
    if (!el) continue;
    el.scrollIntoView({block: 'center'});
    tocados++;
    await new Promise(r => setTimeout(r, passoMs));
  }
  return tocados;
}
"""


def _coletar_novas(page, vistos: set):
    """
    Retorna (novas, pendentes):
      - novas:     ElementHandles de mensagens hidratadas e ainda nao processadas;
      - pendentes: data-ids renderizados que ainda NAO tem [msg-container].

    Um item sem msg-container NAO e necessariamente notificacao do sistema. A
    lista virtualizada RESERVA a caixa do balao antes de ter o conteudo: medido
    em 29/07 no #03, esses itens sao caixas de ~694x570 com innerText VAZIO (um
    separador de data tem ~30px, entao nao e separador).

    O numero que importa: 47 de 60 data-ids (78%) estavam nesse estado no
    instante em que a subida amostra (650ms apos o scroll), e NENHUM hidratou ao
    esperar 4s parado — hidratar depende de PROXIMIDADE DA VIEWPORT, nao de
    tempo. E a mesma fisica do bug da imagem de 19/07: fora da viewport o
    elemento existe no DOM sem estar realmente montado.

    Antes, o pendente ia para 'vistos' aqui. Como nada volta a ler um id ja
    visto — nem o assentamento, que so recolhe data-id inedito — a mensagem se
    perdia PARA SEMPRE, em silencio. Era a causa dominante da amostragem: 75% da
    perda medida nos baselines de 28/07 era de minuto INTEIRO zerado, e um lote
    postado no mesmo minuto e exatamente um bloco contiguo de pendentes.

    Agora o pendente NAO entra em 'vistos'; quem resolve e _hidratar_pendentes.

    Custo: o inventario sai em UMA ida ao browser (_JS_INVENTARIO). A versao
    anterior fazia `query_selector_all` + um `get_attribute` e um
    `query_selector` POR ELEMENTO renderizado — com ~60 baloes na janela davam
    ~120 round-trips por passada, repetidos em cada passada do assentamento.
    Agora so os que serao mesmo lidos (poucos) custam um handle.
    """
    novas, pendentes = [], []
    for data_id, hidratado in page.evaluate(_JS_INVENTARIO):
        if data_id in vistos:
            continue
        if not hidratado:
            pendentes.append(data_id)
            continue
        msg = _achar_balao(page, data_id)
        if msg is None:
            continue                          # re-renderizou entre o inventario e o handle
        novas.append((data_id, msg))
    return novas, pendentes


def _hidratar_pendentes(page, pendentes, tentativas: dict, vistos: set) -> int:
    """
    Traz os data-ids pendentes para perto da viewport para que o WhatsApp monte o
    conteudo, e devolve quantos foram efetivamente tocados.

    Depois de HIDRATACAO_TENTATIVAS insistencias sem virar balao, o id e aceito
    como notificacao do sistema de verdade e vai para 'vistos' — senao separador
    de data seria re-visitado a cada passada, para sempre.
    """
    alvos = []
    for data_id in pendentes[:HIDRATACAO_POR_PASSADA]:
        n = tentativas.get(data_id, 0) + 1
        tentativas[data_id] = n
        if n > HIDRATACAO_TENTATIVAS:
            vistos.add(data_id)              # e mesmo notificacao do sistema
            continue
        alvos.append(data_id)
    if not alvos:
        return 0
    try:
        tocados = page.evaluate(_JS_HIDRATAR, [alvos, HIDRATACAO_PASSO_MS]) or 0
    except Exception:  # noqa: BLE001
        return 0                             # painel re-renderizou: proxima passada tenta
    if tocados:
        page.wait_for_timeout(HIDRATACAO_ESPERA_MS)
    return tocados


def _descartar_tmp(img_tmp: str) -> None:
    """Apaga uma imagem temporaria coletada mas descartada (fora do corte)."""
    if not img_tmp:
        return
    try:
        Path(img_tmp).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def _coletar_subindo(page, *, limite: int = 0, cutoff_dt=None, marker_id=None, janela=None):
    """
    Vai ao fim do chat e SOBE coletando itens (subir e o unico movimento
    confiavel na lista virtualizada do WhatsApp). Para cada balao com conteudo,
    extrai os campos e salva a imagem num nome temporario (tmpN).

    Dois modos de parada:
      - limite > 0 (SWEEP): coleta ate ~limite itens com conteudo.
      - cutoff_dt / marker_id (CATCH-UP): continua subindo ate encontrar o
        data-id marcador (marker_id) OU ver uma mensagem mais antiga que
        cutoff_dt. Nao filtra aqui — devolve tudo o que carregou; quem chama
        recorta pela posicao do marcador / pela data.

    Retorna (cronologico, achou_marcador, processados):
    janela=(inicio, fim) restringe o que e GUARDADO a [inicio, fim). Serve ao
    re-varrimento de uma janela antiga: para alcancar 20/07 a subida precisa
    atravessar todos os dias seguintes, e salvar a imagem de cada mensagem do
    caminho (canvas + espera de ate 8s + marca d'agua) so para descartar depois
    domina o custo do run. Fora da janela a mensagem e contada e descartada
    antes do salvar_imagem. Nao afeta quem nao passa 'janela'.

    Retorna (cronologico, achou_marcador, processados):
      - cronologico: lista de dicts {campos, img_tmp, data_id, data_hora} em
        ordem cronologica (mais antiga -> mais nova);
      - achou_marcador: True se o marker_id apareceu na varredura;
      - processados: set de data-ids vistos (para alimentar o dedup ao vivo).
    """
    _ir_ao_fim(page)
    _esperar_painel_estavel(page)

    chunks: list = []
    processados: set = set()
    tmp_ct = 0
    total = 0
    estavel = 0
    achou_marcador = False
    passou_cutoff = False

    dbg = _dbg_subida()
    motivo_fim = "teto de iteracoes (3000)"    # sobrescrito por quem der o break
    mais_antiga = None                         # menor data/hora vista na subida
    quebras = 0                                # janelas que nao tocaram a anterior
    perdidas = 0                               # ... e que nem reaproximando voltaram
    t0 = time.monotonic()

    # DESTINO DE CADA BALAO VISTO (so diagnostico, ver WA_DEBUG_SUBIDA).
    #
    # Medido em 29/07 sobre os 3 baselines de 28/07 (mesma janela de 42,1h,
    # recortada para o trecho comum aos tres runs): a uniao tem 190 ofertas, cada
    # run pegou ~39%, e **75% da perda e de MINUTO INTEIRO ZERADO** (60 dos 102
    # minutos com oferta nao renderam NADA naquele run) — nao amostragem parcial
    # do lote, que responde pelos outros 25%. Isso reordena a suspeita de 28/07.
    #
    # O que faltava para escolher entre as duas explicacoes possiveis de um minuto
    # zerado — "o balao nunca esteve no DOM enquanto amostravamos" (problema de
    # CAMINHADA) vs "o balao esteve no DOM e foi descartado" (problema de LEITURA)
    # — e saber o DESTINO dos baloes vistos. Hoje 'sem conteudo' e indistinguivel
    # de 'veio vazio', e vazio e a assinatura de elemento virtualizado para fora
    # enquanto o chunk era processado (cada salvar_imagem rola e espera ate 8s,
    # entao um chunk longo demora o bastante para a lista re-renderizar).
    #
    # Importa porque quem ja entrou em 'processados' NUNCA e relido: o
    # assentamento so recolhe data-id inedito, nao repara balao lido em branco.
    d_erro_extrair = d_erro_parse = d_sem_conteudo = d_vazio = d_coletado = 0
    d_fora_janela = 0                          # so com janela=(inicio, fim)

    tentativas_hidr: dict = {}                 # data-id -> vezes que tentei hidratar
    n_hidratados = 0                           # scrolls feitos para montar pendentes

    # TEMPO POR FASE (so diagnostico). Sem isso "a subida esta lenta" nao diz
    # ONDE otimizar — e o gargalo aqui e round-trip com o browser, nao CPU.
    t_coletar = t_extrair = t_imagem = t_hidratar = t_navegar = 0.0
    lentas_img: list = []                      # (segundos, salvou?, nome)

    for it_n in range(1, 3001):                # teto de seguranca de iteracoes
        chunk = []
        parar_inner = False
        n_novas = 0
        vazias = 0

        # ASSENTA na regiao atual antes de avancar (ver ASSENTAMENTO_MAX).
        for _passada in range(ASSENTAMENTO_MAX):
          _t = time.monotonic()
          novas, pendentes = _coletar_novas(page, processados)
          t_coletar += time.monotonic() - _t
          n_novas += len(novas)
          for data_id, msg in novas:
            processados.add(data_id)
            _t = time.monotonic()
            try:
                bruto = parser.extrair_bruto(msg)
            except Exception as e:  # noqa: BLE001
                t_extrair += time.monotonic() - _t
                d_erro_extrair += 1
                print(f"[monitor] Erro ao extrair {data_id}: {e}")
                continue
            t_extrair += time.monotonic() - _t
            # Vazio = nem texto nem link nem imagem: o balao existe no DOM mas nao
            # entregou conteudo. E a assinatura de virtualizado-para-fora.
            if not ((bruto.get("text") or "").strip()
                    or bruto.get("links") or bruto.get("previewImg")):
                d_vazio += 1
            data_hora = parser.extrair_data_hora(bruto)
            if data_hora and (mais_antiga is None or data_hora < mais_antiga):
                mais_antiga = data_hora

            # Marcas de parada (nao interrompem o viewport: dentro dele a ordem e
            # antiga->nova, entao ainda pode haver mensagens novas mais abaixo).
            if marker_id and data_id == marker_id:
                achou_marcador = True
            if cutoff_dt and data_hora and data_hora < cutoff_dt:
                passou_cutoff = True

            try:
                campos = parser.parse_campos(bruto)
            except Exception as e:  # noqa: BLE001
                d_erro_parse += 1
                print(f"[monitor] Erro ao parsear {data_id}: {e}")
                continue
            if not _tem_conteudo(campos):
                d_sem_conteudo += 1
                continue

            # Fora da janela pedida: descarta ANTES de salvar a imagem, que e o
            # passo caro. O balao ja esta em 'processados', entao nao volta.
            if janela is not None:
                _ini, _fim = janela
                if data_hora is None or not (_ini <= data_hora < _fim):
                    d_fora_janela += 1
                    continue

            d_coletado += 1
            tmp_ct += 1
            _t = time.monotonic()
            img_tmp = storage.salvar_imagem(msg, bruto, f"tmp{tmp_ct}", _rotulo_imagem(campos))
            _dt_img = time.monotonic() - _t
            t_imagem += _dt_img
            if dbg:
                # Guarda as mais lentas: a fase 'imagem' varia muito entre runs
                # (13,9s e 29,3s no MESMO sweep de 60), e a duvida e se o custo e
                # uniforme ou se poucas mensagens estao estourando um timeout.
                lentas_img.append((_dt_img, bool(img_tmp),
                                   (campos.get("nome_do_produto") or "")[:34]))
            chunk.append({
                "campos": campos, "img_tmp": img_tmp,
                "data_id": data_id, "data_hora": data_hora,
            })
            total += 1
            if limite and total >= limite:
                parar_inner = True
                break

          if parar_inner:
              break

          # Pendente = balao renderizado que ainda nao montou o conteudo. Trazer
          # para perto da viewport e o UNICO jeito de monta-lo (medido: esperar
          # nao adianta). Enquanto houver pendente a regiao NAO esta esgotada —
          # contar essa passada como vazia encerraria o assentamento justamente
          # em cima do lote que estamos tentando ler.
          _t = time.monotonic()
          tocados = _hidratar_pendentes(page, pendentes, tentativas_hidr, processados)
          t_hidratar += time.monotonic() - _t
          n_hidratados += tocados

          # Duas passadas seguidas sem novidade = regiao esgotada, pode avancar.
          if novas or tocados:
              vazias = 0
          else:
              vazias += 1
              if vazias >= ASSENTAMENTO_VAZIAS:
                  break
          # Micro-movimento: forca a lista virtualizada a re-renderizar a regiao
          # (e o que faz o resto do lote aparecer) e volta para o mesmo ponto.
          _scroll(page, "up", ASSENTAMENTO_NUDGE)
          page.wait_for_timeout(ASSENTAMENTO_ESPERA_MS)
          _scroll(page, "down", ASSENTAMENTO_NUDGE)
          page.wait_for_timeout(ASSENTAMENTO_ESPERA_MS)

        if chunk:
            chunks.append(chunk)

        # Condicoes de parada da subida.
        if limite and total >= limite:
            motivo_fim = f"limite do sweep atingido ({total} >= {limite})"
            break
        if not limite and (achou_marcador or passou_cutoff):
            motivo_fim = ("marcador encontrado" if achou_marcador else "") + \
                         (" + " if achou_marcador and passou_cutoff else "") + \
                         ("passou o cutoff de data" if passou_cutoff else "")
            break
        if not limite and total >= TETO_ITENS:
            motivo_fim = f"teto de itens ({TETO_ITENS})"
            print(f"[monitor] Catch-up atingiu o teto de {TETO_ITENS} itens; parando a subida.")
            break

        # Sobe ANCORANDO NO ELEMENTO mais antigo, nao numa coordenada de scroll.
        #
        # Medido em 28/07: ao chegar perto do topo, a lista virtualizada RE-ANCORA
        # e joga o scrollTop ~31000px de volta para baixo (10 vezes num run de 566
        # iteracoes, sempre com top entre 394 e 951). Quem guia a subida pela
        # coordenada perde o lugar e re-renderiza uma fatia DIFERENTE do historico:
        # dois runs na mesma janela sairam com conjuntos quase DISJUNTOS (65 e 53
        # ofertas, intersecao 1-2), ou seja ~metade das mensagens nunca chegava a
        # estar no DOM no instante em que _coletar_novas amostra.
        #
        # A ancora e re-consultada a cada volta, entao a re-ancoragem deixa de
        # importar: voltamos sempre para a BORDA do que ja esta renderizado. O
        # 'up' logo depois e o empurrao que faz o WhatsApp buscar mais historico
        # (so trazer a ancora para a viewport nao dispara a busca quando ela ja
        # esta visivel).
        _t_nav = time.monotonic()
        ids_antes = _ids_renderizados(page)
        ancora, id_antes = _ancora_mais_antiga(page)
        info = _scroll(page, "info")
        if ancora is not None:
            try:
                ancora.scroll_into_view_if_needed(timeout=5_000)
            except Exception:  # noqa: BLE001
                pass                           # painel re-renderizou: o 'up' resolve
        # Passo CURTO (PASSO_SUBIDA): so o suficiente para o WhatsApp buscar mais
        # historico, sem empurrar a ancora para fora da janela renderizada.
        _scroll(page, "up", PASSO_SUBIDA)
        page.wait_for_timeout(ESPERA_SCROLL_MS)
        depois = _scroll(page, "info")
        _, id_depois = _ancora_mais_antiga(page)

        # SOBREPOSICAO OBRIGATORIA: a janela nova tem de tocar a anterior. Se nao
        # tocar, a lista pulou um trecho — volta para a ancora e reaproxima, senao
        # aquelas mensagens nunca serao lidas.
        ids_depois = _ids_renderizados(page)
        if ids_antes and ids_depois and not (ids_antes & ids_depois):
            quebras += 1
            if id_antes and _reaproximar(page, id_antes):
                page.wait_for_timeout(ESPERA_SCROLL_MS)
                _, id_depois = _ancora_mais_antiga(page)
            else:
                perdidas += 1
                print(f"[monitor] AVISO: salto sem sobreposicao na subida (it {it_n}) "
                      "e nao consegui reaproximar; pode haver mensagens nao lidas nesse trecho.")

        # Progresso agora e SEMANTICO: chegou balao mais antigo do que o que ja
        # tinhamos? Isso substitui o antigo 'scrollTop <= 2', que so era alcancavel
        # no painel degenerado e nada dizia sobre haver mais historico.
        parado = bool(id_antes and id_depois == id_antes
                      and (not info or not depois or depois["h"] <= info["h"] + 5))
        estavel = estavel + 1 if parado else 0
        t_navegar += time.monotonic() - _t_nav

        if dbg:
            _log_iteracao(it_n, info, depois, n_novas, total, len(processados),
                          mais_antiga, estavel, parado, time.monotonic() - t0)

        if parado:
            if estavel > len(ESPERA_TOPO_MS):
                espera_total = sum(ESPERA_TOPO_MS) / 1000
                motivo_fim = (f"topo estavel {estavel}x apos ~{espera_total:.0f}s de espera "
                              "(inicio do chat)")
                break
            # Ainda pode ser rajada de historico a caminho: espera mais e reavalia.
            # A proxima volta do laco recoleta antes de decidir de novo.
            page.wait_for_timeout(ESPERA_TOPO_MS[estavel - 1])

    if dbg:
        print(
            f"[subida] FIM apos {it_n} iteracoes em {time.monotonic() - t0:.1f}s | "
            f"motivo={motivo_fim} | coletados={total} | baloes vistos={len(processados)} | "
            f"mais antiga={estado_mod.fmt_dt(mais_antiga) or '-'} | "
            f"achou_marcador={achou_marcador} | passou_cutoff={passou_cutoff} | "
            f"quebras de sobreposicao={quebras} (nao recuperadas={perdidas})"
        )
        vistos_reais = (d_coletado + d_sem_conteudo + d_erro_extrair
                        + d_erro_parse + d_fora_janela)
        print(
            f"[subida] DESTINO dos {vistos_reais} baloes lidos: "
            f"coletados={d_coletado} | fora da janela={d_fora_janela} "
            f"| sem conteudo={d_sem_conteudo} "
            f"(desses, VAZIOS={d_vazio}) | erro ao extrair={d_erro_extrair} | "
            f"erro ao parsear={d_erro_parse}"
        )
        _tot = time.monotonic() - t0
        _outros = _tot - (t_coletar + t_extrair + t_imagem + t_hidratar + t_navegar)
        print(
            f"[subida] TEMPO POR FASE em {_tot:.1f}s: "
            f"imagem={t_imagem:.1f}s ({100*t_imagem/_tot:.0f}%) | "
            f"hidratar={t_hidratar:.1f}s ({100*t_hidratar/_tot:.0f}%) | "
            f"coletar={t_coletar:.1f}s ({100*t_coletar/_tot:.0f}%) | "
            f"extrair={t_extrair:.1f}s ({100*t_extrair/_tot:.0f}%) | "
            f"navegar={t_navegar:.1f}s ({100*t_navegar/_tot:.0f}%) | "
            f"outros={_outros:.1f}s ({100*_outros/_tot:.0f}%)"
        )
        if lentas_img:
            lentas_img.sort(reverse=True)
            mediana = sorted(s for s, _o, _n in lentas_img)[len(lentas_img) // 2]
            print(f"[subida] IMAGEM: {len(lentas_img)} salvamentos | "
                  f"mediana={mediana:.2f}s | 5 mais lentos:")
            for s, ok, nome in lentas_img[:5]:
                print(f"[subida]   {s:6.2f}s salvou={'sim' if ok else 'NAO '} {nome!r}")
        print(
            f"[subida] HIDRATACAO: {n_hidratados} scroll(s) para montar balao "
            f"pendente | {len(tentativas_hidr)} id(s) pendentes vistos | "
            f"{sum(1 for n in tentativas_hidr.values() if n > HIDRATACAO_TENTATIVAS)} "
            "aceitos como notificacao do sistema"
        )
        if d_vazio:
            print(
                f"[subida] ATENCAO: {d_vazio} balao(oes) vieram VAZIOS do DOM. "
                "Balao vazio ja entrou em 'processados' e NUNCA sera relido — nem "
                "pelo assentamento, que so recolhe data-id inedito. Se este numero "
                "for alto, a perda e de LEITURA (o balao esteve no DOM e foi lido "
                "em branco), nao de caminhada."
            )
    if perdidas:
        print(f"[monitor] ATENCAO: {perdidas} trecho(s) do historico podem nao ter sido lidos.")

    # Reordena para cronologico: os chunks foram coletados do mais NOVO para o
    # mais ANTIGO. A ordem DENTRO do chunk tambem precisa ser imposta — ver
    # _ordenar_cronologico.
    cronologico = _ordenar_cronologico([item for ch in reversed(chunks) for item in ch])
    return cronologico, achou_marcador, processados


def _ordenar_cronologico(itens):
    """
    Ordena os itens da subida por data/hora de verdade (antiga -> nova).

    A premissa antiga era "dentro de cada chunk a ordem ja e cronologica", porque
    o inventario do DOM sai na ordem da lista. O ASSENTAMENTO (28/07) e a
    HIDRATACAO (29/07) mataram essa premissa: a passada 1 colhe os baloes ja
    montados e as passadas seguintes ANEXAM AO MESMO CHUNK os que acabaram de
    hidratar — que sao cronologicamente ANTERIORES. Medido em 30/07 no carol: 47
    itens em 1 iteracao, 3 blocos internamente ascendentes, 2 pares descendentes.

    Nao e cosmetico: o recorte por POSICAO de _capturar_desde_ultima depende
    inteiramente disso. Com o marcador no indice 0 de uma lista fora de ordem, o
    recorte devolveu 46 itens (19 ANTERIORES ao marcador) em vez de 27; com o
    marcador caindo perto do fim, devolve ZERO e a captura perde o dia. Os dois
    sintomas de 30/07 sao a mesma causa, sorteada pela posicao do marcador.

    Item sem data/hora herda a do vizinho anterior em vez de ir para uma ponta:
    ele nao tem como ser comparado, e jogar para o fim mudaria sua vizinhanca
    justamente no recorte por posicao.
    """
    if len(itens) < 2:
        return itens
    ref = None
    chaves = []
    for i, it in enumerate(itens):
        if it.get("data_hora") is not None:
            ref = it["data_hora"]
        # O indice entra como desempate: mantem estavel quem tem a mesma data
        # (mensagens do mesmo minuto preservam a ordem em que o DOM as trouxe).
        chaves.append((ref is None, ref, i))
    return [itens[i] for i in sorted(range(len(itens)), key=lambda i: chaves[i])]


def _log_iteracao(it_n, info, depois, n_novas, total, n_vistos, mais_antiga,
                  estavel, parado, decorrido) -> None:
    """
    Uma linha por iteracao da subida (so com WA_DEBUG_SUBIDA=1).

    O que interessa medir: 'dh' (crescimento do scrollHeight) e 'parado' — este
    ultimo diz se o balao mais antigo do DOM continuou o mesmo, que e o sinal de
    progresso REAL da subida. 'top' fica so como diagnostico: um salto grande
    entre antes/depois sem dh correspondente e a lista virtualizada re-ancorando
    (era o que fazia a subida perder o lugar antes da ancora por elemento).
    """
    def _fmt(i):
        return f"top={i['top']:>6} h={i['h']:>7}" if i else "top=? h=?"

    cresceu = (depois["h"] - info["h"]) if (info and depois) else 0
    print(
        f"[subida] it={it_n:>3} {decorrido:>6.1f}s | antes {_fmt(info)} | "
        f"depois {_fmt(depois)} | dh={cresceu:>+7} | novas={n_novas:>3} "
        f"coletadas={total:>4} vistos={n_vistos:>4} | "
        f"antiga={estado_mod.fmt_dt(mais_antiga) or '-'} | "
        f"parado={int(bool(parado))} estavel={estavel}"
    )


def _gravar_cronologico(itens, nome_grupo, caminho_csv, numero_inicial: int, estado: dict,
                        db=None) -> int:
    """
    Numera, renomeia as imagens (tmp -> definitivo), grava as linhas no CSV e
    atualiza o estado do grupo com a mensagem mais recente processada. Recebe a
    lista JA na ordem cronologica. Retorna o novo contador.
    """
    numero = numero_inicial
    for it in itens:
        numero += 1
        campos = it["campos"]
        img_final = storage.renomear_imagem(it["img_tmp"], numero, _rotulo_imagem(campos))
        linha = _montar_linha(campos, nome_grupo, numero, img_final, it["data_hora"])
        storage.gravar_linha(caminho_csv, linha)
        db_ok = db.inserir_oferta(linha) if (db is not None and db.habilitado) else None
        # A cada leitura persiste CSV (acima) + config.json (contador global e
        # estado do grupo), para o arquivo ficar atualizado se o processo cair.
        estado_mod.set_ultimo_id(estado, numero, salvar_agora=False)
        estado_mod.atualizar_grupo(estado, nome_grupo, it["data_hora"], it["data_id"])
        print(
            f"[captura #{numero}] ({nome_grupo}) {campos['nome_do_produto'][:45]!r} | "
            f"por={campos['preco_por']} | cupom={campos['cupom']} | "
            f"img={'ok' if img_final else '-'}{_marca_db(db_ok)}"
        )
    return numero


def _varrer_ultimas(page, nome_grupo, caminho_csv, max_msgs: int, numero_inicial: int, estado: dict,
                    db=None):
    """
    SWEEP das ~max_msgs mensagens MAIS NOVAS do chat (IGNORA o controle de data).
    Retorna (numero, processados).
    """
    print(f"[monitor] Sweep '{nome_grupo}': subindo e capturando ate ~{max_msgs} promocoes...")
    cronologico, _achou, processados = _coletar_subindo(page, limite=max_msgs)
    numero = _gravar_cronologico(cronologico, nome_grupo, caminho_csv, numero_inicial, estado, db)
    print(f"[monitor] Sweep '{nome_grupo}' concluido: {numero - numero_inicial} promocoes.")
    return numero, processados


def _capturar_desde_ultima(page, nome_grupo, caminho_csv, numero_inicial: int, estado: dict,
                           db=None, *, cutoff_dt, marker_id, inclusivo: bool):
    """
    Captura tudo DESDE a ultima mensagem lida (catch-up). Sobe carregando ate o
    marcador/data de corte, recorta e grava so o que veio DEPOIS.

    - marker_id encontrado: recorta pela POSICAO (mensagem seguinte ao marcador
      em diante). Isso resolve varias mensagens no mesmo minuto.
    - marker_id nao encontrado (rolou para fora / apagado): recorta pela DATA
      (>= cutoff se 'inclusivo', senao > cutoff).

    Retorna (numero, processados).
    """
    cronologico, achou, processados = _coletar_subindo(page, cutoff_dt=cutoff_dt, marker_id=marker_id)

    resultado = None
    if marker_id and achou:
        ids = [it["data_id"] for it in cronologico]
        if marker_id in ids:
            resultado = cronologico[ids.index(marker_id) + 1:]
            # Com a lista ordenada (_ordenar_cronologico) nada depois do marcador
            # pode ser mais antigo que ele. Se for, a ordenacao regrediu: descarta
            # e RECLAMA. Em 30/07 esse caso passou em silencio e gravou 19 linhas
            # ja capturadas — barato de checar, caro de descobrir depois.
            if cutoff_dt:
                velhas = [it for it in resultado if it["data_hora"] and it["data_hora"] < cutoff_dt]
                if velhas:
                    print(f"[monitor] AVISO: {len(velhas)} item(ns) depois do marcador "
                          f"tinham data ANTERIOR a ele ({estado_mod.fmt_dt(cutoff_dt)}); "
                          "descartados. A ordenacao da subida regrediu.")
                    resultado = [it for it in resultado
                                 if not (it["data_hora"] and it["data_hora"] < cutoff_dt)]
    if resultado is None:
        if cutoff_dt:
            resultado = [
                it for it in cronologico
                if it["data_hora"] and (
                    it["data_hora"] >= cutoff_dt if inclusivo else it["data_hora"] > cutoff_dt
                )
            ]
        else:
            resultado = cronologico

    # Limpa as imagens temporarias coletadas mas descartadas (fora do corte).
    manter = {id(it) for it in resultado}
    for it in cronologico:
        if id(it) not in manter:
            _descartar_tmp(it["img_tmp"])

    numero = _gravar_cronologico(resultado, nome_grupo, caminho_csv, numero_inicial, estado, db)
    print(f"[monitor] Catch-up '{nome_grupo}' concluido: {numero - numero_inicial} nova(s) desde a ultima captura.")
    return numero, processados


def _marcar_baseline(page, nome_grupo, estado: dict) -> None:
    """
    Primeira visita SEM estado e sem flags: nao captura historico; apenas marca
    a mensagem mais recente atual como ponto de partida (proxima execucao ja
    retoma dali). Grava data/hora + data-id no estado.
    """
    _ir_ao_fim(page)
    page.wait_for_timeout(500)
    elts = _elts_baloes(page)
    data_id = None
    data_hora = None
    for m in reversed(elts):                   # do mais novo para o mais antigo
        did = m.get_attribute("data-id")
        try:
            bruto = parser.extrair_bruto(m)
        except Exception:  # noqa: BLE001
            continue
        # Marca no ultimo balao real (com ou sem promocao), preferindo um com data.
        if data_id is None:
            data_id = did
            data_hora = parser.extrair_data_hora(bruto)
        if parser.extrair_data_hora(bruto):
            data_id = did
            data_hora = parser.extrair_data_hora(bruto)
            break
    estado_mod.atualizar_grupo(estado, nome_grupo, data_hora, data_id)
    ref = estado_mod.fmt_dt(data_hora) or (data_id or "-")
    print(f"[{nome_grupo}] baseline: marcado ate {ref}; capturando so novas dali.")


def _ler_novas_do_grupo(page, nome_grupo, vistos, numero, caminho_csv, estado, db=None):
    """No grupo ja aberto, vai ao fim e processa as mensagens ainda nao vistas."""
    _ir_ao_fim(page)                       # garante que as mais novas estao renderizadas
    page.wait_for_timeout(500)
    novas, pendentes = _coletar_novas(page, vistos)
    # Ao vivo o lote novo costuma chegar montado (esta no fim, dentro da
    # viewport), mas um lote grande postado de uma vez cai no mesmo caso da
    # subida: caixa reservada, conteudo ainda nao montado. Hidratar e relecoletar
    # custa um scroll e evita perder a mensagem PARA SEMPRE.
    if pendentes:
        if _hidratar_pendentes(page, pendentes, {}, vistos):
            extras, _ = _coletar_novas(page, vistos)
            novas.extend(extras)
    # A guarda de 'vistos' aqui NAO e redundante: _coletar_novas nao marca nada,
    # quem marca e este laco. Com pendentes, a recoleta da linha acima devolve o
    # PRIMEIRO lote de novo (ainda nao esta em 'vistos') e o extend duplicava cada
    # mensagem — duas linhas no CSV e dois inserts no Oracle. Medido em 30/07: no
    # rodizio do Ly, #3094-3099 repetiam #3086-3091 (19 linhas duplicadas em 68).
    lidas = 0
    for data_id, msg in novas:
        if data_id in vistos:
            continue
        vistos.add(data_id)
        lidas += 1
        try:
            numero = _processar(msg, nome_grupo, numero, caminho_csv, data_id, estado, db)
        except Exception as e:  # noqa: BLE001
            print(f"[monitor] Erro ao processar {data_id}: {e}")
    return numero, lidas


_JS_BLOQUEIO = """
() => {
  const dialogos = [...document.querySelectorAll('[role="dialog"]')].map(d => ({
    modal: d.getAttribute('aria-modal') === 'true',
    rotulo: d.getAttribute('aria-label') || '',
    titulo: (document.getElementById(d.getAttribute('aria-labelledby') || '')
             || {}).innerText || '',
    texto: (d.innerText || '').replace(/\\s+/g, ' ').slice(0, 240),
  }));
  return {
    dialogos,
    tem_lista: !!document.querySelector('#pane-side'),
    url: location.href,
  };
}
"""


# Codigo de saida quando o browser morre embaixo do run (ver _browser_morreu).
# Diferente de 0 de proposito: quem lanca consegue distinguir "encerrei" de
# "perdi o browser" e decidir se relanca.
SAIDA_BROWSER_MORTO = 3

# Assinaturas do Playwright para "a pagina/contexto/browser nao existe mais".
# Nao ha excecao propria: chega como Error com esta mensagem.
_MORTE_DO_BROWSER = (
    "target page, context or browser has been closed",
    "browser has been closed",
    "target closed",
    # Visto em 30/07/2026, quando o run foi morto de fora: a conexao com o
    # driver do Playwright caiu. Tambem nao volta — nada adianta insistir.
    "connection closed while reading from the driver",
)


def _browser_morreu(page, erro) -> bool:
    """
    True quando o erro e' 'perdi o browser', nao 'o clique falhou'.

    A distincao importa porque as duas falhas se parecem no log (todo grupo
    falhando em toda volta) e pedem reacoes OPOSTAS: bloqueio (modal de 03/08)
    passa e a pagina volta, entao vale insistir; browser fechado NAO volta —
    nao ha pagina para revitalizar, e o catch-up do resgate falha para sempre.

    Medido em 03/08/2026: um segundo run_captura.py subiu com o primeiro vivo,
    morreu ao tentar abrir o perfil ja travado (user_data/) e DERRUBOU junto o
    browser do run que estava rodando. O run sobrevivente ficou ~2h girando em
    falso, logando 'Target page, context or browser has been closed' a cada 5s
    sem capturar nada. Um lancamento que falhou em 6s custou 2h de captura.

    Confere a mensagem E o estado da pagina: a mensagem sozinha poderia mudar
    entre versoes do Playwright, e is_closed() sozinho nao cobre o caso em que
    quem morreu foi o contexto/browser e nao a page.
    """
    texto = str(erro).lower()
    if any(sinal in texto for sinal in _MORTE_DO_BROWSER):
        return True
    try:
        return page.is_closed()
    except Exception:  # noqa: BLE001
        return True                      # nem responder ele responde mais


def _relatar_bloqueio(page):
    """
    Diz no log POR QUE a volta ficou cega, em vez de deixar so o 'Call log' do
    Playwright (que menciona o dialogo, mas nao o que ele diz).

    Escrito depois de 03/08/2026: um modal do WhatsApp Web bloqueou o clique na
    lista por 48 min e o log nao registrava QUAL modal era — sem isso nao da
    para saber se e atualizacao de versao, chamada, visualizador de midia ou
    outra coisa, nem decidir se um dia vale fecha-lo sozinho.

    So OBSERVA: nao clica, nao fecha nada.
    """
    try:
        info = page.evaluate(_JS_BLOQUEIO)
    except Exception as e:  # noqa: BLE001
        print(f"[monitor] Volta cega e a pagina nem responde ao evaluate: {e}")
        return
    modais = [d for d in info.get("dialogos", []) if d.get("modal")]
    print(f"[monitor] Volta cega. #pane-side presente={info.get('tem_lista')}, "
          f"dialogos abertos={len(info.get('dialogos', []))} (modais={len(modais)}).")
    for d in modais:
        rotulo = d.get("rotulo") or d.get("titulo") or "(sem rotulo)"
        print(f"[monitor]   modal {rotulo!r}: {d.get('texto', '')!r}")


def _recuperar_lacuna(page, nomes_grupos, caminho_csv, numero: int, estado: dict,
                      vistos: set, db, parado_s: float):
    """
    Re-executa o catch-up depois de uma parada longa do rodizio ao vivo.

    O rodizio (Fase 2) so le o que esta RENDERIZADO na viewport: ele nao volta
    no historico. O catch-up (Fase 1), que sabe voltar, so rodava uma vez, no
    arranque do processo. Entre os dois ficava um buraco: se o processo parasse
    e voltasse, o atraso acumulado nunca era lido.

    Medido em 02/08/2026: a maquina entrou em stand by as 01/08 00:31 e so
    acordou 45h29m depois. O processo sobreviveu, retomou o rodizio e capturou
    apenas as mensagens novas — 01/08 inteiro (0 linha) e quase todo o 02/08 se
    perderam EM SILENCIO. E como o marcador avancou para as mensagens novas (e
    ele nao retrocede, por decisao de 30/07), nem reiniciar recuperava: so
    editando o config.json a mao.

    Retorna (numero, ok). ok=False se algum grupo falhou — ao acordar, a pagina
    leva alguns ciclos para revitalizar (no episodio de 02/08 foram ~8 ciclos de
    timeout em '#side'), entao quem chama deve tentar de novo na volta seguinte.
    """
    print(f"[monitor] LACUNA de {parado_s / 60:.1f} min no rodizio ao vivo. Ele nao volta "
          "no historico sozinho; re-executando o catch-up dos grupos.")
    ok = True
    for nome in nomes_grupos:
        grupo_estado = estado_mod.get_grupo(estado, nome) or {}
        cutoff = estado_mod.parse_dt(grupo_estado.get("ultima_data_hora"))
        marker = grupo_estado.get("ultimo_data_id")
        if not (cutoff or marker):
            continue                      # sem marcador nao ha de onde retomar
        try:
            browser.abrir_grupo(page, nome)
            page.wait_for_timeout(800)
            print(f"[{nome}] Recuperando a lacuna desde {estado_mod.fmt_dt(cutoff) or marker}...")
            numero, ja = _capturar_desde_ultima(
                page, nome, caminho_csv, numero, estado, db,
                cutoff_dt=cutoff, marker_id=marker, inclusivo=False,
            )
            vistos |= ja
            vistos.update(_ids_baloes(page))
        except Exception as e:  # noqa: BLE001
            print(f"[monitor] Falha ao recuperar a lacuna de {nome!r}: {e}")
            ok = False
    if ok:
        print("[monitor] Lacuna recuperada; voltando ao rodizio ao vivo.")
    return numero, ok


def captura_msg_whatsapp(
    nomes_grupos,
    intervalo: int = 3,
    headless: bool = False,
    max_historico: int = 0,
    seg_grupo: int = 5,
    force_capture_today: bool = False,
):
    """
    Monitora UM OU VARIOS grupos do WhatsApp em rodizio, gravando cada promocao
    no CSV do run (a coluna nome_do_grupo_do_whatsapp identifica a origem).

    Parametros
    ----------
    nomes_grupos : str | list[str]
        Nome(s) do(s) grupo(s) a monitorar (como aparecem na busca).
    intervalo : int
        (Reservado) segundos entre varreduras — no rodizio usamos seg_grupo.
    headless : bool
        Rodar sem interface (nao recomendado na 1a vez por causa do QR).
    max_historico : int
        Se > 0, faz um SWEEP das ultimas ~N mensagens de CADA grupo (IGNORANDO o
        controle de data). 0 (padrao) = usa o estado salvo (retoma de onde parou).
    seg_grupo : int
        Segundos de espera em cada grupo antes de pular para o proximo.
    force_capture_today : bool
        Ignora o estado salvo e captura tudo desde 00:00 de hoje (util na estreia
        de um grupo). Nao tem efeito quando max_historico > 0.
    """
    if isinstance(nomes_grupos, str):
        nomes_grupos = [nomes_grupos]

    caminho_csv = storage.novo_csv()
    estado = estado_mod.carregar()
    print(f"[monitor] CSV do run: {caminho_csv}")
    print(f"[monitor] Estado: {estado_mod.ESTADO_PATH}")
    print(f"[monitor] Grupos ({len(nomes_grupos)}): {nomes_grupos}")

    # Gravacao em Oracle (best-effort): se o bloco 'db' estiver desligado/ausente
    # ou a conexao falhar, segue so com CSV (comportamento identico ao de hoje).
    db = oracle_db.OracleDB()
    if db.habilitado:
        db.conectar()
    print(f"[monitor] Gravacao no Oracle: {'ligada' if db.habilitado else 'desligada'}.")

    vistos: set = set()
    # Codigo de saida do run: 0 = encerramento normal (Ctrl+C / fim), != 0 avisa
    # quem lancou que a parada NAO foi normal. Ver SAIDA_BROWSER_MORTO.
    saida = 0
    # Contador GLOBAL e CONTINUO entre execucoes: retoma do ultimo_id_processado
    # salvo no config.json. Cada nova mensagem soma 1 e vira o ID_OFERTA no CSV.
    numero = estado_mod.get_ultimo_id(estado)
    print(f"[monitor] Retomando contador de ofertas em ultimo_id_processado={numero}.")

    with sync_playwright() as pw:
        context = None
        try:
            context, page = browser.abrir_whatsapp(pw, headless=headless)
            hoje_0h = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # --- Fase 1: arranque por grupo (sweep / today / catch-up / baseline) ---
            for nome in nomes_grupos:
                try:
                    browser.abrir_grupo(page, nome)
                    page.wait_for_timeout(800)
                except Exception as e:  # noqa: BLE001
                    print(f"[monitor] Nao consegui abrir o grupo {nome!r}: {e}")
                    continue

                grupo_estado = estado_mod.get_grupo(estado, nome)
                if max_historico and max_historico > 0:
                    numero, ja = _varrer_ultimas(page, nome, caminho_csv, max_historico, numero, estado, db)
                elif force_capture_today:
                    print(f"[{nome}] Capturando mensagens de hoje (>= {hoje_0h.strftime('%d/%m/%Y')})...")
                    numero, ja = _capturar_desde_ultima(
                        page, nome, caminho_csv, numero, estado, db,
                        cutoff_dt=hoje_0h, marker_id=None, inclusivo=True,
                    )
                elif grupo_estado and (estado_mod.parse_dt(grupo_estado.get("ultima_data_hora"))
                                       or grupo_estado.get("ultimo_data_id")):
                    cutoff = estado_mod.parse_dt(grupo_estado.get("ultima_data_hora"))
                    marker = grupo_estado.get("ultimo_data_id")
                    print(f"[{nome}] Retomando desde {grupo_estado.get('ultima_data_hora') or marker}...")
                    numero, ja = _capturar_desde_ultima(
                        page, nome, caminho_csv, numero, estado, db,
                        cutoff_dt=cutoff, marker_id=marker, inclusivo=False,
                    )
                else:
                    _marcar_baseline(page, nome, estado)
                    ja = set(_ids_baloes(page))

                vistos |= ja
                vistos.update(_ids_baloes(page))
            print(f"[monitor] Arranque concluido (total #{numero}).")

            # --- Fase 2: RODIZIO ao vivo ---
            print(f"[monitor] Rodizio ao vivo ({seg_grupo}s/grupo). Ctrl+C para parar.")
            # Relogio de PAREDE de proposito: time.monotonic() nao conta o tempo
            # em que a maquina fica suspensa no Windows, que e exatamente o caso
            # que precisamos detectar (ver _recuperar_lacuna).
            fim_da_volta = datetime.now()
            lacuna_s = 0.0
            resgate_pendente = False
            voltas_cegas = 0
            inicio_do_cegueira = None
            browser_morto = False
            while True:
                if resgate_pendente:
                    numero, feito = _recuperar_lacuna(
                        page, nomes_grupos, caminho_csv, numero, estado, vistos, db, lacuna_s,
                    )
                    resgate_pendente = not feito
                    fim_da_volta = datetime.now()

                falhas_na_volta = 0
                for nome in nomes_grupos:
                    try:
                        browser.abrir_grupo(page, nome)
                        page.wait_for_timeout(1200)
                        numero, n = _ler_novas_do_grupo(page, nome, vistos, numero, caminho_csv, estado, db)
                        if n:
                            print(f"[{nome}] {n} nova(s) processada(s) (total #{numero}).")
                    except Exception as e:  # noqa: BLE001
                        falhas_na_volta += 1
                        print(f"[monitor] Erro no grupo {nome!r}: {e}")
                        if _browser_morreu(page, e):
                            browser_morto = True
                            break
                    time.sleep(seg_grupo)

                # Browser morto NAO se recupera girando: sem pagina, o resgate
                # da guarda de voltas cegas tambem falharia para sempre. Sair e'
                # a reacao certa — o estado vai para o disco no finally e quem
                # lancou pode relancar (saida != 0 avisa que nao foi encerramento
                # normal). Ver _browser_morreu.
                if browser_morto:
                    print("[monitor] BROWSER FECHADO embaixo do run — nao ha pagina para "
                          "revitalizar e insistir so gira em falso. Encerrando para poder "
                          "ser relancado.")
                    saida = SAIDA_BROWSER_MORTO
                    break

                # Volta CEGA = nenhum grupo abriu. Falha isolada (1 grupo) e o
                # timeout transitorio de sempre e nao conta; o que interessa
                # aqui e a pagina inteira travada. Ver VOLTAS_CEGAS_RESGATE.
                if falhas_na_volta == len(nomes_grupos):
                    voltas_cegas += 1
                    if voltas_cegas == 1:
                        inicio_do_cegueira = fim_da_volta
                        _relatar_bloqueio(page)
                    if voltas_cegas >= VOLTAS_CEGAS_RESGATE and not resgate_pendente:
                        lacuna_s = (datetime.now() - inicio_do_cegueira).total_seconds()
                        print(f"[monitor] {voltas_cegas} voltas seguidas sem abrir grupo nenhum "
                              f"({lacuna_s / 60:.1f} min). O rodizio nao volta no historico; "
                              "resgate marcado como PENDENTE.")
                        resgate_pendente = True
                elif voltas_cegas:
                    print(f"[monitor] Rodizio destravado apos {voltas_cegas} volta(s) cega(s).")
                    voltas_cegas = 0
                    inicio_do_cegueira = None

                agora = datetime.now()
                parado = (agora - fim_da_volta).total_seconds()
                if parado >= LACUNA_RECAPTURA_S:
                    lacuna_s = parado
                    resgate_pendente = True
                fim_da_volta = agora

        except KeyboardInterrupt:
            print("\n[monitor] Encerrado pelo usuario.")
        finally:
            # Cada passo protegido: quando se sai por browser morto, fechar o
            # contexto levanta excecao — e uma excecao aqui pularia o resto da
            # limpeza, inclusive o salvar do estado (que e o que impede o
            # contador de reemitir IDs no proximo run).
            try:
                estado_mod.salvar(estado)
            except Exception as e:  # noqa: BLE001
                print(f"[monitor] FALHA AO SALVAR O ESTADO: {e}")
            try:
                db.desconectar()
            except Exception as e:  # noqa: BLE001
                print(f"[monitor] Falha ao desconectar do Oracle: {e}")
            if context is not None:
                try:
                    context.close()
                except Exception as e:  # noqa: BLE001
                    print(f"[monitor] Contexto ja estava fechado: {e}")
            print(f"[monitor] Total capturado neste run: {numero}")
    return saida


def _tem_conteudo(campos: dict) -> bool:
    """True se a mensagem parece util (promocao de produto OU anuncio de cupom)."""
    return any(campos.get(c) for c in ("nome_do_produto", "preco_por", "preco_de", "url", "cupom"))


def _marca_db(db_ok) -> str:
    """Sufixo do log com o resultado da gravacao no Oracle (None = DB desligado)."""
    if db_ok is None:
        return ""
    return " | db=ok" if db_ok else " | db=ERRO"


def _rotulo_imagem(campos: dict) -> str:
    """
    Base do nome do arquivo de imagem. Produto -> nome; CUPOM (sem nome) ->
    'cupom_<loja>_<1o codigo>' (ex.: 'cupom_MERCADO LIVRE_LOJASOFICIAIS20').
    """
    if campos.get("nome_do_produto"):
        return campos["nome_do_produto"]
    if campos.get("tipo_anuncio") == "CUPOM":
        partes = ["cupom"]
        if campos.get("loja_cupom"):
            partes.append(campos["loja_cupom"])
        primeiro = (campos.get("cupom") or "").split(" | ")[0].strip()
        if primeiro:
            partes.append(primeiro)
        return "_".join(partes)
    return ""


def _montar_linha(campos: dict, nome_grupo: str, numero: int, caminho_img: str,
                  data_hora_msg=None) -> dict:
    """Monta o dicionario de uma linha do CSV a partir dos campos extraidos.

    As CHAVES aqui sao os nomes de coluna do CSV (storage.COLUNAS); os VALORES
    vem do dict `campos` do parser, cujas chaves internas seguem inalteradas.
    """
    return {
        "DS_TIPO_ORIGEM": "WHATSAPP",
        "DS_ORIGEM": nome_grupo,
        "DS_TIPO_OFERTA": campos["tipo_anuncio"],
        "ID_OFERTA": numero,
        "DT_CAPTACAO": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "DT_OFERTA": data_hora_msg.strftime("%d/%m/%Y %H:%M") if data_hora_msg else "",
        "DS_OFERTA": campos["nome_do_produto"],
        "DS_IMAGEM_OFERTA": caminho_img,
        "DS_OFERTA_AVISO": campos["msg_aviso"],
        "VL_PRECO_DE": campos["preco_de"],
        "VL_PRECO_POR": campos["preco_por"],
        "DS_DESCRICAO_PAGAMENTO": campos["descricao_pagamento"],
        "DS_URL_ORIGEM": campos["url"],
        "DS_MSG_FINAL": campos["mensagem_final"],
        "DS_CUPOM": campos["cupom"],
        "DS_CUPOM_COMENTARIO": campos["comentario_cupom"],
        "DS_CUPOM_LOJA": campos["loja_cupom"],
        "DS_LOJA": campos.get("loja", ""),
    }


def _processar(msg, nome_grupo: str, numero: int, caminho_csv, data_id: str, estado: dict,
               db=None) -> int:
    """Extrai, salva imagem, grava a linha e atualiza o estado (modo ao vivo)."""
    bruto = parser.extrair_bruto(msg)
    campos = parser.parse_campos(bruto)

    # Pula baloes sem conteudo de promocao (msgs de texto/avisos do grupo).
    if not _tem_conteudo(campos):
        return numero

    numero += 1
    data_hora_msg = parser.extrair_data_hora(bruto)
    caminho_img = storage.salvar_imagem(msg, bruto, numero, _rotulo_imagem(campos))
    linha = _montar_linha(campos, nome_grupo, numero, caminho_img, data_hora_msg)
    storage.gravar_linha(caminho_csv, linha)
    db_ok = db.inserir_oferta(linha) if (db is not None and db.habilitado) else None
    # Persiste CSV (acima) + config.json (contador global + estado do grupo) a
    # cada leitura, para o arquivo estar sempre atualizado se o processo cair.
    estado_mod.set_ultimo_id(estado, numero, salvar_agora=False)
    estado_mod.atualizar_grupo(estado, nome_grupo, data_hora_msg, data_id)
    print(
        f"[captura #{numero}] {campos['nome_do_produto'][:50]!r} | "
        f"por={campos['preco_por']} | cupom={campos['cupom']} | "
        f"img={'ok' if caminho_img else '-'}{_marca_db(db_ok)}"
    )
    return numero
