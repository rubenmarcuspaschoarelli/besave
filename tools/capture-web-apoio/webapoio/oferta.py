"""Oferta lida de um site de origem, antes dos filtros."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

PELANDO, PROMOBIT, PECHINCHOU = 'PELANDO', 'PROMOBIT', 'PECHINCHOU'
NOMES = {PELANDO: 'Pelando', PROMOBIT: 'Promobit', PECHINCHOU: 'Pechinchou'}
CENTAVO = Decimal('0.01')


@dataclass
class Oferta:
    site: str
    id_origem: str
    titulo: str
    preco_por: Decimal | None
    preco_de: Decimal | None
    publicada: datetime | None
    # URL da loja como veio da origem (pode ter marca de terceiro): nunca vai para log.
    url: str | None = field(default=None, repr=False)
    loja_origem: str = ''
    cupons: list = field(default_factory=list)
    invalida: str | None = None

    @property
    def chave_local(self):
        return f'{self.site}:{self.id_origem}'


def reais(valor):
    """Número (ou string decimal) em reais -> Decimal com 2 casas; inválido -> None."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        d = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return d.quantize(CENTAVO)


_OFFSET = re.compile(r'([+-])(\d{2}):?(\d{2})$')


def data_iso(texto):
    """ISO 8601 com `Z`, `-03:00` ou `-0300` -> datetime com fuso; sem fuso ou inválido -> None."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    s = texto.strip()
    if s.endswith(('Z', 'z')):
        s = s[:-1] + '+00:00'
    else:
        s = _OFFSET.sub(lambda m: f'{m.group(1)}{m.group(2)}:{m.group(3)}', s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None
