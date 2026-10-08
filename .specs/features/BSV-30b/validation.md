# BSV-30b Validation

**Result**: PASS

**Date**: 2026-10-08
**Spec**: `.specs/features/BSV-30b/spec.md` (EARS) e `docs/specs/BSV-30b.md` (dono)
**Diff range**: `origin/develop..HEAD` = `b7e52d3..d1c5fc1` (6 commits)
**Verifier**: Verifier sub-agente independente (autor ≠ verificador). Leitura do tree real; mutantes num `git worktree` descartável fora do repo.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `maioresDescontos` com filtro | ✅ Done | b7e52d3 |
| T2 prioridade das fotos | ✅ Done | 5df119a |
| T3 página de área | ✅ Done | 72e2b3f |
| T4 áreas como links | ✅ Done | 40385d8 |
| T5 Lato com hash | ✅ Done | 2c98647 |
| T6 CSS embutido | ✅ Done | d1c5fc1 |

Escopo: o diff toca só `apps/site/` e `.specs/features/BSV-30b/` (`git diff --stat origin/develop..HEAD -- . ':!apps/site' ':!.specs'` vazio).
Dependências: `apps/site/package.json` e lockfile sem diff contra `origin/develop` (regra 2).

---

## Gate Check

Comando (em `apps/site/`): `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && CI=1 pnpm e2e`

| gate | resultado |
| ---- | --------- |
| install `--frozen-lockfile` | ok ("Lockfile is up to date") |
| lint (prettier + eslint) | ok |
| check (svelte-check) | 447 arquivos, 0 erros, 0 avisos |
| test (vitest) | **109/109** passed, 12 arquivos |
| build | ok ("Wrote site to build") |
| e2e (Playwright, `CI=1`, projetos `celular` 390 px e `desktop` 1280 px) | **88/88** passed |

- Primeira rodada: `desempenho.test.ts` DES-01/DES-02 (tempo, fora do diff) falharam porque rodavam junto com `pnpm install` e mutantes no scratch (máquina carregada, lição 15 do WORKFLOW). Reexecução sem carga: 109/109. Não é regressão da BSV-30b.
- Contagem antes → depois: unit 105 → 109 (+3 `Grade.test.ts`, +1 `catalogo.test.ts`); e2e 46 → 88 (+21 por projeto: 15 em `area.spec.ts`, +3 em `home.spec.ts` — HOM-04 virou 3 testes de links + 1 de imagens —, +3 em `saida.spec.ts`). Nenhum teste removido sem substituto: HOM-04 (filtro no lugar) foi trocado pelos fluxos de link porque a spec eliminou o filtro no lugar.
- Skips: nenhum.

---

## Spec-Anchored Acceptance Criteria

Todo e2e roda nos dois projetos: `apps/site/playwright.config.ts:10` (`celular`, 390×844) e `apps/site/playwright.config.ts:14` (`desktop`, 1280×800).

| Critério | Resultado definido na spec | `arquivo:linha` + asserção | Result |
| -------- | -------------------------- | -------------------------- | ------ |
| ARE-01 build gera exatamente as 10 áreas e nenhuma outra página | lista exata de HTML | `apps/site/e2e/saida.spec.ts:33` - `expect(htmls).toEqual([...404, desejos, index, 10×{slug}/index.html].sort())` | ✅ PASS |
| ARE-02 `/{slug}/` 200, h1, title, description, canonical | 200; "Ofertas de {Rótulo}"; "Ofertas de {Rótulo} · Besave"; description cita rótulo; canonical `https://besave.com.br/{slug}/` | `apps/site/e2e/area.spec.ts:31` `expect(r?.status()).toBe(200)`; `:33` `toHaveText(\`Ofertas de ${rotulo}\`)`; `:35` fontFamily `toMatch(/^"?Lato"?,/)`; `:36` `toHaveTitle(\`Ofertas de ${rotulo} · Besave\`)`; `:37` canonical `toHaveAttribute('href', \`https://besave.com.br/${slug}/\`)`; `:42` `expect(descricao).toContain(rotulo)`; `:45` canonical no HTML do build | ✅ PASS (10 slugs × 2 viewports) |
| ARE-03 sem `noindex` | nenhum `<meta name="robots" … noindex>` | `apps/site/e2e/area.spec.ts:46` - `expect(html).not.toMatch(/<meta name="robots"[^>]*noindex/)` | ✅ PASS |
| ARE-04 `/elas/` grade e faixa só ELAS, ≥ 1 cada | conjunto = {ELAS}, não vazio | `apps/site/e2e/area.spec.ts:56-57` - `grade.length > 0`, `new Set(grade)).toEqual(new Set(['ELAS']))`; `:62-63` faixa idem; unidade `apps/site/src/lib/dados/catalogo.test.ts:198` - `maioresDescontos(…, { area: 'ELAS' })).toEqual([22, 20])` | ✅ PASS |
| ARE-05 busca "protetor" em `/elas/` só ELAS com o termo; na home > 1 área | ids = ELAS ∩ título com termo; home ≥ 2 áreas | `apps/site/e2e/area.spec.ts:79` - `new Set(areas).size).toBeGreaterThan(1)`; `:85` `toHaveCount(esperados.length)`; `:90` `expect(ids.sort()).toEqual(esperados)` | ✅ PASS |
| ARE-06 `/xyz/` → 404 | status 404 | `apps/site/e2e/area.spec.ts:96` - `expect((await request.get(p)).status(), p).toBe(404)` (`/xyz/`, `/elas-x/`) | ✅ PASS |
| ARE-07 barra, topo, ♡/contador, "Ver mais", rodapé | elementos presentes; contador 1; 40 → 80 | `apps/site/e2e/area.spec.ts:109-111` visíveis/rodapé; `:114` `contador toHaveText('1')`; `:115`/`:117` `toHaveCount(40)` → `toHaveCount(80)` | ✅ PASS |
| LNK-01 links `/` e `/{slug}/` em home, área, desejos, 404 | lista exata texto→href | `apps/site/e2e/home.spec.ts:113` - `expect(links, url).toEqual(esperado)` para `/`, `/elas/`, `/desejos/`, `/404.html` | ✅ PASS |
| LNK-02 "Meu Lar" → `/meu-lar/`, só ele `aria-current` | URL `/meu-lar/`; ativos = ['Meu Lar'] | `apps/site/e2e/home.spec.ts:62` `toHaveURL(/\/meu-lar\/$/)`; `:64` `expect(await ativos()).toEqual(['Meu Lar'])` | ✅ PASS |
| LNK-03 "Todas" → `/` ativo | URL `/`; ativos = ['Todas'] | `apps/site/e2e/home.spec.ts:70-71` - `toHaveURL(/:\d+\/$/)`, `ativos()).toEqual(['Todas'])` | ✅ PASS |
| LNK-04 "Outros" só no "Mais", `/outros/`, "Mais" destacado | oculto fora do menu; `aria-current`; destaque visual | `apps/site/e2e/home.spec.ts:78` `toBeHidden()`; `:83` `toHaveURL(/\/outros\/$/)`; `:87` `toHaveAttribute('aria-current','page')`; `:89` `toHaveCSS('background-color','rgb(11, 110, 79)')` | ✅ PASS |
| FNT-01 Lato 700/900 em `_app/immutable/assets/` com hash, citada pelo CSS do site e `besave.css` | `url(/_app/immutable/assets/lato-latin-{peso}-normal.{hash}.woff2)` nos dois | `apps/site/e2e/saida.spec.ts:101` `expect(arquivo).toBeDefined()` (regex com hash ≥ 6); `:103` `expect(besave).toContain(\`url(${url})\`)`; `:107` CSS do site/HTML contém a URL | ✅ PASS |
| FNT-02 sem `.woff2` em `assets/fontes/`, `OFL.txt` fica | conteúdo = ['OFL.txt'] | `apps/site/e2e/saida.spec.ts:111` - `toEqual(['OFL.txt'])` | ✅ PASS |
| FNT-03 Lato 900 vem de `/_app/immutable/assets/`, logo e títulos em Lato | pedido da fonte com hash, nenhum de `/assets/fontes/` | `apps/site/e2e/saida.spec.ts:85` regex `/_app/immutable/assets/lato-latin-900-normal.[hash].woff2`; `:87` `filter(startsWith('/assets/fontes/'))).toEqual([])`; `:75`/`:78` fontFamily Lato | ✅ PASS |
| CSS-04 CSS num `<style>`, nenhum `<link rel="stylesheet">` (index, área, desejos, 404) | `<style>` com o CSS; nenhum link de CSS **ativo** | `apps/site/e2e/saida.spec.ts:127-128` `estilo.length > 10_000` e `toContain('--cor-marca:#0b6e4f')`; `:131-132` todo link de CSS `disabled` + `media="(max-width: 0)"`; `:148` rede: `expect(css, url).toEqual([])` em `/` e `/elas/` | ⚠️ PASS com observação (ver O1) |
| CSS-05 HTML da home medido antes/depois | registro bruto e gzip | medição do Verifier abaixo; confere com `.specs/features/BSV-30b/tasks.md:175` | ✅ PASS |
| IMG-01 4 primeiras sem `lazy`, 1ª `fetchpriority="high"`, 2ª–4ª sem `fetchpriority` | `[[null,'high'],[null,null]×3]` | `apps/site/e2e/home.spec.ts:248` - `expect(attrs.slice(0, 4)).toEqual([[null,'high'],[null,null],[null,null],[null,null]])`; unidade `apps/site/src/lib/componentes/Grade.test.ts:31-33` | ✅ PASS |
| IMG-02 5ª em diante e faixa `lazy`, sem `fetchpriority` | `['lazy', null]` | `apps/site/e2e/home.spec.ts:254` (grade) e `:260-261` (faixa, 8 imgs) - `toEqual(['lazy', null])`; unidade `Grade.test.ts:38` | ✅ PASS |

**Critério do dono (`docs/specs/BSV-30b.md`)**: Playwright 390/1280 — os 10 slugs 200 + h1 + canonical, `/elas/` só ELAS, `/xyz/` 404, "Meu Lar" ativo, "Todas" volta, busca em `/elas/` — todos cobertos acima. Build: fonte com hash ✅, CSS embutido ✅ (O1), 4 primeiras sem lazy e 1ª com fetchpriority ✅ (O2). "Real (dono)" fora do alcance do Verifier: bloqueia o merge.

### CSS-05 — medição do Verifier (build local, `build/index.html`)

| | HTML bruto | HTML gzip -9 | pedidos de CSS |
| - | - | - | - |
| antes (2c98647) | 12.648 B | 3.145 B | 1 bloqueante, `0.DDZQ_ctd.css` 19.729 B / 4.971 B gzip |
| depois (d1c5fc1) | 32.427 B | 7.867 B | 0 |

`/elas/` 32.434 B (7.877 gzip), `desejos/` 29.416 B, `404.html` 28.107 B. Bate com a tabela do autor (diferença de 1–2 B do nível de gzip).

---

## Discrimination Sensor

Scratch: `git worktree add <temp>/verif-bsv30b HEAD`, `pnpm install --frozen-lockfile`; cada mutante aplicado, testado, revertido com `git checkout -- .` (+ `git clean`). Lotes de 6, 5, 6 e 5; e2e sempre sequencial (`CI=1`, porta 4173). Ao fim: scratch removido, `git worktree prune`, `git status --porcelain` do tree real idêntico à baseline (vazia).

| # | Mutação | Arquivo | Teste que matou | Resultado |
| - | ------- | ------- | --------------- | --------- |
| a | `maioresDescontos` ignora `f` (`cat.lista()`) | `src/lib/dados/catalogo.ts:90` | `catalogo.test.ts` "ARE-04: filtro de área" | ✅ KILLED |
| b1 | prioridade só nas 3 primeiras (`i < 3`) | `src/lib/componentes/Grade.svelte:9` | `Grade.test.ts` IMG-01 | ✅ KILLED |
| b2 | prioridade nas 5 primeiras (`i < 5`) | `Grade.svelte:9` | `Grade.test.ts` IMG-02 | ✅ KILLED |
| c1 | `fetchpriority="high"` nas 4 | `src/lib/componentes/FotoOferta.svelte:29` | `Grade.test.ts` IMG-01 | ✅ KILLED |
| c2 | `fetchpriority` em nenhuma | `FotoOferta.svelte:29` | `Grade.test.ts` IMG-01 | ✅ KILLED |
| c3 | `high` na 2ª em vez da 1ª | `Grade.svelte:9` | `Grade.test.ts` IMG-01 | ✅ KILLED |
| d | faixa (`CardMini`) sem lazy | `src/lib/componentes/CardMini.svelte:16` | `home.spec.ts` "prioridade das fotos da grade" (2 projetos) | ✅ KILLED |
| e | matcher aceita qualquer slug | `src/params.ts:10` | — | ⚪ SURVIVED (equivalente na saída estática, O3) |
| f | `entries` sem `outros` | `src/routes/[area=area]/+page.ts:7` | — | ⚪ SURVIVED (equivalente: o crawler gera `/outros/` pelo link do menu; conferido no build, O3) |
| g1 | canonical com o enum (`/TECH/`) | `src/routes/[area=area]/+page.svelte:15` | `area.spec.ts` ARE-02 | ✅ KILLED |
| g2 | título "Ofertas {rótulo}" | `[area=area]/+page.svelte:10` | `area.spec.ts` ARE-02 | ✅ KILLED |
| h1 | sem `aria-current` | `src/lib/componentes/Areas.svelte:24` | `home.spec.ts` LNK-02/04 | ✅ KILLED |
| h2 | "Todas" sempre ativo | `Areas.svelte:24` | `home.spec.ts` LNK-02 | ✅ KILLED |
| h3 | link de área volta a `/?area=slug` | `Areas.svelte:23` | `home.spec.ts` LNK-01/02 | ✅ KILLED |
| i | `inlineStyleThreshold: 1000` | `apps/site/vite.config.ts:19` | `saida.spec.ts` CSS-04 + rede | ✅ KILLED |
| j | `fontes.css` de volta a `/assets/fontes/` com woff2 em `static/` | `src/lib/estilo/fontes.css:8,15` | `besave-css.test.ts` "declara a Lato auto-hospedada" | ✅ KILLED |
| k | busca da área sem filtro de área | `src/lib/componentes/PaginaOfertas.svelte:35` | `area.spec.ts` ARE-05 | ✅ KILLED |
| l | `noindex` na página de área | `[area=area]/+page.svelte:9` (`<svelte:head>`) | `area.spec.ts` ARE-03 | ✅ KILLED |
| m | faixa da área sem filtro | `PaginaOfertas.svelte:27` | `area.spec.ts` ARE-04 | ✅ KILLED |
| n | grade da área sem filtro (`lista({})`) | `PaginaOfertas.svelte:38` | `area.spec.ts` ARE-04/05, `home.spec.ts` LNK-02 | ✅ KILLED |
| o | "Mais" sem `data-ativo` | `Areas.svelte:43` | `home.spec.ts` LNK-04 | ✅ KILLED |
| o2 | "Mais" sem `!bg-marca` (desenho) | `Areas.svelte:41` | `home.spec.ts` LNK-04 (`toHaveCSS`) | ✅ KILLED |

**Sensor depth**: reforçado (22 mutantes de comportamento).
**Result**: 20/20 mutantes não equivalentes mortos; 2 sobreviventes equivalentes (sem diferença observável no build estático) — PASS.

---

## Code Quality

| Princípio | Status |
| --------- | ------ |
| Código mínimo / sem scope creep | ✅ — home e área compartilham `PaginaOfertas.svelte`; nada de BSV-31/33 |
| Mudanças cirúrgicas, só `apps/site/` | ✅ |
| Svelte 5 runes (`$props`, `$state`, `$derived`), sem stores | ✅ |
| Tailwind sem CSS ad hoc | ✅ (`aria-[current=page]:`, `class:!bg-marca`); `fontes.css` só troca o `url()` |
| Sem dependência nova | ✅ |
| Asserções batem com o valor da spec | ✅ (O1 é interpretação, não asserção fraca) |
| Todo teste novo mapeia AC | ✅ (`Grade.test.ts` "2 cards" = borda de IMG-01) |
| Guias seguidos | `CLAUDE.md`, `apps/site/CLAUDE.md` |

---

## Edge Cases

- [x] Área sem oferta: mensagem "Nenhuma oferta nesta área agora." no componente compartilhado (`PaginaOfertas.svelte:94`); sem teste novo (declarado na spec).
- [x] Manifest falha: mesmo alerta da home (`PaginaOfertas.svelte:70`), coberto pelos testes de borda da BSV-30.
- [ ] Navegar `/elas/` → `/tech/` sem recarregar zera busca e "Ver mais": implementado com `{#key data.area}` (`src/routes/[area=area]/+page.svelte:19`), **sem teste** (G2).

---

## Lacunas (ranqueadas; nenhuma bloqueia o PASS)

1. **G1 (baixa) — matcher e `entries` não são discriminados por teste** (mutantes e, f). Na saída estática são redundantes: o crawler gera os 10 slugs a partir do menu e o S3/preview dá 404 para o resto. O matcher só muda o roteamento no cliente (um link para `/xyz/` seria renderizado com área indefinida em vez de 404), e nenhuma página gera esse link. Aceitável; se quiser fechar, um teste que navegue no cliente para slug inválido.
2. **G2 (baixa) — reset de estado entre áreas** (edge case da spec) sem teste.
3. **G3 (doc) — spec.md cita `src/params/area.ts`**; a implementação usa `src/params.ts` com `defineParams` (SvelteKit 3). Comportamento igual; corrigir o texto da spec.

## Observações

- **O1 — `<link rel="stylesheet" disabled media="(max-width: 0)">`.** O SvelteKit insere esse link de propósito para CSS embutido (`node_modules/@sveltejs/kit/src/runtime/server/page/render.js:317-320`: "don't load stylesheets that are already inlined / include them in disabled state so that Vite can detect them"). Link `disabled` não é baixado nem bloqueia a renderização; o teste de rede (`apps/site/e2e/saida.spec.ts:148`) prova zero pedidos de CSS em `/` e `/elas/`, e o mutante i (limiar 1000) é morto por ele. **Julgamento: atende à intenção da spec** (sem pedido bloqueante), não à letra ("sem `<link rel="stylesheet">`"). Remover o link exigiria pós-processar o HTML e quebraria a detecção do roteador. Sugestão: o dono ajusta a redação do critério para "nenhum `<link rel="stylesheet">` ativo".
- **O2 — "4 primeiras imagens" no build.** A grade é montada no cliente (o HTML do build só tem o esqueleto), então o critério "Build: … 4 primeiras imagens" é verificado no render SSR do componente (`Grade.test.ts`) e no DOM real (`home.spec.ts:248`), não no `index.html`. Equivalente para o LCP.
- **O3 — `/?area=` deixou de ser lido** (decisão "n — proposto" na spec.md). Nenhum produtor de `?area=` no repo (worker/template incluídos); links antigos compartilhados abrem a home com todas. Confirmar com o dono.
- **O4 — `besave.css` (páginas do worker) agora aponta para `/_app/immutable/assets/lato-…woff2`.** Fica atrelado à carência de 7 dias do `_app/` (AD-079). Os `.woff2` antigos de `assets/fontes/` continuam no bucket (deploy sem `--delete`). Na execução real, conferir que a fonte responde `max-age=31536000, immutable` e que uma página de oferta já publicada carrega a Lato.
- **O5 — Bundle inicial**: autor registra 117.893 B JS + 19.729 B CSS = 137.622 B ≤ 150 KB (`tasks.md:184`); o Verifier não mediu de novo o JS, só o CSS (19.729 B, confere).
- **O6 — `desempenho.test.ts`** (fora do diff) falha com a máquina carregada; passou isolado.

## Bloqueia o merge (execução real do dono)

`curl -I https://besave.com.br/{slug}/` 200 nos 10; "Mais ofertas de {Área}" e menu numa página de oferta; PageSpeed celular ≥ 90 nas 4 categorias na home e em `/elas/` (prints); fonte com `max-age=31536000, immutable`.

## Lições propostas (para o dono; não gravadas em LESSONS.md)

1. Em site com prerender por crawler, `entries` e matcher são redundantes na saída estática: testar comportamento de roteamento no cliente se forem requisitos, senão aceitar o mutante como equivalente.
2. Não rodar testes de tempo (`desempenho.test.ts`) em paralelo com `pnpm install`/build de outro worktree: gera falso vermelho (reforça a lição 15).
3. Critério de "sem `<link rel=stylesheet>`" deve dizer "ativo/bloqueante": o framework mantém um link desativado de propósito.

---

## Summary

**Overall**: ✅ Ready (falta a execução real do dono)
**Spec-anchored check**: 18/18 ACs com evidência; 0 lacunas de precisão; 1 observação de interpretação (O1)
**Sensor**: 22 injetados, 20 mortos, 2 sobreviventes equivalentes
**Gate**: lint ok, check 0 erros, vitest 109/109, build ok, e2e 88/88
