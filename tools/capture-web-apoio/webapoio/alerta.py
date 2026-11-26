"""Aviso no Telegram (bloco `alerta` do config.json, mesmo formato do robô das lojas; vazio = só log).

O token nunca vai para log nem exceção (a URL da API o leva).
"""

import json
import logging
import urllib.request

log = logging.getLogger('captura_web')

TIMEOUT_ENVIO_S = 10


def enviar_telegram(token, chat_id, texto):
    corpo = json.dumps({'chat_id': chat_id, 'text': texto}).encode('utf-8')
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=corpo,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=TIMEOUT_ENVIO_S) as r:
        r.read()


class Avisador:
    def __init__(self, cfg=None, enviar=None):
        bloco = (cfg or {}).get('alerta')
        bloco = bloco if isinstance(bloco, dict) else {}
        self.token = str(bloco.get('telegram_token') or '').strip()
        self.chat = str(bloco.get('telegram_chat_id') or '').strip()
        self.enviar = enviar or enviar_telegram

    def avisar(self, texto):
        log.warning('[alerta] %s', texto)
        if not (self.token and self.chat):
            log.info('[alerta] Telegram nao configurado; so log.')
            return
        try:
            self.enviar(self.token, self.chat, texto)
        except Exception as e:  # noqa: BLE001
            log.error('[alerta] falha ao enviar ao Telegram (%s).', type(e).__name__)
