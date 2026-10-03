"""
Estado da captura entre execucoes (controle de "ate onde ja li", POR GRUPO) e o
contador global de ofertas.

Guarda em ./conf/config.json duas coisas:
  - "grupos": para cada grupo, a ultima mensagem capturada — data/hora (do proprio
    WhatsApp) e o data-id (id unico da mensagem, usado como desempate quando ha
    varias mensagens no MESMO minuto). Assim, ao reiniciar, o monitor retoma
    exatamente de onde parou, sem repetir nem perder mensagens.
  - "controle": { "ultimo_id_processado": N } — contador GLOBAL e CONTINUO entre
    execucoes. Vira o ID_OFERTA no CSV. A cada mensagem lida soma 1 e persiste no
    disco (junto com o estado do grupo), para o arquivo estar sempre atualizado
    caso o processo caia.

Formato:
{
  "grupos": {
    "Promos da Ly ✨": {
      "ultima_data_hora": "11/07/2026 12:56",
      "ultimo_data_id": "false_...@g.us_ABC",
      "atualizado_em": "11/07/2026 12:57:03"
    }
  },
  "controle": { "ultimo_id_processado": 13 }
}
"""

import json
from datetime import datetime

from .storage import CONFIG_PATH

# Estado e config vivem no mesmo arquivo: ./conf/config.json (ver storage.py).
ESTADO_PATH = CONFIG_PATH
FMT = "%d/%m/%Y %H:%M"          # data/hora da mensagem (WhatsApp so tem minuto)


def carregar() -> dict:
    """Le o config.json (ou devolve estrutura vazia se nao existir/estiver corrompido)."""
    if ESTADO_PATH.exists():
        try:
            with open(ESTADO_PATH, encoding="utf-8") as f:
                dados = json.load(f)
            if isinstance(dados, dict) and isinstance(dados.get("grupos"), dict):
                # Garante o bloco de controle com o contador global.
                ctrl = dados.get("controle")
                if not isinstance(ctrl, dict):
                    ctrl = {}
                    dados["controle"] = ctrl
                try:
                    ctrl["ultimo_id_processado"] = int(ctrl.get("ultimo_id_processado", 0))
                except (TypeError, ValueError):
                    ctrl["ultimo_id_processado"] = 0
                return dados
        except Exception as e:  # noqa: BLE001
            print(f"[estado] Nao consegui ler {ESTADO_PATH.name}: {e} (comecando do zero).")
    return {"grupos": {}, "controle": {"ultimo_id_processado": 0}}


def salvar(estado: dict) -> None:
    """Grava o config.json (identado, UTF-8)."""
    ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        print(f"[estado] Falha ao salvar {ESTADO_PATH.name}: {e}")


def get_grupo(estado: dict, nome: str):
    """Entrada do grupo (dict com ultima_data_hora/ultimo_data_id) ou None."""
    return (estado.get("grupos") or {}).get(nome)


def get_ultimo_id(estado: dict) -> int:
    """Contador global de ofertas ja processadas (ultimo ID_OFERTA gravado)."""
    ctrl = estado.get("controle") or {}
    try:
        return int(ctrl.get("ultimo_id_processado", 0))
    except (TypeError, ValueError):
        return 0


def set_ultimo_id(estado: dict, valor: int, *, salvar_agora: bool = True) -> None:
    """Atualiza o contador global (ultimo_id_processado) e (por padrao) persiste."""
    estado.setdefault("controle", {})["ultimo_id_processado"] = int(valor)
    if salvar_agora:
        salvar(estado)


def parse_dt(s):
    """Converte 'DD/MM/AAAA HH:MM' de volta para datetime (ou None)."""
    try:
        return datetime.strptime(s, FMT) if s else None
    except (ValueError, TypeError):
        return None


def fmt_dt(dt) -> str:
    """datetime -> 'DD/MM/AAAA HH:MM' (ou '' se None)."""
    return dt.strftime(FMT) if dt else ""


def atualizar_grupo(estado: dict, nome: str, data_hora, data_id, *, salvar_agora: bool = True,
                    permitir_retrocesso: bool = False) -> None:
    """
    Marca a ultima mensagem capturada do grupo e (por padrao) persiste no disco.
    Chame apos gravar cada mensagem, sempre em ordem cronologica, para que o JSON
    reflita a mensagem mais recente ja processada.

    O marcador NAO RETROCEDE. Quem chama grava linha a linha e assume que a ultima
    gravada e a mais recente; em 30/07/2026 essa premissa falhou (a lista do
    catch-up saiu fora de ordem) e o marcador do carol andou de 21:42 para 15:29,
    o que faria a captura seguinte re-varrer 6h e duplicar tudo. Um marcador que
    so avanca limita o estrago de qualquer regressao de ordenacao a UM run.
    Rebobinar de proposito continua possivel editando o config.json (ou com
    permitir_retrocesso=True).
    """
    g = estado.setdefault("grupos", {}).setdefault(nome, {})
    if data_hora:
        atual = parse_dt(g.get("ultima_data_hora"))
        if atual and data_hora < atual and not permitir_retrocesso:
            print(f"[estado] AVISO: ignorei retrocesso do marcador de {nome!r} "
                  f"({fmt_dt(atual)} -> {fmt_dt(data_hora)}); a lista chegou fora "
                  "de ordem cronologica.")
            return                             # data_hora e data_id andam juntos
        g["ultima_data_hora"] = fmt_dt(data_hora)
    if data_id:
        g["ultimo_data_id"] = data_id
    g["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if salvar_agora:
        salvar(estado)
