# BSV-33 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/BSV-33/spec.md`
**Status**: In progress

---

## Test Coverage Matrix

> Guidelines found: `CLAUDE.md` (regras 1–2, 9), `apps/site/CLAUDE.md` (Vitest para lógica, Playwright para fluxos), `apps/worker/CLAUDE.md` (fakes, idempotência), `docs/WORKFLOW-AGENTES.md` lições 11, 18, 19.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Sitemap de páginas (função pura) | unit | 1:1 com SMP-02..04, fronteiras 9/10, 19/20, 90/91% | `apps/worker/tests/sitemap_paginas.rs` | `cargo test` |
| Publicação do site (ciclo) | integration | SMP-01, SMP-05 com `PublicadorMemoria` | `apps/worker/tests/ciclo.rs`, `tests/site.rs` | `cargo test` |
| Rotas, navegação, HTML do build | e2e | todo fluxo da spec em 390 px e 1280 px | `apps/site/e2e/publico.spec.ts` | `pnpm e2e` |
| Textos (`conteudo/areas.ts`) | unit | TXT-01 (contagem de frases, cobertura) | `apps/site/src/lib/conteudo/areas.test.ts` | `pnpm test` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | worker | `cd apps/worker && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |
| Full | site | `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` |
| Build | antes do Verifier | Quick + Full |

---

## Execution Plan

### Phase 1: Worker

```
T1 → T2
```

### Phase 2: Site e evidência

```
T3 → T4 → T5 → T6 → T7
```

---

## Task Breakdown

### T1: Função pura do sitemap de páginas

**What**: `sitemap_paginas(ativas, base) -> Vec<u8>` com limiares nomeados, ordem determinística e `lastmod` em Brasília.
**Where**: `apps/worker/src/site.rs`, `apps/worker/src/pagina_html.rs` (data em Brasília), `apps/worker/tests/sitemap_paginas.rs`
**Depends on**: None
**Reuses**: `escapar`, `dias_de_civil`/`civil_de_dias`, `Area::slug`
**Requirement**: SMP-02, SMP-03, SMP-04, SMP-06

**Done when**:

- [x] Home sempre; área 10 entra, 9 fica fora; subpágina 20 e 90% entra; 19 e 91% ficam fora
- [x] `lastmod` = data −03:00 do maior `dp` das ativas; expiradas não contam
- [x] XML faz parse com namespace 0.9

**Tests**: unit
**Gate**: quick

### T2: `sitemap-paginas.xml` no index e no ciclo

**What**: `sitemaps` inclui `sitemap-paginas.xml` no index; `publicar_site` recebe as ativas; `gerar` passa área, público e `dp` dos cards.
**Where**: `apps/worker/src/site.rs`, `apps/worker/src/geracao.rs`, `apps/worker/tests/{site,ciclo,geracao,dry_run}.rs`
**Depends on**: T1
**Reuses**: índice `_estado/paginas.json` (chaves `sitemap*`)
**Requirement**: SMP-01, SMP-05

**Done when**:

- [x] Primeiro ciclo grava `sitemap-paginas.xml` antes de `sitemap.xml`; o index lista o arquivo
- [x] Segundo ciclo sem mudança: 0 uploads de sitemap
- [x] Testes que listam os arquivos do site passam a incluir `sitemap-paginas.xml` (artefato novo, não afrouxamento)

**Tests**: integration
**Gate**: quick

### T3: Rota `/{slug}/{publico}/`

**What**: matcher `publico`, rota prerenderizada das 40 combinações, cabeçalho com `<h1>`, `<title>`, description, canonical e breadcrumb; grade filtrada pelo público do caminho.
**Where**: `apps/site/src/params.ts`, `apps/site/src/routes/[area=area]/[publico=publico]/*`, `apps/site/src/routes/[area=area]/+page.svelte`, `apps/site/src/lib/componentes/{PaginaOfertas,CabecalhoArea}.svelte`, `apps/site/src/lib/formato.ts`, `apps/site/e2e/publico.spec.ts`
**Depends on**: None
**Requirement**: SUB-01, SUB-02, SUB-03, SUB-04

**Done when**:

- [x] `/elas/masculino/` 200 com h1, canonical e breadcrumb; grade só ELAS + MASCULINO
- [x] `/elas/xyz/` e `/xyz/feminino/` → 404

**Tests**: e2e
**Gate**: full

### T4: Público vira caminho nas áreas

**What**: na área e na subpágina, público navega para o caminho mantendo a query; `?publico=` redireciona com `replace`; home inalterada.
**Where**: `apps/site/src/lib/componentes/{PaginaOfertas,BarraFiltros,PainelFiltros}.svelte`, `apps/site/src/lib/filtros.ts`, `apps/site/src/lib/filtros.test.ts`, `apps/site/e2e/publico.spec.ts`
**Depends on**: T3
**Requirement**: PUB-01, PUB-02, PUB-03, PUB-04

**Done when**:

- [x] Em `/elas/?loja=amazon`, "Masculino" → `/elas/masculino/?loja=amazon`; "Todos" → `/elas/?loja=amazon`
- [x] `/elas/?publico=infantil` → `/elas/infantil/` sem entrada nova no histórico
- [x] Home: público continua em `?publico=`
- [x] Bundle inicial da home ≤ 150 KiB: painel do celular sob demanda (pedido do dono); painel continua passando nos PNL-01..05 da BSV-31

**Tests**: unit + e2e
**Gate**: full

### T5: Textos por área e estado sem ofertas

**What**: `conteudo/areas.ts` com os textos; texto abaixo do `<h1>` no HTML prerenderizado; estado "Ainda não temos ofertas aqui"; bundle da home ≤ 150 KiB.
**Where**: `apps/site/src/lib/conteudo/areas.ts`, `areas.test.ts`, `CabecalhoArea.svelte`, `PaginaOfertas.svelte`, `apps/site/e2e/publico.spec.ts`
**Depends on**: T4
**Requirement**: TXT-01, TXT-02, TXT-03, TXT-04

**Done when**:

- [ ] 10 áreas com 2–3 frases; 7 subpáginas com 1 frase
- [ ] Texto no `build/{slug}/index.html` e no da subpágina
- [ ] `/eles/` sem ofertas mostra texto, aviso e links
- [ ] BUD-01 verde

**Tests**: unit + e2e
**Gate**: full

### T6: JSON-LD `BreadcrumbList`

**What**: JSON-LD na área e na subpágina, no HTML prerenderizado.
**Where**: `CabecalhoArea.svelte` (ou rotas), `apps/site/e2e/publico.spec.ts`
**Depends on**: T5
**Requirement**: JLD-01

**Done when**:

- [ ] JSON válido com `@context`, `@type`, posições 1..n e `item` absolutos, igual ao breadcrumb visível

**Tests**: e2e
**Gate**: full

### T7: Evidência

**What**: `sitemap-paginas.xml` gerado pelo worker com os cards reais públicos; prints de `/elas/masculino/` e `/elas/unissex/` em 390 e 1280 px; tamanho do bundle.
**Where**: `.specs/features/BSV-33/` (evidência)
**Depends on**: T6
**Requirement**: Success Criteria

**Done when**:

- [ ] Arquivos de evidência revisados pela regra 11

**Tests**: none
**Gate**: build
