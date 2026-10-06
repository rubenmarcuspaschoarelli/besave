# BSV-35 — Site: camada de dados (manifest, chunks, sincronização, busca), sem UI

Fonte: `docs/specs/BSV-35.md` (escopo), CONTRATO §2, §3; MANIFEST §2, §3, §3.1, §4, §7; AD-020, AD-061..064.
Pasta: `apps/site/` (ainda não existe). Depende do contrato 1.3.3 (`packages/contract`).

## Problem Statement

A lista e a busca do site precisam de todos os cards no navegador (17 mil hoje, meta 30 mil), em
sincronia com o `manifest.json` que o worker regrava a cada ciclo. Sem uma camada de dados testável,
a UI (BSV-30..34) teria fetch, diff, polling e busca espalhados em componentes.

## Goals

- [ ] Um módulo TS puro (`src/lib/dados/`, exposto por `src/lib/dados.ts`) mantém o catálogo e baixa só os chunks que mudaram.
- [ ] Lista filtrada, contagem de novas e busca por prefixo respondem dentro dos orçamentos com 30 mil cards em Node.
- [ ] Esqueleto SvelteKit estático com `pnpm lint/check/test/build` verdes no CI.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| UI, componentes, toast visual, virtualização | BSV-30..34 |
| Tailwind e design | BSV-30 (a regra de Tailwind do `apps/site/CLAUDE.md` vale a partir dela) |
| Servir `.json.br` no `vite dev` | fora da spec |
| Índice de busca do worker, busca fuzzy, Web Worker, IndexedDB | fora da spec (AD-061) |
| `/404.html` e deploy do site | ticket de deploy do site |
| Fábrica de `Deps` para o navegador | a UI (BSV-30) monta as deps; o módulo não toca `window` (regra 11) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Como os eventos saem do sincronizador | `Deps.aoEvento(e: Evento)`, união discriminada por `tipo` | A spec lista os eventos, não o mecanismo; callback injetado mantém o módulo puro | n |
| Evento extra `atualizado` | Emitido ao fim de cada sincronização que aplicou ou descartou chunk | Regra 8 exige que mudança de preço apareça "na hora"; sem sinal a UI não sabe quando reler `lista` | n |
| `versao` igual à atual | Não é ignorada: faz o diff contra o que está carregado (0 fetch se tudo carregou) | Regra 5 manda tentar de novo no próximo ciclo um `n` que falhou; o resultado observável para manifest idêntico é o mesmo (0 chunks). `versao` menor é ignorada | n |
| `pronto` e `completo` | Emitidos uma vez por vida do sincronizador; `completo` só quando todos os chunks do manifest estão carregados | Regra 1 descreve a primeira carga | n |
| `carregados` / `total` | Contam chunks (do manifest-alvo), não cards | Indicador de progresso; `total_ofertas` é ambíguo no MANIFEST | n |
| Alvo do catálogo | Método extra `Catalogo.alvo(manifest)` define os chunks esperados | `completo` precisa saber quantos chunks existem; a assinatura da spec não diz como | n |
| Base de "exibidos" | Fixada na primeira vez em que `completo` vira true: todos os ids do catálogo naquele momento | Regra 8 | n |
| Id novo que já chega com `x:1` | Entra direto na base (não é "nova", não fica pendente) | Regra 8: nova = fora da base e sem `x` | n |
| `buscar` e ids pendentes | `buscar` cobre todo o catálogo, inclusive pendentes | Busca é pedido explícito do usuário; pendência só protege a ordem da lista | n |
| Desempate das ordens | `desconto` e `preco` desempatam por `recentes` (`dt` desc, `id` desc) | Ordem total e determinística | n |
| Desconto para ordenar | Razão exata `pp/pd` (não o % arredondado) | Mais preciso; o % exibido é da UI | n |
| `pd` ausente no card | Tratado como `null` | Schema não exige `pd` | n |
| Falha de chunk | Refaz o manifest no máximo 1 vez por sincronização; o `n` que falhou é tentado de novo com o `arquivo` do manifest novo; se o `n` sumiu dele, é descartado | Regra 5 | n |
| Validação do manifest recebido | Mínima (objeto, `contrato` semver, `versao` número, `chunks` array); inválido → `erro('manifest')` | O worker já valida; o cliente só evita quebrar | n |
| Hash e `bytes` no `gerarManifest` | SHA-256/16 hex do JSON e Brotli 9 real (`node:crypto`, `node:zlib`) | Igual ao MANIFEST §2/§3; o gerador é só de teste/Node, fora do bundle | n |
| Onde fica o gerador | `src/lib/dados/gerador.ts`, não reexportado por `dados.ts` | Usa APIs do Node; não pode ir para o bundle do navegador | n |
| Versão do contrato no build | `packages/contract/package.json` importado como JSON | Regra 4 ("lido no build"); mesmo arquivo serve ao `medir` em Node | n |
| `pnpm medir` | Script Node (`--experimental-strip-types`), sem dependência nova; a 2ª passada roda no mesmo processo | Spec pede "rodar duas vezes"; mesma sessão garante o mesmo manifest com alta probabilidade | n |
| Tolerância das distribuições do gerador | ±1,5 pp por categoria com 30 mil cards; título médio 65..75, p95 140..160, máx ≤ 200 | "~70", "~150" da spec | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Catálogo sincronizado com o manifest ⭐ MVP

**User Story**: Como visitante, quero ver as ofertas atualizadas sem baixar de novo o que não mudou.

**Acceptance Criteria**:

1. SIN-01: WHEN the first sync runs THEN the module SHALL fetch `manifest.json`, then the 3 chunks with highest `n`, emit `pronto`, then fetch the remaining chunks one at a time in decreasing `n`, and emit `completo` only after the last one.
2. SIN-02: The module SHALL request `manifest.json` with `cache: 'no-cache'`.
3. SIN-03: WHEN a manifest identical to the loaded one arrives THEN the module SHALL fetch 0 chunks.
4. SIN-04: WHEN exactly one chunk's `arquivo` changes THEN the module SHALL fetch exactly that chunk.
5. SIN-05: WHEN an `n` disappears from the manifest THEN the module SHALL remove its cards from `lista` and `buscar`.
6. SIN-06: IF the new manifest's `versao` is lower than the loaded one THEN the module SHALL ignore it (0 chunk fetches, catalog unchanged).
7. SIN-07: IF the manifest's `contrato` major differs from `packages/contract` THEN the module SHALL emit `atualizarApp` and SHALL NOT apply anything.
8. SIN-08: IF a chunk fetch fails (404 or error) THEN the module SHALL refetch the manifest once and retry the chunk once.
9. SIN-09: IF the retry also fails THEN the module SHALL keep the old cards of that `n`, emit `erro`, and retry on the next cycle.
10. DIF-01: `diferenca` SHALL return `baixar` in decreasing `n` (all chunks when `atual` is null) and `descartar` with every `n` absent from the new manifest.

**Independent Test**: fake fetch with log + fake clock in `sincronizador.test.ts`.

---

### P1: Polling por visibilidade ⭐ MVP

**Acceptance Criteria**:

1. POL-01: WHILE the tab is visible the module SHALL poll the manifest every 5 minutes (15 min → 3 polls).
2. POL-02: WHILE the tab is hidden the module SHALL make no fetch (15 min → 0).
3. POL-03: WHEN the tab becomes visible and the last sync is more than 5 minutes old THEN the module SHALL sync immediately (after 12 min hidden → 1 poll).

---

### P1: Lista e novas ⭐ MVP

**Acceptance Criteria**:

1. CAT-01: The `lista` SHALL exclude cards with `x:1` by default.
2. CAT-02: WHERE `mostrarExpiradas` is true the `lista` SHALL include cards with `x:1`.
3. CAT-03: WHEN `area`, `publico` or `loja` is set THEN `lista` SHALL return only matching cards.
4. CAT-04: The `lista` SHALL order `recentes` by `dt` desc, ties by `id` desc (default).
5. CAT-05: WHERE `ordem` is `desconto` the `lista` SHALL order by discount desc with `pd` null last.
6. CAT-06: WHERE `ordem` is `preco` the `lista` SHALL order by `pp` asc.
7. CAT-07: WHEN a chunk with 4 new ids (1 expired, 1 with old `dt`) is applied after `completo` THEN `novas()` SHALL return 3.
8. CAT-08: WHILE new ids are pending the `lista` SHALL stay unchanged until `confirmarNovas()`, after which it SHALL include them.
9. CAT-09: WHEN the price of an already displayed id changes THEN `lista` SHALL show the new price without `confirmarNovas()`.
10. CAT-10: `completo` SHALL be true only when every chunk of the target manifest is loaded; `carregados`/`total` SHALL count chunks.

---

### P1: Busca ⭐ MVP

**Acceptance Criteria**:

1. BUS-01: WHEN the query is "protetor solar" THEN `buscar` SHALL find "Protetor Solar Facial FPS 50".
2. BUS-02: The `buscar` SHALL return the same result for "PROTETOR", "protetor" and "protetór".
3. BUS-03: WHEN the query is "cafe" THEN `buscar` SHALL find "Café".
4. BUS-04: WHEN the query is "olar" THEN `buscar` SHALL NOT find "Solar" (word-prefix only).
5. BUS-05: WHEN the query is "besave" THEN `buscar` SHALL find the card with coupon `BESAVE10`.
6. BUS-06: WHEN the query is "mercado livre" THEN `buscar` SHALL find cards of store `MERCADO_LIVRE`.
7. BUS-07: IF the normalized query has fewer than 2 characters THEN `buscar` SHALL return 0 items.
8. BUS-08: The `buscar` SHALL include expired cards, require all terms, honor the filter's order and `limite`, and report `total` and `completo`.

---

### P1: Contrato, gerador, desempenho e esqueleto ⭐ MVP

**Acceptance Criteria**:

1. TIP-01: The types SHALL list exactly the enum values of `packages/contract/schema/enums.schema.json`.
2. TIP-02: The module SHALL load `fixtures/chunk-ok.json` and `fixtures/manifest-ok.json`.
3. GER-01: 30 000 cards from `gerarCards` and their `gerarManifest` SHALL pass the contract JSON Schema (ajv).
4. GER-02: The same seed SHALL produce the same bytes.
5. GER-03: The generator SHALL follow the production distribution of the spec (rule 13) within the tolerance logged above.
6. DES-01: Applying all chunks of 30 000 cards SHALL take ≤ 400 ms (median of 5).
7. DES-02: `buscar` p95 over 50 queries SHALL be ≤ 20 ms.
8. DES-03: `lista` with area + order SHALL take ≤ 40 ms (median of 5).
9. DES-04: The module bundle SHALL be ≤ 10 KB gzip.
10. PUR-01: The module SHALL NOT reference `window`/`document` and the site SHALL have no runtime `dependencies`.
11. ESQ-01: The site SHALL build with `adapter-static`, fallback off, `prerender = true`, and `pnpm lint && pnpm check && pnpm test && pnpm build` SHALL exit 0.
12. MED-01: WHEN `pnpm medir` runs with `BESAVE_BASE_URL` THEN it SHALL print cards, bytes, time to `pronto` and `completo`, apply time and search p95 over 20 queries, plus the chunk count of a second pass.

---

## Edge Cases

- IF `consulta` normalizes to "" or 1 char THEN `buscar` SHALL return `{ itens: [], total: 0 }`.
- IF the manifest has 0 chunks THEN the catalog SHALL be empty and `completo` true.
- IF the manifest fetch fails THEN the module SHALL emit `erro('manifest')` and keep the catalog.
- WHEN a new manifest no longer lists a failed `n` on retry THEN the module SHALL discard that `n`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ESQ-01 | Esqueleto | T1 | Verified |
| TIP-01 | Contrato | T2 | Verified |
| TIP-02 | Contrato | T2 | Verified |
| GER-01 | Gerador | T3 | Verified |
| GER-02 | Gerador | T3 | Verified |
| GER-03 | Gerador | T3 | Verified |
| CAT-01 | Lista e novas | T4 | Verified |
| CAT-02 | Lista e novas | T4 | Verified |
| CAT-03 | Lista e novas | T4 | Verified |
| CAT-04 | Lista e novas | T4 | Verified |
| CAT-05 | Lista e novas | T4 | Verified |
| CAT-06 | Lista e novas | T4 | Verified |
| CAT-07 | Lista e novas | T4 | Verified |
| CAT-08 | Lista e novas | T4 | Verified |
| CAT-09 | Lista e novas | T4 | Verified |
| CAT-10 | Lista e novas | T4 | Verified |
| BUS-01 | Busca | T5 | Verified |
| BUS-02 | Busca | T5 | Verified |
| BUS-03 | Busca | T5 | Verified |
| BUS-04 | Busca | T5 | Verified |
| BUS-05 | Busca | T5 | Verified |
| BUS-06 | Busca | T5 | Verified |
| BUS-07 | Busca | T5 | Verified |
| BUS-08 | Busca | T5 | Verified |
| DIF-01 | DIF | T6 | Verified |
| SIN-01 | SIN | T6 | Verified |
| SIN-02 | SIN | T6 | Verified |
| SIN-03 | SIN | T6 | Verified |
| SIN-04 | SIN | T6 | Verified |
| SIN-05 | SIN | T6 | Verified |
| SIN-06 | SIN | T6 | Verified |
| SIN-07 | SIN | T6 | Verified |
| SIN-08 | SIN | T6 | Verified |
| SIN-09 | SIN | T6 | Verified |
| POL-01 | POL | T6 | Verified |
| POL-02 | POL | T6 | Verified |
| POL-03 | POL | T6 | Verified |
| DES-01 | DES | T7 | Verified |
| DES-02 | DES | T7 | Verified |
| DES-03 | DES | T7 | Verified |
| DES-04 | DES | T7 | Verified |
| PUR-01 | PUR | T7 | Verified |
| MED-01 | Medição real | T8 | Verified |

**Coverage:** 43 total, 43 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Segundo sync com o mesmo manifest baixa 0 chunks (teste e `pnpm medir`).
- [ ] Busca p95 ≤ 20 ms e aplicação ≤ 400 ms com 30 mil cards em Node.
