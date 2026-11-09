"""
Aviso avulso no Telegram pela linha de comando (BSV-54).

Uso: python -m wa.avisar "<texto>"

Token e chat vem de alerta.telegram_token / telegram_chat_id do conf/config.json
(fora do git), nunca da linha de comando. Sem eles, so loga e sai com 0: aviso
nao pode derrubar quem chama. So o tipo do erro vai ao log (a URL leva o token).
"""

import json
import sys

from . import alerta
from .storage import CONFIG_PATH


def avisar(texto: str, config_path=CONFIG_PATH, enviar=None) -> int:
    print(f"[avisar] {texto}")
    try:
        with open(config_path, encoding="utf-8") as f:
            bloco = json.load(f).get("alerta")
    except (OSError, ValueError, AttributeError) as e:
        print(f"[avisar] config.json ilegivel ({type(e).__name__}); so log.")
        return 0
    bloco = bloco if isinstance(bloco, dict) else {}
    token = str(bloco.get("telegram_token") or "").strip()
    chat = str(bloco.get("telegram_chat_id") or "").strip()
    if not (token and chat):
        print("[avisar] Telegram nao configurado (alerta.telegram_token/telegram_chat_id); so log.")
        return 0
    try:
        (enviar or alerta.enviar_telegram)(token, chat, texto)
    except Exception as e:  # noqa: BLE001
        print(f"[avisar] Falha ao enviar ao Telegram ({type(e).__name__}).")
    return 0


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return avisar(" ".join(args).strip() or "(sem texto)")


if __name__ == "__main__":
    sys.exit(main())
