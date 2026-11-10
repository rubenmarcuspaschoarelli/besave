-- =============================================================================
-- BSV-56: ID_OFERTA gerado pelo banco (sequence + trigger) na OFERTA_FILA_CAPTURA
--
-- Aplicar como BESAVE (dono da tabela; o robo tambem conecta como BESAVE), COM O
-- ROBO DO WHATSAPP PARADO, no SQL*Plus / SQL Developer. Producao: Oracle
-- Autonomous (bsvdb_tp).
--
-- REEXECUTAVEL: se SQ_OFERTA_FILA ja existe, o bloco 1 nao recria (so imprime o
-- LAST_NUMBER); a trigger e CREATE OR REPLACE. Rodar duas vezes nao da erro nem
-- muda a sequence; a conferencia (bloco 3) continua barrando sequence <= maior id.
--
--   * SQ_OFERTA_FILA: o robo pede NEXTVAL ANTES de salvar a imagem (o id e o
--     nome do arquivo). START WITH = maior ID_OFERTA ja usado (fila ou OFERTA) + 1.
--     NOCACHE: ~1000 ids/dia; evita buracos grandes (cache perdido em restart)
--     e mantem a ordem. Buracos pequenos sao aceitos (MANIFEST §2, §3.1).
--   * TRG_OFERTA_FILA_ID: preenche ID_OFERTA so quando ele vem NULO (produtor
--     que nao precisa do id antes, como o robo de sites; rede de seguranca).
--   * A SP STP_OFERTA_FILA_CAPTURA_INSERT nao muda (continua com P_ID_OFERTA).
-- =============================================================================

SET SERVEROUTPUT ON

-- 1. Sequence. START WITH exige literal: calcula e cria por EXECUTE IMMEDIATE.
--    Ja existe -> nao recria nem altera; so informa o LAST_NUMBER (proximo valor, NOCACHE).
DECLARE
  v_inicio NUMBER;
  v_existe NUMBER;
  v_ultimo NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_existe FROM USER_SEQUENCES WHERE SEQUENCE_NAME = 'SQ_OFERTA_FILA';
  IF v_existe > 0 THEN
    SELECT LAST_NUMBER INTO v_ultimo FROM USER_SEQUENCES WHERE SEQUENCE_NAME = 'SQ_OFERTA_FILA';
    DBMS_OUTPUT.PUT_LINE('SQ_OFERTA_FILA ja existe (LAST_NUMBER ' || v_ultimo || '); nao recriada.');
  ELSE
    SELECT GREATEST(
             NVL((SELECT MAX(ID_OFERTA) FROM OFERTA_FILA_CAPTURA), 0),
             NVL((SELECT MAX(ID_OFERTA) FROM OFERTA), 0)
           ) + 1
      INTO v_inicio
      FROM DUAL;
    EXECUTE IMMEDIATE 'CREATE SEQUENCE SQ_OFERTA_FILA START WITH ' || TO_CHAR(v_inicio)
                   || ' INCREMENT BY 1 NOCACHE NOCYCLE';
    DBMS_OUTPUT.PUT_LINE('SQ_OFERTA_FILA criada com START WITH ' || v_inicio);
  END IF;
END;
/

-- 2. Trigger: so age quando ID_OFERTA vem nulo.
CREATE OR REPLACE TRIGGER TRG_OFERTA_FILA_ID
  BEFORE INSERT ON OFERTA_FILA_CAPTURA
  FOR EACH ROW
  WHEN (NEW.ID_OFERTA IS NULL)
BEGIN
  :NEW.ID_OFERTA := SQ_OFERTA_FILA.NEXTVAL;
END;
/

-- 3. Conferencia: a sequence tem de estar acima de todo id existente.
--    Usa LAST_NUMBER (proximo valor, NOCACHE) para nao consumir numero.
DECLARE
  v_proximo NUMBER;
  v_maior   NUMBER;
  v_status  VARCHAR2(10);
BEGIN
  SELECT LAST_NUMBER INTO v_proximo FROM USER_SEQUENCES WHERE SEQUENCE_NAME = 'SQ_OFERTA_FILA';
  SELECT GREATEST(
           NVL((SELECT MAX(ID_OFERTA) FROM OFERTA_FILA_CAPTURA), 0),
           NVL((SELECT MAX(ID_OFERTA) FROM OFERTA), 0)
         )
    INTO v_maior
    FROM DUAL;
  SELECT STATUS INTO v_status FROM USER_TRIGGERS WHERE TRIGGER_NAME = 'TRG_OFERTA_FILA_ID';
  IF v_proximo > v_maior AND v_status = 'ENABLED' THEN
    DBMS_OUTPUT.PUT_LINE('OK: proximo id ' || v_proximo || ' > maior existente ' || v_maior
                         || '; trigger ' || v_status);
  ELSE
    RAISE_APPLICATION_ERROR(-20056, 'FALHOU: proximo id ' || v_proximo || ', maior existente '
                            || v_maior || ', trigger ' || v_status);
  END IF;
END;
/

-- 4. Reversao (so se precisar voltar ao contador em arquivo; robo parado):
-- DROP TRIGGER TRG_OFERTA_FILA_ID;
-- DROP SEQUENCE SQ_OFERTA_FILA;
