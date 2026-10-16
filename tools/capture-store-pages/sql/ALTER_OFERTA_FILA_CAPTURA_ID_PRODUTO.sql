-- =============================================================================
-- Coluna ID_PRODUTO em OFERTA_FILA_CAPTURA (2026-09-02)
-- Liga cada oferta capturada (ST_CAPTURA='1') ao produto correspondente na
-- nova tabela BESAVE.PRODUTO (cadastro consolidado por produto, ver
-- STP_PRODUTO_UPSERT.STP). Gravada por cadastrar_produtos.py -- nao mexe no
-- fluxo de captura do main.py.
-- =============================================================================
ALTER TABLE BESAVE.OFERTA_FILA_CAPTURA ADD ID_PRODUTO NUMBER;
