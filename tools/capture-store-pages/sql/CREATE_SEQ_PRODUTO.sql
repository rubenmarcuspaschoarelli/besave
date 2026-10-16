-- =============================================================================
-- Sequence do ID_PRODUTO (2026-09-02) -- gera o ID unico da tabela
-- BESAVE.PRODUTO ao cadastrar um produto novo (STP_PRODUTO_UPSERT).
-- =============================================================================
CREATE SEQUENCE BESAVE.SEQ_PRODUTO START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
