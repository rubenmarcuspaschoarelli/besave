-- BSV-40 · Envio de ofertas ao canal do Telegram — DDL (Oracle XE 11.2)
-- Rodar como o dono das tabelas (BESAVE), no SQL*Plus ou SQL Developer, um bloco por vez.
-- Idempotência: não é idempotente; rodar uma vez. Desfazer: bloco 5 (comentado).

-- 0. CHECAGEM ANTES DE TUDO ---------------------------------------------------------------
-- A OFERTA ganha uma coluna nova (bloco 1). Um INSERT sem lista de colunas quebraria a captura.
-- Confira cada linha devolvida: o INSERT precisa listar as colunas (INSERT INTO OFERTA (A, B, ...)).
-- Se algum for "INSERT INTO OFERTA VALUES (...)" ou "INSERT INTO OFERTA SELECT ...", PARE e avise.
-- 0a. Objetos do banco que usam a tabela OFERTA (procedures, triggers, views):
SELECT NAME, TYPE FROM USER_DEPENDENCIES
 WHERE REFERENCED_NAME = 'OFERTA' AND REFERENCED_TYPE = 'TABLE'
 ORDER BY TYPE, NAME;
-- 0b. Linhas com INSERT na OFERTA (um INSERT quebrado em duas linhas não aparece aqui: abra os
--     objetos de 0a que gravam na OFERTA e confira a lista de colunas):
SELECT NAME, TYPE, LINE, TRIM(TEXT) AS TEXTO
  FROM USER_SOURCE
 WHERE UPPER(TEXT) LIKE '%INSERT%INTO%OFERTA%'
   AND UPPER(TEXT) NOT LIKE '%OFERTA\_%' ESCAPE '\'
 ORDER BY NAME, LINE;

-- 1. DATA EM QUE A OFERTA FOI AO AR NO SITE -------------------------------------------------
-- Gravada pelo besave-ciclo depois que o manifest é publicado (só quando nula). O envio ao canal
-- só considera ofertas com esta data preenchida: a página /oferta/{id}/ já existe.
ALTER TABLE OFERTA ADD (DT_PUBLICACAO_SITE DATE);

-- 2. CANAIS -------------------------------------------------------------------------------
CREATE TABLE CANAL_ENVIO (
  ID_CANAL     NUMBER(10)   NOT NULL,
  DS_NOME      VARCHAR2(60) NOT NULL,
  DS_CHAT_ID   VARCHAR2(64) NOT NULL,
  ST_ATIVO     NUMBER(1)    DEFAULT 1 NOT NULL,
  DT_CADASTRO  DATE         DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_CANAL_ENVIO PRIMARY KEY (ID_CANAL),
  CONSTRAINT CK_CANAL_ENVIO_ATIVO CHECK (ST_ATIVO IN (0, 1))
);

-- 3. PARÂMETROS POR CANAL (lidos no início de cada execução do besave-envio) ----------------
CREATE TABLE PARAMETROS_ENVIO (
  ID_CANAL              NUMBER(10) NOT NULL,
  QT_MAX_DIA            NUMBER(5)  DEFAULT 180 NOT NULL,  -- envios por dia (Brasília)
  QT_POR_EXECUCAO       NUMBER(3)  DEFAULT 2   NOT NULL,  -- tamanho do lote por execução
  NR_HORA_INICIO        NUMBER(2)  DEFAULT 8   NOT NULL,  -- janela [início, fim)
  NR_HORA_FIM           NUMBER(2)  DEFAULT 22  NOT NULL,
  NR_HORA_SOM_INICIO    NUMBER(2)  DEFAULT 9   NOT NULL,  -- fora daqui: envio silencioso
  NR_HORA_SOM_FIM       NUMBER(2)  DEFAULT 21  NOT NULL,
  PC_DESCONTO_MIN       NUMBER(3)  DEFAULT 30  NOT NULL,  -- oferta sem preço "de" entra
  NR_HORAS_OFERTA_MAX   NUMBER(4)  DEFAULT 24  NOT NULL,  -- idade máxima de DT_OFERTA
  NR_DIAS_REPETICAO     NUMBER(3)  DEFAULT 5   NOT NULL,  -- mesmo ID_PRODUTO
  PC_QUEDA_REPETICAO    NUMBER(3)  DEFAULT 10  NOT NULL,  -- queda mínima para repetir
  PC_DESCONTO_DESTAQUE  NUMBER(3)  DEFAULT 30  NOT NULL,  -- selo "-xx%" a partir daqui
  DT_ATUALIZACAO        DATE       DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_PARAMETROS_ENVIO PRIMARY KEY (ID_CANAL),
  CONSTRAINT FK_PARAM_ENVIO_CANAL FOREIGN KEY (ID_CANAL) REFERENCES CANAL_ENVIO (ID_CANAL),
  CONSTRAINT CK_PARAM_ENVIO_JANELA CHECK (NR_HORA_INICIO BETWEEN 0 AND 23
                                      AND NR_HORA_FIM BETWEEN 1 AND 24
                                      AND NR_HORA_INICIO < NR_HORA_FIM),
  CONSTRAINT CK_PARAM_ENVIO_SOM CHECK (NR_HORA_SOM_INICIO BETWEEN 0 AND 23
                                   AND NR_HORA_SOM_FIM BETWEEN 1 AND 24),
  CONSTRAINT CK_PARAM_ENVIO_QT CHECK (QT_MAX_DIA >= 0 AND QT_POR_EXECUCAO BETWEEN 1 AND 10),
  CONSTRAINT CK_PARAM_ENVIO_PC CHECK (PC_DESCONTO_MIN BETWEEN 0 AND 99
                                  AND PC_QUEDA_REPETICAO BETWEEN 0 AND 99
                                  AND PC_DESCONTO_DESTAQUE BETWEEN 0 AND 99)
);

-- 4. REGISTRO DO QUE FOI POSTADO -----------------------------------------------------------
-- A linha nasce antes do envio (NR_MESSAGE_ID nulo) e é apagada se o envio falhar: sem duplicata.
-- Sem FK para OFERTA de propósito: não pode travar nenhuma operação do robô na OFERTA.
CREATE SEQUENCE SQ_ENVIO_TELEGRAM START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE ENVIO_TELEGRAM (
  ID_ENVIO       NUMBER(12) NOT NULL,
  ID_CANAL       NUMBER(10) NOT NULL,
  ID_OFERTA      NUMBER     NOT NULL,
  ID_PRODUTO     NUMBER,
  VL_PRECO_POR   NUMBER,                       -- mesmo valor/unidade de OFERTA.VL_PRECO_POR
  NR_MESSAGE_ID  NUMBER(12),                   -- nulo até o Telegram confirmar
  DT_ENVIO       DATE DEFAULT SYSDATE NOT NULL,
  DT_EDICAO      DATE,                         -- "Oferta encerrada" aplicada
  CONSTRAINT PK_ENVIO_TELEGRAM PRIMARY KEY (ID_ENVIO),
  CONSTRAINT UK_ENVIO_TELEGRAM UNIQUE (ID_CANAL, ID_OFERTA),
  CONSTRAINT FK_ENVIO_TELEGRAM_CANAL FOREIGN KEY (ID_CANAL) REFERENCES CANAL_ENVIO (ID_CANAL)
);

CREATE INDEX IX_ENVIO_TELEGRAM_PRODUTO ON ENVIO_TELEGRAM (ID_CANAL, ID_PRODUTO, DT_ENVIO);
CREATE INDEX IX_ENVIO_TELEGRAM_DATA ON ENVIO_TELEGRAM (ID_CANAL, DT_ENVIO);

-- Canal inicial e parâmetros padrão.
INSERT INTO CANAL_ENVIO (ID_CANAL, DS_NOME, DS_CHAT_ID) VALUES (1, 'Besave Ofertas', '@besaveofertas');
INSERT INTO PARAMETROS_ENVIO (ID_CANAL) VALUES (1);
COMMIT;

-- Conferência.
SELECT * FROM CANAL_ENVIO;
SELECT * FROM PARAMETROS_ENVIO;

-- Se o worker conectar com outro usuário que não o dono das tabelas, rodar também (trocar <USUARIO>):
-- GRANT SELECT ON CANAL_ENVIO TO <USUARIO>;
-- GRANT SELECT ON PARAMETROS_ENVIO TO <USUARIO>;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ENVIO_TELEGRAM TO <USUARIO>;
-- GRANT SELECT ON SQ_ENVIO_TELEGRAM TO <USUARIO>;
-- GRANT UPDATE (DT_PUBLICACAO_SITE) ON OFERTA TO <USUARIO>;

-- 5. DESFAZER (só se precisar voltar atrás) -------------------------------------------------
-- DROP TABLE ENVIO_TELEGRAM;
-- DROP SEQUENCE SQ_ENVIO_TELEGRAM;
-- DROP TABLE PARAMETROS_ENVIO;
-- DROP TABLE CANAL_ENVIO;
-- ALTER TABLE OFERTA DROP COLUMN DT_PUBLICACAO_SITE;
