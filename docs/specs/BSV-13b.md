# BSV-13b · Worker: reaproveitamento de imagens por listagem (custo e tempo) + tempo por fase

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-13 (mergeado), BSV-21 (PR #10).
MANIFEST.md §6; CONTRATO.md §6 · Tipo: correção de custo

## Contexto (medido pelo dono em 30/09/2026)
`publicar_imagens` decide o reaproveitamento com `Publicador::existem` em lote; no `PublicadorS3`
isso vira um `HeadObject` por chave (pool de 16). Com ~10,8 mil ofertas publicadas são ~21,7 mil
HEAD por ciclo. A segunda execução real sem mudanças relevantes levou **788 s** para publicar 67
imagens e 79 páginas. Com o agendamento previsto (BSV-14, ciclo de 5 min = 288 ciclos/dia), só os
HEAD custariam ~6,2 milhões de requisições/dia ≈ **US$ 75/mês**, o dobro do teto do projeto, e o
ciclo não caberia na cadência.

Anomalia a investigar (não bloqueante): na **primeira** execução real da BSV-21 todas as 21.212
imagens foram reenviadas (`imagens_reaproveitadas = 0`), embora ~11,5 mil já existissem desde
27/09; o agrupamento de `aws s3 ls` por data confirmou que todos os objetos foram regravados.
Na segunda execução, com o mesmo código, `imagens_reaproveitadas = 10.539`. O tratamento de erro
de `existe_async` (NotFound → false, demais → erro) parece correto por leitura.

## Objetivo
Um ciclo sem mudanças publica zero imagens e termina em menos de 2 minutos, com custo de
verificação de existência desprezível, e o relatório mostra quanto cada fase de `gerar()` custou.

## Solução
1. No início de `publicar_imagens`, obter **uma vez** o conjunto de chaves existentes com
   `Publicador::listar("img/ofertas/")` (no S3: `ListObjectsV2` paginado, 1000 chaves por página
   → ~22 chamadas para 21 mil objetos). Reaproveitar = as **duas** chaves do id pertencem ao
   conjunto (regra 4 da BSV-13 inalterada). O mesmo para placeholders com `listar("img/placeholder/")`.
2. `publicar_imagens` **não chama** `existe`/`existem` para imagens. `existem` continua no trait
   (chunks usam) e continua com o pool no S3.
3. Conjunto em memória como `HashSet<String>`; nada é persistido (a listagem já é a fonte de verdade
   e é barata). Não criar índice em `_estado/` para imagens.
4. **Tempo por fase** no `Relatorio` e na saída do binário, em ms: `t_leitura_fonte`,
   `t_imagens` (com sub-medida `t_imagens_listagem`), `t_chunks`, `t_paginas`, `t_redirects`
   (com sub-medida `t_redirects_listagem`), `t_manifest`, `t_orfaos`. Medido com `Instant`, sem
   dependência nova. Objetivo: localizar o próximo gargalo (suspeita: `Redirects::listar()` da
   KVS a cada ciclo, ~10,8 mil chaves).
5. **Investigação da anomalia**: examinar `existem`/`gravar_lote` do `PublicadorS3` e o fluxo da
   primeira execução (ex.: erro de HEAD convertido em "não existe", 403 vs 404 quando a política
   ainda propagava, timeouts do pool, blocos processados fora de ordem, cache do conjunto). Registrar
   a hipótese mais provável no PR com evidência de código (`file:line`). Não é bloqueante: a
   listagem substitui esse caminho para imagens.

## Regras
- Não alterar `gerar()` além de ler/propagar os tempos e trocar o mecanismo de existência nas imagens.
- Listagem que falha → erro nomeado e aborta antes do manifest (não cair para "tudo novo": isso
  reenviaria 21 mil objetos em silêncio).
- Chave listada com nome inesperado (fora de `{id}.webp` / `{id}-small.webp`) é ignorada na decisão
  e contada em `imagens_chaves_estranhas` (sem remover nada).
- `PublicadorMemoria` passa a contar chamadas de `listar`, `existe` e `existem` separadamente.
- Sem dependência nova. Sem mudança de contrato, de MANIFEST ou de headers.

## Fora de escopo
Mudar a listagem da KVS (será decidido com os tempos medidos aqui), agendamento (BSV-14),
índice de imagens em `_estado/`, reprocessamento de imagens.

## Critério de aceite
- 5000 ids com todas as imagens existentes no `PublicadorMemoria` → 0 chamadas a `existe`/`existem`
  vindas de imagens, ≤ 10 chamadas a `listar`, `imagens_publicadas = 0`, `imagens_reaproveitadas = 5000`.
- Id novo (sem chaves no conjunto) → publicado; id com só uma das duas chaves → publicado (as duas).
- Placeholder já existente → não reenviado; placeholder ausente → enviado.
- `listar` falhando → erro nomeado, nenhum manifest gravado.
- Chave estranha em `img/ofertas/` → contada, não afeta a decisão, não é removida.
- Relatório contém todas as medidas de tempo da Solução 4 (teste confere presença, não valores).
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` sem rede.
- **Real (dono):** duas execuções `--publicar --sim` seguidas; a segunda termina em **< 2 min** com
  `imagens_publicadas` ≈ ofertas novas do intervalo; o comando abaixo, rodado antes e depois,
  mostra que **nenhuma imagem antiga ganhou data nova** (só as das ofertas novas):
  `aws s3 ls s3://besave-site/img/ofertas/ | % { $_.Substring(0,10) } | Group-Object | Select Name,Count`
  Colar no PR os tempos por fase das duas execuções.

## Definition of done
PR com a hipótese da anomalia (com `file:line`), relatório real com tempos por fase, testes verdes.
