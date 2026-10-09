# BSV-31 Validation

**Verdict**: PASS — conjunto inicial (`7e7fa32..5fb22e8`) e revisão do dono (`807e445..e59e737`) aprovados; o mutante M5 morre desde e59e737 (ver "Re-verificação após e59e737" no fim). Veredito anterior do delta (histórico, em 56a8aad): reprovado por M5 vivo.

**Date**: 2026-10-08
**Spec**: `.specs/features/BSV-31/spec.md` (escopo do dono: `docs/specs/BSV-31.md`)
**Diff range**: `7e7fa32..5fb22e8` (30f64ae, 849ca70, 4f0820a, 5fb22e8)
**Verifier**: Verifier independente (sub-agente), autor ≠ verificador

Todos os 21 ACs têm teste com `file:line` e valor afirmado igual ao da spec; gates verdes; 20 de 21 mutantes
mortos e 1 equivalente (nenhum vivo). Bundle inicial passa pela convenção do repositório (KB = 1024 B), com
folga de 1,5 KB. Lacunas abaixo não bloqueiam; a primeira é decisão do dono.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | 30f64ae |
| T2 | ✅ Done | 849ca70 |
| T3 | ✅ Done | 4f0820a |
| T4 | ✅ Done | 5fb22e8 |

---

## Spec-Anchored Acceptance Criteria

Testes de unidade em `apps/site/src/lib/`; e2e em `apps/site/e2e/filtros.spec.ts` (roda nos projetos `celular` 390 px e `desktop` 1280 px).

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| DAD-01 | `ate50` ≤ 5000; `50a100` 5001–10000; `100a200` 10001–20000; `acima200` > 20000, em `lista` e `buscar` | `dados/catalogo.test.ts:221` `toEqual([1, 2])` (pp 1, 5000); `:225` `toEqual([3, 4])` (5001, 10000); `:229` `toEqual([5, 6])` (10001, 20000); `:233` `toEqual([7, 8])` (20001, 999999); `dados/busca.test.ts:102` `buscar(..., {faixa:'ate50'})` → `[1]` (5000), `'50a100'` → `[2]` (5001), `'acima200'` → `[3]` (20001) | ✅ PASS (seis fronteiras exatas) |
| DAD-02 | `soComCupom: true` só cards com `c`; ausente/false não filtra | `dados/catalogo.test.ts:249` `toEqual([1, 3])`; `:253` `toEqual([1, 2, 3])` com ausente e `false`; `dados/busca.test.ts:108` `toEqual([2, 3])` e `total` `toBe(2)` | ✅ PASS |
| DAD-03 | interseção de todos os filtros, na ordem pedida | `dados/catalogo.test.ts:276` desconto `toEqual([2, 1, 3])`; `:277` preço `toEqual([2, 1, 3])`; `:279` recentes `toEqual([3, 2, 1])`; cards 4–7 falham um critério cada | ✅ PASS |
| DAD-04 | `lista` ≤ 50 ms, mediana de 5, com aquecimento, 30 mil cards | `dados/desempenho.test.ts:108`, asserção `:129` `toBeLessThanOrEqual(50)` para 6 combinações; aquecimento 2× | ✅ PASS (medianas de 2,0 a 11,4 ms) |
| URL-01 | valores válidos em minúsculas viram filtro | `lib/filtros.test.ts:15` exemplo da spec `toEqual({ordem:'desconto', publico:'FEMININO', loja:'AMAZON', faixa:'ate50', soComCupom:true})`; `:24` todos os demais valores (inclui `mercado-livre` → `MERCADO_LIVRE`) | ✅ PASS |
| URL-02 | inválido ignorado sem afetar os outros | `lib/filtros.test.ts:37` `loja=xyz&publico=feminino` → só `publico`; `ordem=DESCONTO` → `recentes`; `cupom=0`/`cupom=true` → `false`; `:57` repetido → primeiro; e2e `filtros.spec.ts:193` `/?loja=xyz&publico=feminino` → "Todas" e "Feminino" pressionados | ✅ PASS |
| URL-03 | padrão fora da URL, sem `?`; `q`/`utm_*` preservados | `lib/filtros.test.ts:63` `toBe('/elas/')`; `:68` `toBe('/?ordem=desconto&publico=feminino&loja=amazon&preco=ate50&cupom=1')` (exatamente a URL da spec); `:83` `toBe('/?q=serum&utm_source=telegram&loja=shopee')` | ✅ PASS |
| URL-04 | troca por substituição, sem nova entrada no histórico | `e2e/filtros.spec.ts:160` dois filtros, sai para oferta, `goBack()` volta à home filtrada e um `goBack()` a mais cai em `/desejos/` (`:178`) | ✅ PASS |
| URL-05 | abrir, recarregar e voltar já filtram e marcam botões | `e2e/filtros.spec.ts:144` reload mantém `aria-pressed` e grade só Mercado Livre em ordem de desconto; `:160`–`:175` voltar restaura contador e botão; `:182` `/elas/?loja=shopee` grade = `ELAS` ∧ `SHOPEE`, contagem exata | ✅ PASS |
| BAR-01 | grupos e rótulos da spec, `aria-pressed` refletindo estado | `e2e/filtros.spec.ts:337` os 17 rótulos visíveis no desktop; `:68`–`:69` `aria-pressed` true/false; `:213` exatamente 3 pressionados no padrão | ✅ PASS |
| BAR-02 | faixa marcada tocada de novo desmarca; cupom alterna | `e2e/filtros.spec.ts:110`–`:113` contagem volta a 130, `aria-pressed=false`, URL `/`; `:125`–`:126` cupom desliga | ✅ PASS |
| BAR-03 | grade só com cards que casam, na ordem escolhida | `e2e/filtros.spec.ts:65` desconto não crescente; `:89` só `SHOPEE`; `:99` máx ≤ 5000 e contém 5000; `:117` todos com `c`; `:130` Feminino+Amazon = conjunto exato | ✅ PASS |
| BAR-04 | "Limpar filtros" quando fora do padrão; volta tudo e tira os parâmetros | `lib/filtros.test.ts:106`; `e2e/filtros.spec.ts:203` URL `/elas/?q=x` (só `q` fica), botão some; `:216` ausente no padrão | ✅ PASS |
| BAR-05 | "N ofertas" com o total do resultado | `e2e/filtros.spec.ts:93`, `:103`, `:121`, `:136` `toHaveText(\`${esperado} ofertas\`)` com `esperado` derivado da fixture | ✅ PASS |
| BAR-06 | "Ver mais" volta a 40 quando o filtro muda | `e2e/filtros.spec.ts:235` 40 → 80 → filtro → `toHaveCount(40)` | ✅ PASS |
| BAR-07 | faixa "Maiores descontos de hoje" não muda | `e2e/filtros.spec.ts:245` ids antes = depois (`:256`) e a faixa tem card fora do filtro (`:258`) | ✅ PASS |
| BAR-08 | "Nenhuma oferta com esses filtros" + "Limpar filtros" | `e2e/filtros.spec.ts:222` texto visível, grade vazia, "0 ofertas", Limpar → URL `/` e 40 cards; `lib/filtros.test.ts:117` ordem sozinha não é filtro | ✅ PASS |
| BAR-09 | toque ≥ 44 px, foco visível | `e2e/filtros.spec.ts:262` todos os botões visíveis da barra `≥ 44`; contorno `solid rgb(29, 78, 216)`; `:319`–`:322` botões do painel ≥ 44 | ✅ PASS (ver lacuna 4: contraste AA sem teste) |
| PNL-01 | < 640 px: Ordem + "Filtros" fora; demais só no painel | `e2e/filtros.spec.ts:291` 4 visíveis, 4 ocultos, sem `dialog` | ✅ PASS |
| PNL-02 | "Filtros" abre folha inferior; aplica na hora; "Ver N ofertas" fecha | `e2e/filtros.spec.ts:301` base do painel = 844 (fim da tela); URL muda com o painel aberto (`:316`); `Ver ${n} ofertas` (`:317`); fecha, `dialog` some e grade = Shopee ∧ ≤ 5000 (`:325`–`:329`) | ✅ PASS |
| PNL-03 | ≥ 640 px: todos os grupos numa linha que quebra, sem "Filtros" | `e2e/filtros.spec.ts:337` sem "Filtros", 17 rótulos visíveis, `scrollWidth ≤ clientWidth` | ✅ PASS |

**Status**: ✅ 21/21 ACs cobertos com o valor da spec. Spec-precision gaps: unidade do orçamento de bundle e contraste AA (lacunas 1 e 4).

### Regras da spec do dono (lidas no código)

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| Sem dependência nova | `git diff 7e7fa32..5fb22e8 -- apps/site/package.json pnpm-lock.yaml` vazio; `desempenho.test.ts` PUR-01 `dependencies` = `{}` | ✅ |
| Filtros sem fetch | `PaginaOfertas.svelte` `filtrar()` só atribui estado e chama `goto(..., { shallow: true, replace: true })`; `lista`/`buscar` sobre `vitrine.cat` em memória | ✅ |
| `AvisoNovas.svelte` e `vitrine.svelte.ts` intocados | fora do `--stat` do diff | ✅ |
| `PaginaOfertas.svelte` só no bloco da grade e no estado | diff: imports, `filtros`/`filtro`/`comFiltro`, `resultado` usa `filtro`, `filtrar()`, `lerFiltros` no `onMount`, `<BarraFiltros>` e estado vazio dentro da seção "Mais recentes"; `faixa` (descontos) inalterada | ✅ |
| Busca fora da URL | `escreverFiltros` só escreve/apaga `ordem, publico, loja, preco, cupom` (`lib/filtros.ts:18`, `:42`) | ✅ |

---

## Discrimination Sensor

Worktree temporário `git worktree add --detach <scratchpad>/verif 5fb22e8`, `pnpm install --frozen-lockfile`;
cada mutante aplicado, testado e revertido com `git checkout`. Unit: `vitest --run` em `catalogo`, `busca` e
`filtros.test.ts`. E2E: `pnpm build` por mutante e `CI=1 playwright test e2e/filtros.spec.ts -g <teste>` (CI=1
força servidor próprio, sem reaproveitar preview de outro worktree). Lotes de 10, 5 e 6 (+2).

| # | File:line | Mutação | Resultado |
| - | --------- | ------- | --------- |
| M1 | `src/lib/dados/catalogo.ts:102` | `ate50: [0, 5000]` → `[0, 4999]` (`≤` → `<`) | ✅ Morto (catalogo:221, :258; busca:102) |
| M2 | `catalogo.ts:103` | `'50a100'` 5001 → 5000 | ✅ Morto |
| M3 | `catalogo.ts:105` | `acima200` 20001 → 20000 | ✅ Morto (catalogo:233) |
| M3b | `catalogo.ts:104` | `'100a200'` 20000 → 19999 | ✅ Morto |
| M4 | `catalogo.ts:114` | `soComCupom` ignorado (`true`) | ✅ Morto |
| M5 | `src/lib/dados/busca.ts:42` | `buscar` sem faixa (`{ ...f, faixa: undefined }`) | ✅ Morto (busca:102) |
| M6 | `src/lib/filtros.ts:43` | `ordem=recentes` escrita na URL | ✅ Morto (filtros.test:63, :83) |
| M7 | `filtros.ts:17` | `mercado-livre` → `mercado_livre` | ✅ Morto |
| M8 | `filtros.ts:28` | `cupom` inválido aceito (`!== null`) | ✅ Morto (filtros.test:37) |
| M8b | `filtros.ts:27` | ordem padrão → `desconto` | ✅ Morto |
| M9 | `componentes/PaginaOfertas.svelte:59` | `replace: true` → `false` | ✅ Morto (e2e:160, 2 projetos) |
| M10 | `PaginaOfertas.svelte:58` | "Ver mais" não volta a 40 | ✅ Morto (e2e:235) |
| M11 | `PaginaOfertas.svelte:37` | faixa de descontos passa a usar `filtro` | ✅ Morto (e2e:245) |
| M12 | `componentes/BarraFiltros.svelte:137` | tocar de novo na faixa não desmarca | ✅ Morto (e2e:99) |
| M13 | `BarraFiltros.svelte:152` | "Ver N ofertas" não fecha o painel | ✅ Morto (e2e:301) |
| M14 | `BarraFiltros.svelte:41` | `min-h-11` removido | ✅ Morto (e2e:262, :301) |
| M15 | `BarraFiltros.svelte:41` | `focus-visible:outline-*` removido | ⚪ Equivalente: `src/app.css:34` já dá `:focus-visible { outline: 2px solid var(--cor-foco) }` a todo elemento; foco continua visível (lição 18) |
| M15b | `BarraFiltros.svelte:41` | `focus-visible:outline-none` (foco escondido) | ✅ Morto (e2e:262) |
| M16 | `PaginaOfertas.svelte:110` | estado vazio desligado (`&& false`) | ✅ Morto (e2e:222) |
| M17 | `BarraFiltros.svelte:166` | "Limpar" mantém a ordem | ✅ Morto (e2e:203) |
| M18 | `PaginaOfertas.svelte:65` | `onMount` não lê os filtros da URL | ✅ Morto (e2e:144, :182, :193) |
| M19 | `BarraFiltros.svelte:82` | `aria-pressed` fixo em `false` | ✅ Morto (e2e:65) |
| M20 | `BarraFiltros.svelte:115` | painel `hidden` também no desktop | ✅ Morto (e2e:337) |

**Sensor depth**: expandido (23 mutações, 10 de unidade e 13 de e2e)
**Saída do sensor (conjunto inicial)**: 22 mortos, 1 equivalente, 0 vivos - aprovado ✅
**Isolamento**: worktree removido (`Remove-Item -LiteralPath '\\?\...'` + `git worktree prune`; `git worktree remove` falhou com "Filename too long"); `git status --porcelain` do worktree real antes = depois (`?? package.json`, `?? pnpm-lock.yaml` na raiz, alheios ao ticket).

---

## Orçamentos

| Item | Limite | Medido | Result |
| ---- | ------ | ------ | ------ |
| Trocar filtro, 30 mil cards (DAD-04) | ≤ 50 ms, mediana de 5 com aquecimento | Teste passou 3/3 rodado por último e sozinho; medianas fora do runner: `{}` 11,4 ms, `publico` 9,7, `loja+desconto` 5,3, `faixa` 4,6, `cupom+preço` 5,3, combinação total 2,0 | ✅ |
| Bundle inicial da home (JS de `modulepreload` + `import()` do `index.html` e imports estáticos transitivos, + CSS do `<style>`) | ≤ 150 KB | BSV-31: 18 arquivos, JS 130.124 B (52.212 B gzip) + CSS 21.920 B (5.389 B gzip) = **152.044 B brutos (148,5 KiB); 57.601 B gzip**. `origin/develop` 7e7fa32: 141.000 B (137,7 KiB). Delta +11.044 B (+7,8 %) | ✅ com KB = 1024 B (convenção do repo: `desempenho.test.ts:151` `10 * 1024`, `gerador.test.ts:106` `60 * 1024`), folga 1.556 B. ❌ se KB = 1000 B |

Medida refeita pelo Verifier com script próprio sobre `apps/site/build` (o mesmo número do autor nos dois commits).

---

## Prints (`.specs/features/BSV-31/prints/`)

| Arquivo | O que mostra | DoD |
| ------- | ------------ | --- |
| `painel-celular.png` | 390 px, folha inferior "Filtros" aberta sobre o fundo escurecido, Feminino e Amazon marcados, "Ver 13 ofertas" | ✅ celular com o painel aberto |
| `filtros-desktop.png` | 1280 px, barra em duas linhas: Maior desconto, Shopee, Só com cupom marcados; "14 ofertas" e "Limpar filtros" | ✅ desktop com filtros |
| `barra-celular.png` | 390 px, "Filtros" + ordem numa linha que rola ("Menor preço" cortado na borda) | complementar |
| `vazio-desktop.png` | estado vazio com "Nenhuma oferta com esses filtros" e "Limpar filtros" | complementar |

Imagens dos cards aparecem quebradas nos prints: catálogo sintético sem `img/`, não é defeito da tela.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ `casaFiltro` ganha duas condições; `filtros.ts` puro (60 linhas) |
| Surgical changes | ✅ só `lib/dados`, `lib/filtros.ts`, `BarraFiltros.svelte`, bloco da grade de `PaginaOfertas.svelte` |
| No scope creep | ✅ busca fora da URL; sem subpáginas de público |
| Matches patterns | ✅ Svelte 5 runes, Tailwind, sem CSS ad hoc |
| Spec-anchored outcome check | ✅ (2 spec-precision gaps) |
| Per-layer Coverage | ✅ dados 1:1 com DAD; fluxos e2e nos dois tamanhos |
| Every test maps to a spec requirement | ✅ cada `it`/`test` tem o ID no nome ou no comentário |
| Documented guidelines followed: `CLAUDE.md`, `apps/site/CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` §6 | ✅ |

---

## Edge Cases

- [x] Busca com filtros ativos: `buscar` recebe `filtro` (`PaginaOfertas.svelte:44`); unidade em `busca.test.ts:102`, `:108`. Sem e2e de busca + filtro (lacuna 5).
- [ ] Catálogo ainda não carregado → barra sem contador: implementado (`BarraFiltros.svelte:159` `total !== null`), sem teste (lacuna 5).
- [x] Parâmetro repetido vale o primeiro: `filtros.test.ts:57`.

---

## Gate Check

- **Gate command**: `cd apps/site && pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`
- **Result**: install ok; lint ok; check ok; Vitest 14 arquivos, **136 passed**; build ok; Playwright **140 passed** (1,3 min); 0 falhas, 0 pulados
- **Test count before feature**: 116 unit, 100 e2e (derivado do diff: +20 unit, +40 e2e = 20 testes × 2 projetos)
- **Test count after feature**: 136 unit, 140 e2e
- **Skipped tests**: nenhum
- **Failures**: nenhuma

---

## Lacunas (ranqueadas; nenhuma bloqueia o PASS)

1. **Unidade do orçamento de bundle** - `docs/specs/BSV-31.md` regra 4 diz "150 KB" sem unidade. 152.044 B passa com KiB (convenção do repo) e reprova com 1000 B; folga de 1,5 KB após +11 KB neste ticket. Não há gate automático do bundle da home (só DES-04 do módulo de dados). Proposta: dono fixa KiB em `MANIFEST.md §7`/spec e um teste mede `build/index.html` como acima.
2. **Painel sem foco preso** - `BarraFiltros.svelte:111`–`:123` é `div role="dialog" aria-modal="true"`, não `<dialog>` como diz a premissa da spec ("`<dialog>` dá foco preso e Esc"). Esc e clique no fundo fecham, mas Tab sai do painel para a página por trás. Desvio da premissa sem registro; teste não cobre teclado no painel.
3. **Ordem cortada no celular** - `prints/barra-celular.png`: "Menor preço" sai da tela na linha rolável. PNL-01 passa (`toBeVisible` aceita parcial); conferir na execução real se o dono aceita a rolagem.
4. **Contraste AA sem teste** - regra 3 da spec do dono pede contraste AA; BAR-09 da spec EARS omitiu. Cobertura fica no PageSpeed/Lighthouse do "Real (dono)".
5. **Casos de borda sem teste** - barra sem contador antes do catálogo (`BarraFiltros.svelte:159`) e busca + filtro na tela (só unidade). Baixo risco.
6. **Foco visível testado num botão só** - `e2e/filtros.spec.ts:271` mede "Maior desconto"; M15 é equivalente porque `src/app.css:34` cobre todo elemento. Se a regra global sair, os outros botões (painel, "Limpar") ficam sem garantia de teste.

## Lições propostas (para o dono consolidar; não gravadas em LESSONS.md)

- Orçamento em "KB" na spec precisa de unidade explícita; o repo usa 1024 nos testes, mas a medida manual deixa a dúvida para a revisão.
- Premissa de spec que escolhe um elemento pela propriedade de a11y (`<dialog>` → foco preso) vira AC testável, senão a troca de implementação passa sem rastro.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| DAD-01..04 | Done | ✅ Verified |
| URL-01..05 | Done | ✅ Verified |
| BAR-01..09 | Done | ✅ Verified |
| PNL-01..03 | Done | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (bloqueia o merge só o "Real (dono)" da spec: filtros em `/elas/` no celular, link filtrado em outro aparelho, PageSpeed celular ≥ 90)

**Spec-anchored check**: 21/21 ACs com o valor da spec; 2 spec-precision gaps (unidade do bundle, contraste AA)
**Sensor**: 22/22 mortos + 1 equivalente
**Gate**: 136 unit + 140 e2e passed

---

## Revisão do dono — delta 807e445..56a8aad

**Veredito do delta em 56a8aad (histórico)**: reprovado (1 mutante vivo não equivalente; o código atende os 3 ACs, mas um requisito da T5 não tem teste que o discrimine)
**Verificou**: Verifier independente (sub-agente), autor ≠ verificador
**Diff range**: `807e445..56a8aad` (86643a2, 7a443ca, 57285ec, 56a8aad)
**Data**: 2026-10-08

### Gates (`apps/site`, worktree real)

`pnpm lint` ok; `pnpm check` ok; `pnpm test` Vitest 14 arquivos, **136 passed** (DES/DAD-04 passaram na primeira, sem repetição); `pnpm build` ok; `pnpm e2e` **146 passed** (1,9 min), 0 falhas, 0 pulados. Antes do delta: 140 e2e; +6 = 3 testes novos × 2 projetos. Nenhum teste removido ou enfraquecido no diff.

### ACs novos (evidência ou zero)

| AC | Valor da spec | Código | `file:line` + asserção | Result |
| -- | ------------- | ------ | ---------------------- | ------ |
| PNL-04 foco preso, fundo inerte | Tab e Shift+Tab não saem; fundo inerte | `<dialog>` + `showModal()` (`BarraFiltros.svelte:181`, `:57`); `cicloTab` dá a volta no último/primeiro botão (`:68`–`:77`, ligado em `:187`) | `e2e/filtros.spec.ts:379`–`:381` 25 × Tab `dentro()` `toBe(true)`; `:384` passou por "Ver 130 ofertas" e "Todos" (deu a volta); `:386`–`:388` 25 × Shift+Tab; `:390`–`:393` `card.focus()` não tira o foco do painel (fundo inerte) | ✅ (M1, M2 mortos) |
| PNL-04 Esc | painel fecha e foco volta a "Filtros" | `onclose={aoFechar}` (`:185`) → `aberto = false; gatilho?.focus()` (`:62`–`:65`) | `:395` `press('Escape')`; `:396` `getByRole('dialog')` `toHaveCount(0)`; `:397` gatilho `toBeFocused()` | ✅ (M4 morto; M3 equivalente no Chromium) |
| PNL-04 grupos num lugar só (What da T5) | grupos só no diálogo enquanto aberto | `{#if !aberto}` (`:169`) | **sem asserção**: os seletores por papel ignoram a cópia `display:none` | ❌ M5 vivo |
| PNL-05 degradê com conteúdo à direita | visível no início | `hidden={!mais}` (`:175`); `mais` = `scrollLeft + clientWidth < scrollWidth - 1` (`:83`), medido em `scroll` e `ResizeObserver` (`:85`–`:90`) | `e2e/filtros.spec.ts:341` `toBeVisible()`; `:348` borda direita do degradê = borda da linha; `:349`–`:351` `linear-gradient(... rgb(255, 255, 255))`; `:353` `pointerEvents` `'none'` | ✅ (M7, M8 mortos) |
| PNL-05 some no fim | oculto no fim da rolagem, volta no início | idem | `:354`–`:355` `scrollTo(scrollWidth)` → `toBeHidden()`; `:356` "Menor preço" `toBeInViewport({ratio: 1})`; `:359`–`:360` volta → `toBeVisible()` | ✅ (M6, M12 mortos) |
| PNL-05 ≥ 640 px | sem degradê | `sm:hidden` (`:174`) e `mais` falso com `sm:overflow-visible` + `sm:flex-wrap` (`:155`) | `:430` `[data-mais]` `toBeHidden()` a 1280 px | ✅ (M9 equivalente) |
| PNL-05 sem rolagem horizontal a 390 px | a linha rola por dentro | `min-w-0` na envoltória (`:153`), `overflow-x-auto` na linha (`:155`) | `:343` `documentElement.scrollWidth` `≤ 390` | ✅ (M8 morto) |
| BUD-01 | JS inicial (`modulepreload` + imports estáticos, bruto) + `<style>` ≤ 153.600 B | `jsInicial` segue `href=`/`import(` do HTML e `from`/`import` relativos dos módulos (`e2e/saida.spec.ts:160`–`:173`) | `saida.spec.ts:190` `toBeLessThanOrEqual(ORCAMENTO_KIB * 1024)` com `ORCAMENTO_KIB = 150` (`:157`); sanidade `:187` `entry/start.`, `:188` `> 5` arquivos, `:189` CSS `> 10_000` | ✅ (M10 morto; M11 equivalente hoje) |

ACs anteriores depois da troca para `<dialog>`: PNL-01 (`filtros.spec.ts:291`), PNL-02 (`:301`, base do painel = 844, aplica com o painel aberto, "Ver N ofertas" fecha), PNL-03 (`:405`) e BAR-01..09 continuam verdes nos dois projetos (146/146).

Sonda extra do Verifier (worktree temporário, não versionada): com o painel aberto a 390 px há 1 `#filtro-publico` no DOM (o código atende o "num lugar só"); girando para 844 × 390 o diálogo continua aberto e visível (`display: grid`: `open:grid` vence `sm:hidden`), o clique na grade é bloqueado e a linha não mostra os grupos até fechar. Não trava: o painel segue usável. Print do painel refeito pelo Verifier a partir de 56a8aad: mesma folha de `prints/painel-celular.png` (o arquivo é de 5fb22e8, mas segue representativo).

### Discrimination Sensor (worktree temporário em 56a8aad, porta 4174, `CI=1`, 2 workers, `pnpm build` por mutante)

| # | Mutação | Testes | Resultado |
| - | ------- | ------ | --------- |
| M1 | `showModal()` → `show()` (`BarraFiltros.svelte:57`) | 11 falhas em `filtros.spec.ts` (PNL-02, PNL-04, filtros no celular) | ✅ morto |
| M2 | sem `onkeydown={cicloTab}` (`:187`) | `filtros.spec.ts:364` falha nos 2 projetos (Tab sai do painel) | ✅ morto |
| M3 | `aoFechar` sem `gatilho?.focus()` (`:64`) | 42 passed | ⚪ equivalente no Chromium: o `<dialog>` devolve o foco nativamente ao elemento focado antes do `showModal`. No WebKit (iPhone) o toque não foca o botão; a linha `:64` é quem garante lá, e não há projeto WebKit no `playwright.config.ts` |
| M4 | `oncancel` com `preventDefault` (Esc bloqueado) | `filtros.spec.ts:396` `toHaveCount(0)` falha nos 2 projetos | ✅ morto |
| M5 | `{#if !aberto}` → `{#if true}` (`:169`): grupos duplicados com o painel aberto | 42 passed | ❌ **vivo**: 2 cópias de cada grupo e ids `filtro-publico`/`filtro-loja`/`filtro-preco` duplicados; nenhum teste conta os grupos |
| M6 | degradê sempre visível (`hidden={false}`, `:175`) | `filtros.spec.ts:355` `toBeHidden` falha | ✅ morto |
| M7 | degradê nunca visível (`hidden={true}`) | `filtros.spec.ts:341` `toBeVisible` falha | ✅ morto |
| M8 | sem `min-w-0` na envoltória (`:153`) | `filtros.spec.ts:341` falha (a linha não rola, `mais` falso) | ✅ morto |
| M9 | `sm:hidden` removido do degradê (`:174`) | 42 passed | ⚪ equivalente: ≥ 640 px a linha quebra e não rola, `mais` é sempre falso e `hidden` já esconde |
| M10 | limite `150 * 1024` → `150 * 1000` (`saida.spec.ts:190`) | bundle falha nos 2 projetos (153.069 > 153.000) | ✅ morto |
| M11 | `jsInicial` ignora imports estáticos (`saida.spec.ts:171`) | 16 passed | ⚪ equivalente no build atual: os 18 arquivos alcançados pelos imports já estão todos no `modulepreload` do `index.html` (conferido pelo script próprio do Verifier) |
| M12 | `mais` com margem de +40 px (`:83`) | `filtros.spec.ts:355` falha | ✅ morto |

**Sensor depth**: expandido (12 mutações). **Resultado do sensor**: 8 mortos, 3 equivalentes, **1 vivo (M5)**.
Isolamento: worktree temporário removido (`Remove-Item \\?\…` + `git worktree prune`); `git status --porcelain` do worktree real antes e depois: `?? package.json`, `?? pnpm-lock.yaml` (iguais).

### Bundle (BUD-01)

Medida refeita com script próprio (regex mais larga, caminhos relativos resolvidos, CSS em bytes UTF-8): **18 arquivos JS, 130.903 B (52.660 B gzip) + CSS 22.166 B = 153.069 B = 149,5 KiB**; igual à anotação do teste (`JS 130903 B (18 arquivos) + CSS 22166 B = 153069 B`). Nenhum import dinâmico entra na conta. **Folga: 531 B (0,35 %)**. Delta desde o PASS anterior: +1.025 B (painel `<dialog>` + degradê).

### Prints (lição 19)

| Arquivo | O que mostra | OK? |
| ------- | ------------ | --- |
| `prints/barra-celular.png` | 390 px, "Filtros" + Recentes + Maior desconto; "Menor preç" esmaecendo na borda direita | ✅ degradê visível (sutil, para o branco do fundo) |
| `prints/barra-celular-fim.png` | mesma linha rolada até o fim: "Filtros" cortado à esquerda, "Menor preço" inteiro, sem esmaecer à direita | ✅ fim sem degradê |
| `prints/painel-celular.png` | folha inferior sobre fundo escurecido, Feminino e Amazon marcados, "Ver 13 ofertas" | ✅ (de 5fb22e8; o print do Verifier em 56a8aad tem o mesmo layout) |

### Lacunas (ranqueadas)

1. **M5 vivo: duplicação dos grupos sem teste** - `BarraFiltros.svelte:169`; `e2e/filtros.spec.ts:364` não conta. **Fix-1**: no teste PNL-04 (ou PNL-02), com o painel aberto, `expect(page.locator('[id="filtro-publico"]')).toHaveCount(1)` (e o mesmo para `filtro-loja`/`filtro-preco`), ou contar os botões "Shopee" no DOM incluindo ocultos. Prioridade: Major (requisito da T5 sem sensor); a correção é só de teste.
2. **Folga do bundle: 531 B** - `e2e/saida.spec.ts:190`. Qualquer mudança de ~0,5 KB na home quebra o gate; o dono decide se aceita ou se o próximo ticket de site já nasce com corte.
3. **Retorno de foco só testado no Chromium** - `BarraFiltros.svelte:64` (M3 equivalente). No iPhone o toque não foca "Filtros"; conferir no "Real (dono)" ou adicionar projeto WebKit.
4. **"Fundo inerte" testado só por foco** - `e2e/filtros.spec.ts:390`–`:393`; o comentário fala em clique, mas não há asserção de clique bloqueado (a sonda do Verifier confirmou que o clique é bloqueado). Baixa.
5. **Ramo de imports estáticos de `jsInicial` sem efeito hoje** - `e2e/saida.spec.ts:171` (M11 equivalente). Só pesa se o SvelteKit deixar de listar algum chunk no `modulepreload`. Baixa.
6. **Celular girado com o painel aberto** - ≥ 640 px o diálogo fica visível (`open:grid` vence `sm:hidden`, `BarraFiltros.svelte:184`) e a linha não mostra os grupos até fechar. Usável; informativo.

### Lições propostas (para o dono consolidar; não gravadas)

- Requisito do tipo "X existe uma vez só" precisa de contagem no DOM (`[id=…]` ou locator CSS); `getByRole` ignora cópias ocultas e deixa a duplicação passar.
- Comportamento que o Chromium já faz sozinho (devolver o foco ao fechar `<dialog>`) não é discriminado por e2e só em Chromium; se o alvo é iPhone, o teste precisa de WebKit.

### validate_state

`python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-31 --root .` → exit 1 em 56a8aad (histórico): o script leu juntas a linha de resultado do sensor inicial (aprovado) e a do delta (reprovado) e acusou "placeholder". Corrigido na re-verificação: um único veredito vigente no fim do arquivo.

**Veredito do delta em 56a8aad (histórico)**: reprovado — Fix-1 pedido (feito em e59e737, abaixo).

### Re-verificação após e59e737 (iteração 2 de 3)

**Verificou**: Verifier independente (sub-agente), autor ≠ verificador
**Diff range**: `56a8aad..e59e737` (só teste: `apps/site/e2e/filtros.spec.ts`, +6 linhas no teste PNL-04)

**Fix-1 conferido**: com o painel aberto, `e2e/filtros.spec.ts:378`–`:379` `#filtro-ordem`, `#filtro-publico`, `#filtro-loja`, `#filtro-preco` `toHaveCount(1)`; `:381` `[data-filtros] button[aria-pressed]` `toHaveCount(17)` (3 ordem + 5 público + 4 loja + 4 preço + cupom, os mesmos 17 rótulos de PNL-03); `:382` painel `button[aria-pressed]` `toHaveCount(14)` (5 + 4 + 4 + 1, sem a ordem). Valores conferidos contra `BarraFiltros.svelte:15`–`:38` e `:143`. Com o fix, as linhas citadas acima para o teste PNL-04 em diante andam +6 (Esc em `:401`–`:403`; degradê no desktop em `:436`).

**Gates** (worktree real, em e59e737): `pnpm lint` ok; `pnpm check` ok; Vitest 14 arquivos, **136 passed** (testes de tempo verdes na primeira, sem repetição); `pnpm build` ok; Playwright **146 passed** (2,6 min), 0 falhas, 0 pulados.

**Sensor** (worktree temporário em e59e737, porta 4174, `CI=1`, `pnpm build` por mutante):

| # | Mutação | Resultado |
| - | ------- | --------- |
| M5 | `{#if !aberto}`/`{/if}` removidos em volta de `<div class="hidden sm:contents">{@render grupos()}</div>` (`BarraFiltros.svelte:169`–`:171`) | ✅ morto: `filtros.spec.ts:364` falha nos 2 projetos em `toHaveCount` |
| M1 | `showModal()` → `show()` (sanidade) | ✅ morto (11 falhas, inclui PNL-02 e PNL-04) |
| M6 | degradê sempre visível (sanidade) | ✅ morto (`:337`, `toBeHidden`) |
| M2 | sem `cicloTab` (sanidade) | ✅ morto (`:364`, Tab sai do painel) |

Sensor do delta somado: 12 mutações em 56a8aad + M5 refeito = **9 mortos, 3 equivalentes (M3, M9, M11), 0 vivos**. Isolamento: worktree temporário removido (`Remove-Item \\?\…` + `git worktree prune`); `git status --porcelain` do worktree real igual ao de antes (só `validation.md` desta verificação, `?? package.json`, `?? pnpm-lock.yaml`).

**Print**: `prints/painel-celular.png` refeito pelo autor em 56a8aad, idêntico em bytes ao anterior (sem mudança no git); bate com o print do Verifier.

**Lacunas que seguem abertas (nenhuma bloqueia)**: 2 (folga do bundle 531 B), 3 (retorno de foco só no Chromium), 4 (clique no fundo sem asserção), 5 (ramo de imports estáticos sem efeito hoje), 6 (painel aberto ao girar o celular). Bloqueia o merge só o "Real (dono)" da spec.

**validate_state**: `python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-31 --root .` → **exit 0** (`validate_state: 0 error(s) across [BSV-31]`)

**Result**: PASS
