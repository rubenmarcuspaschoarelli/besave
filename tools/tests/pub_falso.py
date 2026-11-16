"""Mundo falso do publicador (BSV-63): Oracle, relogio, pagina do WhatsApp Web, foto e Telegram."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pub import config, regras
from pub.fila import ErroBanco
from pub.publicador import BrowserMorto, Publicador

T0 = datetime(2026, 11, 16, 13, 0, tzinfo=UTC)          # 10:00 em Brasilia


class FilaFalsa:
    def __init__(self):
        self.linhas = {}            # id_envio -> dict
        self.ativas = {}            # id_oferta -> bool
        self.params = regras.Parametros(40, 8, 22)
        self.nome = "BeSave - Canal de Teste"
        self.fora = False
        self.proximo = 1
        self.leituras_de_estado = []

    def add(self, dt_fila, ativa=True, st="P", legenda=None, slug="elas"):
        i = self.proximo
        self.proximo += 1
        oferta = 5000 + i
        self.linhas[i] = {"id": i, "oferta": oferta, "st": st, "motivo": None, "dt_envio": None,
                          "dt_fila": dt_fila, "legenda": legenda or f"*Oferta {i}*\n\nlinha\n\n🔥 _frase_", "slug": slug}
        self.ativas[oferta] = ativa
        return i

    def _checar(self):
        if self.fora:
            raise ErroBanco("DPY-4011")

    def pendentes(self, canal):
        self._checar()
        self.leituras_de_estado.append(sorted({x["st"] for x in self.linhas.values()}))
        return [regras.Linha(x["id"], x["oferta"], x["legenda"], x["slug"], x["dt_fila"], self.ativas[x["oferta"]])
                for x in self.linhas.values() if x["st"] == "P"]

    def parametros(self, canal):
        self._checar()
        return self.params

    def nome_canal(self, canal):
        self._checar()
        return self.nome

    def enviados_desde(self, canal, inicio):
        self._checar()
        return sum(1 for x in self.linhas.values() if x["st"] in ("E", "D") and x["dt_envio"] is not None and x["dt_envio"] >= inicio)

    def marcar(self, id_envio, de, para, motivo, dt):
        self._checar()
        x = self.linhas[id_envio]
        if x["st"] != de:
            return False
        x.update(st=para, motivo=motivo, dt_envio=dt)
        return True

    def st(self, i):
        return self.linhas[i]["st"], self.linhas[i]["motivo"]


class PaginaFalsa:
    """Registra cada passo. `falhar` = nome do passo que levanta; `confirma` = resultado da confirmacao."""

    def __init__(self):
        self.estado_sessao = "ok"
        self.falhar = None
        self.confirma = True
        self.chamadas = []
        self.envios = []            # (canal, foto, legenda) a cada clique em enviar
        self.canal = None
        self.foto = None
        self.legenda = None
        self.recargas = 0
        self.morto_em = None

    def _passo(self, nome):
        self.chamadas.append(nome)
        if self.morto_em == nome:
            raise BrowserMorto("Target page, context or browser has been closed")
        if self.falhar == nome:
            raise RuntimeError(f"falha falsa em {nome}")

    def sessao(self):
        self._passo("sessao")
        return self.estado_sessao

    def abrir_canal(self, nome):
        self._passo("abrir_canal")
        self.canal = nome

    def anexar(self, foto):
        self._passo("anexar")
        assert Path(foto).exists(), "anexo sem arquivo"
        self.foto = foto

    def escrever_legenda(self, texto, modo):
        self._passo("escrever_legenda")
        self.legenda = texto

    def enviar(self):
        self._passo("enviar")
        self.envios.append((self.canal, self.foto, self.legenda))

    def confirmar(self, legenda, timeout_s):
        self._passo("confirmar")
        return self.confirma

    def limpar(self):
        self._passo("limpar")
        self.canal = self.foto = self.legenda = None

    def recarregar(self):
        self._passo("recarregar")
        self.recargas += 1


class Mundo:
    def __init__(self, tmp_path, cfg=None):
        self.t = T0
        self.fila = FilaFalsa()
        self.pagina = PaginaFalsa()
        self.avisos = []
        self.logs = []
        self.batidas = []
        self.cfg = dict(cfg or {})
        self.sem_foto = set()       # ids de oferta sem foto nem placeholder
        self.fotos_pedidas = []     # (id_oferta, slug da area) pedidos pelo laco
        self.tmp = Path(tmp_path)
        self.pub = Publicador(
            fila=self.fila, pagina=self.pagina, avisar=self.avisos.append, relogio=lambda: self.t,
            carregar_config=lambda: config.de_dict(self.cfg), preparar_foto=self._foto,
            batimento=self, aleatorio=lambda: 0.5, pasta_tmp=self.tmp, log=self.logs.append)

    def _foto(self, id_oferta, slug, destino):
        self.fotos_pedidas.append((id_oferta, slug))
        if id_oferta in self.sem_foto:
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"\xff\xd8jpeg")
        return destino

    def bater(self, agora, fase, dorme_s=0):
        self.batidas.append((agora, fase, dorme_s))
        return True

    def local(self, **k):
        """Hora local (ingenua) de agora + delta, como o Oracle guarda."""
        return regras.local(self.t + timedelta(**k))

    def volta(self):
        return self.pub.volta()

    def andar(self, **k):
        self.t += timedelta(**k)

    def envios_da_oferta(self, id_envio):
        legenda = self.fila.linhas[id_envio]["legenda"]
        return sum(1 for _, _, x in self.pagina.envios if x == legenda)
