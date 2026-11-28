"""Requisições aos sites (BSV-66, Saída 1): só urllib, sem cookies, sem compressão, com pausa.

`abrir(req, timeout, seguir) -> (status, headers, corpo)` é a costura dos testes; o padrão usa urllib e,
com `seguir=False`, não segue redirect (devolve o 3xx com o `Location`).
"""

import logging
import random
import time
import urllib.error
import urllib.request

log = logging.getLogger('captura_web')

TIMEOUT_S = 20
REDIRECTS = (301, 302, 303, 307, 308)


class ErroHttp(Exception):
    pass


class Bloqueado(ErroHttp):
    """403 ou 429: o site para na rodada."""

    def __init__(self, codigo):
        super().__init__(f'HTTP {codigo}')
        self.codigo = codigo


class SemResposta(ErroHttp):
    """Timeout/5xx depois de uma repetição, ou outro código HTTP."""


class _SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def abrir_urllib(req, timeout, seguir):
    opener = urllib.request.build_opener() if seguir else urllib.request.build_opener(_SemRedirect())
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read()
        except Exception:  # noqa: BLE001
            corpo = b''
        return e.code, e.headers, corpo


class Http:
    def __init__(self, user_agent, pausa=(3, 6), abrir=None, dormir=time.sleep, sortear=random.uniform,
                 timeout=TIMEOUT_S):
        self.user_agent = user_agent
        self.pausa = pausa
        self.abrir = abrir or abrir_urllib
        self.dormir = dormir
        self.sortear = sortear
        self.timeout = timeout
        self.requisicoes = 0

    def _uma(self, url, seguir):
        if self.requisicoes:
            self.dormir(self.sortear(*self.pausa))
        self.requisicoes += 1
        req = urllib.request.Request(url, headers={'User-Agent': self.user_agent, 'Accept-Language': 'pt-BR'})
        return self.abrir(req, self.timeout, seguir)

    def _pedir(self, url, seguir):
        motivo = ''
        for _ in range(2):
            try:
                status, headers, corpo = self._uma(url, seguir)
            except (TimeoutError, OSError) as e:  # URLError e socket.timeout são OSError
                motivo = type(e).__name__
                continue
            if status in (403, 429):
                raise Bloqueado(status)
            if status >= 500:
                motivo = f'HTTP {status}'
                continue
            return status, headers, corpo
        raise SemResposta(motivo)

    def get(self, url):
        """Corpo (texto) de um 200; outro código -> SemResposta; 403/429 -> Bloqueado."""
        status, headers, corpo = self._pedir(url, True)
        if status != 200:
            raise SemResposta(f'HTTP {status}')
        charset = 'utf-8'
        try:
            charset = headers.get_content_charset() or 'utf-8'
        except AttributeError:
            pass
        try:
            return corpo.decode(charset, errors='replace')
        except LookupError:
            return corpo.decode('utf-8', errors='replace')

    def location(self, url):
        """`Location` de um 3xx, sem seguir; outro código -> None."""
        status, headers, _ = self._pedir(url, False)
        if status not in REDIRECTS or headers is None:
            return None
        return headers.get('Location')
