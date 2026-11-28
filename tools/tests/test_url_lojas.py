"""BSV-68 URL-01/URL-02: limpar_url do robo das lojas (core/url.py) e paridade com o do WhatsApp.

TABELA_LIMPAR_URL e copia de capture-chat-groups/tests/test_parser_url.py (teste abaixo confere).
"""
import ast
import inspect
from pathlib import Path

from core import url as url_lojas
from wa import parser as parser_wa

TABELA_LIMPAR_URL = [
    ("https://meli.la/AbC123\u2060", "https://meli.la/AbC123"),
    ("\u200bhttps://s.shopee.com.br/XyZ\ufeff", "https://s.shopee.com.br/XyZ"),
    ("https://amzn.to/a\u200db\u2060", "https://amzn.to/ab"),
    (" https://x.com.br/p\u00ad ", "https://x.com.br/p"),
    ("https://www.magazineluiza.com.br/caf%C3%A9/p/123/", "https://www.magazineluiza.com.br/caf%C3%A9/p/123/"),
    ("https://exemplo.com.br/café?q=✨", "https://exemplo.com.br/café?q=✨"),
    ("\u2060", ""),
    ("", ""),
    (None, ""),
]


def test_tabela_inteira():
    obtido = [(entrada, url_lojas.limpar_url(entrada)) for entrada, _ in TABELA_LIMPAR_URL]
    assert obtido == TABELA_LIMPAR_URL


def test_mesma_tabela_nos_dois_robos():
    arquivo = Path(__file__).resolve().parent.parent / "capture-chat-groups" / "tests" / "test_parser_url.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    no = next(n for n in arvore.body if isinstance(n, ast.Assign) and n.targets[0].id == "TABELA_LIMPAR_URL")
    assert ast.literal_eval(no.value) == TABELA_LIMPAR_URL


def test_mesmo_corpo_nos_dois_robos():
    assert inspect.getsource(url_lojas.limpar_url) == inspect.getsource(parser_wa.limpar_url)
