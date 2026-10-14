-- =============================================================================
-- Carga inicial de BESAVE.COMUNIDADE (2026-09-04)
-- ST_ATIVO = 1 para todas (nenhuma foi pedida como inativa).
-- =============================================================================
INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Tech',
  'Para pessoas de todas idades que gostam e consomem tecnologia atual como celulares, computadores, informatica, tvs, uma comunidade focada em quem gosta de tecnologia e está sempre ligado em inovações.',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Players',
  'jogos, consoles e novidades do mundo Gamer',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Meu Lar',
  'Para quem gosta de cuidar e decorar a sua casa ou esta pensando em um novo eletrodomestico, movel, roupas de camas, etc., ou até mesmo coisas basicas para o dia a dia  como produtos de limpeza, alimentos, etc...',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Elas',
  'Para mulheres que se interessam por moda, perfumes, saúde, beleza e estética.',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Eles',
  'Para Homens que procuram boas promoções para cuidar do corpo e do visual. (abrange moda, roupas, perfumes, calcados)',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Cultura',
  'Para quem gosta de literatura, cinema e música. (livros, etc)',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Família & filhos',
  'Para quem cuida e pensa na sua família, para familias com crianças que se interessam por brinquedos (principalmente pedagogicos) moda infantil e educacao infantil (livros, jogos), para produtos para pais livros, Mochilas maternidade, Babás eletrônicas com vídeo',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Pets',
  'Para quem tem um Pet e deseja o melhor cuidado para ele',
  1);

INSERT INTO BESAVE.COMUNIDADE (ID_COMUNIDADE, DS_COMUNIDADE, OBS_COMUNIDADE, ST_ATIVO)
VALUES (BESAVE.SEQ_COMUNIDADE.NEXTVAL, 'Esporte & vida',
  'Para quem se preocupa em  quer cuidar do corpo e da mente.',
  1);

COMMIT;
