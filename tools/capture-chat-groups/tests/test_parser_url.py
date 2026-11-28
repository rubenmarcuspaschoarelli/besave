"""
BSV-68: caractere invisivel (Unicode Cf) no href do link do WhatsApp.

A tabela TABELA_LIMPAR_URL e copiada igual em tools/tests/test_url_lojas.py
(o robo das lojas tem a mesma funcao em core/url.py).

Rodar:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wa import parser

# Saida 5 da spec. Caracteres invisiveis escritos como escape para ficarem visiveis no fonte.
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


class LimparUrl(unittest.TestCase):
    def test_tabela_inteira(self):
        obtido = [(entrada, parser.limpar_url(entrada)) for entrada, _ in TABELA_LIMPAR_URL]
        self.assertEqual(obtido, TABELA_LIMPAR_URL)


class ParseCamposUrl(unittest.TestCase):
    def test_convite_com_caractere_e_pulado_e_url_sai_limpa(self):
        campos = parser.parse_campos({
            "text": "Oferta",
            "links": ["https://chat.whatsapp.com/Abc\u2060", "https://meli.la/AbC123\u2060"],
        })
        self.assertEqual(campos["url"], "https://meli.la/AbC123")

    def test_link_que_fica_vazio_e_descartado(self):
        campos = parser.parse_campos({"text": "Oferta", "links": ["\u2060"]})
        self.assertEqual(campos["url"], "")


    def test_link_vazio_descartado_nao_tampa_o_seguinte(self):
        campos = parser.parse_campos({"text": "Oferta", "links": ["\u2060", "https://meli.la/AbC123"]})
        self.assertEqual(campos["url"], "https://meli.la/AbC123")

    def test_convite_com_caractere_no_inicio_e_pulado(self):
        campos = parser.parse_campos({
            "text": "Oferta",
            "links": ["\u2060https://chat.whatsapp.com/Abc", "https://meli.la/AbC123"],
        })
        self.assertEqual(campos["url"], "https://meli.la/AbC123")

    def test_so_a_url_muda(self):
        texto = "Fone XYZ\nDe R$ 299,90\npor R$ 199,90\nCupom: BESAVE10\nhttps://meli.la/AbC123"
        sujo = parser.parse_campos({"text": texto, "links": ["https://meli.la/AbC123\u2060"]})
        limpo = parser.parse_campos({"text": texto, "links": ["https://meli.la/AbC123"]})
        self.assertEqual(sujo, limpo)

if __name__ == "__main__":
    unittest.main()
