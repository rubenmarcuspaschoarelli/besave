# BSV-40 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; `docs/specs/BSV-40.md` fixa regras; decisões em `spec.md` → Assumptions)
**Status**: In progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` (Oracle e Telegram só por trait com fake; `cargo test` sem rede; testes derivam da spec).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Contrato (versão) | unit | CON-01 | `apps/worker/tests/envio_modelo.rs` | `cargo test` |
| Ciclo (`DT_PUBLICACAO_SITE`) | unit | CIC-01..04 | `apps/worker/tests/publicacao_site.rs` | `cargo test` |
| Envio: janela, modelo (puro) | unit | JAN-01..03, JAN-06 | `apps/worker/tests/envio_janela.rs` | `cargo test` |
| Envio: seleção (fake Oracle) | unit | FIL-01..02, REP-01..02, ORD-01 | `apps/worker/tests/envio_selecao.rs` | `cargo test` |
| Envio: legenda e foto (puro) | unit | LEG-01..04, FOT-01..02 | `apps/worker/tests/envio_legenda.rs`, `envio_foto.rs` | `cargo test` |
| Envio: orquestração (fakes Oracle/Telegram/relógio) | unit | JAN-04, 05, 07, DUP-01..02, EXP-01..02, LIM-01..02 | `apps/worker/tests/envio_execucao.rs` | `cargo test` |
| Binário `besave-envio` | integration | BIN-01..03 | `apps/worker/tests/cli_envio.rs` | `cargo test` |
| Oracle real / Telegram real (I/O) | none | build gate only; testes nunca tocam rede | - | build gate only |

## Gate Check Commands

> Rodar em `apps/worker/` com `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=4`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

8 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: Domínio

```
T1 → T2 → T3 → T4 → T5
```

### Phase 2: Orquestração e operação

```
T5 → T6 → T7 → T8
```

---

## Task Breakdown

### T1: Contrato 1.4.0 e `OfertaCanal`

**What**: CONTRATO §11 `OfertaCanal`, versão 1.4.0 (`docs/CONTRATO.md`, `packages/contract/package.json`, `package-lock.json`); `envio::modelo` com `OfertaCanal`, `LinhaCanal`, `Parametros`, `para_canal`.
**Where**: `docs/CONTRATO.md`, `packages/contract/`, `apps/worker/src/envio/modelo.rs`
**Depends on**: None
**Reuses**: `para_card`, `desconto_pct`, `truncar`
**Requirement**: CON-01, FIL-01 (regras §9)

**Done when**:

- [x] `versao_contrato()` = `1.4.0`; `para_canal` rejeita como §9 e exige `id_produto`
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T2: `DT_PUBLICACAO_SITE` no ciclo

**What**: `FonteOfertas::marcar_publicadas_site` (fake + Oracle), lotes de 1 000 depois do manifest, WARN + `publicacao_site_falhas` no relatório, nada com `BESAVE_DESTINO_LOCAL`.
**Where**: `apps/worker/src/{fonte,oracle,execucao,ciclo,geracao}.rs`
**Depends on**: T1
**Reuses**: `blocos_in`
**Requirement**: CIC-01, CIC-02, CIC-03, CIC-04

**Done when**:

- [x] Segunda execução → 0 updates; 2 500 ids → 3 lotes; falha → código 0 e manifest publicado
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Janela, cota e silêncio

**What**: `envio::janela::{lote_devido, silencioso, inicio_do_dia}` puras.
**Where**: `apps/worker/src/envio/janela.rs`
**Depends on**: T2
**Reuses**: `logs::FUSO_BRASILIA`
**Requirement**: JAN-01, JAN-02, JAN-03, JAN-06

**Done when**:

- [x] Casos 07:59/08:00/08:05/08:10/21:59/22:00 e 08:30/09:00
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T4: Fonte do envio e seleção

**What**: trait `FonteEnvio` + `FakeEnvio`; `selecionar` (filtros, repetição, ordem).
**Where**: `apps/worker/src/envio/{fonte,selecao}.rs`
**Depends on**: T3
**Reuses**: `para_canal`
**Requirement**: FIL-01, FIL-02, REP-01, REP-02, ORD-01

**Done when**:

- [x] Todos os casos de filtro, repetição e ordem da spec
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T5: Legenda e foto

**What**: `envio::legenda::{legenda, legenda_encerrada, preco}`; `envio::foto::foto_quadrada` (feature `jpeg` do `image`).
**Where**: `apps/worker/src/envio/{legenda,foto}.rs`, `apps/worker/Cargo.toml`, `src/imagens.rs` (placeholder público)
**Depends on**: T4
**Reuses**: placeholders embutidos, `truncar`
**Requirement**: LEG-01, LEG-02, LEG-03, LEG-04, FOT-01, FOT-02

**Done when**:

- [ ] Casos de legenda da spec; JPEG 800×800 com bordas brancas e proporção
- [ ] Gate build passa (fim da fase 1)

**Tests**: unit
**Gate**: build

---

### T6: Orquestração do envio

**What**: traits `CanalTelegram` e `Relogio` com fakes; `envio::executar` (lote, reserva → envio → confirma/cancela, espaçamento ≥ 1 s, 429, edições de expiradas).
**Where**: `apps/worker/src/envio/{canal,execucao}.rs`
**Depends on**: T5
**Reuses**: T3–T5
**Requirement**: JAN-04, JAN-05, JAN-07, DUP-01, DUP-02, EXP-01, EXP-02, LIM-01, LIM-02

**Done when**:

- [ ] Dia simulado 180 ± 2; parada de 1 h; duplicata; expiradas; 429; pausa
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T7: I/O real e binário `besave-envio`

**What**: `OracleEnvio` (SQL), `CanalTelegramHttp` (`sendPhoto` multipart, `editMessageCaption`), binário com `--env-file`, `--sim`, trava, log diário, alerta, estado de pausa.
**Where**: `apps/worker/src/envio/{oracle,http,binario}.rs`, `src/bin/besave-envio.rs`, `src/logs.rs`, `src/alerta.rs`
**Depends on**: T6
**Reuses**: `Trava`, `iniciar_log`, `Alertas`, `TelegramHttp`
**Requirement**: BIN-01, BIN-02, BIN-03

**Done when**:

- [ ] Sem token → código 2; argumento inválido → 2; `Debug` sem token; multipart com campos certos
- [ ] Gate quick passa

**Tests**: integration
**Gate**: quick

---

### T8: Tarefa agendada e README

**What**: `scripts/registrar-tarefa-envio.ps1`; README (bot, admin do canal, parâmetros, tarefa, `--sim`).
**Where**: `apps/worker/scripts/`, `apps/worker/README.md`
**Depends on**: T7
**Reuses**: `registrar-tarefa.ps1`
**Requirement**: BIN-04

**Done when**:

- [ ] Script parseia (`[scriptblock]::Create`); README cobre a operação
- [ ] Gate build passa

**Tests**: none
**Gate**: build
