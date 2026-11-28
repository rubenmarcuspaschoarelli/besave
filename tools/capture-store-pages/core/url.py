"""Limpeza da URL da fila de captura (BSV-68).

`limpar_url` tem o mesmo corpo de `wa/parser.py` (robo do WhatsApp); os dois pacotes nao se importam.
"""
import unicodedata


def limpar_url(texto):
    """Tira todo caractere Unicode de formatacao (categoria Cf), em qualquer posicao, e as pontas (BSV-68)."""
    if not texto:
        return ""
    return "".join(c for c in texto if unicodedata.category(c) != "Cf").strip()


def invisiveis(texto):
    """Caracteres Cf de `texto`, na ordem em que aparecem (para o log de quem limpou)."""
    return [c for c in (texto or "") if unicodedata.category(c) == "Cf"]
