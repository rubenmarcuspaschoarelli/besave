# BSV-35 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; `docs/specs/BSV-35.md` fixa assinaturas e regras; decisões em `spec.md` → Assumptions)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/site/CLAUDE.md` (Vitest para lógica: diff, filtro, busca), `docs/specs/BSV-35.md` (testável em Node sem DOM nem rede).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Esqueleto SvelteKit (config, rota placeholder) | none | build gate only | - | `pnpm lint && pnpm check && pnpm build` |
| Tipos (`tipos.ts`) | unit | TIP-01, TIP-02 | `apps/site/src/lib/dados/tipos.test.ts` | `pnpm test` |
| Gerador (`gerador.ts`) | unit | GER-01..03 | `apps/site/src/lib/dados/gerador.test.ts` | `pnpm test` |
| Catálogo (`catalogo.ts`) | unit | CAT-01..10 + edge cases | `apps/site/src/lib/dados/catalogo.test.ts` | `pnpm test` |
| Busca (`busca.ts`) | unit | BUS-01..08 + edge cases | `apps/site/src/lib/dados/busca.test.ts` | `pnpm test` |
| Sincronizador (`sincronizador.ts`) | unit (fetch e relógio falsos) | DIF-01, SIN-01..09, POL-01..03 + edge cases | `apps/site/src/lib/dados/sincronizador.test.ts` | `pnpm test` |
| Fachada + orçamentos (`dados.ts`) | unit | DES-01..04, PUR-01 | `apps/site/src/lib/dados/desempenho.test.ts` | `pnpm test` |
| Script `medir` (rede real) | none | build gate; execução real pelo dono | - | `pnpm check` |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/site/`. Localmente `pnpm` = `corepack pnpm@9.15.9`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `pnpm test` |
| Full | After tasks with e2e/integration tests | `pnpm test` |
| Build | After phase completion or config/entity-only tasks | `pnpm lint && pnpm check && pnpm test && pnpm build` |

---

## Execution Plan

8 tarefas, um lote: execução inline, sem sub-agentes (WORKFLOW-AGENTES §3).

### Phase 1: Base

```
T1 → T2 → T3
```

### Phase 2: Domínio

```
T3 → T4 → T5 → T6
```

### Phase 3: Fachada e medição

```
T6 → T7 → T8
```

---

## Task Breakdown

### T1: Esqueleto SvelteKit

**What**: `apps/site` com SvelteKit 3 + `adapter-static` (fallback desligado), `prerender = true`, TS strict, Vitest, ESLint + Prettier, `+page.svelte` placeholder, `pnpm-lock.yaml`.
**Where**: `apps/site/` (config)
**Depends on**: None
**Reuses**: saída de `sv create --template minimal --types ts --add eslint prettier vitest sveltekit-adapter`
**Requirement**: ESQ-01

**Done when**:

- [ ] `pnpm lint && pnpm check && pnpm build` saem 0; `build/index.html` gerado
- [ ] Sem `dependencies` de runtime

**Tests**: none
**Gate**: build

---

### T2: Tipos do contrato

**What**: `tipos.ts` com `Loja`, `Area`, `Publico`, `OfertaCard`, `ChunkRef`, `Manifest`, `Filtro`, listas dos enums e rótulos de loja.
**Where**: `apps/site/src/lib/dados/tipos.ts`
**Depends on**: T1
**Reuses**: `packages/contract/schema/*.json`
**Requirement**: TIP-01, TIP-02

**Done when**:

- [ ] Listas de enum iguais às do schema; fixtures `chunk-ok`/`manifest-ok` passam na guarda de tipo
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Gerador sintético

**What**: `gerarCards(qtd, semente)` (PRNG próprio) e `gerarManifest(cards)` (SHA-256/16, Brotli 9).
**Where**: `apps/site/src/lib/dados/gerador.ts`
**Depends on**: T2
**Reuses**: `tipos.ts`; `ajv`/`ajv-formats` como em `packages/contract/validate.mjs`
**Requirement**: GER-01, GER-02, GER-03

**Done when**:

- [ ] 30 mil cards e o manifest passam no schema; mesma semente → mesmos bytes; distribuições na tolerância
- [ ] Gate build passa (fim da fase 1)

**Tests**: unit
**Gate**: build

---

### T4: Catálogo

**What**: `normalizar`, `Catalogo` (`aplicarChunk`, `descartar`, `alvo`, `lista`, `novas`, `confirmarNovas`, `completo`, `carregados`, `total`).
**Where**: `apps/site/src/lib/dados/catalogo.ts`
**Depends on**: T3
**Reuses**: `tipos.ts`
**Requirement**: CAT-01, CAT-02, CAT-03, CAT-04, CAT-05, CAT-06, CAT-07, CAT-08, CAT-09, CAT-10

**Done when**:

- [ ] Cobertura 1:1 de CAT-01..10
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T5: Busca

**What**: `buscar(cat, consulta, f?, limite = 200)` sobre o texto pré-computado.
**Where**: `apps/site/src/lib/dados/busca.ts`
**Depends on**: T4
**Reuses**: `normalizar` e ordenação de `catalogo.ts`
**Requirement**: BUS-01, BUS-02, BUS-03, BUS-04, BUS-05, BUS-06, BUS-07, BUS-08

**Done when**:

- [ ] Cobertura 1:1 de BUS-01..08
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T6: Diff e sincronizador

**What**: `diferenca` e `criarSincronizador` (primeira carga, diff, versão, contrato, falha, polling por visibilidade, eventos).
**Where**: `apps/site/src/lib/dados/sincronizador.ts`
**Depends on**: T5
**Reuses**: `Catalogo`, `packages/contract/package.json` (versão)
**Requirement**: DIF-01, SIN-01, SIN-02, SIN-03, SIN-04, SIN-05, SIN-06, SIN-07, SIN-08, SIN-09, POL-01, POL-02, POL-03

**Done when**:

- [ ] Cobertura 1:1 com fetch e relógio falsos
- [ ] Gate build passa (fim da fase 2)

**Tests**: unit
**Gate**: build

---

### T7: Fachada e orçamentos

**What**: `src/lib/dados.ts` reexporta a API pública; testes de desempenho (30 mil cards), bundle ≤ 10 KB gzip e pureza.
**Where**: `apps/site/src/lib/dados.ts`
**Depends on**: T6
**Reuses**: gerador (T3)
**Requirement**: DES-01, DES-02, DES-03, DES-04, PUR-01

**Done when**:

- [ ] Orçamentos medidos em teste e verdes
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T8: `pnpm medir`

**What**: script Node que roda o módulo contra `BESAVE_BASE_URL` e imprime as métricas da spec, com segunda passada.
**Where**: `apps/site/scripts/medir.ts`
**Depends on**: T7
**Reuses**: `dados.ts`
**Requirement**: MED-01

**Done when**:

- [ ] `pnpm check` cobre o script; execução real colada no PR (domínio `REDACTED`)
- [ ] Gate build passa (fim da fase 3)

**Tests**: none
**Gate**: build
