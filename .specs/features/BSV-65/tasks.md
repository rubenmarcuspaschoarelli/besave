# BSV-65 Tasks

## Execution Plan

### Phase 1: Robô
T1 → T2 → T3

### Phase 2: Vigia e documentação
T4 → T5

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
```

## Task Breakdown

### T1: Classificação, controle e diagnóstico ✅
**What**: `core/navegador.py` (`sinal`, `e_timeout`, `Controle`, `diagnostico`), `batimento` usa `sinal` e grava os campos da Saída 6, `estado.ler_relancar_navegador_horas`, `link_afiliado.capturar` relança navegador quebrado.
**Where**: `tools/capture-store-pages/core/{navegador,batimento,estado,link_afiliado}.py`
**Depends on**: none
**Reqs**: CLS-01, CLS-02, VIG-01, DIA-01, PRE-01
**Tests**: `tools/tests/test_navegador_lojas.py`
**Gate**: `cd tools && pytest tests/test_navegador_lojas.py tests/test_batimento_lojas.py`

### T2: Lote: linha retida, timeouts e parada ✅
**What**: `_processar_lote` retém a linha, conta timeouts, para o lote, avisa "voltou", atualiza os campos do batimento.
**Where**: `tools/capture-store-pages/main.py`
**Depends on**: T1
**Reqs**: LIN-01, LIN-02, TMO-01, TMO-02, TMO-03, TEL-03, VIG-01
**Tests**: `tools/tests/test_navegador_lote.py`
**Gate**: `cd tools && pytest`

### T3: Recuperação, código 3 e preventivo ✅
**What**: `_Sessao`, `_recuperar_navegador`, `_relancar`, saída 3, preventivo no `_monitorar`, lote sem monitor, evento `crash`.
**Where**: `tools/capture-store-pages/main.py`
**Depends on**: T2
**Reqs**: REC-01, REC-02, REC-03, TEL-01, TEL-02, DIA-01, PRE-01
**Tests**: `tools/tests/test_navegador_recuperacao.py`
**Gate**: `cd tools && pytest`

### T4: Vigia vê captura por navegador
**What**: `Batimento` com os dois campos opcionais; aviso sem reinício, lembrete e "voltou".
**Where**: `tools/vps/vigia_robos.py`
**Depends on**: T3
**Reqs**: VIG-02
**Tests**: `tools/tests/test_vigia_navegador.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T5: README e config de exemplo
**What**: seção "Navegador quebrado", código 3, preventivo, SQL; `config.example.json`.
**Where**: `tools/capture-store-pages/README.md`, `tools/capture-store-pages/conf/config.example.json`
**Depends on**: T4
**Reqs**: DOC-01
**Tests**: none (documentação)
**Gate**: `cd tools && pytest`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| CLS-01, CLS-02, VIG-01, DIA-01, PRE-01 (leitura da chave) | `tools/tests/test_navegador_lojas.py` | T1 |
| LIN-01, LIN-02, TMO-01..03, TEL-03, VIG-01 | `tools/tests/test_navegador_lote.py` | T2 |
| REC-01..03, TEL-01, TEL-02, DIA-01, PRE-01 | `tools/tests/test_navegador_recuperacao.py` | T3 |
| VIG-02 | `tools/tests/test_vigia_navegador.py` | T4 |
| DOC-01 | none (revisão do README) | T5 |

## Gate Check Commands

| Level | Command |
| ----- | ------- |
| quick | `cd tools && pytest tests/<arquivo>` |
| build | `cd tools && pytest && ruff check vps/ tests/` |
| wsl | `wsl -- bash -lc 'cd <tools> && python3 -m pytest tests/test_vigia_navegador.py tests/test_vigia_robos.py'` |
