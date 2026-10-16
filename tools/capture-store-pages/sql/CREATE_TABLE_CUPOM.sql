-- =============================================================================
-- BESAVE.CUPOM (2026-09-06)
-- Cadastro consolidado de cupons de desconto, um por (CUPOM, DS_LOJA) --
-- confirmado no historico de OFERTA_FILA_CAPTURA que o MESMO codigo de cupom
-- se repete em lojas diferentes com condicoes diferentes (ex.: "EUCERIN20"
-- aparece em 4 lojas, "RESGATE" em 3) -- por isso a chave de upsert e o PAR
-- (CUPOM, DS_LOJA), nao CUPOM sozinho (ver sql/STP_CUPOM_UPSERT.STP).
--
-- Origem dos campos (OFERTA_FILA_CAPTURA), confirmada por amostragem real:
--   CUPOM   <- DS_CUPOM             (codigo do cupom propriamente dito)
--   DS_CUPOM <- DS_CUPOM_COMENTARIO (descricao/condicao, ex. "10% OFF acima
--               de R$ 800 (Limite de R$ 100)")
--   DS_LOJA <- DS_CUPOM_LOJA        (loja associada AO CUPOM -- diferente da
--               coluna OFERTA_FILA_CAPTURA.DS_LOJA generica, que nunca e
--               gravada por nenhuma SP, ver CREATE_TABLE_OFERTA.sql)
--
-- Populada por: main.py (a cada captura bem-sucedida com cupom, ver
-- core/cupons.py) e por backfill_cupons.py (backfill do historico).
-- =============================================================================
CREATE TABLE BESAVE.CUPOM (
  ID_CUPOM           NUMBER            NOT NULL,
  CUPOM              VARCHAR2(30 CHAR) NOT NULL,
  DS_CUPOM           VARCHAR2(150 CHAR),
  DS_LOJA            VARCHAR2(100 CHAR),
  DT_CADASTRO        DATE,
  DT_ULT_ATUALIZACAO DATE,
  CONSTRAINT PK_CUPOM PRIMARY KEY (ID_CUPOM)
);
