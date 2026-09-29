# BSV-21 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; `docs/specs/BSV-21.md` fixa assinaturas e regras; decisões em `spec.md` → Assumptions)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-21.md` (testes nunca tocam Oracle nem AWS; `cargo test` sem rede; testes derivam da spec).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Fonte (trait + fake + SQL puro) | unit | PRD-01..03 | `apps/worker/tests/{fonte,oracle}.rs` | `cargo test` |
| Headers (`meta_para`) | unit | SIT-10, SIT-12 | `apps/worker/tests/headers.rs` | `cargo test` |
| Sitemap/robots/config (funções puras) | unit | SIT-03, SIT-06, SIT-08, SIT-09, SIT-15 + edge cases | `apps/worker/tests/site.rs` | `cargo test` |
| Páginas (domínio) | unit | PAG-01..11 + edge cases | `apps/worker/tests/paginas.rs` | `cargo test` |
| Geração/ciclo (orquestração) | unit | SIT-01, 02, 04, 05, 07, 11, 13, 14, PRD-02 | `apps/worker/tests/{ciclo,geracao}.rs` | `cargo test` |
| Plano | unit | PLN-01 | `apps/worker/tests/plano.rs` | `cargo test` |
| Binário (`main.rs`) | integration | PRD-04, relatório e env | `apps/worker/tests/dry_run.rs` | `cargo test` |
| Oracle real (`oracle.rs` I/O) | none | build gate only; testes nunca tocam Oracle | - | build gate only |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

7 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: Blocos independentes

```
T1 → T2 → T3 → T4
```

### Phase 2: Integração

```
T4 → T5 → T6 → T7
```

---

## Task Breakdown

### T1: Produtos em lote na fonte

**What**: `FonteOfertas::produtos(&[i64])`, `FakeFonte` contando chamadas, `OracleFonte` com `IN` em blocos de 1 000 e `sql_produtos(n)` testável.
**Where**: `apps/worker/src/fonte.rs`
**Depends on**: None
**Reuses**: `SQL_PRODUTO`/`linha_produto` de `oracle.rs`
**Requirement**: PRD-01, PRD-02, PRD-03

**Done when**:

- [x] `produtos` devolve só ids achados (fake) e conta chamadas
- [x] `sql_produtos(3)` tem `IN (:1, :2, :3)`; `BLOCO_IN = 1000`
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T2: Headers de `assets/` e `_estado/`

**What**: `meta_para` cobre `assets/*.css` e `_estado/*.json`; constantes `META_CSS`, `META_ESTADO`.
**Where**: `apps/worker/src/publicador.rs`
**Depends on**: T1
**Reuses**: tabela existente de `meta_para`
**Requirement**: SIT-10, SIT-12

**Done when**:

- [ ] `meta_para("assets/besave.css")` = CSS; `meta_para("_estado/paginas.json")` = no-store
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Sitemaps, robots e config do site

**What**: módulo `site` com `sitemaps`, `robots`, `ConfigSite::de`.
**Where**: `apps/worker/src/site.rs`
**Depends on**: T2
**Reuses**: nenhum
**Requirement**: SIT-03, SIT-06, SIT-08, SIT-09, SIT-15

**Done when**:

- [ ] 46 000 ativas → 2 arquivos + index, parse ok, ≤ 50 MB; 45 000 → 1 arquivo; 0 → `urlset` vazio
- [ ] robots nos dois modos; env inválida nomeada
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T4: `publicar_paginas`

**What**: módulo `paginas` com `chave_pagina`, `IndicePaginas`, `RelatorioPaginas`, `publicar_paginas` (blocos de 64, orçamento, expurgo, falha de render).
**Where**: `apps/worker/src/paginas.rs`
**Depends on**: T3
**Reuses**: `TemplateOferta`, `gravar_lote`, hash SHA-256/16 hex como em `chunks.rs`
**Requirement**: PAG-01, PAG-02, PAG-03, PAG-04, PAG-05, PAG-06, PAG-07, PAG-08, PAG-09, PAG-10, PAG-11

**Done when**:

- [ ] Cobertura 1:1 de PAG-01..10 e teste `#[ignore]` de PAG-11
- [ ] Gate build passa (fim da fase 1)

**Tests**: unit
**Gate**: build

---

### T5: Ligar ao `gerar()`

**What**: `gerar` carrega produtos em lote, publica CSS → páginas → sitemaps → robots → índice antes da KVS; `ConfigSite` como parâmetro; testes de ciclo existentes ajustados à nova ordem/expurgo.
**Where**: `apps/worker/src/geracao.rs`
**Depends on**: T4
**Reuses**: `publicar_paginas`, `sitemaps`, `robots`
**Requirement**: SIT-01, SIT-02, SIT-04, SIT-05, SIT-07, SIT-11, SIT-13, SIT-14

**Done when**:

- [ ] Testes de ciclo das ACs listadas passam; 10 000 ofertas → ≤ 10 chamadas a `produtos`
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T6: Plano resume páginas

**What**: `Plano::linhas` agrupa gravações/remoções de `oferta/*/index.html` em contagem + 5 exemplos.
**Where**: `apps/worker/src/plano.rs`
**Depends on**: T5
**Reuses**: `Operacao`
**Requirement**: PLN-01

**Done when**:

- [ ] Plano com 30 páginas → 1 linha com contagem e 5 exemplos
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T7: Binário e README

**What**: `main.rs` lê `ConfigSite` do env, imprime o relatório de páginas/site, `--dry-run` usa `produtos`; README documenta `BESAVE_BASE_URL`, `BESAVE_INDEXAVEL` e `_estado/`.
**Where**: `apps/worker/src/main.rs`
**Depends on**: T6
**Reuses**: `imprimir_relatorio`
**Requirement**: PRD-04, SIT-15

**Done when**:

- [ ] `--gerar` fake imprime `paginas_publicadas: 3` e cria `oferta/5412/index.html`, `robots.txt`
- [ ] `BESAVE_INDEXAVEL=talvez` falha nomeando a variável
- [ ] Gate build passa

**Tests**: integration
**Gate**: build
