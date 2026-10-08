# BSV-30 Specification — Site: shell, design system (modelo A) e home básica

Fonte: `docs/specs/BSV-30.md`. Contrato: CONTRATO §2.3, §3; MANIFEST §1, §3.1, §4; AD-001, AD-020, AD-032,
AD-061..067, AD-075..078. Referência visual: `docs/design/vitrine.html`, modelo A.

## Problem Statement

`besave.com.br` mostra uma home provisória ("Em construção"). A camada de dados (BSV-35/36) já baixa,
sincroniza e busca os cards, mas não há tela. A página de oferta do worker usa um CSS próprio que diverge
da identidade escolhida (modelo A) e que o worker publica, embora o dono agora seja o deploy do site (AD-078).

## Goals

- [ ] Home estática com topo fixo, barra do canal, áreas, "Maiores descontos de hoje", "Mais recentes" com busca e lista de desejos local.
- [ ] Um único conjunto de tokens (modelo A) alimenta o Tailwind do site e o `besave.css` da página de oferta.
- [ ] O worker deixa de publicar o CSS; o build do site gera `assets/besave.css`.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Filtros (público, loja, preço, cupom), ordens, virtualização | BSV-31 |
| Toast "N novas ofertas" | BSV-32 (a lista já segura os pendentes, AD-066) |
| Páginas de área `/{slug}/` | BSV-33; aqui as áreas filtram a grade na home |
| Página de busca | BSV-34 |
| Login, likes, comentários, notificações, modo escuro, analytics | spec |
| Playwright no CI (`ci.yml`) | fora da pasta do ticket; proposto no PR |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Fonte única dos tokens | `src/lib/estilo/tokens.css` com variáveis CSS puras (`--cor-*`, `--raio`); o tema do Tailwind as referencia com `@theme inline` | Um arquivo alimenta Tailwind e `besave.css` sem depender do Tailwind para compilar o CSS do worker | n |
| Como `besave.css` é gerado | rota prerenderizada `src/routes/assets/besave.css/+server.ts` que devolve `tokens.css` + `fontes.css` + `besave.css` (regras) processados pelo Vite (`?inline`) | Sai em `build/assets/besave.css` no `pnpm build`, sem script extra; o deploy (BSV-17) já publica esse caminho | n |
| Lato | `lato-latin-700-normal.woff2` e `lato-latin-900-normal.woff2` do pacote `@fontsource/lato` (OFL), copiados para `static/assets/fontes/` com a licença; não vira dependência | Spec: auto-hospedada, só latin, `font-display: swap`; caminho estável que a página de oferta também usa | n |
| Classes do worker | `besave.css` mantém toda classe de `templates/oferta.html` e também `aviso`, `canal` de `aviso.html` | Mesmo arquivo serve as duas páginas; nada é renomeado (regra 6) | n |
| Testes do worker que liam `assets/css/besave.css` | passam a ler `apps/site/src/lib/estilo/besave.css` (fonte das regras); asserções mantidas | O arquivo do worker sai; a garantia "toda classe do template tem regra" continua no CI do worker | n |
| Índice `_estado/paginas.json` antigo com `_css` | chave ignorada na leitura e omitida na próxima gravação (índice regravado uma vez) | Sem migração manual; `de_json` já ignora chaves desconhecidas | n |
| "há X h" | `< 60 min` → "há N min" (N ≥ 1); `< 24 h` → "há N h"; `< 7 d` → "há N d" (floor); senão "em DD/MM" na data de Brasília (UTC−3 fixo); base `dp ?? dt` | Spec pede "há X h" em Brasília; data absoluta só aparece para ofertas antigas e usa AD-032 | n |
| `dp` no futuro (relógio do aparelho atrasado) | "há 1 min" | Nunca mostra tempo negativo | n |
| Favoritos no `localStorage` | chave `besave:favoritos`, array JSON de ids inteiros ≥ 1, mais recente primeiro; conteúdo inválido → lista vazia; sem `localStorage` → só memória | AD-076; leitura tolerante a lixo | n |
| Barra do canal fechada | chave `besave:barra-canal` = `"fechada"`; um script inline no `<head>` marca `<html data-barra-fechada>` antes da pintura e o CSS esconde a barra | Sem piscar nem layout shift ao recarregar | n |
| Busca na home | consulta normalizada ≥ 2 caracteres troca a grade por `buscar(cat, q, {area})`; a faixa de descontos some durante a busca; título vira "Resultados para “q”" | Spec: busca filtra a grade sem navegação; `buscar` inclui expiradas (exibidas em cinza, CONTRATO §3) | n |
| Área + faixa | a área filtra só a grade "Mais recentes"; a faixa "Maiores descontos de hoje" continua geral | Spec só pede que a área filtre a grade | n |
| "Ver mais" | 40 por vez; volta a 40 quando área ou busca mudam; botão some quando tudo já aparece | Spec | n |
| Ordem das áreas | Elas, Meu Lar, Tech, Esporte & vida, Família & filhos, Pets, Players, Cultura, Eles; "Outros" só no menu "Mais" | Ordem do mock aprovado (público inicial beleza/feminino) | n |
| Colunas da grade | 2 (< 640 px), 3 (≥ 640), 4 (≥ 768), 5 (≥ 1024) | Spec: 2 no celular, 5 no desktop largo (1280 px) | n |
| Lista de desejos com catálogo incompleto | ids ainda não encontrados aparecem como "Carregando…" até `completo`; depois, "Esta oferta saiu do ar" com botão "Remover" | Não declarar fora do ar antes de baixar todos os chunks | n |
| Expirada (`x:1`) na lista de desejos | aparece como card em cinza | Ainda tem página (CONTRATO §7) | n |
| Link do canal | `https://t.me/besaveofertas` em `lib/config.ts` | Mesmo canal do worker (`CANAL_PADRAO`) | n |
| Rotas | `trailingSlash = 'always'` (gera `desejos/index.html`), `paths.relative = false` (o `404.html` é servido em qualquer path) | Prefixos do deploy (`desejos/*`) e Function `rewrite-index` | n |
| Playwright | `@playwright/test` (dev), script `pnpm e2e`, servidor `vite preview` do build, manifest e chunks interceptados com `page.route` | Spec pede Playwright; fixture determinística sem rede | n |
| Tailwind | `tailwindcss` + `@tailwindcss/vite` 4.3.x (dev) | Já previsto no CLAUDE.md do site | n |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Tokens e base visual ⭐ MVP

**User Story**: Como dono, quero um único conjunto de tokens do modelo A para o site e a página de oferta.

**Acceptance Criteria**:

1. TOK-01: The `tokens.css` SHALL define fundo `#ffffff`, superfície `#f4f6f5`, borda `#e1e6e3`, texto `#17201c`, suave `#56615b`, marca `#0b6e4f`, marca-escura `#084c37`, destaque `#c2410c`, texto sobre destaque `#ffffff`, rodapé `#084c37`, texto do rodapé `#e3efe9` and raio `10px`.
2. TOK-02: The site SHALL load Lato 700 and 900 from `/assets/fontes/*.woff2` with `font-display: swap`, used only by the logo and headings; body text SHALL use the system font stack.
3. TOK-03: The logo SHALL be the text "Besave" in Lato 900 with the `marca` color.

**Independent Test**: `pnpm build`; inspecionar `build/_app/**/*.css` e `build/assets/fontes/`.

### P1: Utilitários de exibição e configuração ⭐ MVP

**User Story**: Como visitante, quero preço, desconto e tempo legíveis, e nenhum ícone que não leve a lugar algum.

**Acceptance Criteria**:

1. TEM-01: WHEN the elapsed time since `dp` is under 24 h THEN `haQuanto` SHALL return "há N h" with N = floor(hours) (≥ 1 h) or "há N min" under 1 h.
2. TEM-02: WHEN the elapsed time is 24 h or more and under 7 days THEN `haQuanto` SHALL return "há N d".
3. TEM-03: WHEN the elapsed time is 7 days or more THEN `haQuanto` SHALL return "em DD/MM" using the Brasília date (UTC−3 fixed), e.g. `dp` `2026-10-01T02:00:00Z` → "em 30/09".
4. TEM-04: IF `dp` is absent THEN `haQuanto` SHALL use `dt`.
5. CFG-01: WHERE a social network or app has no link in `config.ts` THEN its icon SHALL NOT be listed for rendering.
6. CFG-02: WHERE a feature flag (`postar`, `notificacoes`, `entrar`, `social`) is `false` THEN its button SHALL NOT be listed for rendering.
7. CFG-03: The default `config.ts` SHALL have every social/app link `null`, every flag `false`, and the channel link `https://t.me/besaveofertas`.

**Independent Test**: `pnpm test` (`formato.test.ts`, `config.test.ts`).

### P1: Favoritos ⭐ MVP

**User Story**: Como visitante, quero marcar ofertas com ♡ e encontrá-las depois no mesmo aparelho.

**Acceptance Criteria**:

1. FAV-01: WHEN an id is added THEN the favorites SHALL contain it and `localStorage["besave:favoritos"]` SHALL hold it.
2. FAV-02: WHEN an id is removed THEN the favorites SHALL no longer contain it and storage SHALL be updated.
3. FAV-03: WHEN a new instance reads the same storage THEN it SHALL restore the saved ids.
4. FAV-04: IF the id to remove is not a favorite THEN the list SHALL stay unchanged.
5. FAV-05: IF storage holds invalid JSON or non-integer values THEN the favorites SHALL start empty (or keep only valid ids ≥ 1).
6. FAV-06: WHEN the same id is added twice THEN it SHALL appear once.

**Independent Test**: `pnpm test` (`favoritos.test.ts`).

### P1: Card ⭐ MVP

**User Story**: Como visitante, quero um card com foto, preço, desconto, loja e tempo, que abra a página da oferta.

**Acceptance Criteria**:

1. CAR-01: WHEN the card has `pd` THEN it SHALL show the seal `-N%` (N = desconto do contrato) and the "de" price struck through.
2. CAR-02: IF the card has no `pd` THEN it SHALL show neither the seal nor the "de" price.
3. CAR-03: The card SHALL link to `/oferta/{id}/` and SHALL NOT contain any `/ir/` link nor the coupon.
4. CAR-04: The card image SHALL be `/img/ofertas/{id}-small.webp` with `loading="lazy"`, fixed `width`/`height`, and fall back to `/img/placeholder/{slug-da-área}.webp` on error.
5. CAR-05: The card SHALL show the "por" price in BRL, the store label and `haQuanto(dp)`.
6. CAR-06: WHILE the card is expired (`x:1`) the card SHALL render grayed out.

**Independent Test**: `pnpm test` (`Card.test.ts`, render SSR).

### P1: Home ⭐ MVP

**User Story**: Como visitante, quero ver os maiores descontos e as ofertas mais recentes, buscar e filtrar por área.

**Acceptance Criteria**:

1. HOM-01: The home SHALL render, in order: channel bar, header, areas, "Maiores descontos de hoje" (up to 8 from `maioresDescontos`), "Mais recentes" (`lista()`), footer.
2. HOM-02: WHILE the page scrolls the header SHALL stay at the top of the viewport.
3. HOM-03: WHEN the channel bar is closed THEN it SHALL hide and stay hidden after reload.
4. HOM-04: WHEN an area is selected THEN the grid SHALL show only cards of that area; "Outros" SHALL be reachable only from the "Mais" menu.
5. HOM-05: WHEN the search has "protetor" THEN the grid SHALL show only cards whose searchable text contains a word starting with "protetor".
6. HOM-06: The grid SHALL show 40 cards initially; WHEN "Ver mais ofertas" is clicked THEN 40 more SHALL be appended.
7. HOM-07: WHEN ♡ is clicked THEN the header counter SHALL show the number of favorites.
8. HOM-08: WHEN a card is clicked THEN the browser SHALL navigate to `/oferta/{id}/`.
9. HOM-09: The grid SHALL have 2 columns at 390 px and 5 columns at 1280 px.
10. HOM-10: The page SHALL fetch only `manifest.json` and chunks via `lib/dados.ts`; components SHALL NOT call `fetch`.
11. HOM-11: The footer SHALL show the affiliate disclosure and the channel link; social/app icons only per CFG-01.

**Independent Test**: `pnpm e2e` (Playwright, 390 px e 1280 px).

### P1: Lista de desejos ⭐ MVP

**User Story**: Como visitante, quero ver minhas ofertas favoritas em `/desejos/`.

**Acceptance Criteria**:

1. DES-01: WHEN `/desejos/` opens THEN it SHALL list a card for each favorite found in the catalog.
2. DES-02: IF a favorite id is not in the complete catalog THEN it SHALL show "Esta oferta saiu do ar" with a "Remover" button that removes it.
3. DES-03: IF there are no favorites THEN the page SHALL show an empty-state message with a link to the home.

**Independent Test**: `pnpm e2e` (`desejos.spec.ts`).

### P1: 404 e CSS compartilhado ⭐ MVP

**User Story**: Como dono, quero a 404 estática e a página de oferta com o visual novo.

**Acceptance Criteria**:

1. ERR-01: The build SHALL emit `build/404.html` with `<meta name="robots" content="noindex">`, the text "Oferta encerrada ou não encontrada", a link to `/` and a link to the channel.
2. ERR-02: The build SHALL NOT emit an SPA fallback (only prerendered pages).
3. CSS-01: The build SHALL emit `build/assets/besave.css` containing the tokens of TOK-01 and the Lato `@font-face`.
4. CSS-02: The `besave.css` SHALL have a rule for every class used in `apps/worker/templates/oferta.html` and `aviso.html`.
5. CSS-03: The compressed (brotli) `besave.css` SHALL be ≤ 20 KB.

**Independent Test**: `pnpm test` (`besave-css.test.ts`) + `pnpm build`.

### P1: Worker sem fase de CSS ⭐ MVP

**User Story**: Como dono, quero um único publicador do CSS (o deploy do site).

**Acceptance Criteria**:

1. WRK-01: WHEN the worker runs a cycle THEN it SHALL NOT write `assets/besave.css`.
2. WRK-02: The `_estado/paginas.json` written by the worker SHALL NOT contain `_css`; IF a previous index has `_css` THEN it SHALL be ignored.
3. WRK-03: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` and `cargo test` SHALL pass.

**Independent Test**: `cd apps/worker && cargo test`.

---

## Edge Cases

- IF the manifest fails to load THEN the home SHALL show "Não foi possível carregar as ofertas" instead of the grid skeleton.
- IF no card has a discount in the last 24 h THEN the band SHALL show "Sem descontos novos nas últimas 24 h".
- IF the search has fewer than 2 normalized characters THEN the grid SHALL show the regular list.
- WHEN `localStorage` throws (modo privado) THEN favorites and the bar SHALL keep working in memory for the session.

---

## Implicit-requirement sweep

| Dimension | Resolution |
| --------- | ---------- |
| Input validation & bounds | FAV-05 (storage inválido), busca < 2 caracteres |
| Failure / partial-failure | manifest falhou (edge case); desejos com catálogo incompleto (assumption) |
| Idempotency / duplicates | FAV-06 |
| Auth / rate limits | N/A because o site é estático, sem login (AD-001) |
| Concurrency / ordering | N/A because a ordem vem da camada de dados (BSV-35/36) |
| Data lifecycle / expiry | expiradas em cinza (CAR-06); id fora do ar (DES-02) |
| Observability | N/A because analytics está fora de escopo |
| External-dependency failure | manifest/chunk falham (edge case); imagem ausente → placeholder (CAR-04) |
| State-transition integrity | barra fechada persiste (HOM-03) |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| TOK-01 | P1: Tokens | T1 | Verified |
| TOK-02 | P1: Tokens | T1 | Verified |
| TOK-03 | P1: Tokens | T1 | Verified |
| TEM-01 | P1: Utilitários | T2 | Verified |
| TEM-02 | P1: Utilitários | T2 | Verified |
| TEM-03 | P1: Utilitários | T2 | Verified |
| TEM-04 | P1: Utilitários | T2 | Verified |
| CFG-01 | P1: Utilitários | T2 | Verified |
| CFG-02 | P1: Utilitários | T2 | Verified |
| CFG-03 | P1: Utilitários | T2 | Verified |
| FAV-01 | P1: Favoritos | T3 | Verified |
| FAV-02 | P1: Favoritos | T3 | Verified |
| FAV-03 | P1: Favoritos | T3 | Verified |
| FAV-04 | P1: Favoritos | T3 | Verified |
| FAV-05 | P1: Favoritos | T3 | Verified |
| FAV-06 | P1: Favoritos | T3 | Verified |
| CAR-01 | P1: Card | T4 | Verified |
| CAR-02 | P1: Card | T4 | Verified |
| CAR-03 | P1: Card | T4 | Verified |
| CAR-04 | P1: Card | T4 | Verified |
| CAR-05 | P1: Card | T4 | Verified |
| CAR-06 | P1: Card | T4 | Verified |
| HOM-01 | P1: Home | T5 | Verified |
| HOM-02 | P1: Home | T5 | Verified |
| HOM-03 | P1: Home | T5 | Verified |
| HOM-04 | P1: Home | T5 | Verified |
| HOM-05 | P1: Home | T5 | Verified |
| HOM-06 | P1: Home | T5 | Verified |
| HOM-07 | P1: Home | T5 | Verified |
| HOM-08 | P1: Home | T5 | Verified |
| HOM-09 | P1: Home | T5 | Verified |
| HOM-10 | P1: Home | T5 | Verified |
| HOM-11 | P1: Home | T5 | Verified |
| DES-01 | P1: Lista de desejos | T6 | Verified |
| DES-02 | P1: Lista de desejos | T6 | Verified |
| DES-03 | P1: Lista de desejos | T6 | Verified |
| ERR-01 | P1: 404 e CSS | T7 | Verified |
| ERR-02 | P1: 404 e CSS | T7 | Verified |
| CSS-01 | P1: 404 e CSS | T7 | Verified |
| CSS-02 | P1: 404 e CSS | T7 | Verified |
| CSS-03 | P1: 404 e CSS | T7 | Verified |
| WRK-01 | P1: Worker | T8 | Verified |
| WRK-02 | P1: Worker | T8 | Verified |
| WRK-03 | P1: Worker | T8 | Verified |

**Coverage:** 44 total, 44 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `pnpm lint && pnpm check && pnpm test && pnpm build` e `pnpm e2e` verdes; `cargo fmt/clippy/test` verdes.
- [ ] Bundle inicial (JS + CSS da home) ≤ 150 KB.
- [ ] Real (dono): deploy com `SITE_DEPLOY_ATIVO`, Lighthouse mobile ≥ 90 nas quatro categorias, `curl -I /assets/besave.css` → 200 `text/css`.
