# BSV-36 Specification — `dp` (data de publicação no site) no card

Fonte: `docs/specs/BSV-36.md`. Contrato: CONTRATO §3, §10.6, §11; MANIFEST §3.1, §7; AD-063, AD-064, AD-066, AD-074.

## Problem Statement

"Mais recentes" ordena por `DT_OFERTA`; uma oferta antiga que só ganhou URL de afiliado agora cai no meio
da lista. A data em que a oferta entrou no site já existe no Oracle (`OFERTA.DT_PUBLICACAO_SITE`, BSV-40),
mas não está no card. O site precisa dela para ordenar e para a faixa "Maiores descontos de hoje".

## Goals

- [ ] Todo `OfertaCard` publicado traz `dp` (ISO 8601 UTC), igual ao valor gravado no Oracle.
- [ ] A camada de dados do site ordena `recentes` por `dp` e oferece `maioresDescontos(cat, agora, n)`.
- [ ] Ciclo sem mudança continua com 0 chunks escritos (AD-028).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| UI da home (faixas, toast, layout) | BSV-30/31 |
| Envio ao canal | continua com `DT_OFERTA` nas 24 h (spec) |
| `dp` na página da oferta (`OfertaPagina`) | spec, fora de escopo |
| `dt_max`/alerta de "horas sem novas" por `dp` | não pedido; segue por `dt` |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Limite inferior "2026-10-06" | `2026-10-06T00:00:00Z` (1791244800) | Menor que qualquer gravação real (a BSV-40 gravou a partir de 06/10 hora local, ≥ 03:00Z); aceitar 3 h a mais não muda nada | n |
| "Instante do ciclo" | `agora` do ciclo truncado ao minuto (UTC); é também o limite superior | Texto da spec | y |
| Limite inferior quando o instante do ciclo é anterior a 2026-10-06 (só testes/ensaio com relógio antigo) | sem limite inferior: faixa = `(-∞, instante]` | Os testes existentes usam relógio de 24/09/2026; faixa colapsada em `[instante, instante]` tornaria todo valor gravado inválido no ciclo seguinte e quebraria a idempotência. Em produção o instante é sempre ≥ limite | n |
| Valor fora da faixa no Oracle | card usa o instante do ciclo + WARN, e o `UPDATE` pós-manifest **regrava** a coluna com esse instante | Sem regravar, o próximo ciclo cairia de novo no instante (novo) e os chunks mudariam todo ciclo, violando a regra 2 (idempotência). A data só é escrita pelo `besave-ciclo` | n |
| `UPDATE` pós-manifest | `SET DT_PUBLICACAO_SITE = <instante local> WHERE ID_OFERTA IN (…) AND (DT_PUBLICACAO_SITE IS NULL OR < <limite> OR > <instante>)`; datas como segundos locais (`DATE '1970-01-01' + :n/86400`), mesmo padrão do envio | Grava o mesmo valor do card; só toca nula ou fora da faixa; continua 1 statement por bloco de 1 000 ids (BSV-40) | n |
| `BESAVE_DESTINO_LOCAL` | continua sem gravar a coluna (BSV-40); `dp` dos novos muda a cada ciclo nesse modo | Modo de ensaio; não é publicado | y |
| Posição de `dp` no JSON | logo depois de `dt` | Agrupa as datas; fixtures definem a ordem | n |
| Card sem `dp` no site | tipo `dp?: string`; ordem e janela usam `dp ?? dt` | Chunk antigo em cache durante a troca (spec) | y |
| "Desconto" em `maioresDescontos` | `round((1 - pp/pd) * 100)` (CONTRATO §3); card sem `pd` fica de fora | Sem `pd` não há desconto a mostrar | n |
| Janela "últimas 24 h" | `agora - 24 h ≤ dp`; `agora` em ms (`Date.now()`) | 24 h exatas entram; 25 h ficam de fora (critério) | n |
| `maioresDescontos` e ids pendentes (toast, AD-066) | segue a `lista()`: não mostra pendentes nem expiradas | Faixa da home não pode furar o "N novas ofertas" | n |
| Desempate em `maioresDescontos` | desconto desc → `dp` desc → `id` desc | Spec dá `dp`; `id` torna a ordem total, como em `recentes` | n |
| `dp` no gerador sintético | `dp = dt + (id·7919 mod 48 h)` s, sem consumir o PRNG | `dp ≥ dt` e não altera a sequência das outras colunas (testes de distribuição) | n |
| Orçamento de 1 000 cards realistas | medido sobre `gerarCards(1000, s)` (distribuição de produção, BSV-35) no teste do gerador | É o gerador "realista" que o repositório já mantém, na mesma serialização do worker | n |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Contrato 1.5.0 com `dp` ⭐ MVP

**User Story**: Como consumidor do chunk (site, app), quero `dp` em todo card para ordenar pela entrada no site.

**Acceptance Criteria**:

1. CON-01: The `oferta-card` schema SHALL require `dp` as `date-time`; IF a card lacks `dp` THEN `npm run validate` SHALL report it invalid (fixture `chunk-invalido.json`).
2. CON-02: WHEN `npm run validate` runs THEN `chunk-ok.json` (com `dp`) and `manifest-ok.json` (`contrato` 1.5.0) SHALL be valid.
3. CON-03: The contract package version SHALL be `1.5.0`, and the worker SHALL publish `contrato: "1.5.0"` in the manifest.
4. CON-04: CONTRATO §3 SHALL document `dp` and the 230 B average budget (AD-074); §10.6 SHALL be answered ("ordenação por `dp`").

**Independent Test**: `cd packages/contract && npm run validate`.

### P1: Worker publica `dp` e grava o mesmo instante ⭐ MVP

**User Story**: Como dono, quero que o card publicado e o Oracle tenham a mesma data de publicação.

**Acceptance Criteria**:

1. DP-01: WHEN `DT_PUBLICACAO_SITE` is within `[limite, instante]` THEN the worker SHALL publish `dp` = that value in ISO 8601 UTC (local → UTC by `BESAVE_ORACLE_TZ`, como `dt`).
2. DP-02: WHEN `DT_PUBLICACAO_SITE` is null THEN the worker SHALL publish `dp` = cycle instant (`agora` truncated to the minute).
3. DP-03: IF `DT_PUBLICACAO_SITE` is after the cycle instant THEN the worker SHALL publish `dp` = cycle instant AND log a WARN naming the id; the offer SHALL still be published.
4. DP-04: IF `DT_PUBLICACAO_SITE` is before `2026-10-06T00:00:00Z` THEN the worker SHALL publish `dp` = cycle instant AND log a WARN; the offer SHALL still be published.
5. GRV-01: WHEN the manifest is published THEN the post-manifest `UPDATE` SHALL write the cycle instant (the same `dp` of the card) to every published id whose column is null or out of range, and SHALL leave in-range values unchanged.
6. GRV-02: The `UPDATE` SQL SHALL bind the instant (no `SYSDATE`) and keep one bind per id.
7. IDE-01: WHEN a second cycle runs with no change in the source THEN every card SHALL keep the same `dp`, and the cycle SHALL write 0 chunks.
8. ORC-01: The average raw card of 1 000 realistic cards SHALL be ≤ 230 B, and their compressed chunk SHALL be ≤ 60 KB.

**Independent Test**: `cargo test` in `apps/worker` (fakes; no Oracle).

### P1: Site ordena por `dp` e oferece "Maiores descontos de hoje" ⭐ MVP

**User Story**: Como visitante, quero ver primeiro o que entrou no site por último e os maiores descontos do dia.

**Acceptance Criteria**:

1. SIT-01: WHEN `lista({ordem: 'recentes'})` runs THEN cards SHALL be ordered by `dp` desc, then `id` desc, even when that differs from the `dt` order.
2. SIT-02: IF a card has no `dp` THEN `recentes` SHALL use its `dt` in place of `dp`.
3. SIT-03: WHEN `maioresDescontos(cat, agora, n)` runs THEN it SHALL return at most `n` active cards with `dp ≥ agora − 24 h`, ordered by discount desc, then `dp` desc.
4. SIT-04: IF a card has `dp` 25 h before `agora` THEN `maioresDescontos` SHALL exclude it.
5. SIT-05: IF a card is expired (`x: 1`) THEN `maioresDescontos` SHALL exclude it.
6. SIT-06: The synthetic generator SHALL emit `dp` on every card with `dp ≥ dt`, and its output SHALL validate against the 1.5.0 schema.

**Independent Test**: `pnpm test` in `apps/site`.

---

## Edge Cases

- IF `DT_PUBLICACAO_SITE` equals the cycle instant exactly THEN it SHALL be accepted (upper bound inclusive).
- WHEN `agora` is not minute-aligned THEN `dp` for new offers SHALL end in `:00` seconds.
- IF the `UPDATE` fails THEN the cycle SHALL still exit 0 with `publicacao_site_falhas` (BSV-40 CIC-03 unchanged).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CON-01 | P1: Contrato | T1 | Verified |
| CON-02 | P1: Contrato | T1 | Verified |
| CON-03 | P1: Contrato | T1 | Verified |
| CON-04 | P1: Contrato | T1 | Verified |
| DP-01 | P1: Worker | T1 | Verified |
| DP-02 | P1: Worker | T1 | Verified |
| DP-03 | P1: Worker | T1 | Verified |
| DP-04 | P1: Worker | T1 | Verified |
| GRV-01 | P1: Worker | T2 | Verified |
| GRV-02 | P1: Worker | T2 | Verified |
| IDE-01 | P1: Worker | T2 | Verified |
| ORC-01 | P1: Worker | T3 | Verified |
| SIT-01 | P1: Site | T3 | Verified |
| SIT-02 | P1: Site | T3 | Verified |
| SIT-03 | P1: Site | T3 | Verified |
| SIT-04 | P1: Site | T3 | Verified |
| SIT-05 | P1: Site | T3 | Verified |
| SIT-06 | P1: Site | T3 | Verified |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `npm run validate`, `cargo fmt/clippy/test`, `pnpm lint/check/test/build` verdes.
- [ ] Execução real (dono): primeiro ciclo regrava os chunks uma vez; segundo ciclo → `chunks_escritos=0`.
