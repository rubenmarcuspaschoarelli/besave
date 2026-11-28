# BSV-67 Tasks

## Execution Plan

### Phase 1: Robô
T1 → T2

### Phase 2: VPS
T3 → T4

### Phase 3: Documentação
T5

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
```

## Task Breakdown

### T1: Tela de login, código e teto de pedidos ✅
**What**: `wa/pareamento.py` (seletores, `TelaWhatsApp`, leitura do código, máscara do número, teto 3/h e 12/dia persistido, mensagens, espera viva com batimento); fixtures redigidas da página real e simulador de teste.
**Where**: `tools/capture-chat-groups/wa/pareamento.py`, `tools/tests/fixtures/whatsapp/`
**Depends on**: none
**Reqs**: TEL-01, TEL-02, PAR-01..07, FIX-01
**Tests**: `tools/tests/test_pareamento.py`, `tools/tests/test_pareamento_pagina.py`
**Gate**: `cd tools && pytest tests/test_pareamento.py tests/test_pareamento_pagina.py && ruff check vps/ tests/`

### T2: Restauração da cópia e fiação no robô ✅
**What**: `wa/sessao.py` (restaurar uma vez, `restaurada_em`, `user_data.qr/`); `browser.abrir_whatsapp` detecta a tela, restaura, pareia; `monitor` passa batimento e config.
**Where**: `tools/capture-chat-groups/wa/{sessao,browser,monitor}.py`
**Depends on**: T1
**Reqs**: RES-01..03, TEL-01, PAR-03
**Tests**: `tools/tests/test_sessao_whatsapp.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T3: Cópia da sessão no reinício programado ✅
**What**: `reiniciar_whatsapp.sh`: `stop` + cópia (sem caches, `.nova` + `mv`, só com `Grupo aberto`) + `start`.
**Where**: `tools/vps/reiniciar_whatsapp.sh`
**Depends on**: T2
**Reqs**: COP-01..03
**Tests**: `tools/tests/test_reinicio_whatsapp.py`
**Gate**: `cd tools && pytest tests/test_reinicio_whatsapp.py && ruff check vps/ tests/`

### T4: Vigia: fase pareamento e reinício por memória ✅
**What**: `vigia_robos.py`: espera do pareamento sem reinício nem laço, lembrete de 6 h; vencido reinicia; RSS > limite dispara o reinício programado (1/60 min, aviso no 2º em 6 h).
**Where**: `tools/vps/vigia_robos.py`
**Depends on**: T3
**Reqs**: VIG-01, VIG-02, MEM-01, MEM-02
**Tests**: `tools/tests/test_vigia_pareamento.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T5: README, config de exemplo e .gitignore ✅
**What**: mensagens novas, chave `pareamento`, VNC, cópia e restauração à mão; `config.example.json`; `.gitignore` das pastas novas.
**Where**: `tools/capture-chat-groups/README.md` (novo), `tools/capture-chat-groups/conf/config.example.json`, `.gitignore`, `tools/vps/README.md`
**Depends on**: T4
**Reqs**: DOC-01
**Tests**: none (documentação)
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| TEL-01, TEL-02, PAR-01..07, FIX-01 | `tools/tests/test_pareamento.py`, `tools/tests/test_pareamento_pagina.py` | T1 |
| RES-01..03 | `tools/tests/test_sessao_whatsapp.py` | T2 |
| COP-01..03 | `tools/tests/test_reinicio_whatsapp.py` | T3 |
| VIG-01, VIG-02, MEM-01, MEM-02 | `tools/tests/test_vigia_pareamento.py` | T4 |
| DOC-01 | none (revisão) | T5 |

## Gate Check Commands

- quick: `cd tools && pytest tests/<arquivo>`
- build: `cd tools && pytest && ruff check vps/ tests/`
- página com Chromium (PC/WSL): venv com Playwright → `pytest tests/test_pareamento_pagina.py`
