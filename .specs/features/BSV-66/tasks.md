# BSV-66 Tasks

## Execution Plan

### Phase 1: Núcleo puro
T1 → T2 → T3

### Phase 2: Rodada e operação
T4 → T5 → T6

### Phase 3: Correções do Verifier (ciclo 1)
T7

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
T6 → T7
```

## Test Coverage Matrix

| Req | Test file |
| --- | --------- |
| LER-03, LER-04 | `tools/tests/test_web_extrair.py` |
| URL-01, URL-02, URL-03 | `tools/tests/test_web_url.py` |
| LER-01, LER-02, LER-05 | `tools/tests/test_web_http.py` |
| FIL-01, FIL-02, GRV-01, GRV-02 | `tools/tests/test_web_filtros.py`, `tools/tests/test_web_banco.py` |
| COT-01, AVI-01, ROD-01 | `tools/tests/test_web_rodada.py` |
| CFG-01, OPS-01, OPS-02 | `tools/tests/test_web_config.py` |

## Gate Check Commands

- `cd tools && python -m pytest -q tests/test_web_*.py`
- `cd tools && python -m ruff check vps/ tests/ capture-web-apoio/`

## Task Breakdown

### T1: Extratores ✅
**What**: `webapoio/extrair.py` (Astro do Pelando, `__NEXT_DATA__` do Promobit e Pechinchou, redirect do Promobit, datas), `webapoio/oferta.py`; caminho no `conftest.py`.
**Where**: `tools/capture-web-apoio/webapoio/extrair.py`
**Depends on**: none
**Reqs**: LER-03, LER-04, LER-05
**Tests**: `tools/tests/test_web_extrair.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_extrair.py`

### T2: URL limpa e cupons ✅
**What**: `webapoio/url.py` (limpeza por loja, chave de produto, encurtador), `webapoio/cupons.py` (§4.3).
**Where**: `tools/capture-web-apoio/webapoio/url.py`
**Depends on**: T1
**Reqs**: URL-01, URL-02, URL-03
**Tests**: `tools/tests/test_web_url.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_url.py`

### T3: HTTP, banco e estado ✅
**What**: `webapoio/http.py` (cabeçalhos, pausa, repetição, 403/429, sem redirect), `webapoio/banco.py` (consulta de "já vista", `INSERT`, reconexão), `webapoio/estado.py` (`vistas.json`, trava).
**Where**: `tools/capture-web-apoio/webapoio/banco.py`
**Depends on**: T2
**Reqs**: LER-01, LER-02, GRV-01, GRV-02
**Tests**: `tools/tests/test_web_http.py`, `tools/tests/test_web_banco.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_http.py tests/test_web_banco.py`

### T4: Rodada ✅
**What**: `webapoio/rodada.py` (filtros na ordem, rodízio, cotas, resumo, mensagem), `webapoio/alerta.py`.
**Where**: `tools/capture-web-apoio/webapoio/rodada.py`
**Depends on**: T3
**Reqs**: FIL-01, FIL-02, COT-01, AVI-01
**Tests**: `tools/tests/test_web_filtros.py`, `tools/tests/test_web_rodada.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_filtros.py tests/test_web_rodada.py`

### T5: CLI, config e log ✅
**What**: `main.py`, `webapoio/cli.py` (`--simular`, trava → 2, log com rotação), `webapoio/config.py`, `conf/config.example.json`, `requirements.txt`.
**Where**: `tools/capture-web-apoio/webapoio/cli.py`
**Depends on**: T4
**Reqs**: ROD-01, CFG-01
**Tests**: `tools/tests/test_web_config.py`, `tools/tests/test_web_rodada.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_*.py`

### T6: Operação e CI ✅
**What**: `agendar.ps1`, `sql/bsv-66-usuario.sql`, `README.md`, `ruff` no job `tools`.
**Where**: `tools/capture-web-apoio/agendar.ps1`
**Depends on**: T5
**Reqs**: OPS-01, OPS-02
**Tests**: `tools/tests/test_web_config.py`
**Gate**: `cd tools && python -m pytest -q && python -m ruff check vps/ tests/ capture-web-apoio/`

### T7: Testes dos 4 mutantes sobreviventes do ciclo 1 ✅
**What**: título com trim e corte em 350 no INSERT; `preco_de` igual ao `por` vira `NULL`; linha inteira do resumo (`lidas`/`validas`); descartes transitórios fora do estado local.
**Where**: `tools/tests/test_web_filtros.py`
**Depends on**: T6
**Reqs**: GRV-01, LER-03, FIL-02
**Tests**: `tools/tests/test_web_filtros.py`, `tools/tests/test_web_extrair.py`, `tools/tests/test_web_rodada.py`
**Gate**: `cd tools && python -m pytest -q tests/test_web_*.py`
