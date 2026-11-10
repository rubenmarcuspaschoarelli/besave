# BSV-57 Tasks

## Execution Plan

### Phase 1: Batimento
T1 → T2

### Phase 2: Scope das lojas
T3

### Phase 3: Vigia
T4 → T5 → T6

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
```

## Task Breakdown

### T1: Batimento do WhatsApp
**What**: `wa/batimento.py` (escrita atômica, prazo, `grupos_falhando`) e ligação no rodízio: renova só com grupo aberto, banco fora renova, sono grava prazo de acordar + 10 min.
**Where**: `tools/capture-chat-groups/wa/batimento.py`, `wa/monitor.py`, `.gitignore`
**Depends on**: none
**Reqs**: BAT-01, BAT-02, BAT-03, BAT-04, BAT-05, BAT-06
**Tests**: `tools/tests/test_batimento_whatsapp.py`
**Gate**: `pytest tests/test_batimento_whatsapp.py` (em `tools/`)
- [x] Done

### T2: Batimento das lojas
**What**: `core/batimento.py` e ligação em `_processar_lote` e `_monitorar`: linha concluída, varredura, fila vazia, pausa; exceção de navegador não renova; sono grava prazo.
**Where**: `tools/capture-store-pages/core/batimento.py`, `main.py`
**Depends on**: T1
**Reqs**: BAT-05, BAT-06, BAT-07, BAT-08
**Tests**: `tools/tests/test_batimento_lojas.py`
**Gate**: `pytest tests/test_batimento_lojas.py`
- [x] Done

### T3: Scope das lojas
**What**: trecho comum `scope.sh`, `iniciar_lojas.sh`, unidade das lojas com `ExecStop` e `TimeoutStopSec=45`.
**Where**: `tools/vps/scope.sh`, `iniciar_lojas.sh`, `iniciar_captura.sh`, `systemd/besave-captura-lojas.service`
**Depends on**: T2
**Reqs**: ESC-01, ESC-02, ESC-03
**Tests**: `tools/tests/test_scope_lojas.py`, `test_scope_whatsapp.py`, `test_iniciar_captura.py`, `test_unidades.py`
**Gate**: `pytest tests/test_scope_lojas.py tests/test_scope_whatsapp.py tests/test_iniciar_captura.py tests/test_unidades.py`
- [ ] Done

### T4: Vigia, decisão e estado
**What**: `vigia_robos.py` com parado, madrugada, pid, operador, grupo morto, laço, limite, voltou, estado.
**Where**: `tools/vps/vigia_robos.py`
**Depends on**: T3
**Reqs**: VIG-01, VIG-02, VIG-03, VIG-04, VIG-05, VIG-06, VIG-07, VIG-08, VIG-09, VIG-10
**Tests**: `tools/tests/test_vigia_robos.py`
**Gate**: `pytest tests/test_vigia_robos.py`
- [ ] Done

### T5: Mensagens e rotação de logs
**What**: texto do aviso, redação de token e URL, credencial do `worker.env`, rotação diária.
**Where**: `tools/vps/vigia_robos.py`
**Depends on**: T4
**Reqs**: MSG-01, MSG-02, MSG-03, ROT-01, ROT-02, ROT-03
**Tests**: `tools/tests/test_vigia_mensagens.py`, `tools/tests/test_vigia_rotacao.py`
**Gate**: `pytest tests/test_vigia_mensagens.py tests/test_vigia_rotacao.py`
- [ ] Done

### T6: Unidades e README
**What**: `besave-vigia-robos.service` e `.timer`, README, teste das unidades.
**Where**: `tools/vps/systemd/`, `tools/vps/README.md`
**Depends on**: T5
**Reqs**: UNI-01
**Tests**: `tools/tests/test_unidades.py`
**Gate**: `pytest tests/test_unidades.py`
- [ ] Done

## Test Coverage Matrix

| Camada | Teste | Tarefas |
| --- | --- | --- |
| Batimento WhatsApp (relógio e monitor falsos) | `tools/tests/test_batimento_whatsapp.py` | T1 |
| Batimento lojas (sem Playwright) | `tools/tests/test_batimento_lojas.py` | T2 |
| Scripts bash com comandos falsos | `tools/tests/test_scope_lojas.py`, `test_scope_whatsapp.py`, `test_iniciar_captura.py` | T3 |
| Vigia (relógio, systemctl, cgroup, log e Telegram falsos) | `tools/tests/test_vigia_robos.py`, `test_vigia_mensagens.py`, `test_vigia_rotacao.py` | T4, T5 |
| Unidades | `tools/tests/test_unidades.py` | T3, T6 |

## Gate Check Commands

- `cd tools/capture-chat-groups && python -m unittest discover -s tests`
- `cd tools && python -m pytest -q`
- `cd tools && ruff check vps/ tests/`
- `cd tools && shellcheck vps/*.sh`
- `systemd-analyze --user verify tools/vps/systemd/*` (na inst1, se não houver aqui)
