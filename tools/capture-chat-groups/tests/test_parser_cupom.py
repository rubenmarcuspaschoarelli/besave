"""
Classificacao PRODUTO x CUPOM e preco que e REGRA de cupom (wa/parser.py).

As mensagens abaixo sao as capturadas em 19/10/2026 (CSV 19_10_2026_08_48):
o anuncio "CUPONZAOOO MERCADO LIVRE" (ID 37175) entrou como PRODUTO e levou o
teto do cupom (R$ 15) como preco da oferta, no lugar do preco do site.

Rodar:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wa import parser  # noqa: E402


def campos(texto, links=None):
    return parser.parse_campos({"text": texto, "links": links or []})


# ID 37175 — anuncio de cupom; o link resolvia para uma pagina de produto.
MSG_CUPONZAO = """🚨🚨 CORRE!!! CUPONZÃOOO MERCADO LIVRE

Usa logooooo:😱

🎟️ CPAMD19
30% OFF máx R$15 via saldo Mercado Pago

🎟️ SITE150TODO - R$150/999

🎟️ JOGOS1910
10% OFF  máx R$20 em Livros & Jogos

🛒 Clique em "ir para produto" e na barra de busca procure o produto desejado: https://meli.la/2RpaQkM"""

# ID 37170 — os cupons estao so na IMAGEM; a legenda apenas chama.
MSG_PRINT_CUPONS = """CORREE são 3 cupons pra resgatar e usar agora 👇
⚡️CUPONS MERCADO LIVRE
https://meli.la/1e38U4R"""

# ID 37243 — produto de verdade que cita cupom: nao pode virar CUPOM.
MSG_PRODUTO_COM_CUPOM = """Cupom: VALEPROMO ⚠️

Tripé Magnético e Bastão Selfie Basike com Controle Bluetooth
De: R$ 266,00
Por: R$ 103,22
https://meli.la/1UwL67Y"""

# ID 35769 — produto sem "De:", preco solto na linha.
MSG_PRODUTO_PRECO_SOLTO = """EUCERIN COM CUPOM!!!!
EUCERIN Pomada Reparadora Aquaphor Duopack
R$ 35,99 no pix
https://amzn.promos.link/qNf3M2"""

# Produto cujo preco aparece DEPOIS da regra de um cupom.
MSG_PRODUTO_APOS_REGRA = """Perfume Árabe Sabah Al ward Sugar Feminino
cupom de 30% OFF, máx R$ 15, compras acima de R$ 45
R$ 199,90 no pix
https://meli.la/1zHuHHd"""

# ID 37176 — anuncio de cupom no formato antigo ('Cupom: CODE'), ja suportado.
MSG_CUPOM_ROTULADO = """NOVOS CUPONS NO ML
R$ 150 OFF em R$ 999
Cupom: SITE150TODO
30% OFF, Limite de R$ 15
Cupom: CPAMD19
https://mercadolivre.com/sec/1rn8M1w"""


class TestAnuncioDeCupom(unittest.TestCase):
    def test_cuponzao_e_anuncio_de_cupom(self):
        c = campos(MSG_CUPONZAO, ["https://meli.la/2RpaQkM"])
        self.assertEqual(c["tipo_anuncio"], "CUPOM")

    def test_cuponzao_nao_leva_teto_do_cupom_como_preco(self):
        """O bug: R$ 15 (teto do cupom) virava VL_PRECO_POR da oferta."""
        c = campos(MSG_CUPONZAO, ["https://meli.la/2RpaQkM"])
        self.assertEqual(c["preco_por"], "")
        self.assertEqual(c["preco_de"], "")

    def test_cuponzao_extrai_os_tres_codigos(self):
        c = campos(MSG_CUPONZAO, ["https://meli.la/2RpaQkM"])
        self.assertEqual(c["cupom"], "CPAMD19 | SITE150TODO | JOGOS1910")
        self.assertEqual(c["loja_cupom"], "MERCADO LIVRE")

    def test_cuponzao_comenta_a_regra_de_cada_cupom(self):
        c = campos(MSG_CUPONZAO, ["https://meli.la/2RpaQkM"])
        comentarios = c["comentario_cupom"].split(" | ")
        self.assertEqual(len(comentarios), 3)
        self.assertIn("30% OFF máx R$15", comentarios[0])
        self.assertIn("R$150/999", comentarios[1])
        self.assertIn("10% OFF máx R$20", comentarios[2])

    def test_print_de_cupons_sem_codigo_no_texto(self):
        c = campos(MSG_PRINT_CUPONS, ["https://meli.la/1e38U4R"])
        self.assertEqual(c["tipo_anuncio"], "CUPOM")
        self.assertEqual(c["preco_por"], "")

    def test_cupom_rotulado_continua_funcionando(self):
        c = campos(MSG_CUPOM_ROTULADO, ["https://mercadolivre.com/sec/1rn8M1w"])
        self.assertEqual(c["tipo_anuncio"], "CUPOM")
        self.assertEqual(c["cupom"], "SITE150TODO | CPAMD19")
        self.assertEqual(c["preco_por"], "")


class TestProdutoNaoRegride(unittest.TestCase):
    def test_produto_com_de_por_continua_produto(self):
        c = campos(MSG_PRODUTO_COM_CUPOM, ["https://meli.la/1UwL67Y"])
        self.assertEqual(c["tipo_anuncio"], "PRODUTO")
        self.assertEqual(c["preco_de"], "266,00")
        self.assertEqual(c["preco_por"], "103,22")
        self.assertEqual(c["cupom"], "VALEPROMO")

    def test_produto_com_preco_solto_mantem_o_preco(self):
        c = campos(MSG_PRODUTO_PRECO_SOLTO, ["https://amzn.promos.link/qNf3M2"])
        self.assertEqual(c["tipo_anuncio"], "PRODUTO")
        self.assertEqual(c["preco_por"], "35,99")
        self.assertEqual(c["descricao_pagamento"], "no pix")

    def test_preco_do_produto_vence_a_regra_do_cupom(self):
        c = campos(MSG_PRODUTO_APOS_REGRA, ["https://meli.la/1zHuHHd"])
        self.assertEqual(c["tipo_anuncio"], "PRODUTO")
        self.assertEqual(c["preco_por"], "199,90")


class TestRegraDeCupomNoValor(unittest.TestCase):
    """Unidade: quais 'R$ x' sao regra de cupom e nao preco."""

    REGRAS = [
        "30% OFF máx R$15 via saldo Mercado Pago",
        "10% OFF  máx R$20 em Livros & Jogos",
        "SITE150TODO - R$150/999",
        "R$ 150 OFF em R$ 999",
        "Limite de R$ 15",
        "Compra mín. R$ 999",
        "30% OFF compras acima de R$45 limitado a R$15",
    ]
    PRECOS = [
        "R$ 141,55 via Pix",
        "De: R$ 266,00",
        "Por: R$ 103,22",
        "R$ 35,99 no pix",
        "Fone Bluetooth por R$ 199,90 à vista",
    ]

    def test_linhas_de_regra(self):
        for ln in self.REGRAS:
            with self.subTest(linha=ln):
                self.assertTrue(parser._eh_linha_regra_cupom(ln))

    def test_linhas_de_preco(self):
        for ln in self.PRECOS:
            with self.subTest(linha=ln):
                self.assertFalse(parser._eh_linha_regra_cupom(ln))


class TestCodigoSolto(unittest.TestCase):
    def test_codigo_sozinho_na_linha(self):
        self.assertEqual(parser._codigo_solto("🎟️ CPAMD19"), ("CPAMD19", ""))

    def test_codigo_com_a_regra_colada(self):
        codigo, resto = parser._codigo_solto("🎟️ SITE150TODO - R$150/999")
        self.assertEqual(codigo, "SITE150TODO")
        self.assertEqual(resto, "R$150/999")

    def test_grito_sem_digito_nao_e_codigo(self):
        self.assertEqual(parser._codigo_solto("CORRE!!!"), ("", ""))
        self.assertEqual(parser._codigo_solto("PROMOCAO LIBERADA"), ("", ""))

    def test_linha_comum_nao_e_codigo(self):
        self.assertEqual(parser._codigo_solto("Usa logooooo:😱"), ("", ""))
        self.assertEqual(parser._codigo_solto("R$ 35,99 no pix"), ("", ""))


if __name__ == "__main__":
    unittest.main()
