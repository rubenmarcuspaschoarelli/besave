"""Separação de cupons (CONTRATO §4.3): trim, maiúsculas, `^[A-Z0-9_-]{1,30}$`, sem repetidos, até 5."""

import logging
import re

log = logging.getLogger('captura_web')

_VALIDO = re.compile(r'^[A-Z0-9_-]{1,30}$')
MAX_CUPONS = 5


def separar(valores, ref=''):
    """Lista (ou string) de cupons da origem -> códigos válidos, na ordem; cada item é dividido por `|`."""
    if isinstance(valores, str):
        valores = [valores]
    codigos = []
    for valor in valores or []:
        if not isinstance(valor, str):
            continue
        for parte in valor.split('|'):
            c = parte.strip().upper()
            if not c:
                continue
            if not _VALIDO.match(c):
                log.warning('cupom invalido descartado (%s): %r', ref, c)
                continue
            if c not in codigos:
                codigos.append(c)
    if len(codigos) > MAX_CUPONS:
        log.warning('mais de %d cupons (%s): descartados %s', MAX_CUPONS, ref, codigos[MAX_CUPONS:])
        codigos = codigos[:MAX_CUPONS]
    return codigos


def ds_cupom(codigos):
    return '|'.join(codigos) if codigos else None
