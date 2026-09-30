# BSV-13b — Reaproveitamento de imagens por listagem + tempo por fase

Fonte: `docs/specs/BSV-13b.md` (escopo), CONTRATO §6; MANIFEST §6.
Pasta: `apps/worker/`. Depende de BSV-13 e BSV-21 (ambos em `develop`).

## Problem Statement

`publicar_imagens` decide reaproveitamento com `existem`, que no `PublicadorS3` é um `HeadObject`
por chave: ~21,7 mil HEAD por ciclo com ~10,8 mil ofertas. O 2º ciclo real levou 788 s e, a 288
ciclos/dia, os HEAD sozinhos custariam ~US$ 75/mês. O relatório não diz qual fase gastou o tempo.

## Goals

- [ ] Ciclo sem mudança: 0 imagens publicadas, 0 `existe`/`existem` vindos de imagens, poucas listagens.
- [ ] Relatório e saída do binário mostram o tempo (ms) de cada fase de `gerar()`.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Mudar a listagem da KVS | decidido depois, com os tempos medidos aqui |
| Agendamento | BSV-14 |
| Índice de imagens em `_estado/` | spec regra 3: a listagem é a fonte de verdade |
| Reprocessar imagens | fora da spec |
| `PublicadorPlano` repassar `existem`/`gravar_lote` ao destino | não pedido; relatado no PR |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Chave estranha | Em `img/ofertas/`, tudo que não é `{dígitos}.webp` nem `{dígitos}-small.webp` | Spec regra 3; `5412_small.webp` e `.jpg` contam como estranhas | n |
| Erro de listagem | `ErroImagens::Listagem { prefixo, fonte }`, embrulhado em `ErroGeracao::Imagens` | "erro nomeado"; imagens vêm antes dos chunks, então nenhum manifest é gravado | n |
| Onde medir `t_imagens_listagem` | `gerar` lista uma vez (`ImagensExistentes::listar`) e passa o conjunto a `publicar_imagens_com`; `publicar_imagens` continua como atalho | Mede sem decorator e sem mudar a assinatura pública existente | n |
| `t_redirects_listagem` | Soma de todo `Redirects::listar()` do ciclo (o do início, para expurgo, e o de `sincronizar_redirects`) via decorator privado em `geracao.rs` | São duas listagens da KVS por ciclo; o objetivo é achar esse custo | n |
| `t_redirects` | Listagem inicial + `sincronizar_redirects` | Sub-medida ⊂ medida | n |
| `t_manifest` | Leitura do manifest anterior + gravação de `manifest.prev.json` e `manifest.json` | Tudo que toca o manifest | n |
| `t_orfaos` | Remoção de chunks órfãos + expurgo de imagens | Etapas 6–7 do MANIFEST §6 | n |
| `t_leitura_fonte` | `ofertas()` + conversão + `produtos()` + páginas | Tudo antes da 1ª escrita | n |
| Formato na saída | `t_<fase>: <n> ms`, uma linha por medida | Nomes exatos da spec; unidade explícita | n |
| Contadores do `PublicadorMemoria` | `Cell<u64>` para `listar`, `existe`, `existem`; `existem` sobrescrito para não contar `existe` | Spec regra 4 ("separadamente") | n |
| Teste de literal `Relatorio {..}` em `tests/geracao.rs` | Recebe `tempos: rel.tempos` e `chaves_estranhas: 0` | Campo novo exige no literal; nenhuma asserção enfraquecida | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Existência de imagens por listagem ⭐ MVP

**User Story**: Como dono, quero que um ciclo sem mudança não pague um HEAD por imagem.

**Acceptance Criteria**:

1. LST-01: WHEN 5000 ids have both keys in the destination THEN `publicar_imagens` SHALL make 0 calls to `existe` and 0 to `existem`, at most 10 calls to `listar`, and report `publicadas = 0`, `reaproveitadas = 5000`.
2. LST-02: WHEN an id has no key in the listed set THEN the worker SHALL publish both keys.
3. LST-03: WHEN an id has only one of its two keys in the listed set THEN the worker SHALL publish (write) both keys.
4. LST-04: WHEN a placeholder key is listed THEN the worker SHALL NOT write it; WHEN it is absent THEN the worker SHALL write it.
5. LST-05: IF `listar("img/ofertas/")` or `listar("img/placeholder/")` fails THEN `gerar` SHALL return `ErroGeracao::Imagens(ErroImagens::Listagem { prefixo, .. })` naming that prefix and SHALL NOT write `manifest.json`.
6. LST-06: WHEN `img/ofertas/` holds a key other than `{id}.webp` / `{id}-small.webp` THEN the worker SHALL count it in `chaves_estranhas`, SHALL NOT treat it as either image of any id, and SHALL NOT remove it.
7. LST-07: `PublicadorMemoria` SHALL expose separate call counts for `listar`, `existe` and `existem`.

**Independent Test**: `publicar_imagens` sobre `PublicadorMemoria` pré-populado com 10 000 chaves.

### P1: Tempo por fase

**User Story**: Como dono, quero ver quanto cada fase de `gerar()` custou para achar o próximo gargalo.

**Acceptance Criteria**:

1. TMP-01: `Relatorio` SHALL carry, in ms, `t_leitura_fonte`, `t_imagens`, `t_imagens_listagem`, `t_chunks`, `t_paginas`, `t_redirects`, `t_redirects_listagem`, `t_manifest`, `t_orfaos`, with each sub-measure ≤ its parent.
2. TMP-02: WHEN the binary finishes `--gerar` or `--publicar` THEN it SHALL print one line per measure of TMP-01, plus `imagens_chaves_estranhas`.

**Independent Test**: `--gerar` com `BESAVE_FONTE=fake` imprime as 9 linhas `t_*`.

---

## Edge Cases

- WHEN `img/ofertas/5412_small.webp` and `img/ofertas/5412.webp` exist THEN id 5412 SHALL be published (the strange key is not a small; LST-06 × LST-03).
- WHEN the id list is empty THEN only the placeholder decision runs (LST-04).

Dimensions: dependência externa com falha (LST-05); idempotência (LST-01, LST-04); observabilidade (TMP-01, TMP-02, LST-06). Auth, concorrência, estado persistido: N/A because a listagem é só leitura, o conjunto vive em memória e nada é gravado em `_estado/`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| LST-07 | P1: Listagem | Step 1 | Done |
| LST-01 | P1: Listagem | Step 2 | Done |
| LST-02 | P1: Listagem | Step 2 | Done |
| LST-03 | P1: Listagem | Step 2 | Done |
| LST-04 | P1: Listagem | Step 2 | Done |
| LST-05 | P1: Listagem | Step 2 | Done |
| LST-06 | P1: Listagem | Step 2 | Done |
| TMP-01 | P1: Tempo por fase | Step 3 | Pending |
| TMP-02 | P1: Tempo por fase | Step 3 | Pending |

**Coverage:** 9 total, 9 mapped to steps, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde, sem rede.
- [ ] Execução real do dono: duas `--publicar --sim` seguidas; a 2ª < 2 min; nenhuma imagem antiga com data nova.
