"""
Navegador quebrado do robo das lojas (BSV-65): classificacao, estado da recuperacao e diagnostico.

So stdlib. A classificacao e uma funcao so (`sinal`), usada pelo lote, pelo batimento e pelo link de
afiliado: nada de `in str(e)` espalhado. `Controle` guarda o estado de uma execucao (timeouts seguidos,
linhas retidas, ocorrencia aberta, relancamentos); a recuperacao em si (aba, contexto, Playwright) fica
no main.py, que tem o Playwright na mao.
"""

import os
import time
from pathlib import Path

# Pagina/contexto/navegador fechado (BSV-57) e renderer/aba morta (BSV-65), em minusculas.
SINAIS_NAVEGADOR_FECHADO = ('has been closed', 'target closed', 'target page, context or browser')
SINAIS_NAVEGADOR_QUEBRADO = ('page crashed', 'target crashed') + SINAIS_NAVEGADOR_FECHADO

TIMEOUTS_SEGUIDOS = 3          # timeouts de navegacao seguidos que disparam a recuperacao
TIMEOUTS_POR_LINHA = 3         # timeouts da mesma linha que a mandam para '9'
MAX_RELANCAMENTOS = 3          # o 3o relancamento por falha em JANELA_RELANCAMENTOS sai com codigo 3
JANELA_RELANCAMENTOS_S = 3600
CODIGO_SAIDA = 3
RELANCAR_HORAS_PADRAO = 6.0

MSG_NAO_REABRIU = 'Robo das lojas: navegador nao reabriu; saindo (codigo 3) para o vigia reiniciar.'
SINAL_TIMEOUTS = f'{TIMEOUTS_SEGUIDOS} timeouts seguidos'
ACAO_ABA = 'aba nova'
ACAO_RELANCADO = 'navegador relancado'


def sinal(erro):
    """Sinal de navegador quebrado na excecao (ou no texto de status), ex. 'Page crashed'; senao None."""
    texto = str(erro or '').lower()
    for s in SINAIS_NAVEGADOR_QUEBRADO:
        if s in texto:
            return s[:1].upper() + s[1:]
    return None


def e_timeout(erro):
    """TimeoutError (do Playwright ou do Python) -- so vale quando vem do goto."""
    return type(erro).__name__ == 'TimeoutError'


def msg_quebrou(sinal_txt, acao, retidas):
    return f'Robo das lojas: navegador quebrou ({sinal_txt}); {acao}. {retidas} linha(s) retida(s).'


def msg_voltou(retidas):
    return f'Robo das lojas: navegador voltou ({retidas} linha(s) retida(s) voltam a ser processadas).'


class Controle:
    """Estado do navegador numa execucao do robo. `agora` = relogio monotono em segundos (testes trocam)."""

    def __init__(self, avisar=None, agora=None, relancar_horas=RELANCAR_HORAS_PADRAO):
        self.avisar = avisar or (lambda texto: print(f'[alerta] {texto}'))
        self.agora = agora or time.monotonic
        self.relancar_horas = relancar_horas
        self.seq_timeouts = 0
        self.timeouts_linha = {}       # ID_OFERTA -> timeouts nesta execucao
        self.retidas = 0               # linhas retidas pelo navegador desde a ultima ok por navegador
        self.aberta = False            # houve recuperacao e ainda nao veio ok por navegador
        self.pendente = None           # sinal que pede recuperacao antes da proxima linha
        self.aba_nova = False          # aba nova ainda sem a primeira navegacao bem-sucedida
        self.crash = False             # evento 'crash' da page atual
        self.relancamentos = []        # instantes dos relancamentos por falha (o preventivo nao entra)
        self.lancado_em = self.agora()
        self.navegacoes = 0

    # --- linha ---------------------------------------------------------------------------------------
    def navegou(self):
        self.navegacoes += 1

    def quebrou(self, sinal_txt):
        """Linha retida por navegador quebrado: pede recuperacao."""
        self.retidas += 1
        self.pendente = sinal_txt

    def timeout(self, id_oferta):
        """Timeout de navegacao. Devolve True quando a linha ja tem TIMEOUTS_POR_LINHA (vai para '9')."""
        self.seq_timeouts += 1
        n = self.timeouts_linha.get(id_oferta, 0) + 1
        self.timeouts_linha[id_oferta] = n
        para_9 = n >= TIMEOUTS_POR_LINHA
        if not para_9:
            self.retidas += 1
        if self.seq_timeouts >= TIMEOUTS_SEGUIDOS:
            self.seq_timeouts = 0
            self.pendente = SINAL_TIMEOUTS
        return para_9

    def ok(self):
        """Linha ok de loja por navegador: zera a sequencia e fecha a ocorrencia com "voltou"."""
        self.seq_timeouts = 0
        self.aba_nova = False
        if self.aberta:
            self.avisar(msg_voltou(self.retidas))
        self.aberta = False
        self.retidas = 0

    # --- recuperacao ---------------------------------------------------------------------------------
    def pode_relancar(self):
        """False quando este seria o MAX_RELANCAMENTOS-esimo relancamento por falha na janela."""
        agora = self.agora()
        self.relancamentos = [t for t in self.relancamentos if agora - t < JANELA_RELANCAMENTOS_S]
        return len(self.relancamentos) + 1 < MAX_RELANCAMENTOS

    def relancou(self, preventivo=False):
        if not preventivo:
            self.relancamentos.append(self.agora())
        self.lancado_em = self.agora()
        self.navegacoes = 0
        self.aba_nova = False
        self.crash = False

    def preventivo_vencido(self):
        return self.relancar_horas > 0 and self.agora() - self.lancado_em >= self.relancar_horas * 3600

    def diagnostico(self, proc=None, pid=None):
        return diagnostico(self.agora() - self.lancado_em, self.navegacoes, proc=proc, pid=pid)


# --- diagnostico (Saida 8) -----------------------------------------------------------------------------


def _kb(texto, chave):
    for linha in texto.splitlines():
        if linha.startswith(chave + ':'):
            return int(linha.split()[1])
    raise ValueError(chave)


def _mem_disponivel(proc):
    try:
        return f'{_kb((proc / "meminfo").read_text(encoding="utf-8"), "MemAvailable") // 1024} MB'
    except (OSError, ValueError, IndexError):
        return '?'


def _processos(proc):
    """pid -> (nome, ppid, rss_kb) de /proc; processo que sumiu no meio da leitura fica de fora."""
    tabela = {}
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            status = (d / 'status').read_text(encoding='utf-8')
            nome = next((x.split(':', 1)[1].strip() for x in status.splitlines() if x.startswith('Name:')), '')
            ppid = _kb(status, 'PPid')
            try:
                rss = _kb(status, 'VmRSS')
            except (ValueError, IndexError):
                rss = 0                 # processo zumbi nao tem VmRSS
        except (OSError, ValueError, IndexError):
            continue
        tabela[int(d.name)] = (nome, ppid, rss)
    return tabela


def _chromium(proc, pid):
    """(quantidade, soma do RSS, maior RSS) dos Chromium descendentes de `pid`; '?' se /proc nao ler."""
    try:
        tabela = _processos(proc)
    except OSError:
        return '?', '?', '?'
    filhos = {}
    for p, (_, ppid, _) in tabela.items():
        filhos.setdefault(ppid, []).append(p)
    descendentes, fila = [], list(filhos.get(pid, []))
    while fila:
        p = fila.pop()
        descendentes.append(p)
        fila.extend(filhos.get(p, []))
    rss = [tabela[p][2] for p in descendentes if 'chrom' in tabela[p][0].lower()]
    return str(len(rss)), f'{sum(rss) // 1024} MB', f'{max(rss, default=0) // 1024} MB'


def diagnostico(desde_s, navegacoes, proc=None, pid=None):
    """Linha `[navegador] diagnostico:` (Saida 8). Nunca levanta; fora do Linux so tempo e navegacoes."""
    proc = Path(proc) if proc is not None else Path('/proc')
    pid = os.getpid() if pid is None else pid
    partes = []
    try:
        linux = proc.is_dir()
    except OSError:
        linux = False
    if linux:
        qtd, soma, maior = _chromium(proc, pid)
        partes += [f'mem_disponivel={_mem_disponivel(proc)}', f'chromium={qtd}', f'rss_chromium={soma}',
                   f'maior={maior}']
    try:
        partes.append(f'desde_lancamento={int(desde_s // 60)} min')
    except (TypeError, ValueError):
        partes.append('desde_lancamento=?')
    partes.append(f'navegacoes={navegacoes}')
    return '[navegador] diagnostico: ' + ' | '.join(partes)
