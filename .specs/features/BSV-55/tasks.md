# BSV-55 Tasks

## Execution Plan

### Phase 1: Partida sem perguntas
T1

### Phase 2: Bloqueio e afiliado
T2 → T3

### Phase 3: Pausa, alerta e docs
T4 → T5

```
T2 → T3
T3 → T4
T4 → T5
```

## Task Breakdown

### T1: `--sem-perguntas` e unidade ✅
**What**: opção no `main.py`; gates de Shopee, afiliados e "Fechou tudo?" sem `input()`; navegador aberto → `exit 2`; unidade com a opção.
**Where**: `tools/capture-store-pages/main.py`, `tools/vps/systemd/besave-captura-lojas.service`
**Depends on**: none
**Reqs**: SEM-01, SEM-02, SEM-03, SEM-04
**Tests**: `tools/tests/test_sem_perguntas.py`, `tools/tests/test_unidades.py`
**Gate**: `pytest` (em `tools/`)

### T2: Marcas de bloqueio e linha retida ✅
**What**: marcas das três lojas no caminho da URL; `bloqueado_ou_login` fica `'0'` e trava o ponteiro.
**Where**: `tools/capture-store-pages/main.py`
**Depends on**: none
**Reqs**: BLQ-01, BLQ-02
**Tests**: `tools/tests/test_bloqueio_lojas.py`
**Gate**: `pytest`

### T3: Motivo do afiliado ✅
**What**: `link_afiliado.capturar` devolve `motivo_afiliado` (`sessao`/`outro`); `sessao` segura a linha; corta-circuito conta só `outro`.
**Where**: `tools/capture-store-pages/core/link_afiliado.py`, `tools/capture-store-pages/main.py`
**Depends on**: T2
**Reqs**: AFI-01, AFI-02
**Tests**: `tools/tests/test_bloqueio_lojas.py`
**Gate**: `pytest`

### T4: Pausa por loja e Telegram ✅
**What**: `core/bloqueio.py` (pausa, sonda, avisos com relógio injetado), `core/alerta.py` (envio); ligação no lote e no monitor; config de exemplo.
**Where**: `tools/capture-store-pages/core/bloqueio.py`, `core/alerta.py`, `main.py`, `conf/config.example.json`
**Depends on**: T3
**Reqs**: PAU-01, PAU-02, PAU-03, TEL-01, TEL-02
**Tests**: `tools/tests/test_pausa_lojas.py`
**Gate**: `pytest`

### T5: README da VPS
**What**: o que é automático, o que chega no Telegram, como logar pela tela sem parar o robô.
**Where**: `tools/vps/README.md`
**Depends on**: T4
**Reqs**: DOC-01
**Tests**: `tools/tests/test_pausa_lojas.py` (confere as chaves documentadas)
**Gate**: `pytest` e `ruff check vps/ tests/`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| SEM-01..03 | `tools/tests/test_sem_perguntas.py` | T1 |
| SEM-04 | `tools/tests/test_unidades.py` | T1 |
| BLQ-01, BLQ-02 | `tools/tests/test_bloqueio_lojas.py` | T2 |
| AFI-01, AFI-02 | `tools/tests/test_bloqueio_lojas.py` | T3 |
| PAU-01..03, TEL-01, TEL-02 | `tools/tests/test_pausa_lojas.py` | T4 |
| DOC-01 | `tools/tests/test_pausa_lojas.py` | T5 |

## Gate Check Commands

- `cd tools && pytest`
- `cd tools && ruff check vps/ tests/`
- `cd tools/capture-chat-groups && python -m unittest discover -s tests`
