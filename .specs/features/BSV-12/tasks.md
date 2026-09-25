# BSV-12 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; a spec do ticket fixa trait, funções e regras; decisões em `spec.md` → Assumptions)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-12.md` (testes nunca tocam Oracle nem AWS; fakes em memória; `cargo test` sem credenciais e sem rede).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Conversão / SQL (domínio) | unit | URL-01..03 | `apps/worker/tests/{pagina,geracao,oracle}.rs` | `cargo test` |
| Headers (função pura) | unit | HDR-01..04, teste tabular | `apps/worker/tests/headers.rs` | `cargo test` |
| Redirects (domínio) | unit | KVS-01..07 e edge cases com `RedirectsMemoria` | `apps/worker/tests/redirects.rs` | `cargo test` |
| Geração com KVS (domínio) | unit | ORD-01..05 com `FakeFonte` + `PublicadorMemoria` + `RedirectsMemoria` | `apps/worker/tests/{geracao,ciclo}.rs` | `cargo test` |
| Plano (domínio) | unit | PLN-01..03 com espiões que registram chamadas | `apps/worker/tests/plano.rs` | `cargo test` |
| Adaptadores AWS (`aws.rs`) | none | build gate only; sem rede nos testes | - | build gate only |
| Binário (`--publicar`) | integration | AWS-03, AWS-04 via processo real | `apps/worker/tests/dry_run.rs` | `cargo test` |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

### Phase 1: Blocos puros

```
T1 → T2 → T3
```

### Phase 2: Orquestração

```
T4 → T5
```

### Phase 3: AWS e binário

```
T6 → T7
```

---

## Task Breakdown

### T1: `DS_URL_AFILIADO` na leitura e rejeição sem URL

**What**: Campo `url_afiliado: String` em `LinhaOferta`, coluna no `SQL_OFERTAS`, `Rejeicao::UrlAfiliadoAusente` em `para_pagina` e na geração; fake de demonstração e helpers de teste com URL.
**Where**: `apps/worker/src/{conversao,oracle,geracao,main}.rs`, `apps/worker/tests/{comum/mod,pagina,geracao,oracle}.rs`
**Depends on**: None
**Reuses**: padrão de rejeição de `IdProdutoAusente`
**Requirement**: URL-01, URL-02, URL-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `SQL_OFERTAS` contém `DS_URL_AFILIADO`; `LinhaOferta.url_afiliado` lido dela (NULL → `""`)
- [x] URL vazia após trim → `UrlAfiliadoAusente` em `para_pagina` e card não publicado em `gerar`
- [x] Contagens do `--dry-run` da fake inalteradas
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): read DS_URL_AFILIADO and reject offers without it`

---

### T2: `meta_para` com a tabela de MANIFEST §4

**What**: Função pura `meta_para(chave) -> Option<Meta>` cobrindo todos os prefixos; `gerar` usa a mesma `Meta`.
**Where**: `apps/worker/src/publicador.rs`, `apps/worker/tests/headers.rs`
**Depends on**: T1
**Reuses**: `META_CHUNK`, `META_MANIFEST`
**Requirement**: HDR-01, HDR-02, HDR-03, HDR-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Teste tabular: uma chave por linha de MANIFEST §4 → os três headers literais da tabela
- [x] `manifest.prev.json` → headers do manifest; chave desconhecida → `None`
- [x] Chunks e manifest gravados por `gerar` têm `meta == meta_para(chave)`
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): map bucket keys to MANIFEST cache headers`

---

### T3: `Redirects`, `RedirectsMemoria` e `sincronizar_redirects`

**What**: Trait `Redirects`, fake em memória com injeção de falha e contagem de `aplicar`, diff, limites nomeados e aviso > 40 000.
**Where**: `apps/worker/src/redirects.rs`, `apps/worker/src/lib.rs`, `apps/worker/tests/redirects.rs`
**Depends on**: T2
**Reuses**: padrão `thiserror` de `publicador.rs`
**Requirement**: KVS-01, KVS-02, KVS-03, KVS-04, KVS-05, KVS-06, KVS-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Cenários {1→a,2→b} → {1→a,2→c,3→d} → {1→a} → repetição, com put/del exatos
- [ ] `ValorGrandeDemais` e `KvsAcimaDoLimite` sem chamar `aplicar`
- [ ] `WARN` acima de 40 000 capturado no teste
- [ ] Chave não numérica preservada; URL trimada
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): sync affiliate redirects by diff through Redirects trait`

---

### T4: `gerar` sincroniza a KVS antes do manifest

**What**: `gerar` recebe `&mut dyn Redirects`, sincroniza `(id, url)` dos cards publicados depois dos chunks e antes dos manifests; falha → sem manifest; `Relatorio.redirects`.
**Where**: `apps/worker/src/geracao.rs`, `apps/worker/src/main.rs`, `apps/worker/tests/{geracao,ciclo}.rs`
**Depends on**: None (Phase 1 concluída)
**Reuses**: `sincronizar_redirects`, `RedirectsMemoria`
**Requirement**: ORD-01, ORD-02, ORD-03, ORD-04, ORD-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] KVS = cards publicados (inclui expirado, exclui rejeitado)
- [ ] Ordem: chunks → KVS → `manifest.prev.json` → `manifest.json`
- [ ] Falha injetada na KVS → `ErroGeracao::Redirects` e sem `manifest.json`
- [ ] Expurgo apaga a chave; relatório com puts/dels
- [ ] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): update redirects KVS before publishing the manifest`

---

### T5: Plano (`PublicadorPlano`, `RedirectsPlano`, `publicar`)

**What**: Wrappers que leem do destino e só registram escritas; `publicar(…, sim)` escolhe entre plano e execução.
**Where**: `apps/worker/src/plano.rs`, `apps/worker/src/lib.rs`, `apps/worker/tests/plano.rs`
**Depends on**: T4
**Reuses**: `gerar`, `meta_para`
**Requirement**: PLN-01, PLN-02, PLN-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Modo plano: espiões de destino recebem 0 `gravar`/`remover`/`aplicar`
- [ ] Plano lista gravações (bytes, `Cache-Control`), remoções, putKey e deleteKey
- [ ] `--sim`: escritas chegam ao destino, plano vazio
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): add plan mode that records writes without applying them`

---

### T6: `PublicadorS3` e `RedirectsKvs`

**What**: `ContextoAws` (runtime `current_thread` + `SdkConfig` da cadeia padrão), `PublicadorS3` e `RedirectsKvs`; dependências AWS e `tokio`.
**Where**: `apps/worker/src/aws.rs`, `apps/worker/src/lib.rs`, `apps/worker/src/publicador.rs`, `apps/worker/src/redirects.rs`, `apps/worker/Cargo.toml`, `apps/worker/Cargo.lock`
**Depends on**: None (Phase 2 concluída)
**Reuses**: `Publicador`, `Redirects`, `Meta`
**Requirement**: AWS-01, AWS-02, AWS-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `existe`=HeadObject (404→false), `ler`=GetObject (NoSuchKey→None), `gravar`=PutObject com headers da `Meta`, `remover`=DeleteObject, `listar`=ListObjectsV2 paginado
- [ ] `RedirectsKvs`: ListKeys paginado; UpdateKeys em lotes de 50 com `IfMatch` encadeado
- [ ] Nenhum campo de credencial; config só `BESAVE_BUCKET`, `BESAVE_KVS_ARN` e cadeia do SDK
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: none
**Gate**: build

**Commit**: `feat(worker): add S3 publisher and CloudFront KVS redirects adapters`

---

### T7: Binário `--publicar [--sim]` e README

**What**: Flag `--publicar` (grupo `modo`) e `--sim`; lê env, monta adaptadores AWS, imprime plano ou relatório; README com envs e plan/sim.
**Where**: `apps/worker/src/main.rs`, `apps/worker/README.md`, `apps/worker/tests/dry_run.rs`
**Depends on**: T6
**Reuses**: `publicar`, `imprimir_contagens`
**Requirement**: AWS-03, AWS-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `--publicar` sem `BESAVE_BUCKET` (ou `BESAVE_KVS_ARN`) → erro nomeando a variável, sem panic
- [ ] `--sim` sem `--publicar` → erro, sem panic
- [ ] README documenta `--publicar`, envs, plano e `--sim`
- [ ] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: integration
**Gate**: build

**Commit**: `feat(worker): add --publicar command with plan and --sim modes`
