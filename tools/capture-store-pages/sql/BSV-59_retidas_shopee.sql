-- BSV-59: descarta as linhas da Shopee retidas ('0') ha mais de 1 dia, com preco velho,
-- antes de ligar shopee_afiliado.habilitado. Aplicado pelo dono; anotar a contagem antes/depois na PR.

SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA
 WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;

UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '9', DS_CAPTURA = 'descartada_atraso_bsv'
 WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;

-- Conferir (deve dar 0) antes do COMMIT.
SELECT COUNT(*) FROM OFERTA_FILA_CAPTURA
 WHERE ST_CAPTURA = '0' AND DS_URL_ORIGEM LIKE '%shopee%' AND DT_CAPTACAO < SYSDATE - 1;

COMMIT;
