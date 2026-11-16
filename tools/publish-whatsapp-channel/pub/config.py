"""conf/config.json do publicador (BSV-63). Relido a cada volta; o publicador nunca grava nele."""

import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

CAMINHO = Path(__file__).resolve().parent.parent / "conf" / "config.json"

PADRAO_INTERVALO_MIN = 15.0
PADRAO_MAX_HORAS_FILA = 3.0
PADRAO_TIMEOUT_POST_S = 60.0
PADRAO_ID_CANAL = 2
MODOS_LEGENDA = ("colar", "digitar")


class ErroConfig(RuntimeError):
    """config.json ausente, ilegivel ou fora do formato."""


@dataclass
class Config:
    habilitado: bool = True
    intervalo_minutos: float = PADRAO_INTERVALO_MIN
    max_horas_fila: float = PADRAO_MAX_HORAS_FILA
    timeout_post_segundos: float = PADRAO_TIMEOUT_POST_S
    id_canal: int = PADRAO_ID_CANAL
    modo_legenda: str = "colar"
    oracle: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


def _positivo(bruto: dict, chave: str, padrao: float, avisos: list[str]) -> float:
    if chave not in bruto:
        return padrao
    v = bruto[chave]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        avisos.append(f"{chave}={v!r} invalido; usando {padrao:g}")
        return padrao
    return float(v)


def de_dict(bruto: dict) -> Config:
    if not isinstance(bruto, dict):
        raise ErroConfig("config.json nao e um objeto JSON")
    avisos: list[str] = []
    hab = bruto.get("habilitado", True)
    if not isinstance(hab, bool):
        avisos.append(f"habilitado={hab!r} invalido; usando false")
        hab = False
    canal = bruto.get("id_canal", PADRAO_ID_CANAL)
    if isinstance(canal, bool) or not isinstance(canal, int) or canal < 1:
        avisos.append(f"id_canal={canal!r} invalido; usando {PADRAO_ID_CANAL}")
        canal = PADRAO_ID_CANAL
    modo = bruto.get("modo_legenda", "colar")
    if modo not in MODOS_LEGENDA:
        avisos.append(f"modo_legenda={modo!r} invalido; usando colar")
        modo = "colar"
    oracle = bruto.get("oracle") or {}
    if not isinstance(oracle, dict):
        raise ErroConfig("bloco oracle fora do formato")
    return Config(
        habilitado=hab,
        intervalo_minutos=_positivo(bruto, "intervalo_minutos", PADRAO_INTERVALO_MIN, avisos),
        max_horas_fila=_positivo(bruto, "max_horas_fila", PADRAO_MAX_HORAS_FILA, avisos),
        timeout_post_segundos=_positivo(bruto, "timeout_post_segundos", PADRAO_TIMEOUT_POST_S, avisos),
        id_canal=canal,
        modo_legenda=modo,
        oracle=dict(oracle),
        avisos=avisos,
    )


def carregar(caminho=None) -> Config:
    caminho = Path(caminho or CAMINHO)
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErroConfig(f"nao consegui ler {caminho.name} ({type(e).__name__})") from e
    return de_dict(bruto)


def aviso_permissao(caminho=None) -> str | None:
    """Config legivel por grupo/outros tem a senha do Oracle exposta (BSV-60): WARN, nao recusa."""
    if sys.platform == "win32":
        return None
    try:
        modo = stat.S_IMODE(os.stat(caminho or CAMINHO).st_mode)
    except OSError:
        return None
    if modo & 0o077:
        return f"config.json com permissao {modo:03o}; use 600 (chmod 600 conf/config.json)"
    return None
