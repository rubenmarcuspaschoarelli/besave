# BSV-10 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; nenhuma decisão de arquitetura além da spec do ticket)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-10.md` (fixtures do contrato como esperado; testes nunca tocam Oracle).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Modelo (serde do contrato) | unit | Round-trip byte a byte de cada fixture `*-ok.json` | `apps/worker/tests/modelo.rs` | `cargo test` |
| Mapeamento / conversão (domínio) | unit | 1:1 com CONV-01..11; cada motivo de rejeição e edge case com teste próprio | `apps/worker/tests/*.rs` | `cargo test` |
| Fonte fake | unit | FONTE-01, FONTE-02 | `apps/worker/tests/fonte.rs` | `cargo test` |
| Fonte Oracle | unit | Só o caminho de erro de config (FONTE-04); leitura real roda com o dono | `apps/worker/tests/oracle.rs` | `cargo test` |
| Binário (dry-run) | integration | DRY-01, DRY-02 via processo real com `BESAVE_FONTE=fake` | `apps/worker/tests/dry_run.rs` | `cargo test` |
| Cargo.toml / README | none | build gate only | - | build gate only |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

### Phase 1: Contrato e conversão

```
T1 → T2 → T3 → T4
```

### Phase 2: Fontes e binário

```
T5 → T6 → T7
```

---

## Task Breakdown

### T1: Modelo do contrato com serde

**What**: Crate `apps/worker` (lib + bin vazio) com enums, `OfertaCard`, `OfertaPagina`, `Produto`, `Manifest` e round-trip das fixtures.
**Where**: `apps/worker/src/modelo.rs`
**Depends on**: None
**Reuses**: `packages/contract/schema/*.json`, `packages/contract/fixtures/*-ok.json`
**Requirement**: CONV-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Cargo.toml`, `src/lib.rs`, `src/main.rs` mínimos; deps só as autorizadas pela spec
- [x] Round-trip de `chunk-ok.json`, `oferta-pagina-ok.json`, `manifest-ok.json` idêntico à fixture compactada
- [x] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): add contract model with serde round-trip`

---

### T2: Mapeamento texto → enum

**What**: `Mapeamento` carregado de `mapeamento.json` e `normalizar()` (maiúsculas, NFKD sem acento, trim, espaços simples).
**Where**: `apps/worker/src/mapeamento.rs`
**Depends on**: T1
**Reuses**: `packages/contract/mapeamento.json`
**Requirement**: CONV-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `MERCADOLIVRE`, `Mercado  Livre`, `Família & filhos`, ` criança ` mapeiam para o enum certo
- [ ] Texto sem mapeamento devolve `None`
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): load enum mapping with text normalization`

---

### T3: Linha → OfertaCard

**What**: `LinhaOferta`, `Rejeicao`, `centavos`, truncamento de título, formatação ISO e `para_card`.
**Where**: `apps/worker/src/conversao.rs`
**Depends on**: T2
**Reuses**: `modelo.rs`, `mapeamento.rs`
**Requirement**: CONV-02, CONV-03, CONV-04, CONV-05, CONV-06, CONV-07, CONV-08, CONV-09, CONV-10, CONV-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Cada motivo de rejeição do §9 tem teste
- [ ] `pd ≤ pp` → `pd: null`; truncamento 197 + `…`; `centavos(19.995) == 2000`; `ST_ATIVO=0` → `x:1`
- [ ] Linhas equivalentes às 3 fixtures geram JSON idêntico; cada card ≤ 220 B, média ≤ 160 B
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): convert oracle rows to OfertaCard with rejection reasons`

---

### T4: Linha → OfertaPagina

**What**: `LinhaProduto` e `para_pagina` (desconto, nota, status, produto).
**Where**: `apps/worker/src/conversao.rs` (modify)
**Depends on**: T3
**Reuses**: helpers de T3
**Requirement**: CONV-07, CONV-09, CONV-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Linha + produto equivalentes à fixture geram `oferta-pagina-ok.json` byte a byte
- [ ] Título longo fica integral na página; `ST_ATIVO=0` → `ENCERRADA`
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): convert oracle rows to OfertaPagina`

---

### T5: Trait FonteOfertas e FakeFonte

**What**: Trait `FonteOfertas` e `FakeFonte` com filtro de expurgo de 7 dias.
**Where**: `apps/worker/src/fonte.rs`
**Depends on**: None (Phase 1 concluída)
**Reuses**: `LinhaOferta`, `LinhaProduto`
**Requirement**: FONTE-01, FONTE-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Inativa há 8 dias fica de fora; há 6 dias sai; ativa sai; inativa sem data fica de fora
- [ ] `produto(id)` devolve o produto ou `None`
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add FonteOfertas trait with in-memory fake`

---

### T6: OracleFonte

**What**: `OracleFonte` com crate `oracle`, config por env, SQL com filtro de expurgo e conversão de fuso para UTC.
**Where**: `apps/worker/src/oracle.rs`
**Depends on**: T5
**Reuses**: trait de T5
**Requirement**: FONTE-03, FONTE-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Variável de conexão ausente → erro com o nome da variável
- [ ] Compila sem Instant Client (ODPI-C carrega OCI em runtime)
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add OracleFonte reading OFERTA and PRODUTO`

---

### T7: Dry-run e README

**What**: `main.rs` com `--dry-run`, `BESAVE_FONTE=fake|oracle`, relatório de contagens, e README da crate.
**Where**: `apps/worker/src/main.rs`
**Depends on**: T6
**Reuses**: `FakeFonte`, `OracleFonte`, `para_card`, `para_pagina`
**Requirement**: DRY-01, DRY-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `BESAVE_FONTE=fake cargo run -- --dry-run` imprime lidas / validas / rejeitadas por motivo e sai 0
- [ ] README explica rodar com fake e com Oracle (Instant Client ≥ 19)
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: integration
**Gate**: build

**Commit**: `feat(worker): add dry-run report and crate README`

---

## Phase Execution Map

```
Phase 1 → Phase 2

Phase 1:  T1 ------→ T2 ------→ T3 ------→ T4
Phase 2:  T5 ------→ T6 ------→ T7
```
