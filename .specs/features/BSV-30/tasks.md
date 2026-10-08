# BSV-30 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/BSV-30/spec.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines found: `CLAUDE.md` (regras 1–2), `apps/site/CLAUDE.md` (Vitest para lógica, Playwright para fluxos), `apps/worker/CLAUDE.md`, `apps/site/vite.config.ts` (`requireAssertions`).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Lógica do site (`lib/*.ts`) | unit | 1:1 com os ACs; todo edge case listado | `apps/site/src/lib/**/*.test.ts` | `pnpm test` |
| Componentes com regra de exibição (Card) | unit (render SSR) | CAR-01..06 | `apps/site/src/lib/componentes/*.test.ts` | `pnpm test` |
| Páginas e fluxos (home, desejos) | e2e | todo fluxo da spec em 390 px e 1280 px | `apps/site/e2e/*.spec.ts` | `pnpm e2e` |
| Saída do build (404, besave.css) | unit sobre o build/fonte | ERR-01..02, CSS-01..03 | `apps/site/src/lib/estilo/*.test.ts` | `pnpm test` (após `pnpm build`) |
| Estilo/tokens/config de build | none | build gate | - | `pnpm build` |
| Worker (`site.rs`) | integration | WRK-01..03 | `apps/worker/tests/*.rs` | `cargo test` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | tarefas só com unit | `cd apps/site && pnpm test` |
| Full | tarefas com e2e | `cd apps/site && pnpm build && pnpm test && pnpm e2e` |
| Build | fim de fase / sem testes | `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build` |
| Worker | T8 | `cd apps/worker && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

### Phase 1: Fundação

```
T1 → T2 → T3
```

### Phase 2: Telas

```
T4 → T5 → T6 → T7
```

### Phase 3: Worker

```
T8
```

---

## Task Breakdown

### T1: Tailwind, tokens, fontes e layout [x]

**What**: Tailwind 4 via Vite, `tokens.css` (modelo A), `fontes.css` (Lato 700/900 woff2 em `static/assets/fontes/`), `app.css`, layout raiz com `trailingSlash='always'` e `paths.relative=false`.
**Where**: `apps/site/src/lib/estilo/tokens.css`
**Depends on**: None
**Requirement**: TOK-01, TOK-02, TOK-03

**Done when**:

- [ ] `pnpm build` gera CSS com as variáveis do TOK-01 e `build/assets/fontes/lato-latin-{700,900}-normal.woff2`
- [ ] Build gate verde

**Tests**: none
**Gate**: build
**Commit**: `build(site): adiciona tailwind, tokens do modelo A e Lato auto-hospedada`

---

### T2: Formato e configuração [x]

**What**: `lib/formato.ts` (`reais`, `haQuanto`, rótulos e slugs de área) e `lib/config.ts` (links, flags, listas visíveis).
**Where**: `apps/site/src/lib/formato.ts`
**Depends on**: T1
**Requirement**: TEM-01..04, CFG-01..03

**Done when**:

- [ ] `formato.test.ts` e `config.test.ts` cobrem TEM-01..04 e CFG-01..03
- [ ] Quick gate verde

**Tests**: unit
**Gate**: quick
**Commit**: `feat(site): adiciona formato de preço e tempo e configuração de links`

---

### T3: Favoritos [ ]

**What**: `lib/favoritos.svelte.ts`: favoritos reativos persistidos no `localStorage`.
**Where**: `apps/site/src/lib/favoritos.svelte.ts`
**Depends on**: T2
**Requirement**: FAV-01..06

**Done when**:

- [ ] `favoritos.test.ts` cobre FAV-01..06 com `Storage` falso
- [ ] Quick gate verde

**Tests**: unit
**Gate**: quick
**Commit**: `feat(site): adiciona lista de desejos no localStorage`

---

### T4: Card, CardMini e BotaoFavorito [ ]

**What**: componentes do card conforme o modelo A.
**Where**: `apps/site/src/lib/componentes/Card.svelte`
**Depends on**: None (fase 1 concluída)
**Requirement**: CAR-01..06

**Done when**:

- [ ] `Card.test.ts` (render SSR) cobre CAR-01..06
- [ ] Quick gate verde

**Tests**: unit
**Gate**: quick
**Commit**: `feat(site): adiciona card de oferta do modelo A`

---

### T5: Home [ ]

**What**: Topo, BarraCanal, Busca, Areas, FaixaDescontos, Grade, Rodape e `routes/+page.svelte` ligados ao catálogo; Playwright configurado.
**Where**: `apps/site/src/routes/+page.svelte`
**Depends on**: T4
**Requirement**: HOM-01..11

**Done when**:

- [ ] `e2e/home.spec.ts` cobre HOM-02..09 em 390 px e 1280 px
- [ ] Full gate verde

**Tests**: e2e
**Gate**: full
**Commit**: `feat(site): adiciona home com faixa de descontos, recentes, busca e áreas`

---

### T6: Lista de desejos [ ]

**What**: `routes/desejos/+page.svelte`.
**Where**: `apps/site/src/routes/desejos/+page.svelte`
**Depends on**: T5
**Requirement**: DES-01..03

**Done when**:

- [ ] `e2e/desejos.spec.ts` cobre DES-01..03 e o fluxo ♡ → `/desejos/`
- [ ] Full gate verde

**Tests**: e2e
**Gate**: full
**Commit**: `feat(site): adiciona página da lista de desejos`

---

### T7: 404 e besave.css [ ]

**What**: rota `/404.html` (noindex) e rota prerenderizada `assets/besave.css` com tokens, fontes e as classes dos templates do worker restilizadas.
**Where**: `apps/site/src/lib/estilo/besave.css`
**Depends on**: T6
**Requirement**: ERR-01..02, CSS-01..03

**Done when**:

- [ ] `besave-css.test.ts` e `saida.test.ts` cobrem CSS-01..03 e ERR-01..02
- [ ] Build gate verde

**Tests**: unit
**Gate**: build
**Commit**: `feat(site): gera besave.css e 404 a partir dos tokens`

---

### T8: Worker deixa de publicar o CSS [ ]

**What**: remove a fase de CSS e a entrada `_css` do índice; testes do worker leem o CSS do site.
**Where**: `apps/worker/src/site.rs`
**Depends on**: None (fase 2 concluída)
**Requirement**: WRK-01..03

**Done when**:

- [ ] Testes de `ciclo.rs`, `dry_run.rs`, `geracao.rs` afirmam que `assets/besave.css` não é gravado e `_css` não existe no índice
- [ ] Worker gate verde

**Tests**: integration
**Gate**: worker
**Commit**: `refactor(worker): deixa de publicar besave.css (passa ao deploy do site)`

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | início da fase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | None (fase 1) | início da fase 2 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | None (fase 2) | início da fase 3 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | estilo/config de build | none | none | ✅ |
| T2 | lógica | unit | unit | ✅ |
| T3 | lógica | unit | unit | ✅ |
| T4 | componente com regra | unit | unit | ✅ |
| T5 | página/fluxo | e2e | e2e | ✅ |
| T6 | página/fluxo | e2e | e2e | ✅ |
| T7 | saída do build | unit | unit | ✅ |
| T8 | worker | integration | integration | ✅ |
