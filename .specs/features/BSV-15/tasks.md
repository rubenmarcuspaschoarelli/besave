# BSV-15 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `spec.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `docs/specs/BSV-15.md` §7 (`terraform test` + `unittest` sem rede com dublês).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Lambda vigia | unit | VER-*, AVI-* 1:1 + edge cases, dublês de S3/HTTP/Telegram/SSM | `infra/lambdas/vigia/test_handler.py` | `python -m unittest discover -s lambdas/vigia` |
| Terraform do vigia | integration | INF-* via `mock_provider` | `infra/tests/vigia.tftest.hcl` | `terraform test` |
| CI / README | none | leitura | - | build gate only |

## Gate Check Commands

> Rodar em `infra/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `python -m unittest discover -s lambdas/vigia -v` |
| Full | After tasks with e2e/integration tests | `terraform init -backend=false && terraform validate && terraform test` |
| Build | After phase completion or config/entity-only tasks | `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test && python -m unittest discover -s lambdas/vigia && cd functions && npm test` |

---

## Execution Plan

### Phase 1: Vigia

```
T1 → T2 → T3
```

---

## Task Breakdown

### T1: Lambda vigia (handler + testes)

**What**: `handler.py`: verificações de frescor e disponibilidade, máquina de estados do aviso, envio ao Telegram e `lambda_handler` com `boto3` do runtime. `test_handler.py` com dublês, sem rede.
**Where**: `infra/lambdas/vigia/`
**Depends on**: None
**Reuses**: nada (pasta nova)
**Requirement**: VER-01, VER-02, VER-03, VER-04, VER-05, AVI-01, AVI-02, AVI-03, AVI-04, AVI-05, AVI-06, AVI-07, AVI-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A sequência do critério de aceite (10 min → 31 min → ainda velho → +3 h → fresco) dá 0, 1, 0, 1 lembrete, 1 "voltou" com duração
- [x] HTTP 403 e timeout → alerta de disponibilidade com texto distinto do de frescor
- [x] Telegram falhando → estado não gravado; a próxima execução reenvia
- [x] Gate check passes: `python -m unittest discover -s lambdas/vigia -v`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): add vigia Lambda handler with alert state machine`

---

### T2: Terraform do vigia

**What**: `vigia.tf` (Lambda, `archive_file`, grupo de log, role e policy mínimos, Scheduler e o role dele, 0 retentativas), provider `archive` no lock, `.build/` no `.gitignore`, `tests/vigia.tftest.hcl` + mocks.
**Where**: `infra/vigia.tf`, `infra/main.tf`, `infra/.terraform.lock.hcl`, `infra/tests/`, `.gitignore`
**Depends on**: T1
**Reuses**: `tests/mocks/aws.tfmock.hcl`, `tests/inspecao`
**Requirement**: INF-01, INF-02, INF-03, INF-04, INF-05, INF-06, INF-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A policy da Lambda é igual à da spec (asserção de igualdade exata)
- [ ] Nenhum `aws_ssm_parameter` em `.tf`; nenhum recurso existente alterado
- [ ] Gate check passes: `terraform fmt -check -recursive && terraform validate && terraform test`

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): schedule vigia Lambda every 10 minutes`

---

### T3: CI e README

**What**: job `infra` roda `python -m unittest` (setup-python 3.12); README com parâmetros SSM, `lambda invoke` e custo.
**Where**: `.github/workflows/ci.yml`, `infra/README.md`
**Depends on**: T2
**Reuses**: job `infra` existente
**Requirement**: OPS-03, OPS-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O job `infra` roda os testes do vigia
- [ ] O README cobre a criação dos parâmetros, o `lambda invoke` e o custo
- [ ] Gate check passes: build gate

**Tests**: none
**Gate**: build

**Commit**: `ci(infra): run vigia tests and document operation`
