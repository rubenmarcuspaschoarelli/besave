-- =============================================================================
-- BESAVE.COMUNIDADE (2026-09-04)
-- Cadastro simples de comunidades/segmentos de publico (Tech, Players, etc.)
-- usadas para segmentar publicacao de ofertas. ID_COMUNIDADE gerado por
-- SEQ_COMUNIDADE (ver CREATE_SEQ_COMUNIDADE.sql).
-- =============================================================================
CREATE TABLE BESAVE.COMUNIDADE (
  ID_COMUNIDADE  INTEGER       NOT NULL,
  DS_COMUNIDADE  VARCHAR2(50 CHAR)  NOT NULL,
  OBS_COMUNIDADE VARCHAR2(300 CHAR), -- pedido era 250, mas o texto de "Familia & filhos" tem 261 chars; ampliado p/ nao truncar
  ST_ATIVO       INTEGER,
  CONSTRAINT PK_COMUNIDADE PRIMARY KEY (ID_COMUNIDADE)
);
