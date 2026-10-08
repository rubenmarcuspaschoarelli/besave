# BSV-31 Validation

**Verdict**: PASS

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
**Result**: 22 mortos, 1 equivalente, 0 vivos - PASS ✅
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
