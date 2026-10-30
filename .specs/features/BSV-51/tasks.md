# BSV-51 Tasks

## Execution Plan

### Phase 1: Núcleos (sequencial)
T1 → T2

### Phase 2: Vigia
T3

### Phase 3: Integração e docs
T4 → T5

```
T1 → T2
T1 → T4
T3 → T4
T4 → T5
```

## Task Breakdown

### T1: Destravar sobreposição
**What**: `clicar()` com 5 s por tentativa, Escape, fechar da lista fechada; `recarregar()`.
**Where**: `tools/capture-chat-groups/wa/destravar.py`
**Depends on**: none
**Reqs**: DES-01, DES-02, DES-03, DES-04, DES-05
**Tests**: `tools/tests/test_destravar.py`
**Gate**: `pytest tests/test_destravar.py` (em `tools/`)

### T2: Ligar em abrir_grupo
**What**: os dois cliques de `abrir_grupo` passam por `destravar.clicar`.
**Where**: `tools/capture-chat-groups/wa/browser.py`
**Depends on**: T1
**Reqs**: DES-01, DES-03, DES-05
**Tests**: `tools/tests/test_destravar.py`
**Gate**: `pytest tests/test_destravar.py`

### T3: Vigia de captura parada
**What**: `VigiaCaptura` com relógio injetado e envio ao Telegram por `urllib`.
**Where**: `tools/capture-chat-groups/wa/alerta.py`
**Depends on**: none
**Reqs**: ALE-01, ALE-02, ALE-03, ALE-04
**Tests**: `tools/tests/test_alerta.py`
**Gate**: `pytest tests/test_alerta.py`

### T4: Recarregar e vigia no rodízio
**What**: recarrega a cada N voltas cegas, marca resgate; chama o vigia a cada volta; config de exemplo.
**Where**: `tools/capture-chat-groups/wa/monitor.py`
**Depends on**: T1, T3
**Reqs**: REC-01, REC-02, ALE-01, ALE-02, ALE-03
**Tests**: `tools/tests/test_rodizio_destravar.py`
**Gate**: `pytest tests`

### T5: README da VPS
**What**: o que o robô faz sozinho, log, Telegram, quando entrar na tela.
**Where**: `tools/vps/README.md`
**Depends on**: T4
**Reqs**: spec saída 5
**Tests**: `tools/tests/test_rodizio_destravar.py` (confere as chaves documentadas)
**Gate**: `pytest tests`

## Test Coverage Matrix

| Camada | Teste | Tasks |
| --- | --- | --- |
| clique/destravar | `test_destravar.py` | T1, T2 |
| vigia | `test_alerta.py` | T3 |
| rodízio | `test_rodizio_destravar.py` | T4, T5 |

## Gate Check Commands

| Nível | Comando |
| --- | --- |
| Quick | `cd tools && pytest tests/<arquivo>` |
| Full | `cd tools && pytest && ruff check vps/ tests/ && cd capture-chat-groups && python -m unittest discover -s tests` |
