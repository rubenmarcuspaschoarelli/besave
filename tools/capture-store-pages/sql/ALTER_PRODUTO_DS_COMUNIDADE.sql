-- =============================================================================
-- Coluna DS_COMUNIDADE em PRODUTO (2026-09-04)
-- Comunidade de maior probabilidade, derivada de LS_CATEGORIA/DS_CATEGORIA_RANKING
-- por core/classificador.py. Ver tambem PRODUTO_COMUNIDADE (N:N, todas as
-- comunidades que casaram, nao so a principal).
-- =============================================================================
ALTER TABLE BESAVE.PRODUTO ADD DS_COMUNIDADE VARCHAR2(50 CHAR);
