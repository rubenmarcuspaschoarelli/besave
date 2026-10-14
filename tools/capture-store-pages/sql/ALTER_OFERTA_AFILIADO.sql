-- =============================================================================
-- Colunas do LINK OFICIAL DE AFILIADO em BESAVE.OFERTA (2026-09-10)
--
-- Espelham as colunas criadas em OFERTA_FILA_CAPTURA no mesmo dia (ver
-- sql/ALTER_OFERTA_FILA_CAPTURA_AFILIADO.sql, que explica de onde vem cada
-- valor). A OFERTA nao recaptura nada: STP_OFERTA_PUBLICAR so copia o que ja
-- foi gravado na fila (mesmo principio de DS_URL_BESAVE/DS_URL_FINAL).
--
-- DS_TAXA_COMISSAO_PROD_AFILIADO e texto ("13,00%"), nao NUMBER: e o que a
-- loja exibe, e o formato varia por loja/pagina. Quem precisar calcular deve
-- converter na consulta.
--
-- Seguro de rodar: colunas novas e anulaveis. Reverter:
--   ALTER TABLE BESAVE.OFERTA DROP (DS_URL_AFILIADO,
--     DS_CATEGORIA_PROD_AFILIADO, DS_TAXA_COMISSAO_PROD_AFILIADO,
--     DS_ID_PRODUTO_AFILIADO);
-- =============================================================================
ALTER TABLE BESAVE.OFERTA ADD (
  DS_URL_AFILIADO                VARCHAR2(600 CHAR),
  DS_CATEGORIA_PROD_AFILIADO     VARCHAR2(100 CHAR),
  DS_TAXA_COMISSAO_PROD_AFILIADO VARCHAR2(20 CHAR),
  DS_ID_PRODUTO_AFILIADO         VARCHAR2(50 CHAR)
);
