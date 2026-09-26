# BSV-20 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; a spec do ticket fixa arquivos, estrutura e regras; decisões em `spec.md` → Assumptions)
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-20.md` (goldens byte a byte; escape; orçamentos).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Tabela de rótulos | unit | TAB-01 contra CONTRATO §2.3 e enums.schema.json | `apps/worker/tests/template_oferta.rs` | `cargo test` |
| Template (render) | unit | PAG-03..15 por asserção no HTML | `apps/worker/tests/template_oferta.rs` | `cargo test` |
| Goldens | unit | PAG-01, PAG-02 byte a byte | `apps/worker/tests/template_oferta.rs` | `cargo test` |
| CSS / orçamentos | unit | TAB-02 | `apps/worker/tests/template_oferta.rs` | `cargo test` |
| Binário `render-oferta` | integration | BIN-01, BIN-02 via processo real | `apps/worker/tests/render_oferta.rs` | `cargo test` |

## Gate Check Commands

> Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

### Phase 1: Template

```
T1 → T2 → T3 → T4
```

---

## Task Breakdown

### T1: `areas.json` e módulo `pagina_html` com filtros de formatação

**What**: Tabela única de rótulos/slugs; `TemplateOferta` (minijinja, template embutido) com filtros `reais`, `decimal`, `nota`, `milhar`, `data_br`, `resumo`; esqueleto de `oferta.html`.
**Where**: `apps/worker/templates/{areas.json,oferta.html}`, `apps/worker/src/{pagina_html,lib}.rs`, `apps/worker/Cargo.toml`, `apps/worker/tests/template_oferta.rs`
**Depends on**: None
**Reuses**: `modelo::OfertaPagina`
**Requirement**: TAB-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Teste compara `areas.json` com a tabela de CONTRATO §2.3 e com a ordem de `enums.schema.json`
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add offer page template engine and label table`

---

### T2: Template completo da página

**What**: `oferta.html` com head/SEO, JSON-LD, cabeçalho, faixa expirada, imagem, preço, cupom, CTA, avaliação, detalhes, faixa de preço, rodapé.
**Where**: `apps/worker/templates/oferta.html`, `apps/worker/tests/template_oferta.rs`
**Depends on**: T1
**Reuses**: filtros de T1
**Requirement**: PAG-03, PAG-04, PAG-05, PAG-06, PAG-07, PAG-08, PAG-09, PAG-10, PAG-11, PAG-12, PAG-13, PAG-14, PAG-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Um teste por critério PAG-03..15, com ativa, encerrada, nulos e título com `<script>`
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): render offer page with SEO head and JSON-LD`

---

### T3: `besave.css` e orçamentos

**What**: CSS puro com variáveis, system stack, mobile-first, imagem ao lado do preço ≥ 1024 px, cinza em `.encerrada`, foco visível; teste de orçamento HTML e CSS.
**Where**: `apps/worker/assets/css/besave.css`, `apps/worker/tests/template_oferta.rs`
**Depends on**: T2
**Reuses**: `brotli` (já dependência)
**Requirement**: TAB-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] HTML de `oferta-pagina-ok` ≤ 30 720 B; CSS Brotli ≤ 20 480 B
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add besave.css for the offer page`

---

### T4: Binário `render-oferta`, goldens e README

**What**: `src/bin/render-oferta.rs`; goldens ativa e encerrada; testes golden e do binário; README do template (classes, variáveis, regenerar goldens, validar HTML).
**Where**: `apps/worker/src/bin/render-oferta.rs`, `apps/worker/tests/fixtures/paginas/`, `apps/worker/tests/{template_oferta,render_oferta}.rs`, `apps/worker/templates/README.md`
**Depends on**: T3
**Reuses**: `TemplateOferta`
**Requirement**: PAG-01, PAG-02, TAB-03, BIN-01, BIN-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Goldens iguais byte a byte; binário imprime o mesmo HTML; erro de entrada → código ≠ 0
- [ ] `npx html-validate` sem erros nos goldens
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: integration
**Gate**: build

**Commit**: `feat(worker): add render-oferta dev binary and golden pages`
