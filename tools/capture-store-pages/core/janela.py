"""Janela noturna do --monitorar: "janela_noturna" no config.json.

{"inicio": "22:00", "fim": "08:00", "intervalo_minutos": 120}. Ausente ou invalida =
sem janela (ritmo normal). Pode cruzar a meia-noite (inicio > fim). Copia de
capture-chat-groups/wa/janela.py: os dois robos nao compartilham pacote.
"""
from datetime import datetime
from datetime import time as hora


def _hora(valor):
    try:
        h, m = str(valor).strip().split(':')
        return hora(int(h), int(m))
    except (ValueError, TypeError):
        return None


def ler_janela(cfg):
    """Devolve (inicio, fim, intervalo_s) ou None se ausente/invalida."""
    bloco = (cfg or {}).get('janela_noturna')
    if not isinstance(bloco, dict):
        return None
    inicio, fim = _hora(bloco.get('inicio')), _hora(bloco.get('fim'))
    try:
        intervalo = float(bloco.get('intervalo_minutos'))
    except (TypeError, ValueError):
        return None
    if inicio is None or fim is None or inicio == fim or intervalo <= 0:
        return None
    return inicio, fim, intervalo * 60


def dentro(janela, agora=None):
    if janela is None:
        return False
    inicio, fim, _ = janela
    t = (agora or datetime.now()).time().replace(second=0, microsecond=0)
    if inicio < fim:
        return inicio <= t < fim
    return t >= inicio or t < fim


def espera_s(janela, agora, normal_s):
    """Segundos ate a proxima rodada: ritmo da janela (cortado no `fim`) ou `normal_s`."""
    agora = agora or datetime.now()
    if not dentro(janela, agora):
        return normal_s
    _, fim, intervalo_s = janela
    ate_fim = (datetime.combine(agora.date(), fim) - agora).total_seconds()
    if ate_fim <= 0:
        ate_fim += 86400
    return min(intervalo_s, ate_fim)
