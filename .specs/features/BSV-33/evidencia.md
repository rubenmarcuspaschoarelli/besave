# BSV-33 — evidência

- `sitemap-paginas-real.xml`: saída de `worker::site::sitemap_paginas` sobre os 26.204 cards dos chunks
  públicos de `https://besave.com.br/manifest.json` (contrato 1.5.0), baixados em 09/10/2026. Não é o
  ciclo real (Oracle → S3), que é do dono. 18 URLs: home, as 10 áreas (todas com ≥ 10 ativas) e 7 subpáginas.
- Ativas por área e público na mesma base: ELAS 17.903 (FEMININO 16.876, UNISSEX 1.026, INFANTIL 1);
  MEU_LAR 5.002 (UNISSEX 4.940, FEMININO 60); ESPORTE_VIDA 1.439 (UNISSEX 944, FEMININO 419,
  MASCULINO 74); ELES 718 (MASCULINO 717); TECH 686; FAMILIA 242 (INFANTIL 214, UNISSEX 20);
  OUTROS 159; PETS 29; CULTURA 15; PLAYERS 11.
- `prints/`: build local (`vite preview`) com manifest, chunks e imagens reais de besave.com.br, em
  390 × 844 e 1280 × 800: `/elas/`, `/elas/unissex/`, `/esporte-vida/feminino/` e `/elas/masculino/`
  (sem ofertas: estado vazio). As contagens dos prints são da hora da captura (os dados reais mudam).
- Bundle inicial da home (BUD-01): 149,9 KiB antes da BSV-33 (após a 31); 150,2 KiB com a T4 sem
  ajuste; **149,7 KiB** no final (JS 130.992 B + CSS 22.278 B = 153.270 B), com o painel de filtros
  do celular sob demanda e o JSON-LD gerado no prerender.
- Regra 11: nenhum token, ID, caminho de usuário ou hostname interno nestes arquivos.
