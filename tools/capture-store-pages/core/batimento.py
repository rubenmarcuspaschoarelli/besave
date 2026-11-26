"""
Batimento do robo das lojas para o vigia externo (BSV-57).

Grava conf/batimento.json por arquivo temporario + rename. So stdlib. Renova a cada linha
concluida (ok, retida, pausada, rejeitada) e a cada varredura, inclusive com a fila vazia e com
lojas em pausa (loja pausada nao e robo parado). Excecao de navegador fechado NAO renova: o robo
girando sem pagina nao captura nada. Falha de escrita so loga.

    {"robo":"lojas","pid":1,"em":"...Z","prazo":"...Z","fase":"varredura",
     "ultimo_ok_navegador":"...Z","tentativas_navegador":0}

Os dois ultimos campos (BSV-65) olham so loja por navegador: `ultimo_ok_navegador` = ultima linha ok
(antes da primeira, o primeiro batimento do processo) e `tentativas_navegador` = linhas concluidas sem
ok desde entao. Shopee pela API e loja em pausa nao mexem. O vigia avisa quando a captura por navegador
para com o robo vivo.

`prazo` = (agora + tempo de sono) + 10 min. BESAVE_BATIMENTO troca o caminho (testes). Copia de capture-chat-groups/wa/batimento.py: os dois
robos nao compartilham pacote.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.navegador import SINAIS_NAVEGADOR_FECHADO, sinal  # noqa: F401  (classificacao unica, BSV-65)

ROBO = 'lojas'
PRAZO = timedelta(minutes=10)
CAMINHO = Path(__file__).resolve().parent.parent / 'conf' / 'batimento.json'


_navegador = {'ultimo_ok': None, 'tentativas': 0}


def agora_utc():
    return datetime.now(timezone.utc)


def _iso(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def gravar_atomico(caminho, dados):
    """Escreve `dados` em `caminho` sem nunca deixar o arquivo pela metade. Falha so loga."""
    tmp = None
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_name(f'{caminho.name}.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        os.replace(tmp, caminho)
        return True
    except Exception as e:  # noqa: BLE001
        print(f'[batimento] Falha ao gravar o batimento ({type(e).__name__}); a captura segue.')
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def bater(fase, dorme_s=0, agora=None, caminho=None):
    """Renova o batimento. `dorme_s` = quanto o robo vai dormir: o prazo vale da hora de acordar."""
    agora = agora or agora_utc()
    dados = {
        'robo': ROBO,
        'pid': os.getpid(),
        'em': _iso(agora),
        'prazo': _iso(agora + timedelta(seconds=max(0, dorme_s)) + PRAZO),
        'fase': fase,
    }
    if _navegador['ultimo_ok'] is None:
        _navegador['ultimo_ok'] = agora
    dados['ultimo_ok_navegador'] = _iso(_navegador['ultimo_ok'])
    dados['tentativas_navegador'] = _navegador['tentativas']
    return gravar_atomico(caminho or os.environ.get('BESAVE_BATIMENTO') or CAMINHO, dados)


def registrar_navegador(ok, agora=None):
    """Linha de loja por navegador concluida (BSV-65): ok renova `ultimo_ok_navegador`, senao conta."""
    if ok:
        _navegador['ultimo_ok'] = agora or agora_utc()
        _navegador['tentativas'] = 0
    else:
        _navegador['tentativas'] += 1


def navegador_fechado(status):
    """True se o `status_captura` da linha e uma excecao de navegador quebrado (core/navegador.sinal)."""
    texto = str(status or '')
    return texto.lower().startswith('erro:') and sinal(texto) is not None


def bater_linha(status):
    """Linha concluida: renova, exceto quando o navegador morreu embaixo dela."""
    if navegador_fechado(status):
        return False
    return bater('linha')
