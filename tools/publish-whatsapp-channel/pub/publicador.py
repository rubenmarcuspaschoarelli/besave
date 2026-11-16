"""Laco do publicador (BSV-63): uma volta a cada `intervalo_minutos` (+-30%), no maximo 1 post por volta.

Volta: config (relido) -> pausa -> sessao do WhatsApp Web -> descarte das `P` -> ritmo do canal ->
a `P` mais recente -> foto -> canal, anexo, legenda -> `D 'enviando'` -> clique -> confirmacao -> `E`.

Regra de ouro: postar duas vezes e pior que deixar de postar uma. A linha so vira `D` imediatamente antes
do clique; depois dele, sem confirmacao, fica `D` para sempre (o dono decide). O laco so le linhas `P`.
"""

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import config as config_mod
from . import regras
from .fila import ErroBanco

FALHAS_PARA_PAUSA = 3
PAUSA = timedelta(minutes=60)
LEMBRETE = timedelta(hours=6)
MARCA_ESPERANDO = "Aguardando o WhatsApp Web carregar"      # mesmas marcas da captura: o `pede_qr` do vigia
MARCA_AUTENTICADO = "Sessao autenticada"

OK, QR = "ok", "qr"
POSTADO, FALHA_ANTES, DUVIDOSO = "E", "P", "D"


class BrowserMorto(RuntimeError):
    """O navegador ou a pagina fecharam: o processo sai com codigo != 0 e o systemd reinicia."""


class FalhaPasso(RuntimeError):
    """Passo da pagina que nao deu, previsto (cabecalho divergente, sem anexo, legenda diferente): falha antes do
    clique, sem recarregar a pagina. Excecao fora disso e inesperada e recarrega uma vez."""


def chave_oferta(id_oferta: int) -> str:
    """O que o balao confirmado tem de mostrar: o link curto da oferta (o texto renderizado perde os `*`)."""
    return f"besave.io/{int(id_oferta)}"


@dataclass
class Ocorrencia:
    desde: datetime
    aviso_em: datetime


class Publicador:
    def __init__(self, *, fila, pagina, avisar: Callable[[str], None], relogio: Callable[[], datetime],
                 carregar_config: Callable[[], config_mod.Config], preparar_foto, batimento,
                 aleatorio: Callable[[], float], pasta_tmp: Path, log: Callable[[str], None] = print):
        self.fila = fila
        self.pagina = pagina
        self.avisar = avisar
        self.relogio = relogio
        self.carregar_config = carregar_config
        self.preparar_foto = preparar_foto
        self.batimento = batimento
        self.aleatorio = aleatorio
        self.pasta_tmp = Path(pasta_tmp)
        self.log = log
        self.cfg: config_mod.Config | None = None
        self.falhas_seguidas = 0
        self.pausa_ate: datetime | None = None
        self.pausa: Ocorrencia | None = None
        self.qr: Ocorrencia | None = None

    # ------------------------------------------------------------------------------------------ volta

    def _config(self) -> config_mod.Config:
        try:
            cfg = self.carregar_config()
            for aviso in cfg.avisos:
                self.log(f"[config] WARN {aviso}")
            self.cfg = cfg
        except config_mod.ErroConfig as e:
            if self.cfg is None:
                raise
            self.log(f"[config] WARN {e}; mantendo o config anterior")
        return self.cfg

    def volta(self) -> float:
        """Uma volta. Devolve quantos segundos dormir ate a proxima."""
        cfg = self._config()
        sono = regras.sono_segundos(cfg.intervalo_minutos, self.aleatorio())
        fase = self._volta(cfg)
        self.batimento.bater(self.relogio(), fase, dorme_s=sono)
        return sono

    def _volta(self, cfg) -> str:
        if not cfg.habilitado:
            self.log("[volta] habilitado=false: nada a fazer")
            return "desligado"
        agora = self.relogio()
        if self.pausa_ate is not None:
            if agora < self.pausa_ate:
                self._lembrete_pausa(agora)
                self.log(f"[volta] em pausa ate {_bsb(self.pausa_ate)}")
                return "pausa"
            self.log("[volta] fim da pausa; tentando de novo")
            self.pausa_ate, self.falhas_seguidas = None, 0

        if self.pagina.sessao() == QR:
            self._sessao_deslogada(agora)
            return "qr"
        if self.qr is not None:
            self.log(MARCA_AUTENTICADO)
            self.avisar("sessao do WhatsApp Web autenticada de novo; publicacao retomada.")
            self.qr = None

        try:
            return self._fila(cfg, agora)
        except ErroBanco as e:
            self.log(f"[volta] banco indisponivel ({e}); nada postado nesta volta")
            return "banco_fora"

    def _fila(self, cfg, agora: datetime) -> str:
        descartes, validas = regras.separar(self.fila.pendentes(cfg.id_canal), agora, cfg.max_horas_fila)
        for linha, motivo in descartes:
            if self.fila.marcar(linha.id_envio, "P", "X", motivo, None):
                self.log(f"[fila] linha {linha.id_envio} (oferta {linha.id_oferta}) -> X {motivo}")

        p = self.fila.parametros(cfg.id_canal)
        if p is None:
            self.log(f"[volta] WARN canal {cfg.id_canal} sem linha em PARAMETROS_ENVIO")
            return "sem_parametros"
        enviados = self.fila.enviados_desde(cfg.id_canal, regras.inicio_do_dia(agora))
        if not regras.devido(p, agora, enviados):
            self.log(f"[volta] fora do ritmo/janela (enviados hoje {enviados}/{p.qt_max_dia})")
            return "espera"
        linha = regras.escolher(validas)
        if linha is None:
            self.log("[volta] fila vazia")
            return "fila_vazia"

        resultado = self._tentar(cfg, linha)
        self._contabilizar(resultado, linha, agora)
        return "volta"

    # ---------------------------------------------------------------------------------------- tentativa

    def _tentar(self, cfg, linha) -> str:
        rotulo = f"linha {linha.id_envio} (oferta {linha.id_oferta})"
        try:
            nome = self.fila.nome_canal(cfg.id_canal)
        except ErroBanco as e:
            self.log(f"[post] {rotulo}: banco indisponivel ({e}); falha antes do clique")
            return FALHA_ANTES
        if not nome:
            self.log(f"[post] WARN canal {cfg.id_canal} sem DS_CHAT_ID; falha antes do clique")
            return FALHA_ANTES
        foto = self.preparar_foto(linha.id_oferta, linha.area_slug, self.pasta_tmp / f"{linha.id_oferta}.jpg")
        if foto is None:
            self.log(f"[post] {rotulo}: sem foto da oferta nem placeholder; nao posta sem foto")
            return FALHA_ANTES
        try:
            return self._postar(cfg, linha, nome, foto, rotulo)
        finally:
            self._limpar()

    def _postar(self, cfg, linha, nome: str, foto: Path, rotulo: str) -> str:
        try:
            self.pagina.abrir_canal(nome)
            self.pagina.anexar(foto)
            self.pagina.escrever_legenda(linha.legenda, cfg.modo_legenda)
        except BrowserMorto:
            raise
        except FalhaPasso as e:
            self.log(f"[post] {rotulo}: falha antes do clique ({str(e)[:200]})")
            return FALHA_ANTES
        except Exception as e:  # noqa: BLE001
            self.log(f"[post] {rotulo}: falha antes do clique ({type(e).__name__}: {str(e)[:200]})")
            self._recarregar()
            return FALHA_ANTES

        try:
            marcou = self.fila.marcar(linha.id_envio, "P", "D", "enviando", regras.local(self.relogio()))
        except ErroBanco as e:
            self.log(f"[post] {rotulo}: nao consegui gravar D ({e}); nao clica")
            return FALHA_ANTES
        if not marcou:
            self.log(f"[post] {rotulo}: a linha saiu de P por fora; nao clica")
            return FALHA_ANTES

        confirmado = False
        try:
            self.pagina.enviar()
            confirmado = self.pagina.confirmar(chave_oferta(linha.id_oferta), cfg.timeout_post_segundos)
        except BrowserMorto:
            self._avisar_duvidoso(linha, "o navegador caiu depois do clique")
            raise
        except Exception as e:  # noqa: BLE001
            self.log(f"[post] {rotulo}: erro depois do clique ({type(e).__name__}: {str(e)[:200]})")
        if not confirmado:
            self._avisar_duvidoso(linha, f"sem confirmacao em {cfg.timeout_post_segundos:g} s")
            return DUVIDOSO

        try:
            if not self.fila.marcar(linha.id_envio, "D", "E", None, regras.local(self.relogio())):
                self.log(f"[post] WARN {rotulo}: postado, mas a linha nao estava mais em D")
        except ErroBanco as e:
            self.avisar(f"linha {linha.id_envio} (oferta {linha.id_oferta}) foi postada, mas nao consegui "
                        f"gravar E ({e}); ficou D. Nada sera reenviado.")
        self.log(f"[post] {rotulo}: postado e confirmado")
        return POSTADO

    def _avisar_duvidoso(self, linha, porque: str) -> None:
        self.log(f"[post] linha {linha.id_envio} (oferta {linha.id_oferta}) ficou D: {porque}")
        self.avisar(f"linha {linha.id_envio} (oferta {linha.id_oferta}) ficou D ({porque}): conferir no canal "
                    "se saiu. Linha D nunca e reenviada.")

    def _recarregar(self) -> None:
        """Excecao na pagina: recarrega uma vez. Se nem isso der, o navegador esta morto."""
        try:
            self.pagina.recarregar()
        except BrowserMorto:
            raise
        except Exception as e:
            raise BrowserMorto(f"recarregar falhou ({type(e).__name__})") from e

    def _limpar(self) -> None:
        try:
            self.pagina.limpar()
        except BrowserMorto:
            raise
        except Exception as e:  # noqa: BLE001
            self.log(f"[post] limpeza falhou ({type(e).__name__}); recarregando")
            self._recarregar()

    # ------------------------------------------------------------------------------------ pausa/avisos

    def _contabilizar(self, resultado: str, linha, agora: datetime) -> None:
        if resultado == POSTADO:
            self.falhas_seguidas = 0
            if self.pausa is not None:
                minutos = int((agora - self.pausa.desde).total_seconds() // 60)
                self.avisar(f"voltou: post confirmado depois de {minutos} min com falhas.")
                self.pausa = None
            return
        self.falhas_seguidas += 1
        if self.falhas_seguidas < FALHAS_PARA_PAUSA:
            return
        self.pausa_ate, self.falhas_seguidas = agora + PAUSA, 0
        texto = (f"{FALHAS_PARA_PAUSA} falhas seguidas (ultima: linha {linha.id_envio}); pausa de "
                 f"{int(PAUSA.total_seconds() // 60)} min, ate {_bsb(self.pausa_ate)} (Brasilia).")
        if self.pausa is None:
            self.pausa = Ocorrencia(desde=agora, aviso_em=agora)
            self.avisar(texto)
        else:
            self._lembrete_pausa(agora, texto)

    def _lembrete_pausa(self, agora: datetime, texto: str | None = None) -> None:
        if self.pausa is not None and agora - self.pausa.aviso_em >= LEMBRETE:
            self.pausa.aviso_em = agora
            self.avisar("Lembrete: publicacao com falhas desde "
                        f"{_bsb(self.pausa.desde)} (Brasilia). " + (texto or "Em pausa."))

    def _sessao_deslogada(self, agora: datetime) -> None:
        self.log(f"{MARCA_ESPERANDO}: sessao deslogada (QR na tela); nada postado")
        if self.qr is None:
            self.qr = Ocorrencia(desde=agora, aviso_em=agora)
            self.avisar("sessao do WhatsApp Web deslogada (QR na tela): ler o QR pelo VNC. Nada sera postado ate la.")
        elif agora - self.qr.aviso_em >= LEMBRETE:
            self.qr.aviso_em = agora
            self.avisar(f"Lembrete: sessao deslogada desde {_bsb(self.qr.desde)} (Brasilia): ler o QR pelo VNC.")

    # --------------------------------------------------------------------------------------------- laco

    def rodar(self, dormir: Callable[[float], None]) -> int:
        """Laco infinito. Navegador morto ou erro inesperado -> codigo 1 (o systemd reinicia)."""
        while True:
            try:
                sono = self.volta()
            except BrowserMorto as e:
                self.log(f"[publicador] navegador morto ({e}); saindo com codigo 1")
                return 1
            except config_mod.ErroConfig as e:
                self.log(f"[publicador] ABORTADO: {e}")
                return 2
            except Exception:  # noqa: BLE001
                self.log("[publicador] erro inesperado; saindo com codigo 1\n" + traceback.format_exc())
                return 1
            dormir(sono)


def _bsb(dt: datetime) -> str:
    return dt.astimezone(regras.BRASILIA).strftime("%d/%m %H:%M") if dt.tzinfo else dt.strftime("%d/%m %H:%M")


def agora_utc() -> datetime:
    return datetime.now(UTC)
