# BSV-41 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; `docs/specs/BSV-41.md` fixa regras; decisões em `spec.md` → Assumptions)
**Status**: In progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `apps/worker/CLAUDE.md` (Oracle e Telegram só por trait com fake; `cargo test` sem rede; testes derivam da spec).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Headers (`meta_para`) | unit | PAG-09 | `apps/worker/tests/headers.rs` | `cargo test` |
| Página do aviso (template) | unit | PAG-03..06 | `apps/worker/tests/aviso_pagina.rs` | `cargo test` |
| Ciclo: publicação, índice, remoção, data | unit | PAG-01..02, PAG-07..08, REM-01..06, DTP-01..02 | `apps/worker/tests/aviso_ciclo.rs` | `cargo test` |
| Ciclo: integração e relatório | unit | DTP-03, REL-01..02 | `apps/worker/tests/aviso_ciclo.rs`, `tests/execucao.rs` | `cargo test` |
| Envio: seleção, legenda, foto (puro + fake Oracle) | unit | ENV-05..07, ENV-14, LEG-01..02 | `apps/worker/tests/envio_aviso.rs` | `cargo test` |
| Envio: orquestração (fakes Oracle/Telegram/relógio) | unit | ENV-01..04, ENV-08..13, ENV-15..16 | `apps/worker/tests/envio_aviso.rs` | `cargo test` |
| Oracle real / Telegram real (I/O) | none | build gate only; testes nunca tocam rede | - | build gate only |
| Docs | none | DOC-01..02 | - | build gate only |

## Gate Check Commands

> Rodar em `apps/worker/` com `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=4`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

7 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: Ciclo

```
T1 → T2 → T3 → T4
```

### Phase 2: Envio e documentação

```
T4 → T5 → T6 → T7
```

---

## Task Breakdown

### T1: Modelo do aviso e headers

**What**: `avisos::modelo` (`LinhaAviso`, `vigente`, `link_interno_valido`, `imagem_valida`, `chave_imagem`, `chave_pagina`); `meta_para` e `META_*` para `avisos/` e `img/avisos/`.
**Where**: `apps/worker/src/avisos/{mod,modelo}.rs`, `src/publicador.rs`, `src/lib.rs`
**Depends on**: None
**Reuses**: `META_PAGINA`
**Requirement**: PAG-09

**Done when**:

- [x] `meta_para` devolve os headers de PAG-09
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T2: Página do aviso

**What**: `templates/aviso.html` + `avisos::pagina::TemplateAviso` (escape, parágrafos, botão, link do canal, `noindex`).
**Where**: `apps/worker/templates/aviso.html`, `src/avisos/pagina.rs`
**Depends on**: T1
**Reuses**: formatter de escape de `pagina_html`
**Requirement**: PAG-03, PAG-04, PAG-05, PAG-06

**Done when**:

- [ ] Casos de título/texto com `<script>`, link válido e externo
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Publicação dos avisos no ciclo

**What**: `FonteOfertas::{avisos, marcar_aviso_site}` (fake); `avisos::publicacao::publicar_avisos` (índice `_estado/avisos.json`, só sobe o que mudou, remoção, data).
**Where**: `apps/worker/src/fonte.rs`, `src/avisos/publicacao.rs`
**Depends on**: T2
**Reuses**: `hash16`, padrão de `publicar_site`
**Requirement**: PAG-01, PAG-02, PAG-07, PAG-08, REM-01..06, DTP-01, DTP-02

**Done when**:

- [ ] Todos os casos de ciclo da spec com fakes
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T4: Avisos no ciclo agendado

**What**: SQL do Oracle (`OracleFonte`), chamada em `publicar_ciclo` (S3 marca datas; local não), `ConfigAvisos` (`BESAVE_AVISOS_DIR`, `BESAVE_CANAL_URL`), relatório (`avisos_*`, `t_avisos`).
**Where**: `apps/worker/src/{oracle,ciclo,execucao,geracao}.rs`, `src/avisos/`
**Depends on**: T3
**Reuses**: `marcar_publicacao_site`
**Requirement**: DTP-03, REL-01, REL-02

**Done when**:

- [ ] Relatório com as chaves novas; falha → WARN e código 0
- [ ] Gate build passa (fim da fase 1)

**Tests**: unit
**Gate**: build

---

### T5: Aviso no envio: fonte, seleção, legenda, foto

**What**: `FonteEnvio::{avisos_canal, reservar_aviso, confirmar_aviso, cancelar_aviso}` + fake; `envio::aviso::{devido, legenda_aviso, foto_aviso}`.
**Where**: `apps/worker/src/envio/{fonte,aviso}.rs`
**Depends on**: T4
**Reuses**: `escapar`, `tamanho`, `truncar`, `quadrado_jpeg`, `minuto_local`
**Requirement**: ENV-05, ENV-06, ENV-07, ENV-14, LEG-01, LEG-02

**Done when**:

- [ ] Seleção, legenda e foto da spec
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T6: Orquestração do aviso no envio

**What**: `CanalTelegram::enviar_mensagem` (fake, HTTP, `--sim`); `rodar` posta o aviso antes do lote (reserva → envia → confirma/cancela, 429); `simular` mostra o aviso; `Contexto.dir_avisos`.
**Where**: `apps/worker/src/envio/{canal,http,rodada,binario}.rs`
**Depends on**: T5
**Reuses**: `Ritmo`, `cancelar`
**Requirement**: ENV-01..04, ENV-08..13, ENV-15, ENV-16

**Done when**:

- [ ] 08:00/09:55/10:00; janela; cota; falha; 429; sem imagem; `--sim`
- [ ] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T7: Oracle do envio, MANIFEST e README

**What**: SQL de `AVISO_CANAL`/`ENVIO_AVISO` em `OracleEnvio`; `BESAVE_AVISOS_DIR` no binário; MANIFEST §1/§4; README (cadastrar, pasta, pausar).
**Where**: `apps/worker/src/envio/{oracle,binario}.rs`, `docs/MANIFEST.md`, `apps/worker/README.md`
**Depends on**: T6
**Reuses**: `OracleEnvio`
**Requirement**: DOC-01, DOC-02

**Done when**:

- [ ] Docs cobrem a operação
- [ ] Gate build passa

**Tests**: none
**Gate**: build
