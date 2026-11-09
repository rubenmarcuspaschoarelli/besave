-- BSV-52: conferencia do teste real (KILL SESSION 3x na inst1), SO LEITURA.
-- Parametros: :ptr   = controle.ultimo_id_processado do conf/config.json (apos o teste)
--             :ini   = primeiro ID_OFERTA da fila capturado depois do inicio do teste
--             :t_ini = inicio da janela do teste (DATE, hora local do banco)
--             :t_fim = fim da janela do teste

-- 1) Linhas esquecidas: ST_CAPTURA='0' ATRAS do ponteiro (esperado: 0 linhas).
SELECT ID_OFERTA, DS_CAPTURA
  FROM OFERTA_FILA_CAPTURA
 WHERE ST_CAPTURA = '0' AND ID_OFERTA <= :ptr AND ID_OFERTA >= :ini
 ORDER BY ID_OFERTA;

-- 2) Capturadas ('1') e AUSENTES em OFERTA, de loja com afiliado ativo, na janela do teste
--    (esperado: 0 linhas depois de 1-2 voltas do monitor; ver o log "[pendentes]").
--    Ausencia legitima nao aparece aqui: duplicada vira '9'; vencida e o que nao tem produto
--    (ID_PRODUTO nulo) sao filtrados abaixo.
SELECT f.ID_OFERTA, f.DS_URL_FINAL, f.DS_CAPTURA
  FROM OFERTA_FILA_CAPTURA f
  LEFT JOIN OFERTA o ON o.ID_OFERTA = f.ID_OFERTA
 WHERE f.ST_CAPTURA = '1' AND f.ID_OFERTA >= :ini
   AND o.ID_OFERTA IS NULL
   AND f.ID_PRODUTO IS NOT NULL
   AND f.DT_OFERTA >= SYSDATE - 45
   AND EXISTS (SELECT 1 FROM BESAVE.LOJA_AFILIADA a
                WHERE a.ST_ATIVO = 1
                  AND ((a.DS_LOJA = 'AMAZON'        AND UPPER(f.DS_URL_FINAL) LIKE '%AMAZON.%')
                    OR (a.DS_LOJA = 'MERCADO LIVRE' AND UPPER(f.DS_URL_FINAL) LIKE '%MERCADOLIVRE.%')
                    OR (a.DS_LOJA = 'SHOPEE'        AND UPPER(f.DS_URL_FINAL) LIKE '%SHOPEE.%')))
 ORDER BY f.ID_OFERTA;

-- 3) Duplicadas de 24 h PUBLICADAS na janela do teste (esperado: 0 linhas).
--    Duas ofertas ATIVAS do mesmo produto com DT_OFERTA a menos de 24 h uma da outra.
SELECT a.ID_PRODUTO, a.ID_OFERTA AS id_a, b.ID_OFERTA AS id_b, a.VL_PRECO_POR AS preco_a,
       b.VL_PRECO_POR AS preco_b, a.DT_OFERTA AS dt_a, b.DT_OFERTA AS dt_b
  FROM OFERTA a
  JOIN OFERTA b ON b.ID_PRODUTO = a.ID_PRODUTO AND b.ID_OFERTA > a.ID_OFERTA
 WHERE a.ST_ATIVO = 1 AND b.ST_ATIVO = 1
   AND ABS(a.DT_OFERTA - b.DT_OFERTA) <= 1
   AND (a.ID_OFERTA >= :ini OR b.ID_OFERTA >= :ini)
 ORDER BY a.ID_PRODUTO, a.ID_OFERTA;

-- 4) Sessoes do robo (para o KILL SESSION; rodar como ADMIN, usuario = o do config.json -> db.usuario).
SELECT SID, SERIAL#, USERNAME, STATUS, PROGRAM
  FROM V$SESSION WHERE USERNAME = UPPER(:usuario_do_robo);
-- ALTER SYSTEM KILL SESSION '<sid>,<serial#>' IMMEDIATE;
