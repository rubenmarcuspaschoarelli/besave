# BSV-30b Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/BSV-30b/spec.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines found: `CLAUDE.md` (regras 1–2), `apps/site/CLAUDE.md` (Vitest para lógica, Playwright para fluxos), `apps/site/vite.config.ts` (`requireAssertions`), `.specs/features/BSV-30/tasks.md` (padrão de camadas).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Lógica de dados (`lib/dados/*.ts`) | unit | 1:1 com os ACs; filtro presente e ausente | `apps/site/src/lib/**/*.test.ts` | `pnpm test` |
| Componentes com regra de exibição (Grade/FotoOferta) | unit (render SSR) | IMG-01..02 | `apps/site/src/lib/componentes/*.test.ts` | `pnpm test` |
| Páginas e fluxos (home, área, navegação) | e2e | todo fluxo da spec em 390 px e 1280 px | `apps/site/e2e/*.spec.ts` | `pnpm e2e` |
| Saída do build (páginas, fontes, CSS embutido) | e2e (lê `build/`) | ARE-01, FNT-01..02, CSS-04 | `apps/site/e2e/saida.spec.ts` | `pnpm build && pnpm e2e` |
| `besave.css` | unit | FNT-01 (referência à fonte) | `apps/site/src/lib/estilo/*.test.ts` | `pnpm test` |
| Config de build | none | build gate + teste de saída | - | `pnpm build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | tarefas só com unit | `cd apps/site && pnpm test` |
| Full | tarefas com e2e | `cd apps/site && pnpm build && pnpm test && pnpm e2e` |
| Build | todas as tarefas antes do commit | `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` |

---

## Execution Plan

### Phase 1: Dados e imagens

```
T1 → T2
```

### Phase 2: Rotas

```
T3 → T4
```

### Phase 3: Desempenho do build

```
T5 → T6
```

---

## Task Breakdown

### T1: `maioresDescontos` com filtro

**What**: `maioresDescontos(cat, agora, n, f = {})` aplica o `Filtro` (área) antes de escolher os descontos.
**Where**: `apps/site/src/lib/dados/catalogo.ts`
**Depends on**: None
**Reuses**: `Catalogo.lista(f)`
**Requirement**: ARE-04

**Done when**:

- [x] Sem filtro, resultado igual ao de hoje; com `{ area }`, só cards da área, ainda ordenados por desconto
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick
**Commit**: `feat(site): maiores descontos filtrados por área`

---

### T2: Prioridade das primeiras fotos da grade

**What**: `Grade` marca os 4 primeiros cards como prioritários; `FotoOferta` tira `loading="lazy"` deles e põe `fetchpriority="high"` no primeiro.
**Where**: `apps/site/src/lib/componentes/FotoOferta.svelte`
**Depends on**: T1
**Reuses**: `Card.test.ts` (render SSR)
**Requirement**: IMG-01, IMG-02

**Done when**:

- [x] Unit (render SSR de `Grade`) e e2e na home: imgs 1–4 sem `lazy`, só a 1ª com `fetchpriority="high"`, 5ª em diante e faixa `lazy`
- [x] Gate build passa

**Tests**: e2e
**Gate**: build
**Commit**: `perf(site): primeiras fotos da grade sem lazy e com fetchpriority`

---

### T3: Página de área

**What**: componente da vitrine compartilhado pela home e pela rota `[area=area]` (matcher + `entries` dos 10 slugs), com `<h1>`, `<title>`, description e canonical da área; busca e faixa filtradas.
**Where**: `apps/site/src/routes/[area=area]/+page.svelte`
**Depends on**: None (fase 1 antes)
**Reuses**: `src/routes/+page.svelte`, `SLUG_AREA`, `ROTULO_AREA`
**Requirement**: ARE-01, ARE-02, ARE-03, ARE-04, ARE-05, ARE-06, ARE-07

**Done when**:

- [ ] e2e `area.spec.ts`: 10 slugs com h1/title/canonical/sem noindex; `/elas/` só ELAS na grade e na faixa; busca em `/elas/` só ELAS; `/xyz/` → 404; topo, favoritos e rodapé presentes
- [ ] `saida.spec.ts` (ERR-02) lista as 10 páginas novas e nenhuma outra
- [ ] Gate build passa

**Tests**: e2e
**Gate**: build
**Commit**: `feat(site): páginas de área /{slug}/`

---

### T4: Áreas como links

**What**: `Areas` sempre renderiza links (`/` e `/{slug}/`), com `aria-current="page"` no ativo; a home deixa de filtrar no lugar.
**Where**: `apps/site/src/lib/componentes/Areas.svelte`
**Depends on**: T3
**Reuses**: estilo da pílula atual
**Requirement**: LNK-01, LNK-02, LNK-03, LNK-04

**Done when**:

- [ ] e2e: "Meu Lar" na home → `/meu-lar/` ativo; "Todas" → `/` ativo; "Outros" só no "Mais" → `/outros/` com "Mais" destacado; links iguais em desejos e 404
- [ ] HOM-04 trocado pelo fluxo de links (o filtro no lugar deixou de existir por ordem da spec)
- [ ] Gate build passa

**Tests**: e2e
**Gate**: build
**Commit**: `feat(site): botões de área viram links`

---

### T5: Lato com hash

**What**: `.woff2` movidos para `src/lib/estilo/fontes/` e importados por `url()` relativo em `fontes.css`; site e `besave.css` apontam para `/_app/immutable/assets/`.
**Where**: `apps/site/src/lib/estilo/fontes.css`
**Depends on**: None (fase 2 antes)
**Reuses**: -
**Requirement**: FNT-01, FNT-02, FNT-03

**Done when**:

- [ ] Saída: woff2 com hash em `_app/immutable/assets/`, nenhum em `assets/fontes/`, `OFL.txt` mantido; `besave.css` e CSS do site citam o arquivo com hash
- [ ] e2e TOK-02 pede a fonte de `/_app/immutable/assets/`
- [ ] Gate build passa

**Tests**: e2e
**Gate**: build
**Commit**: `perf(site): Lato com hash no build (cache de 1 ano)`

---

### T6: CSS embutido no HTML

**What**: `inlineStyleThreshold: 32768` no plugin do SvelteKit.
**Where**: `apps/site/vite.config.ts`
**Depends on**: T5
**Reuses**: -
**Requirement**: CSS-04, CSS-05

**Done when**:

- [ ] Saída: home, áreas, desejos e 404 com `<style>` e sem `<link rel="stylesheet">`
- [ ] Medição antes/depois do HTML da home registrada
- [ ] Gate build passa

**Tests**: e2e
**Gate**: build
**Commit**: `perf(site): CSS da página embutido no HTML`

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | início da fase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | None (fase 1 antes) | início da fase 2 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | None (fase 2 antes) | início da fase 3 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | lógica de dados | unit | unit | ✅ |
| T2 | componente + fluxo home | unit + e2e | e2e (com unit) | ✅ |
| T3 | página e fluxo | e2e | e2e | ✅ |
| T4 | componente de navegação | e2e | e2e | ✅ |
| T5 | estilo + saída do build | e2e + unit | e2e (com unit) | ✅ |
| T6 | config de build | none + saída | e2e | ✅ |
