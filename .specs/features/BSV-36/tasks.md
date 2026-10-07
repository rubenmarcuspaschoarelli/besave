# BSV-36 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; decisões em `spec.md` → Assumptions)
**Status**: In progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` (Oracle só por trait com fake), `apps/site/CLAUDE.md`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Contrato (schema, fixtures) | contract | CON-01, CON-02 | `packages/contract/fixtures/` | `npm run validate` |
| Worker: card (`para_card`) | unit | CON-03, DP-01..04 | `apps/worker/tests/card.rs`, `envio_modelo.rs` | `cargo test` |
| Worker: ciclo + `UPDATE` (fake Oracle) | unit | GRV-01, GRV-02, IDE-01 | `apps/worker/tests/publicacao_site.rs` | `cargo test` |
| Site: catálogo e gerador | unit | SIT-01..06, ORC-01 | `apps/site/src/lib/dados/*.test.ts` | `pnpm test` |
| Oracle real (I/O) | none | build gate only; testes nunca tocam Oracle | - | build gate only |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` (worker) / `pnpm test` (site) |
| Build | After phase completion | contrato: `npm run validate`; worker: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`; site: `pnpm lint && pnpm check && pnpm test && pnpm build` |

---

## Execution Plan

3 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: Contrato, worker e site

```
T1 → T2 → T3
```

---

## Task Breakdown

### T1: Contrato 1.5.0 e `dp` no card do worker

**What**: schema `dp` obrigatório; fixtures (`chunk-ok`, `chunk-invalido`, `manifest-ok`); versão 1.5.0; CONTRATO §3/§10.6/§11 e MANIFEST §2/§7; `LinhaOferta.dt_publicacao_site`, `OfertaCard.dp`, `para_card(l, m, instante)` com faixa + WARN.
**Where**: `packages/contract/`, `docs/CONTRATO.md`, `docs/MANIFEST.md`, `apps/worker/src/{modelo,conversao,geracao}.rs`, `apps/worker/src/envio/modelo.rs`
**Depends on**: None
**Reuses**: `iso_utc`
**Requirement**: CON-01, CON-02, CON-03, CON-04, DP-01, DP-02, DP-03, DP-04

**Done when**:

- [x] `npm run validate` verde com card sem `dp` rejeitado
- [x] `dp` da coluna, nulo → instante, futuro/antigo → instante + WARN
- [x] Gate build (contrato + worker) passa

**Tests**: unit
**Gate**: build

---

### T2: Leitura e gravação de `DT_PUBLICACAO_SITE` com o instante do ciclo

**What**: `SQL_OFERTAS` lê a coluna; `marcar_publicadas_site(ids, instante)` grava o instante (sem `SYSDATE`) só em nula/fora da faixa; fake reflete a gravação na leitura seguinte.
**Where**: `apps/worker/src/{fonte,oracle,execucao,geracao}.rs`
**Depends on**: T1
**Reuses**: `blocos_in`, padrão `DATE '1970-01-01' + :n / 86400` do envio
**Requirement**: GRV-01, GRV-02, IDE-01

**Done when**:

- [ ] Fonte fake confere o valor gravado = `dp`; segundo ciclo → mesmo `dp`, 0 chunks
- [ ] Gate build (worker) passa

**Tests**: unit
**Gate**: build

---

### T3: Site — `dp` na camada de dados e orçamento

**What**: `OfertaCard.dp?`; `recentes` por `dp ?? dt`; `maioresDescontos(cat, agora, n)`; gerador com `dp ≥ dt` e contrato 1.5.0; orçamento de 1 000 cards.
**Where**: `apps/site/src/lib/dados/`
**Depends on**: T2
**Reuses**: `Catalogo.lista`, `gerarCards`
**Requirement**: SIT-01, SIT-02, SIT-03, SIT-04, SIT-05, SIT-06, ORC-01

**Done when**:

- [ ] Testes SIT-01..06 e ORC-01 verdes
- [ ] Gate build (site) passa

**Tests**: unit
**Gate**: build
