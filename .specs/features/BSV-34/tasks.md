# BSV-34 Tasks

## Execution Plan

### Phase 1 — Lógica (sequencial)

```
T1 → T2
```

### Phase 2 — Telas do site

```
T2 → T3 → T4
```

### Phase 3 — Worker e entrega

```
T4 → T5 → T6
```

---

## Task Breakdown

### T1: Busca no endereço (`q`, `area` + filtros)

**What**: `src/lib/busca.ts` com `lerBusca(params)` → `{ q, area?, filtros }`, `escreverBusca(url, estado)` e `destinoBusca(q, area?)`; `area` por slug, inválida ignorada; filtros pelo formato da BSV-31.
**Where**: `apps/site/src/lib/busca.ts`, `apps/site/src/lib/busca.test.ts`
**Depends on**: none
**Reuses**: `lerFiltros`/`escreverFiltros` (`filtros.ts`), `SLUG_AREA`
**Requirement**: BUS-02, BUS-03, BUS-10, TOP-02
**Done when**: Vitest cobre leitura e escrita de `q` e `area` junto com os filtros, área inválida e `q` vazio.
**Tests**: unit
**Gate**: quick
- [x] done

### T2: Expiradas no fim da busca e contagem de ofertas carregadas

**What**: `buscar` devolve ativas antes das expiradas (mesma ordem dentro de cada grupo); `Catalogo` expõe `ofertasCarregadas` e `ofertasTotal` (soma de `qtd` do manifest).
**Where**: `apps/site/src/lib/dados/busca.ts`, `catalogo.ts`, testes ao lado
**Depends on**: T1
**Reuses**: `Selecao.ordenar`
**Requirement**: BUS-04, BUS-05
**Done when**: Vitest prova expiradas depois das ativas em todas as ordens e contagens com chunk ausente/presente.
**Tests**: unit
**Gate**: quick
- [x] done

### T3: Rota `/busca/` e campo do topo navegando para ela

**What**: `src/routes/busca/+page.svelte` (prerender) sobre a casca do `PaginaOfertas` (`campo`, `conteudo`): contagem, área com botão para tirar, filtros e ordem, "Ver mais", parcial, sugestões, estado vazio, `noindex`, título, `replaceState` com espera. `Busca.svelte` navega para `/busca/` a partir de 2 caracteres (ou Enter) levando texto e foco (`destino-busca.ts`); home e áreas não filtram mais; e2e antigos de busca reescritos.
**Where**: `apps/site/src/routes/busca/+page.svelte`, `apps/site/src/lib/componentes/Busca.svelte`, `PaginaOfertas.svelte`, `apps/site/src/lib/destino-busca.ts`, `apps/site/e2e/busca.spec.ts`, `e2e/home.spec.ts`, `e2e/area.spec.ts`, `e2e/bordas.spec.ts`, `e2e/saida.spec.ts`
**Depends on**: T2
**Requirement**: BUS-01..03, BUS-05..10, TOP-01..07, BUD-01
**Done when**: e2e da spec (390 e 1280 px) verdes; bundle da home ≤ 150 KiB. Uma tarefa só porque a rota sozinha estoura o bundle (divisão de chunks) e só a casca compartilhada com a home o traz de volta.
**Tests**: e2e
**Gate**: full
- [x] done

### T4: Selo "Encerrada" no card

**What**: card expirado mostra "Encerrada" (foto em cinza já existe); e2e de expiradas no fim da busca.
**Where**: `apps/site/src/lib/componentes/Card.svelte`, `Card.test.ts`, `e2e/desejos.spec.ts`, `e2e/busca.spec.ts`
**Depends on**: T3
**Requirement**: BUS-04
**Done when**: Vitest do card e e2e da busca mostram expiradas por último com "Encerrada".
**Tests**: e2e
**Gate**: build
- [x] done

### T5: Formulário de busca na página da oferta

**What**: `<form class="busca" role="search" action="/busca/" method="get">` no cabeçalho do template; classes no `besave.css` e no README; goldens regenerados; e2e enviando o formulário.
**Where**: `apps/worker/templates/oferta.html`, `templates/README.md`, `tests/template_oferta.rs`, `tests/fixtures/paginas/*.html`, `apps/site/src/lib/estilo/besave.css`, `apps/site/e2e/oferta-busca.spec.ts`
**Depends on**: T4
**Requirement**: OFE-01..04
**Done when**: testes do template (form, ≤ 30 KB, determinismo, classes no CSS) e e2e verdes.
**Tests**: integration
**Gate**: build
- [x] done

### T6: Bundle, prints e entrega

**What**: medir bundle depois; prints (resultados, sugestões, sem resultado; 390 e 1280 px; página da oferta); traceability.
**Where**: `.specs/features/BSV-34/`
**Depends on**: T5
**Requirement**: BUD-01
**Done when**: BUD-01 verde com antes/depois anotados.
**Tests**: none
**Gate**: build
- [ ] done

---

## Test Coverage Matrix

| Layer | Test type | Coverage expectation | Location |
| ----- | --------- | -------------------- | -------- |
| Lógica (URL, busca, catálogo) | Vitest | 1:1 com os ACs, cada borda listada | `apps/site/src/lib/**/*.test.ts` |
| Componentes (card) | Vitest (SSR) | selo "Encerrada" | `apps/site/src/lib/componentes/Card.test.ts` |
| Páginas e navegação | Playwright 390/1280 px | fluxos do critério de aceite | `apps/site/e2e/*.spec.ts` |
| Template da oferta | cargo test | form, ≤ 30 KB, determinismo, classes | `apps/worker/tests/template_oferta.rs` |
| Orçamento | Playwright (BUD-01) | ≤ 150 KiB | `apps/site/e2e/saida.spec.ts` |

## Gate Check Commands

- quick: `cd apps/site && pnpm test`
- full: `cd apps/site && pnpm test && pnpm build && pnpm e2e`
- build: `cd apps/site && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`; worker: `cd apps/worker && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
