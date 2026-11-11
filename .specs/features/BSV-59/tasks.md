# BSV-59 Tasks

## Execution Plan

### Phase 1: Cliente da API
T1 → T2

### Phase 2: Lote e docs
T3 → T4

### Phase 3: Correções do Verifier (iteração 1)
T5

### Phase 4: Rebase sobre a BSV-57 (batimento)
T6

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
```

## Task Breakdown

### T1: Assinatura e cliente GraphQL ✅
**What**: `core/shopee_api.py` com assinatura, `produto`, `link_afiliado` e classificação de erros (HTTP 200 com `errors`).
**Where**: `tools/capture-store-pages/core/shopee_api.py`
**Depends on**: none
**Reqs**: ASS-01, PRO-01, PRO-02, LNK-01, ERR-01, SEG-01
**Tests**: `tools/tests/test_shopee_api.py` (servidor HTTP local)
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T2: Resolução da URL ✅
**What**: `resolver(url)` sem seguir redirect, até 3 pedidos, extração de ids dos formatos da spec.
**Where**: `tools/capture-store-pages/core/shopee_api.py`
**Depends on**: T1
**Reqs**: RES-01, RES-02
**Tests**: `tools/tests/test_shopee_api.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T3: Integração no lote e pausa ✅
**What**: `_processar_lote` usa a API na Shopee com `habilitado`; `shopee_api_indisponivel` em `STATUS_RETER`; motivo `shopee_api` na `PausaLojas`; bloco no `config.example.json`.
**Where**: `tools/capture-store-pages/main.py`, `core/bloqueio.py`, `conf/config.example.json`
**Depends on**: T2
**Reqs**: CFG-01, NAV-01, FAL-01, PAU-01, SEG-01
**Tests**: `tools/tests/test_shopee_lote.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T4: README e SQL das retidas ✅
**What**: seção Shopee no README; `sql/BSV-59_retidas_shopee.sql`.
**Where**: `tools/capture-store-pages/README.md`, `tools/capture-store-pages/sql/BSV-59_retidas_shopee.sql`
**Depends on**: T3
**Reqs**: DOC-01
**Tests**: `tools/tests/test_shopee_lote.py` (motivos e chaves documentados)
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T5: Correções do Verifier ✅
**What**: preço grande trava o `float` (M11); servidor falso sem thread viva nem escrita em socket fechado; `url_final` limpo asserido (M33); `http.client.HTTPException` vira `api_indisponivel`; imagens do teste em `tmp_path`.
**Where**: `tools/tests/test_shopee_api.py`, `tools/tests/test_shopee_lote.py`, `tools/capture-store-pages/core/shopee_api.py`
**Depends on**: T4
**Reqs**: PRO-01, ERR-01, FAL-01
**Tests**: `tools/tests/test_shopee_api.py`, `tools/tests/test_shopee_lote.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

### T6: Batimento no caminho da API e na pausa ✅
**What**: rebase sobre a BSV-57; a linha da Shopee pela API passa pelo mesmo `bater_linha` do lote; testes do batimento por linha da API e da espera com a Shopee pausada pela API.
**Where**: `tools/capture-store-pages/main.py`, `tools/tests/test_shopee_lote.py`
**Depends on**: T5
**Reqs**: BAT-01, BAT-02
**Tests**: `tools/tests/test_shopee_lote.py`
**Gate**: `cd tools && pytest && ruff check vps/ tests/`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| ASS-01, PRO-01, PRO-02, LNK-01, ERR-01 | `tools/tests/test_shopee_api.py` | T1 |
| RES-01, RES-02 | `tools/tests/test_shopee_api.py` | T2 |
| CFG-01, NAV-01, FAL-01, PAU-01, SEG-01 | `tools/tests/test_shopee_lote.py` | T3 |
| DOC-01 | `tools/tests/test_shopee_lote.py` | T4 |
| BAT-01, BAT-02 | `tools/tests/test_shopee_lote.py` | T6 |

## Gate Check Commands

- `cd tools && pytest`
- `cd tools && ruff check vps/ tests/`
