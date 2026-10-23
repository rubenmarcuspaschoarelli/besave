-- BSV-49 · Preparação do banco para o backup. Executar UMA vez, pelo dono, como ADMIN (SQL Developer Web
-- ou sqlplus). Não faz parte do deploy e nada aqui roda sozinho. Substitua &senha_backup pela senha do
-- usuário de backup (a mesma de BACKUP_DB_PASS no backup.env). Conferir cada GRANT na primeira execução real.

-- 1. Usuário de backup. Não é o BESAVE e não é dono de nada; só exporta/importa e confere contagens.
CREATE USER BESAVE_BACKUP IDENTIFIED BY "&senha_backup" QUOTA UNLIMITED ON DATA;
GRANT CREATE SESSION TO BESAVE_BACKUP;
-- Data Pump: exportar BESAVE (outro dono) e importar em BESAVE_RESTORE
GRANT DATAPUMP_CLOUD_EXP, DATAPUMP_CLOUD_IMP TO BESAVE_BACKUP;
-- Credencial do Object Storage (DBMS_CLOUD.CREATE_CREDENTIAL, passo 2 do README)
GRANT EXECUTE ON DBMS_CLOUD TO BESAVE_BACKUP;
-- Log do Data Pump no DATA_PUMP_DIR
GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO BESAVE_BACKUP;
-- Contagem de linhas e objetos inválidos no teste mensal (só leitura)
GRANT SELECT ANY TABLE TO BESAVE_BACKUP;
GRANT SELECT ANY DICTIONARY TO BESAVE_BACKUP;

-- 2. Rotinas que criam e apagam o schema do teste de restauração. Rodam com os direitos do ADMIN e só
--    mexem em BESAVE_RESTORE (nome fixo): o usuário de backup não recebe CREATE USER/DROP USER.
--    Se o primeiro teste real devolver ORA-01031, o ADMIN precisa de CREATE USER e DROP USER concedidos
--    diretamente (papéis não valem dentro de rotina com direitos do definidor).
CREATE OR REPLACE PROCEDURE ADMIN.BACKUP_LIMPA_RESTORE AUTHID DEFINER AS
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM ALL_USERS WHERE USERNAME = 'BESAVE_RESTORE';
  IF n > 0 THEN
    EXECUTE IMMEDIATE 'DROP USER BESAVE_RESTORE CASCADE';
  END IF;
END;
/

CREATE OR REPLACE PROCEDURE ADMIN.BACKUP_PREPARA_RESTORE AUTHID DEFINER AS
BEGIN
  ADMIN.BACKUP_LIMPA_RESTORE;
  EXECUTE IMMEDIATE 'CREATE USER BESAVE_RESTORE NO AUTHENTICATION QUOTA UNLIMITED ON DATA';
END;
/

GRANT EXECUTE ON ADMIN.BACKUP_LIMPA_RESTORE TO BESAVE_BACKUP;
GRANT EXECUTE ON ADMIN.BACKUP_PREPARA_RESTORE TO BESAVE_BACKUP;
