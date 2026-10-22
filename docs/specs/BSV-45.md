# BSV-45 · Worker: imagem de oferta reenviada por hash, não por existência de chave

**Papel:** Backend Rust · **Pasta:** `apps/worker/` + `docs/MANIFEST.md`
(regra 10: chave nova no S3 entra com a adaptação do worker) · **Depende de:** BSV-13b, BSV-21 (mergeados).
MANIFEST.md §1, §4, §6; CONTRATO.md §6; AD-028, AD-041, AD-042, AD-044

## Contexto
O worker decide o envio de imagem por **existência de chave**: `ImagensExistentes::listar` lista
`img/ofertas/` a cada ciclo e `processar_bloco` pula o id cujas duas chaves já estão no bucket
(`apps/worker/src/imagens.rs:322`). Imagem trocada no espelho local com o mesmo id nunca sobe.

Isso apareceu em 19/10/2026: o backfill do `capture-store-pages` trocou a foto de 15 ofertas da
diaenoite (foto do WhatsApp → foto da página da loja) e o site continuou servindo a antiga. Foi preciso
apagar as 30 chaves do bucket à mão e invalidar o CloudFront para o worker reenviá-las. Todo backfill de
imagem vai exigir esse passo manual enquanto a decisão for por existência.

A página de oferta já resolveu o mesmo problema por hash: `_estado/paginas.json` guarda `id → hash16`
e o worker sobe só o que mudou (`apps/worker/src/site.rs:22`, AD-041). Falta fazer o mesmo com a imagem.

O custo atual pesa a favor da troca. Medido em 19/10/2026 contra `besave-site`:

| | hoje | com índice |
|---|---|---|
| `img/ofertas/` | 59.597 chaves, 822 MB | — |
| chamadas por ciclo | **60 `ListObjectsV2`** (+1 de `img/placeholder/`) | **1 `GetObject`** |
| bytes lidos | listagem de 59.597 chaves | ~840 KB |

O comentário em `imagens.rs:227` ainda diz "~22 `ListObjectsV2` para 21 mil objetos" (BSV-13b): o
catálogo quase triplicou desde então e a listagem cresce junto. Já é o segundo defeito dessa forma —
o primeiro foi a listagem da KVS, 300–490 s por ciclo (lição 8, AD-044).

## Objetivo
O envio de imagem de oferta passa a ser decidido por hash do conteúdo, igual ao da página, e a listagem
de `img/ofertas/` sai do caminho quente do ciclo.

## Saídas
1. **`_estado/imagens.json`** (chave nova; `publicador.rs:117` já manda `_estado/*.json` com `no-store`,
   nada a mudar no header): objeto JSON plano `id → hash16`, no molde do `paginas.json`:
   ```json
   {"5412":"9f2a1c3b4d5e6f70","5413":"77b0e4d5c6b7a890","_placeholders":"1"}
   ```
   `hash16` = 16 primeiros hex do SHA-256 da **concatenação dos dois arquivos de origem** lidos do
   espelho local (`{id}.webp` ++ `{id}-small.webp`), reusando `paginas::hash16`. Hash da origem, não do
   que sobe: o `ajustar_small` é função determinística da origem, então a origem identifica o par
   publicado e não é preciso hashear duas vezes.
2. **Decisão por hash em `publicar_imagens`:** lê o índice uma vez por ciclo, hasheia a origem de cada
   id publicável e sobe só quando o hash difere do índice (ou o id não está nele). Índice regravado
   **depois** dos uploads do ciclo, e só quando mudou — mesma ordem do `paginas.json` (AD-041).
3. **Listagem só na reconstrução** (padrão do `redirects.json`, AD-044): o worker lista `img/ofertas/`
   quando o índice está ausente, ilegível ou fora do formato, quando `BESAVE_IMAGENS_RELISTAR=1`, e numa
   **reconciliação periódica** controlada por `BESAVE_IMAGENS_RELISTAR_HORAS` (padrão 24). Nos demais
   ciclos a listagem não acontece. `img/placeholder/` continua listado todo ciclo: são 10 chaves, 1
   chamada.
4. **Relatório:** `t_imagens_listagem` passa a aparecer também no ciclo agendado
   (`apps/worker/src/execucao.rs:216-224` tem `t_imagens` mas não `t_imagens_listagem`; o
   `main.rs:258` já tem). Sem isso não há como medir o antes/depois na execução real (lição 8).
   Acrescentar `imagens_reenviadas` ao `RelatorioImagens` (hoje há `reaproveitadas`, `sem_origem`,
   `reprocessadas`, `chaves_estranhas`), distinguindo imagem nova de imagem trocada.
5. **MANIFEST.md:** `_estado/imagens.json` no §1; §6 passo 1 descreve a decisão por hash e diz que a
   listagem virou caminho de reconstrução; §4 sem mudança (já coberto por `_estado/*.json`).

## Regras
1. **Reconciliação limita o estrago de mexida manual no bucket.** Chave apagada à mão com o índice
   intacto só volta na janela de `BESAVE_IMAGENS_RELISTAR_HORAS`. É o preço de não listar todo ciclo e
   precisa estar escrito no MANIFEST §6, não só no código.
2. Id sem origem em disco (`sem_origem`) ou com falha de envio **não entra** no índice: o ciclo seguinte
   tenta de novo. Mesmo critério das páginas, em que o render que falha mantém o hash anterior.
3. Expurgo (MANIFEST §6 passo 7) continua removendo por chave (`chave_small`/`chave_grande`, não depende
   de listagem) e passa a **tirar o id do índice** no mesmo passo.
4. Idempotência (AD-028): segundo ciclo sem mudança no espelho → 0 uploads de imagem, 0 listagem de
   `img/ofertas/`, índice não regravado.
5. Primeiro ciclo depois do deploy: índice ausente → uma listagem, índice construído, **0 uploads**
   (o conteúdo não mudou). Registrar no PR o tempo dessa execução.
6. `_estado/imagens.json` só carrega id e hash — nunca URL de afiliado nem segredo (AD-055).
7. Sem dependência nova (`sha2` e `serde_json` já estão no worker).

## Fora de escopo
- `img/produtos/` e `img/avisos/` (a imagem do aviso já tem `_estado/avisos.json`).
- Invalidação de CloudFront pelo worker: as chaves de oferta são `immutable` de 1 ano e **sobrescrever
  uma chave existente continua exigindo invalidação**. Esta spec faz a imagem nova chegar ao bucket; quem
  já tem a antiga em cache continua com ela. Decidir se o worker invalida, e com que orçamento de
  caminhos, é ticket próprio — anotar no PR como decisão proposta.
- Backfill de imagem no `capture-store-pages` (já existe, `programas_ajuste/backfill_imagens_oferta.py`).
- Reduzir o `paginas.json`/`redirects.json`, que têm o mesmo porte (678 KB e 694 KB).

## Critério de aceite
Testes com fakes de `Publicador` e espelho local temporário; nenhum deles espelha a implementação.

- **O defeito de 19/10:** id já publicado, arquivo trocado no espelho com o mesmo nome → sobe de novo,
  `imagens_reenviadas = 1`, sem apagar chave nenhuma.
- **Inalterado:** mesmo espelho duas vezes → 2º ciclo com 0 uploads, 0 listagem de `img/ofertas/`,
  índice não regravado.
- **Id novo:** não está no índice → sobe e entra no índice.
- **Índice ausente / JSON inválido / valor fora do formato** → lista, reconstrói, segue sem erro (WARN no
  caso inválido); o ciclo seguinte já não lista.
- **Reconciliação:** com `BESAVE_IMAGENS_RELISTAR_HORAS=0` a listagem acontece todo ciclo; com o padrão,
  não acontece antes da janela. Chave apagada no fake + índice intacto → não volta antes da janela, volta
  depois (o teste prova as duas metades, senão não discrimina).
- **`sem_origem` e falha de envio** não gravam hash: o ciclo seguinte tenta o mesmo id de novo.
- **Expurgo:** id que sai do conjunto → 2 chaves removidas **e** id fora do índice; reentrada do mesmo id
  depois sobe de novo.
- **Placeholders:** ausente → publicado; presente → não republicado (comportamento de hoje, preservado).
- **Orçamento:** índice de 30.000 ids ≤ 1 MB (fixture sintética).
- **Relatório:** linha do ciclo agendado traz `t_imagens_listagem` e `imagens_reenviadas`.
- **Gates:** `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`.
- **Real (dono):** rodar o binário da branch contra o Oracle e o bucket de produção, três ciclos
  seguidos — 1º constrói o índice (anotar `t_imagens_listagem` antes e depois, com aquecimento e
  mediana, lição 15/17), 2º e 3º sem listagem e sem upload; depois trocar à mão uma imagem no espelho e
  conferir que ela sobe sozinha no ciclo seguinte, sem apagar chave no S3.

## Definition of done
PR com: MANIFEST.md atualizado na mesma PR, `t_imagens_listagem` antes/depois da execução real,
`validation.md` do Verifier independente (autor ≠ verificador, com sensor de discriminação; mutantes em
lotes de 5 a 10 e `CARGO_BUILD_JOBS=1`, lição 13), testes verdes, e as decisões propostas
(reconciliação periódica; invalidação de CloudFront como ticket separado) listadas no resumo para o dono
levar ao `docs/DECISOES.md`.
