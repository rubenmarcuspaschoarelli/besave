# BSV-31 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/BSV-31/spec.md`
**Status**: In progress (revisão do dono)

---

## Test Coverage Matrix

> Guidelines found: `CLAUDE.md` (regras 1–2, 9), `apps/site/CLAUDE.md` (Vitest para lógica, Playwright para fluxos), `apps/site/vite.config.ts` (`requireAssertions`), `docs/WORKFLOW-AGENTES.md` lição 15 (tempo com aquecimento e mediana).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Lógica de dados (`lib/dados/*.ts`) | unit | 1:1 com DAD-01..03, fronteiras; DAD-04 por tempo | `apps/site/src/lib/dados/*.test.ts` | `pnpm test` |
| Leitura/escrita da URL (`lib/filtros.ts`) | unit | 1:1 com URL-01..03 | `apps/site/src/lib/filtros.test.ts` | `pnpm test` |
| Barra, painel e página (fluxos) | e2e | todo fluxo da spec em 390 px e 1280 px | `apps/site/e2e/filtros.spec.ts` | `pnpm e2e` |
| Config de build | none | build gate | - | `pnpm build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | tarefas só com unit | `cd apps/site && pnpm test` |
| Full | tarefas com e2e | `cd apps/site && pnpm build && pnpm test && pnpm e2e` |
| Build | todas as tarefas antes do commit | `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` |

---

## Execution Plan

### Phase 1: Lógica e tela

```
T1 → T2 → T3 → T4 → T5 → T6 → T7
```

---

## Task Breakdown

### T1: Faixa de preço e "só com cupom" no `Filtro`

**What**: `Filtro` ganha `faixa` e `soComCupom`; `casaFiltro` (usado por `lista` e `buscar`) respeita os dois.
**Where**: `apps/site/src/lib/dados/tipos.ts`, `catalogo.ts`, `catalogo.test.ts`, `busca.test.ts`, `desempenho.test.ts`, `apps/site/src/lib/dados.ts`
**Depends on**: None
**Reuses**: `casaFiltro`, `apoio-teste.ts`, `gerador.ts`
**Requirement**: DAD-01, DAD-02, DAD-03, DAD-04

**Done when**:

- [x] As quatro faixas respeitam as fronteiras 5000/5001, 10000/10001, 20000/20001 em `lista` e `buscar`
- [x] `soComCupom` só deixa cards com `c`
- [x] Combinação de filtros com ordem devolve a interseção na ordem
- [x] Trocar filtro com 30 mil cards ≤ 50 ms (mediana de 5, com aquecimento)
- [x] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(site): filtro por faixa de preço e por cupom na camada de dados`

---

### T2: Filtros ↔ URL

**What**: Módulo puro que lê os filtros de `URLSearchParams` (ignorando inválidos) e escreve a URL (padrão fora, outros parâmetros preservados).
**Where**: `apps/site/src/lib/filtros.ts`, `apps/site/src/lib/filtros.test.ts`
**Depends on**: T1
**Reuses**: `LOJAS`, `PUBLICOS`, tipos de `dados.ts`
**Requirement**: URL-01, URL-02, URL-03

**Done when**:

- [x] Todos os valores válidos da URL viram filtro
- [x] Inválidos são ignorados sem afetar os outros
- [x] Padrão fica fora da URL; `q`/`utm_*` preservados; sem `?` quando vazia
- [x] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(site): filtros lidos e escritos no endereço`

---

### T3: Barra de filtros na grade "Mais recentes"

**What**: `BarraFiltros.svelte` acima da grade (desktop numa linha), estado em `PaginaOfertas`, URL por `goto(…, { shallow, replace })`, contador, "Limpar", estado vazio, "Ver mais" volta a 40.
**Where**: `apps/site/src/lib/componentes/BarraFiltros.svelte`, `apps/site/src/lib/componentes/PaginaOfertas.svelte` (só o bloco da grade e o estado dos filtros), `apps/site/e2e/filtros.spec.ts`
**Depends on**: T2
**Reuses**: estilo de pílula de `Areas.svelte`, `servir` de `e2e/fixtura.ts`
**Requirement**: URL-04, URL-05, BAR-01..BAR-09

**Done when**:

- [x] Fluxos BAR-01..09 e URL-04..05 passam em e2e (390 px e 1280 px)
- [x] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`

**Tests**: e2e
**Gate**: build

**Commit**: `feat(site): barra de filtros na grade de ofertas`

---

### T4: Painel "Filtros" no celular

**What**: Em < 640 px, Ordem fica fora e os outros grupos vão para um `<dialog>` em folha inferior com "Ver N ofertas".
**Where**: `apps/site/src/lib/componentes/BarraFiltros.svelte`, `apps/site/e2e/filtros.spec.ts`
**Depends on**: T3
**Reuses**: snippets da barra
**Requirement**: PNL-01, PNL-02, PNL-03

**Done when**:

- [x] Painel abre, aplica e fecha no celular; desktop sem botão "Filtros"
- [x] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`

**Tests**: e2e
**Gate**: build

Bundle inicial da home (JS de modulepreload + imports estáticos, CSS embutido), medido com o mesmo critério da BSV-30b:

| | JS bruto | JS gzip | CSS embutido | total bruto |
| - | - | - | - | - |
| `origin/develop` (7e7fa32) | 121.139 B | 49.211 B | 19.861 B | 141.000 B |
| BSV-31 | 130.124 B | 52.212 B | 21.920 B | 152.044 B (148,5 KiB) |

Dentro de 150 KiB; acima de 150.000 B se o orçamento for decimal. A BarraFiltros soma ~7 KB brutos ao chunk da página.
Prints: `prints/barra-celular.png`, `prints/painel-celular.png`, `prints/filtros-desktop.png`, `prints/vazio-desktop.png` (catálogo sintético, sem dado real).

**Commit**: `feat(site): painel de filtros no celular`

---

### T5: Foco preso no painel do celular

**What**: Painel vira `<dialog>` modal (`showModal`: fundo inerte, foco preso); Esc fecha e devolve o foco a "Filtros". Os grupos ficam num só lugar: na linha (desktop) ou no diálogo aberto.
**Where**: `apps/site/src/lib/componentes/BarraFiltros.svelte`, `apps/site/e2e/filtros.spec.ts`
**Depends on**: T4
**Reuses**: snippet `escolhas`
**Requirement**: PNL-04

**Done when**:

- [x] e2e com Tab, Shift+Tab e Esc passa em 390 px
- [x] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`

**Tests**: e2e
**Gate**: build

**Commit**: `fix(site): foco preso no painel de filtros do celular`

---

### T6: Degradê na linha que rola

**What**: Degradê na borda direita da linha "Filtros"/ordem enquanto há conteúdo à direita; some no fim da rolagem e no desktop.
**Where**: `apps/site/src/lib/componentes/BarraFiltros.svelte`, `apps/site/e2e/filtros.spec.ts`
**Depends on**: T5
**Reuses**: -
**Requirement**: PNL-05

**Done when**:

- [ ] e2e: degradê visível no início, some no fim (390 px), ausente em 1280 px; print novo
- [ ] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`

**Tests**: e2e
**Gate**: build

**Commit**: `feat(site): degradê na linha de ordem do celular`

---

### T7: Orçamento do bundle inicial em teste

**What**: e2e de saída do build que soma JS inicial + CSS embutido da home e falha acima de 150 KiB.
**Where**: `apps/site/e2e/saida.spec.ts`
**Depends on**: T6
**Reuses**: `BUILD`/`ler` de `saida.spec.ts`
**Requirement**: BUD-01

**Done when**:

- [ ] Teste passa com o valor atual e falha com limite abaixo dele
- [ ] Gate check passes: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`

**Tests**: e2e
**Gate**: build

**Commit**: `test(site): orçamento do bundle inicial da home em KiB`
