"""
Aviso de captura parada no Telegram (BSV-51).

Em 22/10/2026 o robo girou 5h30 sem abrir grupo e ninguem soube (o alerta do
worker e de 8 h). O vigia roda uma vez por volta: se, FORA da janela noturna,
passar `sem_abrir_minutos` sem nenhum grupo abrir, manda uma mensagem (lembrete a
cada 2 h) e, quando destravar, UMA de "voltou". Sem token/chat no config.json
("alerta"), so loga. So stdlib; relogio e envio entram por parametro para teste.
"""

import json
import urllib.request
from datetime import datetime, timedelta

from . import janela as janela_mod

SEM_ABRIR_MINUTOS_PADRAO = 45
LEMBRETE = timedelta(hours=2)
TIMEOUT_ENVIO_S = 10


def enviar_telegram(token: str, chat_id: str, texto: str) -> None:
    corpo = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=corpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_ENVIO_S) as r:
        r.read()


def fim_mais_recente(janela, agora):
    """Instante em que a janela noturna terminou pela ultima vez (<= agora), ou None sem janela."""
    if janela is None:
        return None
    fim = datetime.combine(agora.date(), janela[1])
    return fim if fim <= agora else fim - timedelta(days=1)


class VigiaCaptura:
    def __init__(self, cfg, janela, inicio=None, enviar=None):
        bloco = (cfg or {}).get("alerta")
        bloco = bloco if isinstance(bloco, dict) else {}
        try:
            minutos = float(bloco.get("sem_abrir_minutos", SEM_ABRIR_MINUTOS_PADRAO))
        except (TypeError, ValueError):
            minutos = SEM_ABRIR_MINUTOS_PADRAO
        self.limite = timedelta(minutes=minutos if minutos > 0 else SEM_ABRIR_MINUTOS_PADRAO)
        self.token = str(bloco.get("telegram_token") or "").strip()
        self.chat = str(bloco.get("telegram_chat_id") or "").strip()
        self.janela = janela
        self.enviar = enviar or enviar_telegram
        self.ultimo_aberto = inicio or datetime.now()
        self.alertado_em = None          # instante do ultimo aviso/lembrete; None = sem ocorrencia aberta
        self.desde = None                # inicio da ocorrencia (ultimo grupo aberto)

    def _avisar(self, texto: str) -> None:
        print(f"[alerta] {texto}")
        if not (self.token and self.chat):
            print("[alerta] Telegram nao configurado (alerta.telegram_token/telegram_chat_id); so log.")
            return
        try:
            self.enviar(self.token, self.chat, texto)
        except Exception as e:  # noqa: BLE001
            # So o tipo: a URL da API leva o token e nao pode ir para o log.
            print(f"[alerta] Falha ao enviar ao Telegram ({type(e).__name__}).")

    def registrar_volta(self, abriu_algum: bool, agora=None) -> None:
        agora = agora or datetime.now()
        if abriu_algum or janela_mod.dentro(self.janela, agora):
            # Dentro da janela noturna o relogio zera: ao sair dela conta do zero.
            if self.alertado_em is not None and abriu_algum:
                parado = (agora - self.desde).total_seconds() / 60
                self._avisar(f"Robo do WhatsApp voltou a abrir grupos (ficou parado ~{parado:.0f} min).")
                self.alertado_em = self.desde = None
            self.ultimo_aberto = agora
            return
        # Fora da janela o tempo parado conta do FIM dela: a ultima volta aberta foi
        # a de dentro (dormiu ate 08:00), e nao pode contar o sono como parada.
        fim = fim_mais_recente(self.janela, agora)
        if fim is not None and fim > self.ultimo_aberto:
            self.ultimo_aberto = fim
        parado = agora - self.ultimo_aberto
        if self.alertado_em is None:
            if parado >= self.limite:
                self.desde, self.alertado_em = self.ultimo_aberto, agora
                self._avisar(f"Robo do WhatsApp parado: nenhum grupo abre ha {parado.total_seconds() / 60:.0f} min. "
                             "Pode haver um aviso cobrindo a tela; veja o log e a tela VNC.")
        elif agora - self.alertado_em >= LEMBRETE:
            self.alertado_em = agora
            self._avisar(f"Robo do WhatsApp continua parado ha {parado.total_seconds() / 60:.0f} min.")
