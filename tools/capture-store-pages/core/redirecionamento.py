"""Redirect de encurtador pelo IP residencial (BSV-58).

Alguns encurtadores (hoje `promos.link`) bloqueiam o IP de datacenter da inst1 no Cloudflare. Para os
dominios de `redirecionamento.dominios` (config.json) so o REDIRECT sai pelo proxy SOCKS do tunel do PC
do dono: `curl` sem seguir redirect, um salto por vez, ate o primeiro destino fora da lista. A pagina da
loja continua aberta pelo navegador da inst1, direto.

O valor de `proxy` e o stderr do curl nunca vao para log. So stdlib + `curl` do sistema.
"""

import os
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

PROXY_INDISPONIVEL = 'proxy_indisponivel'
BLOQUEADO = 'bloqueado'
SEM_REDIRECT = 'sem_redirect'

CODIGOS_BLOQUEIO = {403, 429, 503}
TIMEOUT_PADRAO = 20
MAX_SALTOS_PADRAO = 5


def host(url):
    """Host minusculo, sem porta; '' se nao houver."""
    try:
        return (urlparse(url or '').hostname or '').lower()
    except ValueError:
        return ''


def casa(nome_host, dominio):
    """Sufixo de rotulo: `promos.link` casa `promos.link` e `amzn.promos.link`, nao `xpromos.link`."""
    return bool(nome_host) and (nome_host == dominio or nome_host.endswith('.' + dominio))


def _inteiro(valor, padrao):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return padrao
    return n if n > 0 else padrao


@dataclass(frozen=True)
class Config:
    proxy: str
    dominios: tuple
    timeout: int
    max_saltos: int

    def dominio(self, url):
        """Dominio da lista que casa com a URL, ou None."""
        h = host(url)
        return next((d for d in self.dominios if casa(h, d)), None)


def ler_config(cfg):
    """Bloco `redirecionamento` do config.json; None (desligado) se faltar ou `dominios` vazio."""
    bloco = (cfg or {}).get('redirecionamento')
    if not isinstance(bloco, dict):
        return None
    dominios = bloco.get('dominios')
    dominios = tuple(str(d).strip().lower().strip('.') for d in dominios
                     if str(d).strip()) if isinstance(dominios, list) else ()
    if not dominios:
        return None
    return Config(proxy=str(bloco.get('proxy') or '').strip(), dominios=dominios,
                  timeout=_inteiro(bloco.get('timeout_segundos'), TIMEOUT_PADRAO),
                  max_saltos=_inteiro(bloco.get('max_saltos'), MAX_SALTOS_PADRAO))


def descrever(config):
    """Linha de log da configuracao, sem o proxy."""
    if config is None:
        return '[redirecionamento] desligado (sem redirecionamento.dominios).'
    proxy = 'configurado' if config.proxy else 'AUSENTE (linhas desses dominios ficam retidas)'
    return (f'[redirecionamento] dominios pelo proxy residencial: {", ".join(config.dominios)} '
            f'(proxy {proxy}, max {config.max_saltos} saltos, {config.timeout} s).')


def comando(url, config):
    return ['curl', '-sS', '-o', os.devnull, '-w', '%{http_code} %{redirect_url}',
            '--proxy', config.proxy, '--max-time', str(config.timeout), '--url', url]


def resolver(url, config, executar=None):
    """(url_destino, None) ou (None, motivo): proxy_indisponivel, bloqueado ou sem_redirect."""
    if not config.proxy:
        return None, PROXY_INDISPONIVEL
    executar = executar or subprocess.run
    atual = url
    for _ in range(config.max_saltos):
        try:
            r = executar(comando(atual, config), capture_output=True, text=True,
                         timeout=config.timeout + 5)
        except (OSError, subprocess.SubprocessError):
            return None, PROXY_INDISPONIVEL
        if r.returncode != 0:
            return None, PROXY_INDISPONIVEL
        codigo, _, destino = (r.stdout or '').strip().partition(' ')
        destino = destino.strip()
        try:
            codigo = int(codigo)
        except ValueError:
            return None, SEM_REDIRECT
        if codigo in CODIGOS_BLOQUEIO:
            return None, BLOQUEADO
        if not (300 <= codigo < 400 and destino.startswith(('http://', 'https://'))):
            return None, SEM_REDIRECT
        if config.dominio(destino) is None:
            return destino, None
        atual = destino
    return None, SEM_REDIRECT

