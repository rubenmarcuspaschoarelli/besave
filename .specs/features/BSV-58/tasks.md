# BSV-58 Tasks

## Execution Plan

### Phase 1: Resolução pelo proxy
T1 → T2

### Phase 2: Cloudflare e túnel
T3 → T4

```
T1 → T2
T3 → T4
```

## Test Coverage Matrix

| Req | Teste |
| --- | --- |
| CFG-01, DOM-01, CMD-01, RES-02, FAL-01, FAL-02 | `tools/tests/test_redirecionamento.py` |
| RES-01, RES-03, PAU-01, CF-01, CF-02, SEG-01 | `tools/tests/test_redirecionamento_lote.py` |
| TUN-01, DOC-01 | `tools/tests/test_tunel_residencial.py` |

## Gate Check Commands

```
cd tools && python -m pytest -q && ruff check vps/ tests/ && shellcheck vps/*.sh
```

## Task Breakdown

### T1: `core/redirecionamento.py` ✅
**What**: leitura do bloco, casamento por sufixo de rótulo, comando `curl`, resolução salto a salto com motivos.
**Where**: `tools/capture-store-pages/core/redirecionamento.py`
**Depends on**: none
**Reqs**: CFG-01, DOM-01, CMD-01, RES-02, FAL-01, FAL-02, SEG-01
**Tests**: `tools/tests/test_redirecionamento.py`
**Gate**: `pytest` (em `tools/`)

### T2: Integração no lote e pausa por domínio ✅
**What**: `main.py` resolve antes do `_resolver_ponte`; `redirecionamento_indisponivel` em `STATUS_RETER`; pausa e filtro do monitor pela chave domínio; mensagens da pausa por motivo em `core/bloqueio.py`.
**Where**: `tools/capture-store-pages/main.py`, `core/bloqueio.py`
**Depends on**: T1
**Reqs**: CFG-01, RES-01, RES-03, FAL-01, FAL-02, PAU-01, SEG-01
**Tests**: `tools/tests/test_redirecionamento_lote.py`
**Gate**: `pytest`

### T3: Cloudflare fora da lista ✅
**What**: página de bloqueio do Cloudflare no `_resolver_ponte` retém a linha, loga e pausa pelo host com a sugestão.
**Where**: `tools/capture-store-pages/main.py`, `core/redirecionamento.py`, `core/bloqueio.py`
**Depends on**: none
**Reqs**: CF-01, CF-02
**Tests**: `tools/tests/test_redirecionamento_lote.py`
**Gate**: `pytest`

### T4: Túnel, README e config de exemplo
**What**: `tools/vps/tunel_residencial.ps1`, seção no `tools/vps/README.md`, bloco em `conf/config.example.json`.
**Where**: `tools/vps/`, `tools/capture-store-pages/conf/config.example.json`
**Depends on**: T3
**Reqs**: TUN-01, DOC-01
**Tests**: `tools/tests/test_tunel_residencial.py`
**Gate**: `pytest`, `ruff check vps/ tests/`, `shellcheck vps/*.sh`
