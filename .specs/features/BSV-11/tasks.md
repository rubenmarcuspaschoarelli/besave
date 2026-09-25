# BSV-11 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; a spec do ticket já fixa trait, funções e regras)
**Status**: In progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-11.md` (testes com `FakeFonte` + `PublicadorMemoria`; fixtures e schemas do contrato como esperado; testes nunca tocam Oracle nem AWS).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Publicador (fronteira de I/O) | unit | PUB-01..05; `PublicadorLocal` em pasta temporária | `apps/worker/tests/publicador.rs` | `cargo test` |
| Chunks (domínio) | unit | CHK-01..04 1:1, hash literal da fixture, validação por schema | `apps/worker/tests/chunks.rs` | `cargo test` |
| Geração / manifest (domínio) | unit | MAN-01..08, CHK-05 e edge cases, com `FakeFonte` + `PublicadorMemoria` | `apps/worker/tests/geracao.rs` | `cargo test` |
| Ciclo incremental (domínio) | unit | CIC-01..06, várias execuções sobre o mesmo `PublicadorMemoria` | `apps/worker/tests/ciclo.rs` | `cargo test` |
| Binário (`--gerar`) | integration | CLI-01..03 via processo real com `BESAVE_FONTE=fake` | `apps/worker/tests/dry_run.rs` | `cargo test` |
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

### Phase 1: Blocos

```
T1 → T2
```

### Phase 2: Geração e binário

```
T3 → T4 → T5
```

---

## Task Breakdown

### T1: Trait Publicador, PublicadorLocal e PublicadorMemoria

**What**: `Publicador`, `Meta` (headers do MANIFEST §4), implementação em disco com `.meta.json` e em memória.
**Where**: `apps/worker/src/publicador.rs`
**Depends on**: None
**Reuses**: padrão de erro `thiserror` de `fonte.rs`
**Requirement**: PUB-01, PUB-02, PUB-03, PUB-04, PUB-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `gravar` → bytes em `raiz/chave` e headers em `raiz/chave.meta.json`
- [x] `ler`/`existe` distinguem presente e ausente; `listar` filtra por prefixo sem sidecars; `remover` apaga objeto e sidecar
- [x] `PublicadorMemoria` com o mesmo comportamento e acesso aos headers
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add Publicador trait with local and in-memory backends`

---

### T2: Partição, serialização e compressão de chunks

**What**: `particionar`, `serializar_chunk` (JSON compacto + hash16 SHA-256), `comprimir_br` (Brotli 9); deps `brotli`, `sha2`, `hex` e dev `jsonschema`.
**Where**: `apps/worker/src/chunks.rs`
**Depends on**: T1
**Reuses**: `OfertaCard` de `modelo.rs`, fixture `chunk-ok.json`, `chunk.schema.json`
**Requirement**: CHK-01, CHK-02, CHK-03, CHK-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] ids 999, 1000, 1999, 2000 → n 0, 1, 1, 2; ordem por id dentro do chunk
- [ ] `chunk-ok.json` → JSON idêntico à fixture compactada e hash `89590e56ef6361dc`
- [ ] Descomprimido = JSON do chunk e válido contra `chunk.schema.json`
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): partition, hash and brotli-compress card chunks`

---

### T3: gerar, manifest e relatório

**What**: `gerar(fonte, m, pub_, agora) -> Relatorio`: rejeições, chunks com orçamento, manifest (contrato, versao, areas, ids reais) gravado por último.
**Where**: `apps/worker/src/geracao.rs`
**Depends on**: None (Phase 1 concluída)
**Reuses**: `para_card`, `iso_utc`, `chunks.rs`, `publicador.rs`, `Manifest`/`ChunkRef`
**Requirement**: CHK-05, MAN-01, MAN-02, MAN-03, MAN-04, MAN-05, MAN-06, MAN-07, MAN-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Manifest válido contra `manifest.schema.json`; campos conforme MAN-02..04
- [ ] Headers de chunk e manifest conforme MANIFEST §4; manifest é a última gravação
- [ ] Chunk > 61 440 B → `ChunkAcimaDoOrcamento`, nada gravado; falha ao gravar chunk → sem manifest
- [ ] `Relatorio` com todas as contagens
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): generate chunks and manifest through Publicador`

---

### T4: Reaproveitamento, órfãos e idempotência

**What**: Pular chunks existentes, gravar `manifest.prev.json`, remover órfãos fora dos 2 últimos manifests; teste de 30k cards.
**Where**: `apps/worker/src/geracao.rs` (modify)
**Depends on**: T3
**Reuses**: `gerar` de T3
**Requirement**: CIC-01, CIC-02, CIC-03, CIC-04, CIC-05, CIC-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] 2ª execução sem mudança → 0 escritos, 0 removidos
- [ ] Mudança no chunk 5 → só ele regravado; antigo removido só na 3ª execução
- [ ] Expurgo muda o hash; faixa vazia some do manifest
- [ ] 30 000 cards ≤ 10 s
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): reuse unchanged chunks and prune orphans after two manifests`

---

### T5: Binário --gerar e README

**What**: `--gerar --saida` em `main.rs` (exclusivo com `--dry-run`), relatório no stdout, remover o `bail!` de BSV-11; README com `--gerar`, layout da saída e `.meta.json`.
**Where**: `apps/worker/src/main.rs`
**Depends on**: T4
**Reuses**: `fake_demo`, `PublicadorLocal`, `gerar`
**Requirement**: CLI-01, CLI-02, CLI-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `BESAVE_FONTE=fake cargo run -- --gerar --saida <tmp>` cria a árvore e imprime o relatório
- [ ] `--gerar --dry-run` e `--gerar` sem `--saida` saem com erro sem panic
- [ ] README atualizado
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: integration
**Gate**: build

**Commit**: `feat(worker): add --gerar command writing chunks and manifest to disk`

---

## Phase Execution Map

```
Phase 1 → Phase 2

Phase 1:  T1 ------→ T2
Phase 2:  T3 ------→ T4 ------→ T5
```
