-- =============================================================================
-- BESAVE.PRODUTO_COMUNIDADE (2026-09-04)
-- N:N -- um produto pode casar com mais de uma comunidade (ex.: "Relogios"
-- pondera Elas E Eles). NR_ORDEM=1 e a de maior score, a mesma que fica
-- espelhada em PRODUTO.DS_COMUNIDADE. Sem FK (projeto nao usa FK em nenhuma
-- tabela ate agora -- ver CREATE_TABLE_OFERTA.sql/CREATE_TABLE_COMUNIDADE.sql).
-- Gravada por core/classificador.py + core/produtos.py (DELETE+INSERT
-- idempotente a cada classificacao, nunca UPDATE parcial).
-- =============================================================================
CREATE TABLE BESAVE.PRODUTO_COMUNIDADE (
  ID_PRODUTO     NUMBER  NOT NULL,
  ID_COMUNIDADE  NUMBER  NOT NULL,
  NR_ORDEM       NUMBER  NOT NULL,
  NR_SCORE       NUMBER,
  CONSTRAINT PK_PRODUTO_COMUNIDADE PRIMARY KEY (ID_PRODUTO, ID_COMUNIDADE)
);
