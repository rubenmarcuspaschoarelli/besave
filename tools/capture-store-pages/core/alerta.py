"""Aviso no Telegram do robo das lojas (BSV-55).

Mesmo formato e mesma regra do robo do WhatsApp (capture-chat-groups/wa/alerta.py):
bloco "alerta" do config.json (telegram_token, telegram_chat_id), opcional; sem as
chaves, so log. O token nunca vai para log, print ou excecao (a URL da API o leva).
So stdlib; o envio entra por parametro para teste.
"""

import json
import urllib.request

TIMEOUT_ENVIO_S = 10


def enviar_telegram(token, chat_id, texto):
    corpo = json.dumps({'chat_id': chat_id, 'text': texto}).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage', data=corpo,
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
        print(f'[alerta] {texto}')
        if not (self.token and self.chat):
            print('[alerta] Telegram nao configurado (alerta.telegram_token/telegram_chat_id); so log.')
            return
        try:
            self.enviar(self.token, self.chat, texto)
        except Exception as e:  # noqa: BLE001
            # So o tipo: a mensagem da excecao pode trazer a URL com o token.
            print(f'[alerta] Falha ao enviar ao Telegram ({type(e).__name__}).')
