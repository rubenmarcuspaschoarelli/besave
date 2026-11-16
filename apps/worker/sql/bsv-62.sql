-- BSV-62 · Canal do WhatsApp e fila ENVIO_WHATSAPP — DDL (Oracle XE 11.2)
-- Rodar como o dono das tabelas (BESAVE), no SQL*Plus ou SQL Developer, um bloco por vez.
-- Depende do bsv-40.sql (CANAL_ENVIO, PARAMETROS_ENVIO, ENVIO_TELEGRAM).
-- Idempotência: não é idempotente; rodar uma vez. Desfazer: bloco 5 (comentado).

-- 0. CHECAGEM ANTES DE TUDO ---------------------------------------------------------------
-- 0a. A legenda leva emoji (🔥, 🎟️, 🏃‍♂️). O banco precisa gravar UTF-8 de 4 bytes.
--     Esperado: AL32UTF8. Se vier outro valor, PARE e avise: o emoji viraria "?" na fila.
SELECT VALUE FROM NLS_DATABASE_PARAMETERS WHERE PARAMETER = 'NLS_CHARACTERSET';
-- 0b. O canal 2 ainda não existe. Esperado: 0 linhas. Se vier 1, PARE e avise.
SELECT ID_CANAL, DS_NOME, DS_CHAT_ID FROM CANAL_ENVIO WHERE ID_CANAL = 2;
-- 0c. A fila ainda não existe. Esperado: 0 linhas. Se vier alguma, PARE e avise.
SELECT OBJECT_NAME, OBJECT_TYPE FROM USER_OBJECTS
 WHERE OBJECT_NAME IN ('ENVIO_WHATSAPP', 'SQ_ENVIO_WHATSAPP');

-- 1. CANAL DO WHATSAPP --------------------------------------------------------------------
-- DS_CHAT_ID = nome do canal como aparece no WhatsApp Web (o publicador, BSV-63, procura por ele).
-- Sem número de telefone nem link de convite: a fila não guarda segredo.
INSERT INTO CANAL_ENVIO (ID_CANAL, DS_NOME, DS_CHAT_ID)
VALUES (2, 'WhatsApp', 'BeSave - Preços Baixos e Ofertas incríveis');

-- 2. TETO E JANELA DO CANAL 2 --------------------------------------------------------------
-- Só QT_MAX_DIA e a janela valem para o canal 2 (o publicador aplica). A seleção é a do canal 1.
-- O dono sobe QT_MAX_DIA por semana: UPDATE PARAMETROS_ENVIO SET QT_MAX_DIA = n WHERE ID_CANAL = 2;
INSERT INTO PARAMETROS_ENVIO (ID_CANAL, QT_MAX_DIA, NR_HORA_INICIO, NR_HORA_FIM)
VALUES (2, 40, 8, 22);
COMMIT;

-- 3. FILA DO WHATSAPP ----------------------------------------------------------------------
-- O besave-envio insere a linha 'P' depois que o post da oferta é confirmado no Telegram
-- (BESAVE_ENVIO_ESPELHO_WHATSAPP=2). O publicador (BSV-63) lê as 'P' e marca E, D ou X.
-- Sem FK para OFERTA de propósito, igual a ENVIO_TELEGRAM: não trava nenhuma operação do robô.
CREATE SEQUENCE SQ_ENVIO_WHATSAPP START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE ENVIO_WHATSAPP (
  ID_ENVIO_WA        NUMBER(12)           NOT NULL,
  ID_CANAL           NUMBER(10)           NOT NULL,
  ID_OFERTA          NUMBER               NOT NULL,
  ID_ENVIO_TELEGRAM  NUMBER(12),                       -- ENVIO_TELEGRAM.ID_ENVIO do post espelhado
  DS_LEGENDA         VARCHAR2(4000 BYTE)  NOT NULL,    -- marcação do WhatsApp, pronta
  DS_AREA_SLUG       VARCHAR2(20)         NOT NULL,    -- slug da área (CONTRATO §2.3): placeholder
  ST_ENVIO           CHAR(1)              DEFAULT 'P' NOT NULL,  -- P pendente, E enviado, D duvidoso, X descartado
  DS_MOTIVO          VARCHAR2(60),                     -- por que D ou X
  DT_FILA            DATE                 DEFAULT SYSDATE NOT NULL,
  DT_ENVIO           DATE,                             -- quando o publicador postou
  CONSTRAINT PK_ENVIO_WHATSAPP PRIMARY KEY (ID_ENVIO_WA),
  CONSTRAINT UK_ENVIO_WHATSAPP UNIQUE (ID_CANAL, ID_OFERTA),
  CONSTRAINT FK_ENVIO_WHATSAPP_CANAL FOREIGN KEY (ID_CANAL) REFERENCES CANAL_ENVIO (ID_CANAL),
  CONSTRAINT CK_ENVIO_WHATSAPP_ST CHECK (ST_ENVIO IN ('P', 'E', 'D', 'X'))
);

CREATE INDEX IX_ENVIO_WHATSAPP_FILA ON ENVIO_WHATSAPP (ID_CANAL, ST_ENVIO, DT_FILA);

-- 4. CONFERÊNCIA ---------------------------------------------------------------------------
SELECT * FROM CANAL_ENVIO WHERE ID_CANAL = 2;
SELECT ID_CANAL, QT_MAX_DIA, NR_HORA_INICIO, NR_HORA_FIM FROM PARAMETROS_ENVIO WHERE ID_CANAL = 2;
SELECT COUNT(*) FROM ENVIO_WHATSAPP;

-- Se o worker ou o publicador conectarem com outro usuário que não o dono das tabelas, rodar também
-- (trocar <USUARIO>):
-- GRANT SELECT, INSERT, UPDATE ON ENVIO_WHATSAPP TO <USUARIO>;
-- GRANT SELECT ON SQ_ENVIO_WHATSAPP TO <USUARIO>;
-- GRANT SELECT ON CANAL_ENVIO TO <USUARIO>;
-- GRANT SELECT ON PARAMETROS_ENVIO TO <USUARIO>;

-- 5. DESFAZER (só se precisar voltar atrás) -------------------------------------------------
-- DROP TABLE ENVIO_WHATSAPP;
-- DROP SEQUENCE SQ_ENVIO_WHATSAPP;
-- DELETE FROM PARAMETROS_ENVIO WHERE ID_CANAL = 2;
-- DELETE FROM CANAL_ENVIO WHERE ID_CANAL = 2;
-- COMMIT;
