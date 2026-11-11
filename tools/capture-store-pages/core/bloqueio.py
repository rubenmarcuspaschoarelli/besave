"""Pausa por loja depois de bloqueios seguidos (BSV-55).

Sessao caida (captcha, login, painel de afiliado deslogado) faria o robo girar a
fila daquela loja para sempre, 60-100 s por linha. Com SEGUIDOS bloqueios seguidos
da mesma loja, ela pausa por `bloqueio.pausa_minutos` (config.json, padrao 60): as
linhas dela ficam em '0' e sao puladas; as outras lojas seguem. Vencida a pausa, a
proxima linha da loja e a sonda: sucesso -> volta; bloqueio -> nova pausa.

Avisos (Telegram via core/alerta.py): um ao entrar em pausa, lembrete a cada
LEMBRETE enquanto durar, um de "voltou". Relogio e envio entram por parametro.
"""

from datetime import datetime, timedelta

from core.alerta import Avisador

SEGUIDOS = 3
LEMBRETE = timedelta(hours=6)
PAUSA_MINUTOS_PADRAO = 60

PAGINA = 'pagina'        # captcha/login/verificacao na pagina da loja
AFILIADO = 'afiliado'    # sessao do programa de afiliados
REDIRECIONAMENTO = 'redirecionamento'  # redirect pelo proxy residencial (BSV-58); chave = dominio
CLOUDFLARE = 'cloudflare'  # bloqueio do Cloudflare em dominio fora da lista (BSV-58); chave = host
SHOPEE_API = 'shopee_api'  # API de afiliados da Shopee fora, credencial ou limite (BSV-59); chave = shopee


def ler_pausa_minutos(cfg):
    bloco = (cfg or {}).get('bloqueio')
    bloco = bloco if isinstance(bloco, dict) else {}
    try:
        minutos = float(bloco.get('pausa_minutos', PAUSA_MINUTOS_PADRAO))
    except (TypeError, ValueError):
        return PAUSA_MINUTOS_PADRAO
    return minutos if minutos > 0 else PAUSA_MINUTOS_PADRAO


def _dica_api(detalhe):
    # Request Expired tambem vem com o codigo de credencial: e relogio da maquina (NTP).
    if 'api_credencial' in (detalhe or ''):
        return '; conferir app_id/app_secret em conf/config.json (Request Expired = relogio da maquina)'
    return ''


class _Estado:
    def __init__(self):
        self.seguidos = 0
        self.motivo = ''
        self.ate = None          # fim da pausa; None = loja livre
        self.desde = None        # inicio da ocorrencia
        self.alertado_em = None
        self.retidas = set()     # ids seguros em '0' nesta ocorrencia
        self.detalhe = ''        # motivo da API (SHOPEE_API), sem credencial


class PausaLojas:
    def __init__(self, cfg=None, avisar=None, agora=None, nome=None):
        self.minutos = ler_pausa_minutos(cfg)
        self.pausa = timedelta(minutes=self.minutos)
        self.avisar = avisar or Avisador(cfg).avisar
        self.agora = agora or datetime.now
        self.nome = nome or (lambda loja: loja)
        self.lojas = {}

    def _e(self, loja):
        return self.lojas.setdefault(loja, _Estado())

    def em_pausa(self, loja):
        """True enquanto a pausa da loja nao venceu (vencida, a proxima linha e a sonda)."""
        e = self.lojas.get(loja)
        return bool(e and e.ate is not None and self.agora() < e.ate)

    def reter(self, loja, id_oferta):
        if id_oferta is not None:
            self._e(loja).retidas.add(id_oferta)

    def _rotulo(self, loja):
        return self.nome(loja) or loja

    def registrar_bloqueio(self, loja, motivo, id_oferta=None, restantes=(), detalhe=''):
        e = self._e(loja)
        self.reter(loja, id_oferta)
        e.seguidos += 1
        e.motivo = motivo
        e.detalhe = detalhe
        agora = self.agora()
        if e.ate is not None:
            # Sonda falhou: nova pausa, mesma ocorrencia (sem aviso novo).
            e.ate = agora + self.pausa
            print(f'[bloqueio] {self._rotulo(loja)}: ainda bloqueada ({motivo}); '
                  f'nova pausa de {self.minutos:g} min.')
            return
        if e.seguidos < SEGUIDOS:
            return
        e.ate = agora + self.pausa
        e.desde = e.alertado_em = agora
        e.retidas.update(i for i in restantes if i is not None)
        if motivo == REDIRECIONAMENTO:
            self.avisar(f'Robo das lojas: {self._rotulo(loja)} em pausa: túnel residencial fora? '
                        f'{len(e.retidas)} linha(s) retida(s) (ST_CAPTURA=0; {SEGUIDOS} falhas seguidas '
                        f'do redirect pelo proxy). Conferir o tunel_residencial.ps1 no PC; o robo tenta '
                        f'de novo sozinho em {self.minutos:g} min.')
            return
        if motivo == SHOPEE_API:
            self.avisar(f'Robo das lojas: {self._rotulo(loja)} em pausa: API de afiliados com falha '
                        f'({detalhe}){_dica_api(detalhe)}. {len(e.retidas)} linha(s) retida(s) '
                        f'(ST_CAPTURA=0; {SEGUIDOS} falhas seguidas). O robo tenta de novo sozinho em '
                        f'{self.minutos:g} min.')
            return
        if motivo == CLOUDFLARE:
            self.avisar(f'Robo das lojas: {self._rotulo(loja)} bloqueado pelo Cloudflare; incluir em '
                        f'redirecionamento.dominios? {len(e.retidas)} linha(s) retida(s) (ST_CAPTURA=0; '
                        f'{SEGUIDOS} seguidas). O robo tenta de novo sozinho em {self.minutos:g} min.')
            return
        self.avisar(f'Robo das lojas: {self._rotulo(loja)} em pausa por {self.minutos:g} min '
                    f'({SEGUIDOS} bloqueios seguidos, motivo {motivo}). '
                    f'{len(e.retidas)} linha(s) retida(s) na fila (ST_CAPTURA=0). '
                    'Entrar no VNC :1 e logar; o robo tenta de novo sozinho ao fim da pausa.')

    def registrar_sucesso(self, loja):
        e = self.lojas.get(loja)
        if e is None:
            return
        if e.ate is not None:
            minutos = (self.agora() - e.desde).total_seconds() / 60
            self.avisar(f'Robo das lojas: {self._rotulo(loja)} voltou (ficou em pausa ~{minutos:.0f} min, '
                        f'{len(e.retidas)} linha(s) retida(s) voltam a ser processadas).')
        self.lojas[loja] = _Estado()

    def lembrar(self):
        agora = self.agora()
        for loja, e in self.lojas.items():
            if e.ate is not None and agora - e.alertado_em >= LEMBRETE:
                e.alertado_em = agora
                horas = (agora - e.desde).total_seconds() / 3600
                if e.motivo == REDIRECIONAMENTO:
                    self.avisar(f'Robo das lojas: {self._rotulo(loja)} continua em pausa ha {horas:.0f} h '
                                f'(túnel residencial fora?, {len(e.retidas)} linha(s) retida(s)). '
                                'Conferir o tunel_residencial.ps1 no PC.')
                    continue
                if e.motivo == SHOPEE_API:
                    self.avisar(f'Robo das lojas: {self._rotulo(loja)} continua em pausa ha {horas:.0f} h '
                                f'(API de afiliados: {e.detalhe}{_dica_api(e.detalhe)}, '
                                f'{len(e.retidas)} linha(s) retida(s)).')
                    continue
                if e.motivo == CLOUDFLARE:
                    self.avisar(f'Robo das lojas: {self._rotulo(loja)} continua bloqueado pelo Cloudflare ha '
                                f'{horas:.0f} h ({len(e.retidas)} linha(s) retida(s)); incluir em '
                                'redirecionamento.dominios?')
                    continue
                self.avisar(f'Robo das lojas: {self._rotulo(loja)} continua em pausa ha {horas:.0f} h '
                            f'(motivo {e.motivo}, {len(e.retidas)} linha(s) retida(s)). Entrar no VNC :1 e logar.')
