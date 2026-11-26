# Fixtures da captura web (BSV-66)

Recortes das páginas reais baixadas em 25/11/2026, entre 20:00 e 22:30 (Brasília), com `urllib`.
Cada arquivo guarda **só** a estrutura que o extrator lê, com 5 a 8 ofertas reais. Os campos de usuário
dos sites (autor, apelido, foto) foram tirados ou trocados por `fixture`.

| arquivo | origem | ofertas |
|---|---|---|
| `pelando_lista.html` | `/recentes`, `/mais-quentes`, `/mais-baratos` | Amazon ×2, Shopee, `expired` (Olympikus), `kind: coupon` (Beleza na Web), Magalu |
| `promobit_lista.html` | `/`, `/promocoes/recentes/`, `/em-alta/`, `/menor-preco/` | Amazon ×2, ML com cupom, Shopee com cupom inválido (`25 Full`), Amazon `COUPON`, Amazon `STARTING_AT`, Magalu, `manual.com.br` |
| `promobit_redirect.html` | `/Redirect/to/3255118/` | script `l = '<url>'` e o link do `<p>` |
| `pechinchou_lista.html` | `/recentes`, `/destaques`, `/mais-pontuados`, `/menor-preco` | Amazon, Amazon com cupom, ML por `meli.la` com cupom, Amazon `CLOSED`, Magalu |

Os testes de idade fixam o relógio; as datas das ofertas são as reais (`createdAt` em UTC no Pelando,
offset `-03:00` nos outros dois). Quando um site mudar o HTML, baixe a página de novo e refaça o recorte
mantendo os mesmos casos.
