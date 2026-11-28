"""
Tela de login do WhatsApp Web e vinculo pelo codigo no celular (BSV-67).

Em 26/11 a sessao se perdeu e o robo saiu a cada 5,5 min esperando alguem ler o QR (254 partidas). O WhatsApp
Web tambem vincula por um codigo de 8 caracteres digitado no celular: o robo pede o codigo, manda pelo
Telegram e fica VIVO esperando, com batimento `fase: "pareamento"`.

Seletores colhidos da pagina real em 27/11 (fixtures em tools/tests/fixtures/whatsapp/): data-testid e
aria-label, texto visivel (pt e en) so como reserva; nunca classe ofuscada (regra de browser.py).
O numero nunca vai inteiro ao log nem ao Telegram (`***1234`); o codigo so vai ao Telegram.
"""

import json
import re
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from . import batimento as batimento_mod

WHATSAPP_URL = "https://web.whatsapp.com/"

SEL_LOGADO = "#pane-side"
SEL_QR = 'canvas[aria-label*="QR code"]'
SEL_LINK_NUMERO = '[data-testid="link_device_qr_phone_number_link"]'
TEXTOS_LINK_NUMERO = ("Entrar com número de telefone", "Log in with phone number")
SEL_TELA_NUMERO = '[data-testid="link-device-phone-number-entry-screen"]'
SEL_CAMPO = 'input[data-testid="phone-number-input"]'
TEXTOS_AVANCAR = ("Avançar", "Next")
SEL_CODIGO = '[data-testid="link-with-phone-number-code-cells"]'

LOGADO, QR, NUMERO, CODIGO = "logado", "qr", "numero", "codigo"

ESPERA_TELA_S = 300          # o mesmo prazo de antes para o #pane-side
ESPERA_ACAO_S = 30
INTERVALO_S = 5
PRAZO_PAREAMENTO = timedelta(minutes=15)
NOVA_TENTATIVA = timedelta(seconds=60)
VALIDADE_PADRAO_MIN = 10
POR_HORA, POR_DIA = 3, 12
BRASILIA = timezone(timedelta(hours=-3))      # offset fixo (CLAUDE.md regra 5)
CAMINHO_PEDIDOS = Path(__file__).resolve().parent.parent / "conf" / "pareamento_pedidos.json"

MSG_VINCULADO = "WhatsApp: vinculado de novo pelo codigo; captura retomada."
MSG_SEM_NUMERO = "WhatsApp desconectado e sem pareamento.numero no config: ler o QR pela tela VNC :2."


def agora_utc() -> datetime:
    return datetime.now(UTC)


def hhmm_brasilia(dt: datetime) -> str:
    return dt.astimezone(BRASILIA).strftime("%H:%M")


def so_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def mascarar(numero) -> str:
    return "***" + so_digitos(numero)[-4:]


def codigo_valido(bruto) -> str | None:
    """`data-link-code` ("R,H,S,D,E,V,N,N") -> "RHSDEVNN"; fora de 8 [A-Z0-9] -> None."""
    codigo = str(bruto or "").replace(",", "").strip()
    return codigo if re.fullmatch(r"[A-Z0-9]{8}", codigo) else None


def msg_codigo(codigo: str, pedido_em: datetime) -> str:
    return ("WhatsApp desconectado. No celular: WhatsApp > Aparelhos conectados > Conectar aparelho > "
            f"Conectar com numero de telefone e digite {codigo[:4]}-{codigo[4:]} "
            f"(pedido as {hhmm_brasilia(pedido_em)}, Brasilia).")


def msg_numero_recusado(numero) -> str:
    return (f"WhatsApp desconectado: o campo nao aceitou o numero do config ({mascarar(numero)}); "
            "ler o QR pela tela VNC :2.")


def msg_teto(proximo: datetime) -> str:
    return f"WhatsApp desconectado: limite de codigos atingido; proximo pedido as {hhmm_brasilia(proximo)} (Brasilia)."


def ler_config(cfg) -> tuple[str, float]:
    """(numero so com digitos, validade em minutos) do bloco `pareamento` do config.json."""
    bloco = (cfg or {}).get("pareamento")
    bloco = bloco if isinstance(bloco, dict) else {}
    try:
        validade = float(bloco.get("validade_min") or VALIDADE_PADRAO_MIN)
    except (TypeError, ValueError):
        validade = VALIDADE_PADRAO_MIN
    return so_digitos(bloco.get("numero")), validade if validade > 0 else VALIDADE_PADRAO_MIN


# ------------------------------------------------------------------------------------------- teto


class Teto:
    """No maximo 3 pedidos por hora cheia e 12 por dia (Brasilia), gravados em arquivo: partida nova nao zera
    a conta (o WhatsApp pode bloquear vinculo por excesso de tentativas)."""

    def __init__(self, caminho=None, por_hora=POR_HORA, por_dia=POR_DIA):
        self.caminho = Path(caminho or CAMINHO_PEDIDOS)
        self.por_hora, self.por_dia = por_hora, por_dia

    def _pedidos(self) -> list[datetime]:
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            return [datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) for x in dados]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, TypeError) as e:
            print(f"[sessao] {self.caminho.name} ilegivel ({type(e).__name__}); teto conta do zero.")
            return []

    def registrar(self, agora: datetime) -> None:
        recentes = [p for p in self._pedidos() if agora - p < timedelta(hours=48)] + [agora]
        batimento_mod.gravar_atomico(self.caminho, [batimento_mod._iso(p) for p in recentes])

    def proximo(self, agora: datetime) -> datetime | None:
        """None = pode pedir agora; senao o instante (UTC) do proximo pedido permitido."""
        local = agora.astimezone(BRASILIA)
        hora = local.replace(minute=0, second=0, microsecond=0)
        dia = hora.replace(hour=0)
        pedidos = [p.astimezone(BRASILIA) for p in self._pedidos()]
        if sum(1 for p in pedidos if dia <= p < dia + timedelta(days=1)) >= self.por_dia:
            return (dia + timedelta(days=1)).astimezone(UTC)
        if sum(1 for p in pedidos if hora <= p < hora + timedelta(hours=1)) >= self.por_hora:
            return (hora + timedelta(hours=1)).astimezone(UTC)
        return None


# ------------------------------------------------------------------------------------------- pagina


class TelaWhatsApp:
    """A pagina do WhatsApp Web vista pelo vinculo. So Playwright `page`; os testes usam as fixtures reais."""

    def __init__(self, page, dormir=time.sleep, relogio=time.monotonic):
        self.page = page
        self.dormir = dormir
        self.relogio = relogio

    def _tem(self, seletor: str) -> bool:
        try:
            return self.page.locator(seletor).count() > 0
        except Exception:  # noqa: BLE001
            return False

    def _texto(self, raiz, textos):
        for t in textos:
            loc = raiz.get_by_text(t, exact=True)
            if loc.count() > 0:
                return loc.first
        return None

    def estado(self) -> str | None:
        if self._tem(SEL_LOGADO):
            return LOGADO
        if self._tem(SEL_CODIGO):
            return CODIGO
        if self._tem(SEL_CAMPO):
            return NUMERO
        if self._tem(SEL_QR) or self._tem(SEL_LINK_NUMERO):
            return QR
        return None

    def esperar(self, timeout_s: float = ESPERA_TELA_S, aceitar=None) -> str:
        """Espera a primeira tela conhecida (ou uma de `aceitar`). Nada em `timeout_s` -> TimeoutError."""
        fim = self.relogio() + timeout_s
        while True:
            est = self.estado()
            if est is not None and (aceitar is None or est in aceitar):
                return est
            if self.relogio() >= fim:
                raise TimeoutError(f"WhatsApp Web sem tela conhecida em {timeout_s:g} s")
            self.dormir(1)

    def recarregar(self) -> None:
        self.page.goto(WHATSAPP_URL, wait_until="domcontentloaded")

    def abrir_numero(self) -> None:
        """Leva a pagina ate o campo do numero. O link so responde depois do QR desenhado (medido em 27/11)."""
        est = self.estado()
        if est == NUMERO:
            return
        if est in (CODIGO, None):
            self.recarregar()
        self.esperar(ESPERA_TELA_S, aceitar=(QR, NUMERO, LOGADO))
        if self.estado() != QR:
            return
        self.esperar(ESPERA_ACAO_S, aceitar=(QR,))
        link = self.page.locator(SEL_LINK_NUMERO).first if self._tem(SEL_LINK_NUMERO) else \
            self._texto(self.page, TEXTOS_LINK_NUMERO)
        if link is None:
            raise RuntimeError("tela do QR sem o link de entrar com numero")
        link.click()
        self.esperar(ESPERA_ACAO_S, aceitar=(NUMERO,))

    def informar_numero(self, digitos: str) -> str:
        """Limpa o campo (vem com '+55 '), digita + e os digitos com DDI e devolve o `value` final."""
        campo = self.page.locator(SEL_CAMPO).first
        campo.click()
        campo.fill("")
        campo.press_sequentially("+" + digitos, delay=50)
        return campo.input_value()

    def avancar(self) -> None:
        botao = self._texto(self.page.locator(SEL_TELA_NUMERO).first, TEXTOS_AVANCAR)
        if botao is None:
            raise RuntimeError("tela do numero sem o botao de avancar")
        botao.click()

    def ler_codigo(self, timeout_s: float = ESPERA_ACAO_S) -> str | None:
        self.esperar(timeout_s, aceitar=(CODIGO,))
        return self.page.locator(SEL_CODIGO).first.get_attribute("data-link-code")


# ------------------------------------------------------------------------------------------- vinculo


class Vinculo:
    """Espera viva ate a sessao abrir: pede codigos dentro do teto, ou so espera o QR pelo VNC sem numero."""

    def __init__(self, tela, numero: str, validade_min: float, teto: Teto, avisar, bater,
                 relogio=agora_utc, dormir=time.sleep, intervalo_s: float = INTERVALO_S):
        self.tela, self.numero, self.teto = tela, so_digitos(numero), teto
        self.validade = timedelta(minutes=validade_min)
        self.avisar, self.bater, self.relogio, self.dormir = avisar, bater, relogio, dormir
        self.intervalo_s = intervalo_s
        self.vnc = not self.numero
        self.pedido_em = None          # instante do codigo valido em tela
        self.espera_ate = None         # depois de falha da pagina, espera antes de tentar de novo
        self.teto_avisado = None
        self.pediu = False

    def aguardar(self) -> None:
        if self.vnc:
            print("[sessao] sem pareamento.numero no config: esperando o QR pela tela VNC :2.")
            self.avisar(MSG_SEM_NUMERO)
        while True:
            agora = self.relogio()
            estado = self.tela.estado()
            if estado == LOGADO:
                if self.pediu:
                    print("[sessao] vinculado pelo codigo")
                    self.avisar(MSG_VINCULADO)
                else:
                    print("[sessao] sessao aberta pela tela (QR)")
                return
            self.bater()
            if not self.vnc and self._precisa_pedir(agora, estado):
                proximo = self.teto.proximo(agora)
                if proximo is None:
                    self._pedir(agora)
                elif proximo != self.teto_avisado:
                    self.teto_avisado = proximo
                    print(f"[sessao] limite de codigos atingido; proximo pedido as {hhmm_brasilia(proximo)} (Brasilia).")
                    self.avisar(msg_teto(proximo))
            self.dormir(self.intervalo_s)

    def _precisa_pedir(self, agora: datetime, estado) -> bool:
        if self.espera_ate is not None and agora < self.espera_ate:
            return False
        if self.pedido_em is None or estado in (QR, NUMERO):
            return True
        return agora - self.pedido_em >= self.validade

    def _pedir(self, agora: datetime) -> None:
        self.pedido_em = None
        mascara = mascarar(self.numero)
        try:
            self.tela.abrir_numero()
            valor = self.tela.informar_numero(self.numero)
            if so_digitos(valor) != self.numero:
                print(f"[sessao] o campo nao ficou com o numero do config ({mascara}); nao avancei.")
                self.vnc = True
                self.avisar(msg_numero_recusado(self.numero))
                return
            self.teto.registrar(agora)
            self.pediu = True
            self.tela.avancar()
            codigo = codigo_valido(self.tela.ler_codigo())
        except Exception as e:  # noqa: BLE001
            print(f"[sessao] falha ao pedir o codigo para {mascara} ({type(e).__name__}); tento de novo em 60 s.")
            self.espera_ate = agora + NOVA_TENTATIVA
            return
        if codigo is None:
            print("[sessao] ERRO: codigo da pagina fora de 8 caracteres [A-Z0-9]; novo pedido.")
            return
        self.pedido_em = agora
        self.teto_avisado = None
        print(f"[sessao] codigo pedido para {mascara} as {hhmm_brasilia(agora)} (Brasilia); enviado ao Telegram.")
        self.avisar(msg_codigo(codigo, agora))
