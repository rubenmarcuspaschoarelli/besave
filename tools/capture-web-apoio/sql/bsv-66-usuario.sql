-- BSV-66: usuario so da captura web de apoio. Rodar como ADMIN (SQL*Plus/SQLcl/SQL Developer como script).
-- A senha entra pela variavel de substituicao &senha (pedida na hora); nunca escreva a senha aqui.
-- Depois: BESAVE_WEB_SENHA=<senha> no PC (ou db.senha no conf/config.json, fora do git).

CREATE USER BESAVE_WEB IDENTIFIED BY "&senha";
GRANT CREATE SESSION TO BESAVE_WEB;
GRANT SELECT, INSERT ON BESAVE.OFERTA_FILA_CAPTURA TO BESAVE_WEB;
GRANT SELECT ON BESAVE.OFERTA TO BESAVE_WEB;

-- Reversao:
-- DROP USER BESAVE_WEB CASCADE;
