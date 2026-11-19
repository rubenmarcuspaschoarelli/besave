"""Regras puras do publicador (BSV-63): ritmo do canal, descarte e escolha da linha. Sem I/O.

Horario de Brasilia, offset fixo -03:00 (CLAUDE.md regra 5). As datas do Oracle sao hora local
(igual ao worker, `BESAVE_ORACLE_TZ` padrao) e chegam aqui como `datetime` ingenuo.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

BRASILIA = timezone(timedelta(hours=-3))

EXPIROU, VELHA, OUTRO_DIA = "expirou", "velha", "outro_dia"
VARIACAO_SONO = 0.30


def local(agora: datetime) -> datetime:
    """Instante (com fuso) -> hora de Brasilia ingenua, como o Oracle guarda."""
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=UTC)
    return agora.astimezone(BRASILIA).replace(tzinfo=None)


def inicio_do_dia(agora: datetime) -> datetime:
    """00:00 de Brasilia do dia de `agora`, ingenuo."""
    return local(agora).replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Parametros:
    """`PARAMETROS_ENVIO` do canal: so o teto e a janela valem para o WhatsApp (CONTRATO §11.4)."""

    qt_max_dia: int
    hora_inicio: int
    hora_fim: int


def esperado(p: Parametros, agora: datetime) -> int | None:
    """`min(MAX, 1 + floor(MAX x minutos_desde_INICIO / minutos_da_janela))`; None fora de [INICIO, FIM).
    E o `esperado` do envio do Telegram (apps/worker/src/envio/janela.rs) com L = 1."""
    t = local(agora)
    m = t.hour * 60 + t.minute
    ini, fim = p.hora_inicio * 60, p.hora_fim * 60
    if m < ini or m >= fim or fim <= ini:
        return None
    ritmo = p.qt_max_dia * (m - ini) // (fim - ini)
    return min(p.qt_max_dia, 1 + ritmo)


def devido(p: Parametros, agora: datetime, enviados_hoje: int) -> bool:
    """Cabe 1 post agora: dentro da janela, abaixo do teto e no ritmo."""
    e = esperado(p, agora)
    return e is not None and enviados_hoje < p.qt_max_dia and e - enviados_hoje >= 1


@dataclass(frozen=True)
class Linha:
    """Uma linha `P` de ENVIO_WHATSAPP com o estado da oferta."""

    id_envio: int
    id_oferta: int
    legenda: str
    area_slug: str
    dt_fila: datetime          # hora local ingenua
    ativa: bool                # OFERTA.ST_ATIVO = 1 (oferta ausente = False)


def motivo_descarte(linha: Linha, agora: datetime, max_horas_fila: float) -> str | None:
    """Ordem: expirou > outro_dia > velha. None = pode postar."""
    if not linha.ativa:
        return EXPIROU
    if linha.dt_fila < inicio_do_dia(agora):
        return OUTRO_DIA
    if local(agora) - linha.dt_fila > timedelta(hours=max_horas_fila):
        return VELHA
    return None


def separar(linhas, agora: datetime, max_horas_fila: float):
    """-> (descartes [(linha, motivo)], validas)."""
    descartes, validas = [], []
    for linha in linhas:
        motivo = motivo_descarte(linha, agora, max_horas_fila)
        if motivo is None:
            validas.append(linha)
        else:
            descartes.append((linha, motivo))
    return descartes, validas


def escolher(validas) -> Linha | None:
    """A mais recente da fila (maior DT_FILA; empate: maior id)."""
    return max(validas, key=lambda x: (x.dt_fila, x.id_envio), default=None)


def sono_segundos(intervalo_minutos: float, aleatorio: float) -> float:
    """`intervalo x U(0,7; 1,3)`; `aleatorio` em [0, 1)."""
    if not math.isfinite(aleatorio):
        aleatorio = 0.5
    fator = 1 - VARIACAO_SONO + 2 * VARIACAO_SONO * min(max(aleatorio, 0.0), 1.0)
    return intervalo_minutos * 60 * fator
