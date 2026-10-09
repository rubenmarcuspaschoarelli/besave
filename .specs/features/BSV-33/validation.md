# Validation BSV-33 — PASS (rodada 2)

**Veredito: PASS.** Os 3 mutantes que sobreviveram na rodada 1 (W5, W10, S10) agora morrem com os testes do
commit 2e4bb0b. Os mortos que reamostrei depois do rebase continuam mortos e os gates completos estão verdes.
O merge continua bloqueado pela execução real, que cabe ao dono (lacuna 6).

- **Data:** 2026-10-09
- **Verificou:** Verifier independente, sub-agente (autor ≠ verificador). Não alterou código nem testes do repositório.
- **Spec:** `docs/specs/BSV-33.md` (dono) e `.specs/features/BSV-33/spec.md` (EARS)
- **Faixa de diff:** `origin/develop..HEAD` = `c31e176..2e4bb0b` (9 commits), sobre `origin/develop` em `ebf9199`.
  `git merge-base --is-ancestor origin/develop HEAD` retorna 0. Conferi que o código do ticket é idêntico ao da rodada 1
  (`git diff ff2de72 2e4bb0b~1 -- apps/` vazio). A única diferença é o commit de testes 2e4bb0b.

## Histórico das rodadas

| Rodada | Faixa | Veredito | Achados |
| --- | --- | --- | --- |
| 1 | `cd00ec5..ff2de72` (8 commits, antes do rebase) | FAIL | Gates verdes. 22 mutantes: 18 mortos, 1 equivalente (S1) e 3 sobreviventes: **W10**, os 90% medidos sobre o total em vez da área, porque os testes de 90%/91% tinham uma área só; **W5**, expiradas contando como ativas no sitemap de páginas, sem teste no chamador; **S10**, a decisão proposta de criar entrada no histórico ao trocar de público, sem teste. Também: branch atrás de `origin/develop` (BSV-18), texto de subpágina fixo nos dados de 08/10, "Limpar filtros" sempre visível na subpágina e a execução real pendente. |
| 2 | `c31e176..2e4bb0b` (9 commits, rebase em `ebf9199`) | PASS | Lacunas 1, 2, 3 e 5 resolvidas. As lacunas 4 e o "Limpar filtros" ficam como decisão do dono. A lacuna 6 continua bloqueando o merge. |

---

## Checagem ancorada na spec

| Critério / requisito | Resultado definido na spec | Evidência `arquivo:linha` (asserção) | Status |
| --- | --- | --- | --- |
| `/elas/masculino/` 200, `<h1>`, `canonical` (SUB-01) | 200; `<h1>` "Elas · Masculino"; canonical `https://besave.com.br/elas/masculino/` | `apps/site/e2e/publico.spec.ts:59` `expect(r?.status()).toBe(200)`; `:61` `toHaveText('Elas · Masculino')`; `:64-67` canonical; `:73-74` no HTML do build; `:75` sem `noindex` | ✅ |
| 40 subpáginas prerenderizadas (SUB-01) | 10 slugs × 4 públicos | `apps/site/e2e/publico.spec.ts:79-87`; `apps/site/e2e/saida.spec.ts:47-55` (lista exata do build) | ✅ |
| `<title>` e description próprios (SUB-01) | a spec só pede que sejam "próprios" | `apps/site/e2e/publico.spec.ts:63` `toHaveTitle('Ofertas de Elas · Masculino · Besave')`; `:69-70` | ⚠️ precisão: o texto exato é proposta do autor |
| `/elas/xyz/` e `/xyz/feminino/` → 404 (SUB-02) | 404 | `apps/site/e2e/publico.spec.ts:92-93` `toBe(404)` | ✅ |
| Breadcrumb Início › Área › Público (SUB-03) | três passos, com links `/` e `/elas/` | `apps/site/e2e/publico.spec.ts:102-109` | ✅ |
| Grade só ELAS + MASCULINO (SUB-04) | só cards da área e do público | `apps/site/e2e/publico.spec.ts:119-121`, faixa `:128-130` | ✅ |
| "Masculino" → `/elas/masculino/` mantendo `?loja=` (PUB-01) | `/elas/masculino/?loja=…` | `apps/site/e2e/publico.spec.ts:147`; `apps/site/src/lib/filtros.test.ts:139-140` | ✅ |
| Troca de público cria entrada no histórico (decisão proposta, PUB-01) | voltar retorna a `/elas/?loja=…` | `apps/site/e2e/publico.spec.ts:349-351` `goBack()` + `toHaveURL(/\/elas\/\?loja=shopee$/)` | ✅ (novo) |
| "Todos" e "Limpar filtros" voltam a `/elas/` (PUB-02) | `/elas/?loja=…` / `/elas/` | `apps/site/e2e/publico.spec.ts:175`, `:188`; `apps/site/src/lib/filtros.test.ts:152-153`, `:158` | ✅ |
| `/elas/?publico=infantil` → `/elas/infantil/` com `replace` (PUB-03) | sem entrada nova no histórico | `apps/site/e2e/publico.spec.ts:199`, `:206-207` | ✅ |
| Home mantém `?publico=` (PUB-04) | `/?publico=masculino` | `apps/site/e2e/publico.spec.ts:214-215` | ✅ |
| Texto no HTML sem JS, abaixo do `<h1>` (TXT-02) | texto depois de `</h1>` na resposta direta | `apps/site/e2e/publico.spec.ts:228-238`, `:242-249` | ✅ |
| Quantidade de frases por área e por subpágina (TXT-01) | 2–3 frases por área; 1 por subpágina com volume | `apps/site/src/lib/conteudo/areas.test.ts:21-27`, `:30-32` | ✅ |
| Sem promessa de preço (TXT-01) | não há valor objetivo | `apps/site/src/lib/conteudo/areas.test.ts:35-37` (heurística) | ⚠️ revisão do texto é do dono |
| `/eles/` sem ofertas (TXT-03) | texto + "Ainda não temos ofertas aqui" + links | `apps/site/e2e/publico.spec.ts:261-271` | ✅ |
| Bundle da home ≤ 150 KiB, texto fora dele (TXT-04) | ≤ 150 KiB | `apps/site/e2e/saida.spec.ts:161,180`; `apps/site/e2e/publico.spec.ts:281-295` | ✅ |
| JSON-LD `BreadcrumbList` válido (JLD-01) | `position` 1..n, `item` absoluto | `apps/site/e2e/publico.spec.ts:326-336`, `:341`; `apps/site/src/lib/conteudo/trilha.test.ts:20` | ✅ |
| Home sempre; área com 10 entra, com 9 fica fora (SMP-02) | `/` sempre; 10 entra, 9 fora | `apps/worker/tests/sitemap_paginas.rs:54`, `:63-66` | ✅ |
| Subpágina: 20 e 90% entram; 19 e 91% ficam fora (SMP-03) | 20 e 90% entram; 19 ou 91% fora | `apps/worker/tests/sitemap_paginas.rs:78-88`, `:96-110` | ✅ |
| 90% **da área**, não do total (SMP-03) | MEU_LAR 910/1000 fica fora mesmo com ELAS 1000 no total | `apps/worker/tests/sitemap_paginas.rs:121-131` `assert_eq!(locs(&a), [... sem "/meu-lar/unissex/"])` | ✅ (novo) |
| Só ativas contam (spec do dono; edge case EARS) | expirada não conta no volume nem no `lastmod` | `apps/worker/tests/ciclo.rs:666` `!paginas.contains("/tech/")` (9 ativas + 1 expirada); `:670` `lastmod` 2026-09-21; `:673` sem 2026-09-24 | ✅ (novo) |
| `lastmod` = data em Brasília do maior `dp` (SMP-04) | AAAA-MM-DD −03:00 | `apps/worker/tests/sitemap_paginas.rs:154-176` (01:00Z cai no dia anterior), `:180-197` (subpágina usa o dela) | ✅ |
| `sitemap-paginas.xml` no index, antes dele (SMP-01) | listado; filho antes do index | `apps/worker/tests/ciclo.rs:605`, `:608`; `apps/worker/tests/site.rs:95,125`; `apps/worker/tests/geracao.rs:673` | ✅ |
| Segundo ciclo sem mudança: 0 uploads de sitemap (SMP-05) | 0 | `apps/worker/tests/ciclo.rs:642-643` | ✅ |
| `sitemap-{n}.xml` de ofertas não mudam | só ofertas | `apps/worker/tests/ciclo.rs:630-631` | ✅ |
| XML válido; limiares nomeados (SMP-06) | namespace 0.9; 10/20/90 | `apps/worker/tests/sitemap_paginas.rs:19-25`, `:46-48` | ✅ |
| 390 px e 1280 px | os dois | `apps/site/playwright.config.ts:12,16` | ✅ |
| Real (dono) | bucket, Search Console, celular | — | ⏳ **bloqueia o merge** |

Nenhuma das decisões "n — proposto" da tabela de suposições contraria a spec do dono. Os motivos estão no relatório da
rodada 1 e não mudaram.

---

## Gates (rodada 2, o runner decide)

| Gate | Resultado |
| --- | --- |
| worker `cargo fmt --check` / `cargo clippy --all-targets -- -D warnings` | ✅ / ✅ |
| worker `cargo test` (`CARGO_BUILD_JOBS=2`, target compartilhado) | ✅ 448 passaram, 0 falharam, 3 ignorados (testes de desempenho que já existiam) em 52 binários; `sitemap_paginas.rs` 10/10, `ciclo.rs` 21 (+1 ignorado) |
| site `pnpm install --frozen-lockfile` / `lint` / `check` | ✅ / ✅ / ✅ 0 erros, 0 avisos (467 arquivos) |
| site `pnpm test` | ✅ 146 em 16 arquivos: 139 em 15 arquivos sem os de desempenho, mais `desempenho.test.ts` 7/7, rodado **por último**, depois de remover o worktree de mutantes, sem cargo/rustc rodando |
| site `pnpm build` / `pnpm e2e` | ✅ / ✅ 188 passaram (celular + desktop) |

Delta em relação à rodada 1: +2 testes no worker (446 → 448) e +2 no e2e (186 → 188, o teste novo nos dois tamanhos).
Nenhum teste foi removido ou afrouxado.

---

## Sensor de discriminação (rodada 2)

Worktree temporário `git worktree add --detach <scratch>/bsv33-mut HEAD`, fora do repositório, com um mutante por vez.
No worker: `CARGO_BUILD_JOBS=1` e só `cargo test --test sitemap_paginas --test site --test ciclo --test geracao --test dry_run`.
No site: vitest (sem os de desempenho), `pnpm build` e Playwright `publico`, `saida`, `filtros` e `area` com `CI=1`.

| # | Arquivo | Mutação | Rodada 1 | Rodada 2 | Teste que matou (rodada 2) |
| --- | --- | --- | --- | --- | --- |
| W5 | `apps/worker/src/geracao.rs:253` | expiradas (`x`) contam como ativas | ❌ sobreviveu | ✅ morto | `expirada_nao_conta_no_sitemap_de_paginas` |
| W10 | `apps/worker/src/site.rs:363` | 90% medido sobre o total | ❌ sobreviveu | ✅ morto | `noventa_por_cento_e_da_area_e_nao_do_total` |
| S10 | `apps/site/src/lib/componentes/PaginaOfertas.svelte:70` | troca de público com `replace: true` | ❌ sobreviveu | ✅ morto | `publico.spec.ts:345` (voltar retorna a `/elas/`) |
| W1 | `apps/worker/src/site.rs:355` | área `>=` → `>` | ✅ | ✅ morto | `area_com_dez_entra_e_com_nove_fica_fora` |
| W3 | `apps/worker/src/site.rs:363` | `<=` 90% → `<` | ✅ | ✅ morto | `subpagina_com_vinte_e_noventa_por_cento_entra` |
| W7 | `apps/worker/src/site.rs:151` | sitemap regravado sempre | ✅ | ✅ morto | `segundo_ciclo_sem_mudanca_nao_sobe_sitemap_de_paginas` + 4 de idempotência |
| W8 | `apps/worker/src/site.rs:364` | `lastmod` da subpágina = o da área | ✅ | ✅ morto | `lastmod_da_subpagina_e_o_dela` |
| S2 | `apps/site/src/lib/filtros.ts:66` | `destinoArea` perde a query | ✅ | ✅ morto | `filtros.test.ts` + 2 e2e |
| S3 | `apps/site/src/lib/componentes/PaginaOfertas.svelte:88` | redirect de `?publico=` sem `replace` | ✅ | ✅ morto | `publico.spec.ts:193` (PUB-03) |
| S7 | `apps/site/src/hooks.server.ts:7` | JSON-LD aplicado à home | ✅ | ✅ morto | `publico.spec.ts:340` |
| S9 | `apps/site/src/lib/componentes/PaginaOfertas.svelte:92` | subpágina não aplica o público à grade | ✅ | ✅ morto | SUB-04, PUB-01, PUB-03 (8 falhas) |

Os demais da rodada 1 não foram reaplicados, porque o código deles não mudou com o rebase: W2, W4, W6 e W9 (worker)
e S4, S5, S6, S8, S11 e S12 (site) foram mortos lá. S1 (matcher `publico` aceitando qualquer valor) é equivalente
pela lição 18.

**Placar da rodada 2:** 11 mutantes, 11 mortos e 0 sobreviventes.
**Placar acumulado:** 22 mutantes distintos, 21 mortos, 1 equivalente e 0 sobreviventes.

**Isolamento:** o `git status --porcelain` do worktree real ficou vazio antes e depois. O worktree temporário foi removido
(`git worktree remove --force`, `rm -rf` do que sobrou em node_modules por causa de caminho longo, depois `git worktree prune`)
e não aparece mais em `git worktree list`.

---

## Qualidade do código

Mesma avaliação da rodada 1, porque o código não mudou: mudanças cirúrgicas, nenhuma dependência nova, template da oferta
e card intocados, `robots.txt` intacto, nenhuma página nova com `noindex`. Os testes novos de 2e4bb0b derivam da spec
(90% "da área", "ativas") e da decisão proposta da tabela (histórico), e não espelham a implementação.

---

## Pendências

**Bloqueia o merge**
- Lacuna 6, execução real do dono: `sitemap.xml` no bucket listando `sitemap-paginas.xml` com a home, as áreas
  com ofertas e as subpáginas esperadas; sitemap enviado no Search Console com "Sucesso"; `/elas/masculino/` no celular.

**Decisões do dono (não bloqueiam)**
- Lacuna 4: `TEXTO_SUBPAGINA` cobre as 7 subpáginas com volume em 08/10. O sitemap é dinâmico, então uma subpágina
  que ganhe volume depois entra nele só com o texto da área. A spec aceita isso.
- "Limpar filtros" na subpágina aparece mesmo sem filtro além do público do caminho, porque a `BarraFiltros` conta
  o público como filtro (ver `prints/elas-unissex-celular.png`). O clique leva a `/{slug}/`.
- Revisão dos textos de `apps/site/src/lib/conteudo/areas.ts` ("sem promessa de preço" só tem teste heurístico).

---

## Lições propostas (só neste relatório; não gravadas em STATE.md, LESSONS.md nem lessons.json)

- Teste de limiar relativo ("X% **da área**") precisa de um segundo grupo na entrada. Com um grupo só, os dois
  denominadores possíveis coincidem e o mutante "denominador errado" sobrevive (W10, rodada 1).
- Filtro aplicado antes de uma função pura (ativas × expiradas) precisa de teste no chamador (W5, rodada 1).
- Decisão "n — proposto" que muda comportamento observável (histórico do navegador) precisa de teste, ou um
  mutante a inverte sem nenhum alarme (S10, rodada 1).
- Mutantes do worker no Windows: `cargo test --test …` só com os binários relevantes. A suíte inteira com
  `CARGO_BUILD_JOBS=1` passou de 20 min no primeiro mutante; com o filtro, 6 mutantes levaram cerca de 10 min.
