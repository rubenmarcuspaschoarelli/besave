# BSV-37 Tasks

**Spec**: `.specs/features/BSV-37/spec.md`
**Status**: Done (aguardando Verifier)

---

## Test Coverage Matrix

> Guidelines found: `CLAUDE.md` (regras 1–2, 9), `apps/site/CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` lições 15, 17, 19.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Barra de filtros (Svelte) | e2e | CMP-01..11 em 1280 px; CEL-01 pelos testes de 390 px existentes | `apps/site/e2e/compacta.spec.ts`, `e2e/filtros.spec.ts`, `e2e/publico.spec.ts` | `pnpm e2e` |
| Faixa de descontos (Svelte) | e2e | SET-01..04 em 1280, 500 (ponteiro fino) e 390 px (toque) | `apps/site/e2e/setas.spec.ts` | `pnpm e2e` |
| Bundle | e2e | BUD-01 (teste existente) | `apps/site/e2e/saida.spec.ts` | `pnpm e2e` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Full | toda tarefa | `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` |

---

## Execution Plan

### Phase 1: Site

```
T1 → T2 → T3
```

---

## Task Breakdown

### T1: Linha compacta de filtros (≥ 1024 px) [x]

**What**: itens com divulgação na linha do título; faixa de opções carregada no primeiro clique; painel do celular até 1023 px.
**Where**: `src/lib/componentes/BarraFiltros.svelte`, `FaixaFiltros.svelte`, `GruposFiltros.svelte`, `filtros-sob-demanda.ts` (novos), `PainelFiltros.svelte`, `PaginaOfertas.svelte` (título na barra; `AvisoNovas` carregado ao montar, para o bundle), `src/lib/filtros.ts`, `e2e/compacta.spec.ts`, `e2e/linha-compacta.ts`, `e2e/filtros.spec.ts`, `e2e/publico.spec.ts`
**Depends on**: None
**Requirement**: CMP-01..11, CEL-01, BUD-01

**Done when**:

- [x] Testes de 1280 px cobrem CMP-01..11
- [x] Testes de 390 px existentes passam sem mudar o fluxo do celular
- [x] Gate verde

**Tests**: e2e
**Gate**: full

---

### T2: Setas na faixa de descontos [x]

**What**: barra oculta, setas ‹ › com ponteiro fino, rolagem de uma largura visível.
**Where**: `src/lib/componentes/FaixaDescontos.svelte`, `SetasFaixa.svelte` (novo, sob demanda), `e2e/setas.spec.ts`
**Depends on**: T1
**Requirement**: SET-01..04

**Done when**:

- [x] SET-01..04 cobertos em 1280, 500 e 390 px (toque)
- [x] Gate verde

**Tests**: e2e
**Gate**: full

---

### T3: Evidência (prints e bundle) [x]

**What**: prints 1280 px (fechada, aberta, valor) e 390 px; bundle antes/depois.
**Where**: `.specs/features/BSV-37/evidencia.md`, `.specs/features/BSV-37/prints/`
**Depends on**: T2
**Requirement**: BUD-01

**Done when**:

- [x] Prints olhados pelo autor (lição 19)
- [x] Bundle registrado

**Tests**: none
**Gate**: full
