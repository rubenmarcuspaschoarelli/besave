# BSV-42 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; decisões em `spec.md` → Assumptions)
**Status**: In progress

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `tools/*/CLAUDE.md` (testes derivam da spec; sem rede nem navegador).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Navegador (`core/browser.py`) | unit | NAV-01..03 | `tools/tests/test_navegador.py` | `pytest` |
| Caminhos e processos | unit | POR-01..05 | `tools/tests/test_portabilidade.py` | `pytest` |
| Scripts `.sh` (conferências) | unit | SH-01..05 | `tools/tests/test_iniciar_captura.py` | `pytest` |
| Unidades systemd | unit | SH-06 | `tools/tests/test_unidades.py` | `pytest` |
| README | none | DOC-01..02 | - | build gate only |

## Gate Check Commands

> Rodar em `tools/` com o venv de desenvolvimento (`pip install -r requirements-dev.txt`).

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After each task | `pytest` |
| Build | After phase completion | `pytest && ruff check <arquivos novos> && shellcheck vps/*.sh` |

---

## Execution Plan

4 tarefas, um lote: execução inline, sem sub-agentes.

### Phase 1: Robôs

```
T1 → T2 → T3 → T4
```

---

## Task Breakdown

### T1: Navegador configurável

**What**: `navegador.canal` no `config.json`; `core/browser.py` monta os argumentos; exemplo documentado.
**Where**: `tools/capture-store-pages/core/browser.py`, `conf/config.example.json`, `tools/tests/test_navegador.py`
**Depends on**: None
**Requirement**: NAV-01, NAV-02, NAV-03

**Done when**:

- [x] Argumentos iguais aos de hoje com `chrome`/ausente e sem `channel`/`--profile-directory` com `""`
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T2: Portabilidade de caminhos e processos

**What**: Erro claro no Linux sem `s3.raiz`/`publicacao_s3.destino`; `core/processos.py` só age no Windows; docstring do `run_captura.py` sem `.exe`.
**Where**: `tools/capture-store-pages/{main.py,core/estado.py,core/processos.py}`, `tools/capture-chat-groups/{run_captura.py,wa/storage.py}`, `tools/tests/test_portabilidade.py`
**Depends on**: T1
**Requirement**: POR-01, POR-02, POR-03, POR-04, POR-05

**Done when**:

- [x] Padrões do Windows preservados e erro citando a chave no Linux
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Scripts de subida e parada

**What**: `iniciar_captura.sh`, `encerrar_captura.sh` e `rodar_em_tmux.sh` com as conferências do `.ps1`.
**Where**: `tools/vps/*.sh`, `tools/tests/test_iniciar_captura.py`
**Depends on**: T2
**Requirement**: SH-01, SH-02, SH-03, SH-04, SH-05

**Done when**:

- [ ] Dois processos, perfil preso e contador atrasado recusam sem lançar
- [ ] Caminho feliz lança o robô numa sessão `tmux` com `DISPLAY`
- [ ] Gate build passa

**Tests**: unit
**Gate**: build

---

### T4: Unidades systemd e README

**What**: Duas unidades `systemd --user`, `tools/vps/README.md`.
**Where**: `tools/vps/systemd/*.service`, `tools/vps/README.md`, `tools/tests/test_unidades.py`
**Depends on**: T3
**Requirement**: SH-06, DOC-01, DOC-02

**Done when**:

- [ ] Unidades com `Restart=on-failure`, `rodar_em_tmux.sh` e sem segredo
- [ ] README cobre os seis temas
- [ ] Gate build passa

**Tests**: unit
**Gate**: build
