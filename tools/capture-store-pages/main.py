"""
Captura os dados de produto das ofertas pendentes e devolve os complementos ao
Oracle.

Fonte dos dados: tabela OFERTA_FILA_CAPTURA (linhas com ST_CAPTURA = '0'),
alimentada pelo AgenteCapturaWhatsapp. Para cada linha o programa abre a URL da
oferta, identifica a loja, captura os campos e chama a stored procedure
STP_OFERTA_FILA_CAPTURA_UPDATE, que grava os complementos e forca ST_CAPTURA='1'
(a linha nao volta nas proximas leituras). O CSV em destino/log/ continua sendo
gravado como copia de seguranca.

Retomada: conf/config.json -> controle.ultimo_id_processado guarda o ultimo
ID_OFERTA gravado com sucesso; a fila e lida com ID_OFERTA > esse valor. Linhas
que falharam ficam com ST_CAPTURA='0' mas atras do ponteiro -> use --desde 0
para reprocessa-las.

Modo monitor (--monitorar): em vez de processar um lote e sair, o programa fica
ligado varrendo a fila a cada N minutos (conf/config.json ->
monitor.intervalo_minutos, padrao 3). Achou pendente, captura na hora; nao
achou, dorme ate a proxima varredura. O Chrome e a conexao ficam abertos entre
as varreduras. Nesse modo a fila e lida DESDE O INICIO (ignora o ponteiro),
porque toda linha processada sai da fila sozinha e uma linha devolvida para '0'
na mao precisa ser vista. Sai com Ctrl+C.

Uso:
    python main.py                     # fila inteira, a partir do ultimo ID
    python main.py --monitorar         # fica vigiando a fila (a cada N minutos)
    python main.py --monitorar --intervalo 5   # ... a cada 5 minutos
    python main.py --limite 5          # so as 5 primeiras (teste)
    python main.py --desde 0           # ignora o ponteiro e reprocessa pendentes
    python main.py --sem-oracle        # captura e grava so no CSV (nao atualiza)
    python main.py --sem-link-afiliado # nao captura o link oficial de afiliado
    python main.py --csv origem/x.csv  # modo antigo: le de um CSV de origem
"""

import argparse
import os
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from core import (registry, csv_io, estado, pontes, afiliados, produtos, ofertas,
                  cupons, link_afiliado, imagens_produto, imagens_oferta, duplicidade,
                  validade)
from core import processos
from core.browser import launch_persistent, PERFIL_DIR
from core.oracle_db import OracleDB, COLUNAS_FILA
from core.caminhos import DESTINO_DIR, IMG_DIR, em_log

# Status cuja falha e NOSSA (a loja ainda nao foi implementada), nao um problema
# da oferta. Ficam com ST_CAPTURA='0' (pendente) para reprocessar sozinhos quando
# a loja passar a ser suportada, em vez de virar erro '9'.
STATUS_MANTER_PENDENTE = {'loja_nao_implementada'}

# Marcas na URL que denunciam parede de bloqueio/login/verificacao, e nao uma
# pagina que simplesmente nao tem produto. Distinguir importa: o
# 'bloqueado_ou_login' e TRANSITORIO (vale reprocessar depois), enquanto o
# 'pagina_sem_produto' e definitivo (o link nunca levou a um produto).
# 'verify/' e a Shopee; 'account-verification' e o Mercado Livre.
MARCAS_BLOQUEIO = ('verify/', 'account-verification')


def _gate_fechar_navegadores():
    # Antes de abrir o navegador de automacao, garante que NENHUM Chrome esteja
    # aberto — assim a unica janela na tela sera a da automacao (nao ha como
    # logar na janela errada) e nao ha conflito de perfil.
    if not processos.chrome_aberto():
        return
    while True:
        print('\n' + '=' * 64)
        print('Ha Chrome ABERTO. Feche TODAS as janelas do Chrome (inclusive as')
        print('em segundo plano: bandeja do sistema / Gerenciador de Tarefas) e')
        print('depois pressione S.')
        print('=' * 64)
        resp = input('Fechou tudo? [S = continuar / F = forcar fechamento / Q = sair]: ').strip().lower()
        if resp == 'q':
            sys.exit(0)
        if resp == 'f':
            processos.fechar_chrome_forcado()
            time.sleep(2)
        if not processos.chrome_aberto():
            print('OK: nenhum Chrome aberto.\n')
            return
        print('  ...ainda detectei Chrome aberto. Tente novamente.')


def _status_erro(e):
    """Formata o status de erro p/ DS_CAPTURA com a MENSAGEM real, nao so o
    tipo da excecao -- so a 1a linha (descarta o "Call log:" verboso do
    Playwright), truncada ao limite da coluna (400 CHAR). Sem isso, um
    "erro: Error" generico nao da pista nenhuma p/ diagnosticar depois sem
    reproduzir a mao (foi o caso dos ~1600 erros investigados em 02/09)."""
    primeira_linha = str(e).strip().splitlines()[0] if str(e).strip() else ''
    texto = f'erro: {type(e).__name__}: {primeira_linha}' if primeira_linha else f'erro: {type(e).__name__}'
    return texto[:400]


def _goto_robusto(page, url, timeout=60000):
    # goto que tolera "interrupted by another navigation": alguns links
    # (redirects de encurtador / pos-login) deixam uma navegacao pendente que
    # mata o goto seguinte. Nesse caso espera um pouco e tenta 1x de novo.
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    except Exception as e:
        if 'interrupted by another navigation' in str(e):
            page.wait_for_timeout(1500)
            page.goto(url, wait_until='domcontentloaded', timeout=timeout)
        else:
            raise


def _resolver_ponte(page, url, captura):
    # Dominio fora do registry: antes de desistir, abre a pagina e ve se ela e
    # uma PONTE (vitrine de divulgador) — nesse caso o link da loja de verdade
    # esta no proprio HTML. Retorna (url_da_loja, nome_da_loja, expirada), com
    # `expirada` True quando a vitrine responde mas a oferta ja saiu do ar.
    try:
        _goto_robusto(page, url, timeout=60000)
        # Encurtador generico (amzn.promos.link, amzn.to, GA.MA, onelink...):
        # o goto ja seguiu o redirect e a pagina caiu numa loja conhecida. Nao
        # da p/ mapear esses dominios no registry pela loja -- o mesmo
        # amzn.promos.link ja apontou p/ o Mercado Livre -- entao vale o destino.
        loja = registry.resolver_loja(page.url)
        if loja:
            print(f'[captura {captura}] redirect -> {loja}: {page.url[:70]}')
            return page.url, loja, False
        destino, loja = pontes.resolver_destino(page)
    except Exception as e:
        print(f'[captura {captura}] ponte: {e}')
        return None, None, False
    if destino:
        print(f'[captura {captura}] ponte -> {loja}: {destino[:70]}')
        return destino, loja, False
    expirada = pontes.oferta_expirada(page)
    if expirada:
        print(f'[captura {captura}] ponte: promocao encerrada ({page.url[:70]})')
    return None, None, expirada


def _gate_login_manual(page):
    # Abre a tela de login da Shopee na janela de automacao e espera o usuario
    # logar manualmente, confirmando com "S". A sessao fica salva no perfil.
    try:
        page.goto('https://shopee.com.br/buyer/login',
                  wait_until='domcontentloaded', timeout=60000)
    except Exception:
        pass
    print('\n' + '=' * 64)
    print('Faca LOGIN na SHOPEE nesta janela de automacao que abriu')
    print('(email/senha, OTP e resolva o captcha se aparecer).')
    print('=' * 64)
    while True:
        resp = input('Logou com sucesso? [S = continuar / Q = sair]: ').strip().lower()
        if resp == 's':
            print('Seguindo para a captura da lista completa...\n')
            return
        if resp == 'q':
            sys.exit(0)


def _assentar_pos_login(page):
    # Apos o login a Shopee ainda tem um redirect PENDENTE (-> shopee.com.br)
    # que, se nao for cancelado, interrompe o primeiro goto do loop e vira uma
    # cascata (cada goto e morto pelo anterior). about:blank cancela a navegacao
    # pendente e nos poe num estado conhecido antes de comecar.
    try:
        page.goto('about:blank', timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(2000)


def _gate_login_shopee_arranque(page):
    # No modo monitor nao da para esperar o lote chegar para decidir: o programa
    # fica ligado por horas e a Shopee pode aparecer em qualquer varredura. Entao
    # o login e oferecido UMA vez, no arranque, e depois o loop nunca mais para.
    # A sessao dura ~1 dia; expirando, ofertas da Shopee caem em
    # 'bloqueado_ou_login' ate um novo login.
    print('\n' + '=' * 64)
    print('MODO MONITOR: o programa vai ficar ligado vigiando a fila.')
    print('A Shopee exige sessao logada e o login e MANUAL (captcha/OTP).')
    print('Se voce quer capturar ofertas da Shopee nesta sessao, faca o login')
    print('AGORA — depois o loop nao para mais para pedir.')
    print('=' * 64)
    while True:
        resp = input('Login na Shopee agora? [S = sim / N = seguir sem Shopee / Q = sair]: ').strip().lower()
        if resp == 'q':
            sys.exit(0)
        if resp == 's':
            _gate_login_manual(page)
            _assentar_pos_login(page)
            return
        if resp == 'n':
            print('Seguindo sem login: ofertas da Shopee podem cair em '
                  'bloqueado_ou_login.\n')
            return


def _gate_login_afiliado(page, titulo, url, instrucao):
    """Gate generico de login num PROGRAMA DE AFILIADOS: abre a pagina da loja
    na janela da automacao e espera o usuario confirmar que esta logado.

    Diferente do login da Shopee (que a CAPTURA exige), estes sao necessarios
    so para o LINK DE AFILIADO: sem eles o widget nao aparece na pagina e
    DS_URL_AFILIADO fica NULL -- os dados do produto sao capturados do mesmo
    jeito. Por isso a resposta "N" segue em frente em vez de abortar.
    """
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
    except Exception:  # noqa: BLE001
        pass
    print('\n' + '=' * 64)
    print(f'{titulo}')
    print(instrucao)
    print('=' * 64)
    while True:
        resp = input('Esta logado? [S = continuar / N = seguir sem este link / Q = sair]: ').strip().lower()
        if resp == 'q':
            sys.exit(0)
        if resp == 's':
            return True
        if resp == 'n':
            print('Seguindo: as ofertas desta loja ficarao sem DS_URL_AFILIADO.\n')
            return False


def _gates_login_afiliados(page):
    """Sequencia de login dos programas de afiliados, no arranque: painel da
    Shopee (o gerador de links mora fora da loja), Amazon e Mercado Livre.

    O login da LOJA Shopee (comprador), que a captura dos produtos exige, ja
    foi oferecido antes disto -- aqui e a conta de AFILIADO, que e outra
    sessao. Amazon e Mercado Livre nao pedem login p/ capturar produto: so o
    widget de afiliado (SiteStripe / barra "GANHOS x%") depende dele.
    """
    _gate_login_afiliado(
        page, 'SHOPEE AFILIADOS (gerador de links)',
        link_afiliado.SHP_URL,
        'Confirme que o formulario "Criar link personalizado" abriu logado.\n'
        'Se caiu na tela de login, faca o login nesta janela agora.')
    _gate_login_afiliado(
        page, 'AMAZON ASSOCIADOS (SiteStripe)',
        'https://www.amazon.com.br',
        'Confirme que a barra do SiteStripe ("Obter link") aparece no topo.\n'
        'Se nao aparecer, faca o login na sua conta de Associados nesta janela.')
    _gate_login_afiliado(
        page, 'MERCADO LIVRE AFILIADOS',
        'https://www.mercadolivre.com.br',
        'Confirme que a barra de afiliado ("GANHOS x%" / "Compartilhar")\n'
        'aparece no topo. Se nao aparecer, faca o login nesta janela.')
    _assentar_pos_login(page)


def _esperar(segundos):
    # Espera fatiada: mantem o Ctrl+C responsivo (um sleep unico e longo demora
    # a devolver o controle no Windows).
    fim = time.time() + segundos
    while True:
        restante = fim - time.time()
        if restante <= 0:
            return
        time.sleep(min(5.0, restante))


def _adaptar_linhas(linhas):
    """Adapta as linhas da fila ao formato do loop de captura.

    O loop espera as chaves 'url' e 'numero_da_captura' (herdadas do modo CSV);
    aqui elas viram apelidos de DS_URL_ORIGEM e ID_OFERTA. As colunas Oracle
    originais ficam na linha e vao inteiras para o CSV de seguranca.
    """
    for linha in linhas:
        linha['url'] = (linha.get('DS_URL_ORIGEM') or '').strip()
        linha['numero_da_captura'] = str(linha.get('ID_OFERTA') or '')
    return linhas


def _ler_pendentes(db, ultimo_id, limite, adiados=None):
    """Le a fila pendente ja adaptada, tirando os IDs adiados nesta execucao."""
    linhas = _adaptar_linhas(db.ler_fila(ultimo_id=ultimo_id, limite=limite))
    if adiados:
        linhas = [l for l in linhas if l.get('ID_OFERTA') not in adiados]
    return linhas


def _ler_pendentes_resiliente(db, ultimo_id, limite, adiados):
    """Como _ler_pendentes, mas sobrevive a uma queda da conexao.

    Ligado por horas, a sessao Oracle pode morrer por ociosidade (ORA-03113 e
    parentes). Em erro de leitura, reconecta e tenta mais uma vez; se ainda
    assim falhar, devolve None para o monitor dormir e tentar na proxima
    varredura, em vez de derrubar o programa.
    """
    try:
        return _ler_pendentes(db, ultimo_id, limite, adiados)
    except Exception as e:  # noqa: BLE001
        print(f'[monitor] falha ao ler a fila: {e}')
    print('[monitor] reconectando ao Oracle...')
    db.desconectar()
    # conectar() marca habilitado=False quando falha; como a conexao ja existiu
    # (o arranque passou), religa a flag para poder tentar de novo.
    db.habilitado = True
    if not db.conectar():
        return None
    try:
        return _ler_pendentes(db, ultimo_id, limite, adiados)
    except Exception as e:  # noqa: BLE001
        print(f'[monitor] fila ainda inacessivel: {e}')
        return None


class _Cronometro:
    """Tempo de UMA oferta, fase a fase.

    Nasceu da pergunta "por que a Amazon demora mais de 1 min?" (11/09): sem o
    tempo POR FASE no log, qualquer resposta e chute -- a lentidao pode estar na
    navegacao, na varredura dos seletores, no download das imagens, no link de
    afiliado ou no banco, e cada uma dessas se resolve de um jeito diferente.
    """

    # Fases na ordem em que acontecem (so as > 0,05s entram no log).
    ORDEM = ('ponte', 'nav', 'capt', 'img', 'afil', 'db')

    def __init__(self):
        self.inicio = datetime.now()
        self._perf_inicio = time.perf_counter()
        self._t0 = self._perf_inicio
        self._fim = self._perf_inicio
        self.fases = {}

    def marcar(self, fase):
        """Fecha a fase atual: soma o tempo desde a ultima marcacao."""
        agora = time.perf_counter()
        self.fases[fase] = self.fases.get(fase, 0.0) + (agora - self._t0)
        self._t0 = agora
        self._fim = agora

    @property
    def total(self):
        """Tempo ate a ULTIMA marcacao -- nao o relogio de agora. O resumo do
        lote le isto la no fim, e um total "ao vivo" faria a 1a oferta parecer
        ter durado a varredura inteira (visto no ensaio de 11/09: linhas de 14s
        virando media de 35s)."""
        return self._fim - self._perf_inicio

    def resumo(self):
        detalhe = ' | '.join(f'{f} {self.fases[f]:.1f}' for f in self.ORDEM
                             if self.fases.get(f, 0) >= 0.05)
        return f'{self.total:5.1f}s' + (f' ({detalhe})' if detalhe else '')


def _resumo_tempos(tempos):
    """Media por loja no fim do lote: e a leitura que mostra QUAL loja e qual
    fase puxam o tempo p/ cima (uma oferta sozinha nao diz nada)."""
    if not tempos:
        return
    print('\n[tempos] media por loja (segundos):')
    for loja in sorted(tempos):
        crons = tempos[loja]
        n = len(crons)
        total = sum(c.total for c in crons) / n
        partes = []
        for fase in _Cronometro.ORDEM:
            media = sum(c.fases.get(fase, 0.0) for c in crons) / n
            if media >= 0.05:
                partes.append(f'{fase} {media:.1f}')
        pior = max(c.total for c in crons)
        print(f'  {loja or "-":<13} n={n:<4} total {total:5.1f}  '
              f'(pior {pior:5.1f})  = ' + ' | '.join(partes))


def _nova_page(context):
    page = context.new_page()
    page.set_default_timeout(15000)
    return page


def _processar_lote(page, rows, db, atualiza_banco, img_root, adiados=None):
    """Captura cada linha do lote e devolve (out_rows, gravadas, com_erro).

    `adiados` (set, usado pelo monitor): recebe os IDs que continuam pendentes
    de proposito — sem isso o monitor releria a mesma linha a cada varredura.
    """
    out_rows = []
    gravadas = 0
    com_erro = 0
    tempos = {}  # loja -> [_Cronometro] (media do lote no fim, _resumo_tempos)

    for row in rows:
        cron = _Cronometro()
        out = dict(row)
        url = (row.get('url') or '').strip()
        captura = (row.get('numero_da_captura') or '').strip()
        loja = registry.resolver_loja(url)
        out['loja'] = loja or ''
        out['url_final'] = ''  # preenchido com a URL real apos navegar
        out['url_besave'] = ''  # idem, com o NOSSO codigo de afiliado

        expirada = False
        if url and loja is None:
            # Pode ser uma pagina-ponte de divulgador: a oferta esta la, mas
            # quem vende e outra loja. A URL de origem continua em out['url'].
            destino, loja, expirada = _resolver_ponte(page, url, captura)
            cron.marcar('ponte')
            if loja:
                url = destino
            else:
                # Guarda onde a ponte parou (DS_URL_FINAL), p/ diagnostico.
                try:
                    out['url_final'] = page.url
                except Exception:
                    pass
            out['loja'] = loja or ''

        if not url:
            out['status_captura'] = 'url_vazia'
        elif loja is None:
            # 'oferta_expirada' e definitivo como o 'loja_desconhecida' (ambos
            # viram '9'), mas diz a verdade: o dominio ate seria resolvivel, a
            # oferta e que saiu do ar antes de a fila chegar nela.
            out['status_captura'] = 'oferta_expirada' if expirada else 'loja_desconhecida'
        else:
            store = registry.get_store(loja)
            if store is None:
                out['status_captura'] = 'loja_nao_implementada'
            else:
                try:
                    # goto segue os redirects dos encurtadores (amzn.divulguei.app etc.)
                    _goto_robusto(page, url, timeout=60000)
                    # Hook por loja: fecha popup / clica "Ir para produto" (ML) etc.
                    try:
                        store.prepare(page)
                    except Exception as e:
                        print(f'[captura {captura}] prepare: {e}')
                    # SPA: espera o container do produto (Shopee). Amazon nao define.
                    if store.ready_selector:
                        try:
                            page.wait_for_selector(store.ready_selector, timeout=25000)
                        except Exception:
                            pass
                    page.wait_for_timeout(store.post_load_wait)
                    # URL real do produto (apos redirects do link curto / previa)
                    out['url_final'] = page.url
                    cron.marcar('nav')

                    # Distingue: (1) bloqueio/login/captcha; (2) anuncio que
                    # saiu do ar (a pagina E de produto, mas nao vende mais);
                    # (3) pagina que nao e de produto (cupom/campanha); (4) ok.
                    sem_produto = (
                        (store.ready_selector and page.locator(store.ready_selector).count() == 0)
                        or store.pagina_sem_produto(page)
                    )
                    try:
                        descarte = store.status_descarte(page)
                    except Exception:  # noqa: BLE001
                        descarte = None
                    if any(m in page.url for m in MARCAS_BLOQUEIO):
                        out['status_captura'] = 'bloqueado_ou_login'
                        print(f'[captura {captura}] bloqueio/login/captcha: {page.url[:70]}')
                    elif descarte:
                        # Motivo fica em DS_CAPTURA (ST_CAPTURA='9'): a oferta
                        # sai da fila com a razao registrada, sem virar linha
                        # boa no feed. Ex.: 'anuncio_pausado' (Mercado Livre).
                        out['status_captura'] = descarte
                        print(f'[captura {captura}] {descarte}: {page.url[:70]}')
                    elif sem_produto:
                        out['status_captura'] = 'pagina_sem_produto'
                        print(f'[captura {captura}] nao e pagina de produto (cupom/campanha/link?): {page.url[:70]}')
                    else:
                        out.update(store.capture(page))
                        cron.marcar('capt')
                        if store.baixar_imagens:
                            folder = os.path.join(img_root, captura or 'sem_numero')
                            store.get_images(page, folder)
                            out['pasta_imagens'] = folder
                            cron.marcar('img')
                        # URL com o NOSSO codigo de afiliado (LOJA_AFILIADA),
                        # a partir da url_final real do produto. None (loja
                        # sem afiliado ativo/regra) -> fica '' -> NULL no banco.
                        # So REFERENCIA: calculada por regex, nao alimenta o
                        # link de afiliado nem o PRODUTO (esses usam a
                        # DS_URL_AFILIADO, clicada logo abaixo).
                        out['url_besave'] = afiliados.gerar_url(loja, out['url_final']) or ''
                        # Link OFICIAL do programa de afiliados da loja, clicado
                        # no widget da pagina (Amazon/ML) ou gerado no painel
                        # (Shopee). Por ultimo de proposito: o fluxo clica em
                        # botoes e abre outra aba, entao so roda com a captura e
                        # as imagens ja no bolso. Best-effort: devolve campos
                        # vazios se a sessao de afiliado nao estiver logada, sem
                        # derrubar a captura (ver core/link_afiliado.py).
                        out.update(link_afiliado.capturar(
                            page, loja, out['url_final']))
                        cron.marcar('afil')
                        out['status_captura'] = 'ok'
                except Exception as e:
                    out['status_captura'] = _status_erro(e)
                    print(f'[captura {captura}] erro: {e}')

        # Loja "ativa" = entra em producao agora (conf/config.json ->
        # "lojas_ativas"). As demais sao capturadas e mapeadas do mesmo jeito,
        # so nascem com ST_ATIVO='0' para nao serem publicadas ainda.
        ativo = registry.loja_ativa(loja, url) if loja else False
        out['st_ativo'] = '1' if ativo else '0'

        # Devolve o resultado ao Oracle. Sucesso -> complementos +
        # ST_CAPTURA='1'; falha -> ST_CAPTURA='9' com o motivo em DS_CAPTURA. Em
        # ambos os casos a linha sai da fila; para reprocessar erros, devolva
        # ST_CAPTURA para '0' (ver o cabecalho de
        # sql/STP_OFERTA_FILA_CAPTURA_ERRO.STP).
        # Fecha o que ficou aberto antes do banco (pagina que nem chegou a
        # capturar, erro no meio do caminho) como tempo de pagina -- senao ele
        # seria cobrado do 'db', que e a fase seguinte.
        cron.marcar('nav')

        status_db = ''
        if atualiza_banco:
            id_oferta = row['ID_OFERTA']
            if out['status_captura'] == 'ok':
                ok, erro = db.atualizar_captura(id_oferta, out, ativo=ativo)
                if ok:
                    gravadas += 1
                    status_db = ' | oracle=ok'
                    # Ponteiro so avanca no sucesso: se o processo cair, a
                    # proxima execucao recomeca da primeira linha nao gravada.
                    estado.gravar_ultimo_id(id_oferta)
                    # Cadastro consolidado de produtos (BESAVE.PRODUTO): le de
                    # volta a linha JA GRAVADA (numeros/LS_* ja convertidos,
                    # ver core/oracle_db.buscar_para_produto) e acha-ou-cria o
                    # produto (core/produtos.py -> STP_PRODUTO_UPSERT), que
                    # tambem grava ID_PRODUTO nesta linha. Best-effort: falha
                    # aqui NUNCA derruba a captura, que ja foi bem-sucedida.
                    try:
                        linha_gravada = db.buscar_para_produto(id_oferta)
                        id_produto, classificacao, erro_produto = (
                            produtos.cadastrar_produto(db, id_oferta, linha_gravada)
                            if linha_gravada else (None, None, 'linha nao encontrada apos gravar')
                        )
                    except Exception as e:  # noqa: BLE001
                        id_produto, classificacao, erro_produto = None, None, str(e)
                    if id_produto is not None:
                        status_db += f' | produto={id_produto}'
                    else:
                        status_db += ' | produto=FALHOU'
                        print(f'[captura {captura}] produto: {erro_produto}')
                    # Publica as fotos desta oferta na pasta do PRODUTO no S3,
                    # convertidas para .webp (mesma resolucao, sem redimensionar).
                    # Sobrepoe o que houver la (a captura mais recente vence).
                    # Best-effort, mesmo padrao do cadastro de produto acima; o
                    # original em destino/img/<ID_OFERTA> nunca e alterado.
                    if id_produto is not None:
                        try:
                            n_imgs = imagens_produto.publicar_imagens_produto(
                                id_produto, out.get('pasta_imagens'))
                            if n_imgs:
                                status_db += f' | imgs_produto={n_imgs}'
                        except Exception as e:  # noqa: BLE001
                            print(f'[captura {captura}] imagens_produto: {e}')
                    # Substitui a imagem original (enviada no grupo do
                    # WhatsApp) pela foto capturada na pagina do produto, no
                    # bucket do site (s3/ofertas/img) -- so para os grupos de
                    # origem marcados em conf/config.json -> "grupos"
                    # (core/estado.usa_imagem_loja). Independe do cadastro de
                    # produto (id_produto) -- e por ID_OFERTA. Best-effort,
                    # mesmo padrao das demais gravacoes de imagem.
                    # Demais grupos (2026-10-08): so quando o site ainda NAO
                    # tem imagem dela -- mensagem do WhatsApp sem foto deixava
                    # a oferta no placeholder (~500 casos); a foto do WhatsApp,
                    # quando existe, nunca e sobrescrita.
                    if (estado.usa_imagem_loja(row.get('DS_ORIGEM'))
                            or not imagens_oferta.tem_imagem_publicada(id_oferta)):
                        try:
                            origem_img = imagens_oferta.primeira_imagem(out.get('pasta_imagens'))
                            if origem_img and imagens_oferta.publicar_imagem_oferta(id_oferta, origem_img):
                                status_db += ' | img_oferta=ok'
                        except Exception as e:  # noqa: BLE001
                            print(f'[captura {captura}] imagens_oferta: {e}')
                    # Cadastro/atualizacao de cupons (BESAVE.CUPOM): roda para
                    # QUALQUER loja com captura ok (nao depende de afiliado
                    # ativo, diferente da publicacao em OFERTA abaixo) e so
                    # grava quando a linha tem DS_CUPOM preenchido -- ver
                    # core/cupons.py. Best-effort, mesmo padrao do cadastro de
                    # produto acima.
                    try:
                        linha_cupom = db.buscar_para_cupom(id_oferta)
                        ids_cupom, erro_cupom = (
                            cupons.publicar_cupom(db, linha_cupom, registry.nome_loja(loja, url))
                            if linha_cupom else (None, 'linha nao encontrada apos gravar')
                        )
                    except Exception as e:  # noqa: BLE001
                        ids_cupom, erro_cupom = None, str(e)
                    if ids_cupom:
                        status_db += f" | cupom={','.join(str(i) for i in ids_cupom)}"
                    elif erro_cupom:
                        status_db += ' | cupom=FALHOU'
                        print(f'[captura {captura}] cupom: {erro_cupom}')
                    # Publica em BESAVE.OFERTA (feed de ofertas aprovadas):
                    # so quando o produto foi cadastrado E a loja tem
                    # afiliado ATIVO em LOJA_AFILIADA -- conceito DIFERENTE
                    # do "ativo" de ST_ATIVO (esse vem de conf/config.json).
                    # Best-effort, mesmo padrao do cadastro de produto acima.
                    if id_produto is not None and afiliados.loja_ativa(loja):
                        try:
                            linha_oferta = db.buscar_para_oferta(id_oferta)
                            ok_oferta, erro_oferta = (
                                ofertas.publicar_oferta(
                                    db, id_oferta, id_produto,
                                    registry.nome_loja(loja, url), linha_oferta, classificacao)
                                if linha_oferta else (False, 'linha nao encontrada apos gravar')
                            )
                        except Exception as e:  # noqa: BLE001
                            ok_oferta, erro_oferta = False, str(e)
                        if ok_oferta:
                            status_db += ' | oferta=publicada'
                        elif (erro_oferta or '').startswith(duplicidade.PREFIXO):
                            # Repostagem nas ultimas 24 h (core/duplicidade.py).
                            status_db += f' | oferta={erro_oferta}'
                        elif erro_oferta == validade.MOTIVO:
                            # DT_OFERTA alem da validade (core/validade.py).
                            status_db += f' | oferta={erro_oferta}'
                        else:
                            status_db += ' | oferta=FALHOU'
                            print(f'[captura {captura}] oferta: {erro_oferta}')
                else:
                    status_db = ' | oracle=FALHOU'
                    print(f'[captura {captura}] oracle: {erro}')
                    # A linha continua '0'; nao insistir nela a cada varredura.
                    if adiados is not None:
                        adiados.add(id_oferta)
            elif out['status_captura'] in STATUS_MANTER_PENDENTE:
                # A falha e NOSSA (loja ainda sem implementacao), nao da
                # oferta: mantem ST_CAPTURA='0' para reprocessar sozinha
                # quando a loja passar a ser suportada.
                status_db = ' | oracle=pendente(0)'
                if adiados is not None:
                    adiados.add(id_oferta)
            else:
                ok, erro = db.marcar_erro(
                    id_oferta, out['status_captura'], out['url_final'], ativo=ativo)
                if ok:
                    com_erro += 1
                    status_db = ' | oracle=erro(9)'
                else:
                    status_db = ' | oracle=FALHOU'
                    print(f'[captura {captura}] oracle: {erro}')
                    if adiados is not None:
                        adiados.add(id_oferta)

        # Marca so quando a loja TEM fluxo de link de afiliado: '-' ali quer
        # dizer "tentou e nao veio" (sessao deslogada / layout mudou), nao
        # "loja sem programa" -- a diferenca importa p/ diagnosticar rapido.
        marca_afiliado = ''
        if out.get('url_afiliado'):
            marca_afiliado = ' | afiliado=ok'
        elif (out['status_captura'] == 'ok' and link_afiliado.habilitado()
              and loja in link_afiliado.LOJAS):
            marca_afiliado = ' | afiliado=-'

        cron.marcar('db')
        tempos.setdefault(out['loja'], []).append(cron)

        out_rows.append(out)
        print(f'[{cron.inicio:%d/%m %H:%M:%S}] linha {captura:>4} | '
              f'loja={out["loja"] or "-":<13} | '
              f'status={out["status_captura"]}{status_db}{marca_afiliado}'
              f' | {cron.resumo()}')

    _resumo_tempos(tempos)
    return out_rows, gravadas, com_erro


def _gravar_csv(out_rows, header, base):
    out_csv = em_log(f'captura_{base}.csv')
    csv_io.write_destino(out_csv, header, out_rows)
    print(f'\nGravado: {out_csv} ({len(out_rows)} linhas)')
    return out_csv


def _resumo_oracle(total, gravadas, com_erro):
    pendentes = total - gravadas - com_erro
    print(f'Oracle: {gravadas} com sucesso (ST_CAPTURA=1), '
          f'{com_erro} com erro (ST_CAPTURA=9), '
          f'{pendentes} mantida(s) pendente(s) (ST_CAPTURA=0), '
          f'de {total} linha(s). '
          f'Ultimo ID processado: {estado.ler_ultimo_id()}.')
    if com_erro:
        print('Para reprocessar os erros depois de corrigir a causa:')
        print("  UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA='0' "
              "WHERE ST_CAPTURA='9' AND DS_CAPTURA='<motivo>';")


# Varredura de validade no --monitorar: no maximo 1 por hora (UPDATE barato,
# mas nao precisa rodar a cada 3 min).
VALIDADE_A_CADA_S = 3600


def _varrer_validade(db):
    """Desativa as ofertas vencidas (core/validade.py). Best-effort."""
    if not db:
        return
    try:
        n = validade.desativar_vencidas(db)
        if n:
            print(f'[validade] {n} oferta(s) com mais de '
                  f'{estado.ler_validade_ofertas()} dias desativada(s).')
    except Exception as e:  # noqa: BLE001
        print(f'[validade] falhou: {e}')


def _monitorar(context, page, db, args, header, img_root, intervalo_min):
    """Varre a fila ate o usuario interromper (Ctrl+C).

    Cada varredura que encontra pendentes vira um lote normal, com seu proprio
    CSV de seguranca; achando a fila vazia, dorme `intervalo_min`. Depois de um
    lote a fila e relida NA HORA — o lote pode ter demorado e algo novo pode ter
    entrado nesse meio tempo.
    """
    # Ponteiro ignorado por padrao aqui: toda linha processada sai da fila
    # sozinha (vira '1' ou '9') e uma linha devolvida para '0' na mao (ID antigo)
    # precisa ser vista. --desde continua mandando quando informado.
    ultimo_id = args.desde if args.desde is not None else 0
    adiados = set()  # IDs que ficam '0' de proposito -> nao reler a cada ciclo
    ciclos = 0
    total_grav = 0
    total_erro = 0
    espera_s = intervalo_min * 60

    print(f'\n[monitor] ligado: varredura a cada {intervalo_min:g} min '
          f'(conf/config.json -> monitor.intervalo_minutos). Ctrl+C para sair.\n')
    ult_validade = 0.0
    try:
        while True:
            if time.monotonic() - ult_validade >= VALIDADE_A_CADA_S:
                _varrer_validade(db)
                ult_validade = time.monotonic()
            rows = _ler_pendentes_resiliente(db, ultimo_id, args.limite, adiados)
            if rows is None:  # banco fora do ar: tenta na proxima varredura
                print(f'[monitor] nova tentativa em {intervalo_min:g} min.')
                _esperar(espera_s)
                continue
            if not rows:
                print(f'[{datetime.now():%H:%M:%S}] fila vazia; proxima leitura '
                      f'em {intervalo_min:g} min.')
                _esperar(espera_s)
                continue

            ciclos += 1
            print(f'\n[{datetime.now():%H:%M:%S}] varredura {ciclos}: '
                  f'{len(rows)} oferta(s) pendente(s).')
            # A janela pode ter sido fechada na mao entre as varreduras.
            if page.is_closed():
                print('[monitor] a aba foi fechada; abrindo outra.')
                page = _nova_page(context)

            out_rows, gravadas, com_erro = _processar_lote(
                page, rows, db, True, img_root, adiados)
            total_grav += gravadas
            total_erro += com_erro
            _gravar_csv(out_rows, header, f'oracle_{datetime.now():%d_%m_%Y_%H_%M_%S}')
            _resumo_oracle(len(out_rows), gravadas, com_erro)
            if adiados:
                print(f'[monitor] {len(adiados)} linha(s) adiada(s) nesta execucao '
                      f'(seguem ST_CAPTURA=0): {sorted(adiados)}')
    except KeyboardInterrupt:
        print('\n[monitor] interrompido (Ctrl+C).')
    finally:
        print(f'[monitor] {ciclos} varredura(s) com trabalho | '
              f'{total_grav} gravada(s) (1) | {total_erro} com erro (9).')


def main():
    ap = argparse.ArgumentParser(
        description='Captura dados de produto das ofertas pendentes no Oracle.')
    ap.add_argument('--limite', type=int, default=0,
                    help='Processa no maximo N linhas da fila (0 = todas). '
                         'No modo monitor, vale por varredura.')
    ap.add_argument('--desde', type=int, default=None,
                    help='Le a fila a partir deste ID_OFERTA, ignorando o ponteiro salvo.')
    ap.add_argument('--sem-oracle', action='store_true', dest='sem_oracle',
                    help='Nao atualiza o banco: so captura e grava o CSV.')
    ap.add_argument('--csv', dest='csv_path', default=None,
                    help='Modo antigo: le as ofertas de um CSV de origem em vez do Oracle.')
    ap.add_argument('--monitorar', action='store_true',
                    help='Fica ligado varrendo a fila a cada N minutos, em vez de '
                         'processar um lote e sair. Ctrl+C para parar.')
    ap.add_argument('--intervalo', type=float, default=None,
                    help='Minutos entre as varreduras do --monitorar '
                         '(padrao: monitor.intervalo_minutos do config.json).')
    ap.add_argument('--sem-link-afiliado', action='store_true', dest='sem_link_afiliado',
                    help='Nao captura o link oficial de afiliado (DS_URL_AFILIADO) '
                         'nem pede os logins dos programas de afiliado. A captura '
                         'dos dados do produto continua igual.')
    args = ap.parse_args()

    # Captura do link de afiliado: ligada por padrao (conf/config.json ->
    # link_afiliado.habilitado); a linha de comando so consegue DESLIGAR.
    capturar_link = estado.ler_link_afiliado() and not args.sem_link_afiliado
    link_afiliado.configurar(capturar_link)

    if args.monitorar and args.csv_path:
        print('--monitorar vigia a fila do Oracle; nao combina com --csv.')
        sys.exit(1)
    if args.monitorar and args.sem_oracle:
        print('--monitorar precisa gravar no Oracle (senao releria as mesmas '
              'linhas para sempre). Rode sem --sem-oracle.')
        sys.exit(1)

    intervalo_min = args.intervalo if args.intervalo else estado.ler_intervalo_monitor()

    db = None
    rows = None
    tem_shopee = False
    # --- Origem: Oracle (padrao) ou CSV (modo antigo) -----------------------
    if args.csv_path:
        if not os.path.exists(args.csv_path):
            print(f'CSV de origem nao encontrado: {args.csv_path}')
            sys.exit(1)
        origem_fields, rows = csv_io.read_origem(args.csv_path)
        base = os.path.splitext(os.path.basename(args.csv_path))[0]
    else:
        db = OracleDB()
        if not db.conectar():
            print('Sem conexao com o Oracle: nao ha fila para capturar.')
            print('Verifique o bloco "db" em conf/config.json (ou use --csv).')
            sys.exit(1)
        # Lojas com afiliado ativo (BESAVE.LOJA_AFILIADA), p/ gerar url_besave.
        # Lido uma vez aqui; o monitor fica horas no ar sem reconectar o
        # suficiente para justificar reler a cada varredura.
        afiliados.carregar(db)
        origem_fields = list(COLUNAS_FILA)
        base = f'oracle_{datetime.now():%d_%m_%Y_%H_%M}'
        # No modo lote a fila e lida ANTES de abrir o navegador: nao havendo
        # nada pendente, nem vale abrir o Chrome. O monitor le dentro do loop.
        if not args.monitorar:
            ultimo_id = args.desde if args.desde is not None else estado.ler_ultimo_id()
            print(f'[fila] Lendo OFERTA_FILA_CAPTURA (ST_CAPTURA=0, ID > {ultimo_id})...')
            try:
                rows = _ler_pendentes(db, ultimo_id, args.limite)
            except Exception as e:
                print(f'Falha ao ler a fila: {e}')
                db.desconectar()
                sys.exit(1)
            if not rows:
                print('Nenhuma oferta pendente (ST_CAPTURA = 0) para capturar.')
                db.desconectar()
                return

    atualiza_banco = db is not None and not args.sem_oracle
    header = csv_io.build_header(origem_fields)

    os.makedirs(IMG_DIR, exist_ok=True)
    img_root = IMG_DIR

    if not args.monitorar:
        print(f'{len(rows)} oferta(s) para capturar.')
        # A Shopee exige sessao logada (login manual). So pede login se o lote
        # tiver alguma URL da Shopee.
        tem_shopee = any(
            registry.resolver_loja((r.get('url') or '').strip()) == 'shopee'
            for r in rows
        )

    # 1) Garante que nenhum Chrome do usuario esteja aberto antes de comecar.
    _gate_fechar_navegadores()

    with sync_playwright() as p:
        # Chrome real com o perfil persistente (Default) -> Shopee ja logada.
        # headless=False: a Amazon renderiza diferente em headless.
        try:
            context = launch_persistent(p, headless=False)
        except Exception as e:
            print('Nao consegui abrir o Chrome com o seu perfil.')
            print(f'  Motivo: {e}')
            print(f'  Perfil: {PERFIL_DIR}')
            print('  >> FECHE o Chrome COMPLETAMENTE (inclusive processos em segundo')
            print('     plano: bandeja do sistema / Gerenciador de Tarefas) e rode de novo.')
            if db:
                db.desconectar()
            sys.exit(1)
        # Permissao de area de transferencia: os botoes "copiar link" das lojas
        # entregam o link do afiliado por la (ver core/link_afiliado.py).
        if capturar_link:
            link_afiliado.preparar_contexto(context)
        # Aba nova propria (o perfil real pode restaurar abas antigas).
        page = _nova_page(context)

        if args.monitorar:
            # 2) Monitor: o login da Shopee e decidido UMA vez, no arranque.
            _gate_login_shopee_arranque(page)
            # 3) Logins dos programas de afiliado (so p/ o DS_URL_AFILIADO).
            if capturar_link:
                _gates_login_afiliados(page)
            _monitorar(context, page, db, args, header, img_root, intervalo_min)
        else:
            # 2) Login manual da Shopee (so quando o lote tem produtos da Shopee).
            if tem_shopee:
                _gate_login_manual(page)
                _assentar_pos_login(page)
            # 3) Logins dos programas de afiliado (so p/ o DS_URL_AFILIADO).
            if capturar_link:
                _gates_login_afiliados(page)
            out_rows, gravadas, com_erro = _processar_lote(
                page, rows, db, atualiza_banco, img_root)
            _gravar_csv(out_rows, header, base)
            if atualiza_banco:
                _resumo_oracle(len(out_rows), gravadas, com_erro)
                _varrer_validade(db)

        context.close()

    if db:
        db.desconectar()


if __name__ == '__main__':
    main()
