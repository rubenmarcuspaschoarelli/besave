-- =============================================================================
-- Colunas do LINK OFICIAL DE AFILIADO (2026-09-10)
--
-- Diferenca p/ DS_URL_BESAVE (que ja existia): DS_URL_BESAVE e CALCULADA pelo
-- Python (core/afiliados.py troca o parametro de rastreio do divulgador pelo
-- nosso na propria DS_URL_FINAL). DS_URL_AFILIADO e o link que o PROPRIO
-- PROGRAMA DE AFILIADOS da loja gera -- capturado na pagina (core/link_afiliado.py):
--   * Amazon .......... SiteStripe -> "Obter link" -> "Copiar link de associado"
--                       (ex.: https://link.amazon/B0eZOeQAV)
--   * Mercado Livre ... barra de afiliado -> "Compartilhar" -> copiar link
--                       (ex.: https://meli.la/27d8yQR)
--   * Shopee .......... affiliate.shopee.com.br/offer/custom_link -> "Obter link"
--                       (ex.: https://s.shopee.com.br/1qbwHpaqtU)
-- As duas convivem: a calculada e o fallback quando a captura do link oficial
-- falha (loja sem sessao de afiliado logada, widget ausente etc.).
--
-- Os outros 3 campos vem do MESMO widget, de graca, e so existem em algumas
-- lojas: categoria e taxa na Amazon, taxa e codigo do produto no Mercado Livre.
-- A Shopee so entrega o link -> as demais colunas ficam NULL nela.
--
-- Tamanhos: DS_URL_AFILIADO copia os 600 CHAR de DS_URL_BESAVE (o link curto e
-- bem menor, mas a coluna aceita tambem uma URL longa com parametros). Os
-- demais sao textos curtos ("Beleza", "13,00%", "JD7H7W-PS9Y").
--
-- Seguro de rodar: colunas novas e anulaveis, nao mexem nas linhas existentes.
-- Reverter:
--   ALTER TABLE OFERTA_FILA_CAPTURA DROP (DS_URL_AFILIADO,
--     DS_CATEGORIA_PROD_AFILIADO, DS_TAXA_COMISSAO_PROD_AFILIADO,
--     DS_ID_PRODUTO_AFILIADO);
-- =============================================================================
ALTER TABLE OFERTA_FILA_CAPTURA ADD (
  DS_URL_AFILIADO                VARCHAR2(600 CHAR),
  DS_CATEGORIA_PROD_AFILIADO     VARCHAR2(100 CHAR),
  DS_TAXA_COMISSAO_PROD_AFILIADO VARCHAR2(20 CHAR),
  DS_ID_PRODUTO_AFILIADO         VARCHAR2(50 CHAR)
);
