# BSV-21 — Páginas de oferta em massa, CSS, sitemap e robots.txt

Fonte: `docs/specs/BSV-21.md` (escopo), CONTRATO §4, §5, §7, §7.1; MANIFEST §1, §4, §6, §7.
Pasta: `apps/worker/`. Depende de BSV-20 (`TemplateOferta`) e BSV-13 (`gravar_lote`), ambos em `develop`.

## Problem Statement

`TemplateOferta::renderizar` produz a página de uma oferta, mas `gerar()` ainda não publica
nenhuma página: o bucket não tem `/oferta/{id}/`, o CSS que a página referencia, sitemap nem
`robots.txt`. Com ~25 mil ofertas por ciclo de 5–10 min, subir tudo sempre é caro; só o que mudou
pode subir.

## Goals

- [ ] Cada `gerar()` deixa exatamente uma página por oferta publicada (ativa ou expirada ≤ 7 dias) e remove as expurgadas.
- [ ] Segunda execução sem mudança sobe 0 páginas, 0 CSS, 0 sitemaps, 0 robots.
- [ ] Produtos lidos em lote: 10 000 ofertas → ≤ 10 chamadas à fonte.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Páginas de área e home | BSV-33 |
| 410 real via borda | ticket futuro (CONTRATO §7) |
| Imagens de produto, `hreflang`, sitemap de imagens | fora da spec |
| Versionar o nome do CSS (hash no nome) | BSV-30 |
| Editar `docs/MANIFEST.md` (linhas `assets/` e `_estado/` na §4) | só o dono edita docs; proposto no PR |
| Colapsar as linhas de imagem no plano | não pedido; só páginas (regra 11) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Onde guardar hash de CSS, sitemaps e robots | No mesmo `_estado/paginas.json`, objeto plano: chave numérica = id da página, `_css`, `_robots`, `sitemap*.xml` | Spec pede "mesmo índice, chave `_css`"; sitemaps/robots precisam da mesma detecção de mudança (regra 7 e AC "0 sitemaps") sem ler o objeto do bucket | n |
| Índice regravado toda execução? | Só quando o conteúdo muda | CLAUDE.md do worker: execução sem mudança não sobe nada além dos manifests; a AC diz "só índice/manifest" (permite, não exige) e o teste CIC-01 exige só os manifests | n |
| Momento do expurgo de páginas | Dentro de `publicar_paginas` (antes da KVS e do manifest), como a assinatura da spec pede (`indice_anterior` → `removidas`) | A KVS já é expurgada antes do manifest; página de oferta expurgada há > 7 dias sumir alguns minutos antes do card é aceitável | n |
| Página que falha no render e já estava no índice | Mantém o hash anterior no índice novo (não é removida; será reenviada quando renderizar) | Regra 9: falha individual não publica aquela página; remover a versão antiga seria expurgo indevido | n |
| Gate de 30 KB: abortar antes ou durante uploads | Durante: render e upload em blocos de 64; página acima do orçamento aborta com erro nomeado antes do índice, KVS e manifest | Renderizar 30 mil páginas antes de subir exigiria ~450 MB na primeira carga; páginas são idempotentes | n |
| `sitemap-{n}` começa em 1 | `sitemap-1.xml`, `sitemap-2.xml`, … | Legível; nenhum doc fixa | n |
| `lastmod` | 10 primeiros caracteres de `dt_oferta` (data UTC) | Dado é UTC (CLAUDE.md regra 5); AD-032 só rege exibição | n |
| Ordem das URLs no sitemap | id crescente | Determinismo (sitemap só é regravado se mudar) | n |
| Nenhuma oferta ativa | `sitemap.xml` referencia um `sitemap-1.xml` com `urlset` vazio | Index sempre aponta para arquivo existente; caso raro | n |
| `BESAVE_INDEXAVEL` valores | `true`/`1` → true; `false`/`0`/ausente/vazio → false; outro → erro nomeando a variável | Flag de SEO não pode ligar por erro de digitação | n |
| `BESAVE_BASE_URL` | Padrão `https://besave.com.br`; `/` final removida; precisa começar com `http://` ou `https://` | Base vira `<loc>`; URL relativa geraria sitemap inválido | n |
| Canonical/`og:url` da página | Continua `https://besave.com.br` fixo (BSV-20), independente de `BESAVE_BASE_URL` | Canonical é o domínio final mesmo servido em `*.cloudfront.net`; fora da spec mudar | n |
| Headers de `_estado/paginas.json` | `application/json`, `Cache-Control: no-store`, também em `meta_para` | Spec regra 2 | n |
| XML válido no teste | dev-dependency `roxmltree` (parser puro Rust, sem dependências) | AC exige parse; só em teste | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Páginas publicadas incrementalmente ⭐ MVP

**User Story**: Como visitante, quero abrir `/oferta/{id}/` de toda oferta publicada, e como dono quero que só o que mudou suba ao S3.

**Acceptance Criteria**:

1. PAG-01: The worker SHALL map id `5412` to the key `oferta/5412/index.html` (`chave_pagina`).
2. PAG-02: WHEN `publicar_paginas` runs with an empty previous index THEN the worker SHALL upload one page per `OfertaPagina` and return an index with one `hash16` (16 hex chars) per id.
3. PAG-03: WHEN a page renders to the same hash stored in the previous index THEN the worker SHALL NOT upload it and SHALL count it in `inalteradas`.
4. PAG-04: The worker SHALL render the same `OfertaPagina` to identical bytes on repeated calls.
5. PAG-05: WHEN an offer changes from ATIVA to ENCERRADA THEN the worker SHALL upload only that offer's page on the next run.
6. PAG-06: WHEN an id is in the previous index and absent from the current set THEN the worker SHALL call `remover("oferta/{id}/index.html")`, drop it from the index and count it in `removidas`.
7. PAG-07: IF a page renders to more than 30 720 bytes THEN the worker SHALL return `PaginaAcimaDoOrcamento { id, bytes }` and SHALL NOT write the index nor the manifest.
8. PAG-08: IF rendering one page fails THEN the worker SHALL log its id, count it in `falhas`, not upload it, and continue with the others.
9. PAG-09: The worker SHALL upload pages through `gravar_lote` in batches of at most 64 items, with headers `text/html; charset=utf-8` and `public, max-age=600, stale-while-revalidate=300`.
10. PAG-10: `RelatorioPaginas` SHALL report `renderizadas`, `publicadas`, `inalteradas`, `removidas`, `falhas`, `maior_html` (bytes) and `tempo_render_ms`.
11. PAG-11: The worker SHALL render 30 000 pages in at most 60 s in release (test `#[ignore]`).

**Independent Test**: `publicar_paginas` sobre `PublicadorMemoria` com 3 páginas, depois de novo sem mudança.

### P1: Produtos em lote

**User Story**: Como dono, quero que o worker não faça uma query por oferta no Oracle.

**Acceptance Criteria**:

1. PRD-01: `FonteOfertas` SHALL expose `produtos(&[i64]) -> Result<HashMap<i64, LinhaProduto>>` returning only the ids found.
2. PRD-02: WHEN `gerar` runs with 10 000 valid offers THEN the worker SHALL call `produtos` at most 10 times and `produto` 0 times.
3. PRD-03: The Oracle implementation SHALL query `PRODUTO` with `IN` lists of at most 1 000 binds per statement.
4. PRD-04: WHEN `--dry-run` runs THEN the worker SHALL load products through `produtos`, not `produto`.

**Independent Test**: `FakeFonte` conta chamadas; `sql_produtos(n)` gera `n` binds.

### P1: CSS, sitemap, robots e índice no ciclo

**User Story**: Como dono, quero que o bucket tenha CSS, sitemap e robots coerentes com as páginas a cada ciclo.

**Acceptance Criteria**:

1. SIT-01: WHEN the first run publishes 3 fixture offers THEN the worker SHALL write 3 pages, `assets/besave.css`, `sitemap.xml`, `sitemap-1.xml`, `robots.txt` and `_estado/paginas.json`.
2. SIT-02: WHEN a second run finds no change THEN the worker SHALL write only `manifest.prev.json` and `manifest.json`.
3. SIT-03: The sitemap SHALL list only ATIVA offers, `<loc>` = `{base}/oferta/{id}/`, `<lastmod>` = `AAAA-MM-DD` of `dt_oferta`.
4. SIT-04: WHEN an offer becomes ENCERRADA THEN the worker SHALL remove it from the sitemap in the same run.
5. SIT-05: WHEN an offer is purged THEN the worker SHALL remove its page, drop it from the index and from the sitemap.
6. SIT-06: WHEN 46 000 active offers are given THEN `sitemaps` SHALL return `sitemap-1.xml` (45 000 URLs), `sitemap-2.xml` (1 000 URLs) and `sitemap.xml` index pointing to both; every file SHALL parse as XML and be ≤ 50 MB.
7. SIT-07: WHEN the number of sitemap files shrinks THEN the worker SHALL remove the `sitemap-{n}.xml` keys that are no longer produced.
8. SIT-08: WHERE `BESAVE_INDEXAVEL` is absent or false the worker SHALL write `robots.txt` = `User-agent: *` + `Disallow: /`.
9. SIT-09: WHERE `BESAVE_INDEXAVEL` is true the worker SHALL write `robots.txt` with `Allow: /` and `Sitemap: {base}/sitemap.xml`.
10. SIT-10: The worker SHALL publish `assets/besave.css` with `text/css; charset=utf-8` and `public, max-age=3600, stale-while-revalidate=86400`, and `meta_para("assets/besave.css")` SHALL return those headers.
11. SIT-11: IF `_estado/paginas.json` is unreadable THEN the worker SHALL treat it as absent, upload everything and continue.
12. SIT-12: The worker SHALL write `_estado/paginas.json` with `application/json` and `Cache-Control: no-store`.
13. SIT-13: The worker SHALL publish in the order images → chunks → CSS → pages → sitemaps → robots → index → KVS → manifest.
14. SIT-14: IF a page upload fails THEN `gerar` SHALL return the error without writing the manifest.
15. SIT-15: IF `BESAVE_INDEXAVEL` has a value other than `true`/`false`/`1`/`0` THEN the worker SHALL fail naming the variable; `BESAVE_BASE_URL` absent SHALL default to `https://besave.com.br`.

**Independent Test**: dois `gerar` seguidos sobre `PublicadorMemoria` com as fixtures.

### P2: Plano enxuto

**User Story**: Como dono, quero ver o plano do `--publicar` sem 30 mil linhas de página.

**Acceptance Criteria**:

1. PLN-01: WHEN the plan has page writes or removals THEN `Plano::linhas` SHALL print one line per kind with the count and at most 5 example keys, and no individual `oferta/*/index.html` line.

**Independent Test**: plano com 30 páginas a gravar → uma linha `páginas a gravar: 30 (ex.: …)` com 5 chaves.

---

## Edge Cases

- WHEN no offer is active THEN `sitemaps` SHALL return `sitemap-1.xml` with an empty `urlset` and the index (SIT-06 boundary).
- WHEN there are exactly 45 000 active offers THEN `sitemaps` SHALL return a single `sitemap-1.xml` (SIT-06 boundary).
- IF `BESAVE_BASE_URL` ends with `/` THEN the worker SHALL strip it (no `//oferta`).
- IF a page is exactly 30 720 bytes THEN the worker SHALL accept it (PAG-07 boundary).

Dimensions: idempotência (SIT-02, PAG-03); falha parcial (PAG-07, PAG-08, SIT-11, SIT-14); ciclo de vida/expurgo (PAG-06, SIT-05, SIT-07); transição de estado ATIVA→ENCERRADA (PAG-05, SIT-04); observabilidade (PAG-10, log de id em PAG-08). Auth/rate limit, concorrência e dependência externa: N/A because o acesso a S3/Oracle já passa por traits com fakes e o paralelismo é do `PublicadorS3` (BSV-13).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PRD-01 | P1: Produtos em lote | T1 | Verified |
| PRD-02 | P1: Produtos em lote | T1 | Verified |
| PRD-03 | P1: Produtos em lote | T1 | Verified |
| PRD-04 | P1: Produtos em lote | T7 | Verified |
| PAG-01 | P1: Páginas | T4 | Verified |
| PAG-02 | P1: Páginas | T4 | Verified |
| PAG-03 | P1: Páginas | T4 | Verified |
| PAG-04 | P1: Páginas | T4 | Verified |
| PAG-05 | P1: Páginas | T4 | Verified |
| PAG-06 | P1: Páginas | T4 | Verified |
| PAG-07 | P1: Páginas | T4 | Verified |
| PAG-08 | P1: Páginas | T4 | Verified |
| PAG-09 | P1: Páginas | T4 | Verified |
| PAG-10 | P1: Páginas | T4 | Verified |
| PAG-11 | P1: Páginas | T4 | Verified |
| SIT-01 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-02 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-03 | P1: CSS, sitemap, robots | T3 | Verified |
| SIT-04 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-05 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-06 | P1: CSS, sitemap, robots | T3 | Verified |
| SIT-07 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-08 | P1: CSS, sitemap, robots | T3 | Verified |
| SIT-09 | P1: CSS, sitemap, robots | T3 | Verified |
| SIT-10 | P1: CSS, sitemap, robots | T2 | Verified |
| SIT-11 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-12 | P1: CSS, sitemap, robots | T2 | Verified |
| SIT-13 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-14 | P1: CSS, sitemap, robots | T5 | Verified |
| SIT-15 | P1: CSS, sitemap, robots | T3 | Verified |
| PLN-01 | P2: Plano enxuto | T6 | Verified |

**Coverage:** 31 total, 31 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde, sem rede.
- [ ] Execução real do dono (`--publicar --sim`, curls, Lighthouse) antes do merge.
