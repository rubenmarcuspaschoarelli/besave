# BSV-43 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; decisões em `spec.md` → Assumptions)
**Status**: Done

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md` (testes derivam da spec; lição 14: comando montado compara o comando inteiro; lição 21: rodar todos os gates do job).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| `instalar.sh` | integration (bash, `gh` falso) | INS-01..05 | `infra/vps/teste_instalar.sh` | `bash infra/vps/teste_instalar.sh` |
| `instalar.sh` + artefato real | e2e (CI, ARM) | INS-03, WF-03, WF-04 | `.github/workflows/worker-arm64.yml` job `vps` | execução do workflow |
| Unidades `systemd` | static (`systemd-analyze verify`) | SYS-01, SYS-02 | `infra/vps/*.service`, `*.timer` | job `vps` |
| Binário instalado (fumaça) | e2e (CI, ARM) | SYS-03, SYS-04 | job `vps` | execução do workflow |
| Workflow | static (`actionlint`) | WF-01, WF-02, WF-05 | `.github/workflows/worker-arm64.yml` | `actionlint` |
| Modelo `worker.env.example` × variáveis lidas | integration (Rust, lê `src/`) | SYS-03, ENV-01 | `apps/worker/tests/worker_env_vps.rs` | `cargo test --test worker_env_vps` |
| Docs | none | DOC-01 | - | build gate only |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | `instalar.sh` | `bash infra/vps/teste_instalar.sh && shellcheck infra/vps/*.sh` |
| Build | Workflow, unidades, docs | `actionlint .github/workflows/worker-arm64.yml` (+ execução do workflow na PR) |

---

## Execution Plan

5 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: VPS e CI

```
T1 → T2 → T3 → T4 → T5
```

---

## Task Breakdown

### T1: `instalar.sh` e seu teste

**What**: script que escolhe a execução (último push em `main` ou ID), baixa o artefato pelo `gh`, confere o `SHA256SUMS` e troca os binários por `rename`; teste em bash com `gh` falso.
**Where**: `infra/vps/instalar.sh`, `infra/vps/teste_instalar.sh`
**Depends on**: None
**Reuses**: -
**Requirement**: INS-01, INS-02, INS-03, INS-04, INS-05, INS-06

**Done when**:

- [x] Casos: sem argumento, ID de PR, sucesso, hash errado, binário ausente, `SHA256SUMS` incompleto, argumento inválido
- [x] Gate quick passa

**Tests**: integration
**Gate**: quick

---

### T2: Unidades `systemd` e `worker.env.example`

**What**: `besave-ciclo.{service,timer}`, `besave-envio.{service,timer}`, `worker.env.example`.
**Where**: `infra/vps/`
**Depends on**: T1
**Reuses**: variáveis do README do worker
**Requirement**: SYS-01, SYS-03

**Done when**:

- [x] Unidades com os campos de SYS-01; modelo com as chaves de SYS-03 e sem segredo
- [x] Gate build passa (verificação por `systemd-analyze` no job `vps`, T3)

**Tests**: none
**Gate**: build

---

### T3: Workflow `worker-arm64.yml`

**What**: job `build` (fmt, clippy, test, build release, `SHA256SUMS`, artefato 90 dias) e job `vps` (shellcheck, teste do `instalar.sh`, `instalar.sh` real com o ID da execução, `sha256sum -c`, ELF aarch64, `systemd-analyze verify`, fumaça do `besave-ciclo` com `worker.env.example`).
**Where**: `.github/workflows/worker-arm64.yml`
**Depends on**: T2
**Reuses**: job `rust` do `ci.yml`
**Requirement**: WF-01, WF-02, WF-03, WF-04, WF-05, SYS-02, SYS-04

**Done when**:

- [x] `actionlint` limpo
- [x] Gate build passa (local: actionlint + ensaio do ciclo; execução no ARM depende do push)

**Tests**: e2e
**Gate**: build

---

### T4: README do worker

**What**: seção "Rodar no Linux (VPS)".
**Where**: `apps/worker/README.md`
**Depends on**: T3
**Reuses**: roteiro `docs/infra/VPS-INSTANCIA-1.md` Fase 6
**Requirement**: DOC-01

**Done when**:

- [x] Instalar, unidades, virada (PC desligado antes), logs, reversão
- [x] Gate build passa

**Tests**: none
**Gate**: build

---

### T5: Variáveis do modelo da VPS (pedido do dono antes do teste real)

**What**: `BESAVE_INDEXAVEL=true` e `BESAVE_AVISOS_DIR` no `worker.env.example`; virada copia as imagens
dos avisos e confere o `robots.txt`; teste que compara o modelo com as variáveis lidas.
**Where**: `infra/vps/worker.env.example`, `apps/worker/README.md`, `apps/worker/tests/worker_env_vps.rs`
**Depends on**: T4
**Reuses**: nenhum
**Requirement**: SYS-03, ENV-01, DOC-01

**Done when**:

- [x] Teste reprova com o modelo antigo (falta `BESAVE_AVISOS_DIR`, `BESAVE_INDEXAVEL`, `HOSTNAME`), com
      nome digitado errado e com leitura nova em `src/`
- [x] Gate build passa (fmt, clippy, `cargo test`)

**Tests**: integration
**Gate**: build
