-- =============================================================================
-- Colunas DS_COMUNIDADE / DS_PUBLICO em OFERTA (2026-09-04)
-- Espelham (denormalizado, mesmo padrao de NR_NOTA_AVALIACAO/QT_AVALIACAO) o
-- valor primario ja calculado e gravado em PRODUTO no mesmo momento da
-- captura -- nao ha calculo proprio na oferta.
-- =============================================================================
ALTER TABLE BESAVE.OFERTA ADD DS_COMUNIDADE VARCHAR2(50 CHAR);
ALTER TABLE BESAVE.OFERTA ADD DS_PUBLICO VARCHAR2(30 CHAR);
