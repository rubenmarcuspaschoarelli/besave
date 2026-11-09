# BSV-56 Tasks

## Execution Plan

### Phase 1: Banco e aviso
T1 → T2 → T3

### Phase 2: Robô
T4

### Phase 3: Partida, reinício e docs
T5 → T6 → T7

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
T6 → T7
```

## Task Breakdown

### T1: SQL da sequence e da trigger
**What**: `SQ_OFERTA_FILA` (GREATEST + 1, NOCACHE, EXECUTE IMMEDIATE), `TRG_OFERTA_FILA_ID`, conferência e reversão.
**Where**: `tools/capture-chat-groups/sql/BSV-56_sequence_id_oferta.sql`
**Depends on**: none
**Reqs**: SQL-01, SQL-02, SQL-03
**Tests**: `tools/tests/test_sql_sequence.py` (lê o arquivo)
**Gate**: `pytest tests/test_sql_sequence.py` (em `tools/`)
- [x] Done

### T2: `proximo_id()` e `disponivel()`
**What**: `NEXTVAL` com uma reconexão; `ErroSemId`; `disponivel()`; `espera_segundos`; `configurado`.
**Where**: `tools/capture-chat-groups/wa/oracle_db.py`
**Depends on**: T1
**Reqs**: SEQ-04
**Tests**: `tools/tests/test_sequence_oracle.py`
**Gate**: `pytest tests/test_sequence_oracle.py tests/test_reconexao_oracle.py`
- [x] Done

### T3: Aviso de banco fora
**What**: `VigiaBanco` (1 aviso, lembrete 2 h, "voltou"), relógio e envio injetados, sem token no log.
**Where**: `tools/capture-chat-groups/wa/alerta.py`
**Depends on**: T2
**Reqs**: FORA-02
**Tests**: `tools/tests/test_alerta_banco.py`
**Gate**: `pytest tests/test_alerta_banco.py tests/test_alerta.py`
- [x] Done

### T4: Monitor numera pela sequence e espera o banco
**What**: ao vivo e catch-up com `proximo_id()`; banco fora não grava nem move marcador; espera com aviso; resgate depois; sai sem banco configurado; sem "Retomando contador".
**Where**: `tools/capture-chat-groups/wa/monitor.py`, `conf/config.example.json`
**Depends on**: T3
**Reqs**: SEQ-01, SEQ-02, SEQ-03, SEQ-05, FORA-01, FORA-03, FORA-04, FORA-05
**Tests**: `tools/tests/test_id_sequence_whatsapp.py`
**Gate**: `pytest` (em `tools/`)
- [x] Done

### T5: Partida sem conferência do contador
**What**: tira o passo 3 de `iniciar_captura.sh` e `iniciar_captura.ps1`; nota histórica em `checa_contador.py`.
**Where**: `tools/vps/iniciar_captura.sh`, `tools/capture-chat-groups/iniciar_captura.ps1`, `diag/checa_contador.py`, `tools/vps/encerrar_captura.sh` (mensagem)
**Depends on**: T4
**Reqs**: PAR-01
**Tests**: `tools/tests/test_iniciar_captura.py`, `tools/tests/test_scope_whatsapp.py`
**Gate**: `pytest tests/test_iniciar_captura.py tests/test_scope_whatsapp.py` + `shellcheck vps/*.sh`
- [x] Done

### T6: Reinício diário só com `Grupo aberto`
**What**: testes do reinício sem "Retomando contador"; REI-03 com outro `ABORTADO:`; comentário do script.
**Where**: `tools/tests/test_reinicio_whatsapp.py`, `tools/vps/reiniciar_whatsapp.sh` (comentário)
**Depends on**: T5
**Reqs**: PAR-02
**Tests**: `tools/tests/test_reinicio_whatsapp.py`
**Gate**: `pytest tests/test_reinicio_whatsapp.py`
- [ ] Done

### T7: README e ordem de virada
**What**: ordem de virada e fim da conferência do contador nos dois README.
**Where**: `tools/vps/README.md`, `tools/capture-chat-groups/RESUMO.md`
**Depends on**: T6
**Reqs**: spec saída 5
**Tests**: none (docs)
**Gate**: `pytest` + `ruff check vps/ tests/` (em `tools/`)
- [ ] Done

## Test Coverage Matrix

| Camada | Teste | Tarefas |
| --- | --- | --- |
| SQL (leitura do arquivo) | `tools/tests/test_sql_sequence.py` | T1 |
| Oracle falso | `tools/tests/test_sequence_oracle.py` | T2 |
| Aviso (relógio e envio falsos) | `tools/tests/test_alerta_banco.py` | T3 |
| Monitor sem Playwright | `tools/tests/test_id_sequence_whatsapp.py` | T4 |
| Scripts bash com comandos falsos | `tools/tests/test_iniciar_captura.py`, `test_scope_whatsapp.py`, `test_reinicio_whatsapp.py` | T5, T6 |
| Docs | none | T7 |

## Gate Check Commands

- `cd tools/capture-chat-groups && python -m unittest discover -s tests`
- `cd tools && python -m pytest -q`
- `cd tools && ruff check vps/ tests/`
- `cd tools && shellcheck vps/*.sh`
