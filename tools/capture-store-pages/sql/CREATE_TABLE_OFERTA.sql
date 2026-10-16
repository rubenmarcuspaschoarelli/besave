-- =============================================================================
-- BESAVE.OFERTA (2026-09-02)
-- Consolida as ofertas PUBLICAVEIS: 1 linha por oferta capturada com sucesso
-- (ST_CAPTURA='1') cuja loja tenha afiliado ATIVO em BESAVE.LOJA_AFILIADA
-- (ST_ATIVO=1) -- NAO e a mesma coisa que OFERTA_FILA_CAPTURA.ST_ATIVO (esse
-- vem de conf/config.json -> "lojas_ativas"; hoje coincidem nas mesmas 3
-- lojas -- Amazon/Mercado Livre/Shopee -- mas sao fontes diferentes e podem
-- divergir no futuro).
--
-- Grao: 1 linha POR OFERTA (nao por produto) -- o mesmo produto pode
-- aparecer varias vezes, cada oferta com seu proprio preco/data/cupom. A
-- consolidacao POR PRODUTO (min/max preco entre ofertas) ja existe em
-- BESAVE.PRODUTO (ver STP_PRODUTO_UPSERT.STP); OFERTA e o "feed" de ofertas
-- individuais aprovadas p/ publicacao.
--
-- ID_OFERTA reaproveita o MESMO ID de OFERTA_FILA_CAPTURA (chave natural,
-- 1:1) -- sem sequence propria. DS_LOJA vem do nome COMERCIAL resolvido no
-- Python (registry.nome_loja) -- a coluna OFERTA_FILA_CAPTURA.DS_LOJA existe
-- mas nunca e gravada por nenhuma SP (confirmado 2026-09-02: 0 linhas
-- preenchidas), entao nao da p/ confiar nela como fonte.
--
-- Populada por: main.py (a cada captura bem-sucedida + loja ativa, ver
-- core/ofertas.py) e por publicar_ofertas.py (backfill do historico, mesmo
-- padrao do cadastrar_produtos.py p/ PRODUTO).
-- =============================================================================
CREATE TABLE BESAVE.OFERTA (
  ID_OFERTA           NUMBER        NOT NULL,
  ID_PRODUTO          NUMBER        NOT NULL,
  DS_LOJA             VARCHAR2(100 CHAR),
  DS_TITULO           VARCHAR2(400 CHAR),
  DS_IMAGEM_OFERTA    VARCHAR2(350 CHAR),
  DS_URL_BESAVE       VARCHAR2(600 CHAR),
  DS_URL_FINAL        VARCHAR2(350 CHAR),
  VL_PRECO_DE         NUMBER,
  VL_PRECO_POR        NUMBER,
  VR_PRECO_1          NUMBER,
  DS_CUPOM            VARCHAR2(30 CHAR),
  DS_CUPOM_COMENTARIO VARCHAR2(50 CHAR),
  NR_NOTA_AVALIACAO   NUMBER,
  QT_AVALIACAO        NUMBER,
  DT_OFERTA           DATE,
  DT_CAPTACAO         DATE,
  DT_PUBLICACAO       DATE,
  CONSTRAINT PK_OFERTA PRIMARY KEY (ID_OFERTA)
);
