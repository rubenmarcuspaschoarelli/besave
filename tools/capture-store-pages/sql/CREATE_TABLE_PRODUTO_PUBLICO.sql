-- =============================================================================
-- BESAVE.PRODUTO_PUBLICO (2026-09-04)
-- N:N -- normalmente 1 linha por produto (o valor primario, igual a
-- PRODUTO.DS_PUBLICO), mas permite mais de um publico no futuro (ex.: kit
-- "Menino e Menina"). CHECK no lugar de tabela de dominio: sao so 6 valores
-- fixos, nao justifica outra tabela lookup (ver PRODUTO_COMUNIDADE, que usa
-- FK logico pra BESAVE.COMUNIDADE por ser dominio maior/mutavel).
-- =============================================================================
CREATE TABLE BESAVE.PRODUTO_PUBLICO (
  ID_PRODUTO NUMBER             NOT NULL,
  DS_PUBLICO VARCHAR2(30 CHAR)  NOT NULL,
  NR_ORDEM   NUMBER             NOT NULL,
  CONSTRAINT PK_PRODUTO_PUBLICO PRIMARY KEY (ID_PRODUTO, DS_PUBLICO),
  CONSTRAINT CK_PRODUTO_PUBLICO CHECK (DS_PUBLICO IN
    ('Masculino', 'Feminino', 'Unisex', 'Menino', 'Menina', 'Bebes'))
);
