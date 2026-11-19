"""Avisos ao operador pelo bot de alertas (BSV-63). So stdlib.

Token e chat: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID do ambiente; senao do arquivo BESAVE_WORKER_ENV
(padrao /srv/besave/worker.env, KEY=VALUE), igual ao vigia. Nada disso entra em log ou mensagem; falha do
Telegram so vai ao log (o tipo, nunca a URL: ela leva o token).
"""

import json
import os
import re
import urllib.request
from pathlib import Path

TIMEOUT_ENVIO_S = 10
PADRAO_TOKEN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
PADRAO_URL = re.compile(r"https?://\S+", re.IGNORECASE)
PREFIXO = "Publicador do WhatsApp: "


def ler_env_arquivo(caminho: Path) -> dict:
    valores = {}
    try:
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.removeprefix("export ").split("=", 1)
            valores[k.strip()] = v.strip().strip("'\"")
    except OSError:
        return {}
    return valores


def credenciais(env=None) -> tuple[str, str]:
    env = os.environ if env is None else env
    token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")
    if token and chat:
        return token, chat
    arq = ler_env_arquivo(Path(env.get("BESAVE_WORKER_ENV") or "/srv/besave/worker.env"))
    return arq.get("TELEGRAM_BOT_TOKEN", ""), arq.get("TELEGRAM_CHAT_ID", "")


def enviar_telegram(token: str, chat_id: str, texto: str) -> None:
    corpo = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=corpo,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_ENVIO_S) as r:
        r.read()


class Avisador:
    def __init__(self, token: str = "", chat: str = "", enviar=None, log=print):
        self._segredos = [s for s in (token, chat) if s]
        self._log = log
        if enviar is not None:
            self._enviar = enviar
        elif token and chat:
            self._enviar = lambda texto: enviar_telegram(token, chat, texto)
        else:
            self._enviar = None

    def redigir(self, texto: str) -> str:
        for s in self._segredos:
            texto = texto.replace(s, "REDACTED")
        return PADRAO_URL.sub("[url]", PADRAO_TOKEN.sub("REDACTED", texto))

    def __call__(self, texto: str) -> None:
        texto = self.redigir(PREFIXO + texto)
        self._log(f"[aviso] {texto}")
        if self._enviar is None:
            self._log("[aviso] Telegram nao configurado (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID); so log.")
            return
        try:
            self._enviar(texto)
        except Exception as e:  # noqa: BLE001
            self._log(f"[aviso] falha ao enviar ao Telegram ({type(e).__name__})")
