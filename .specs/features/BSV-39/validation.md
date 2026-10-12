# BSV-39 Validation

**Result**: PASS ✅ (veredito; sem gap bloqueante; gaps 1 e 2 fechados na 2ª rodada, resta 1 informativo)

**Date**: 2026-10-11
**Spec**: `.specs/features/BSV-39/spec.md` (DIE-01..DIE-09) e `docs/specs/BSV-39.md` (critérios do dono)
**Diff range**: `7256b65..616c80f` (1 commit, `apps/site/` + `.specs/features/BSV-39/`) + correções ainda sem commit no worktree (`apps/site/e2e/dieta.spec.ts:99-120`, `apps/site/docs/bundle.md` seção "Do que era feito") — 2ª rodada de verificação
**Verifier**: Verifier sub-agente independente (autor ≠ verificador); não alterou código de produção nem testes

---

## Task Completion

Sem `tasks.md` (ticket de uma tarefa). Commit único `616c80f perf(site): …`, Conventional Commits.

---

## Gate Check (job `site` do CI, rodado pelo Verifier neste worktree)

| comando | resultado |
|---|---|
| `pnpm install --frozen-lockfile` | ok (lockfile inalterado) |
| `pnpm lint` | ok (prettier + eslint) |
| `pnpm check` | 0 erros, 0 avisos (483 arquivos) |
| `pnpm build` | ok |
| `E2E_PORTA=4271 pnpm e2e` | **292 passed**, 0 failed, 0 flaky, 0 skipped (3,3 min) |
| `pnpm test` (por último, inclui `desempenho.test.ts`) | **166 passed** (17 arquivos) |

- 2ª rodada: `e2e/dieta.spec.ts` com o teste novo → 10 passed (5 testes × 2), e o teste novo 40/40 com `--repeat-each=20` (lição 25); `pnpm lint` e `pnpm check` (0 erros, 0 avisos) verdes no worktree com as correções.
- e2e antes: 284 (146 testes × 2 projetos); depois: 292 (+4 testes de `e2e/dieta.spec.ts` × 2). Vitest: 166 → 166 (nenhum arquivo de teste unitário mudou).
- `git diff 7256b65..616c80f -- apps/site/e2e`: só `dieta.spec.ts` (novo) e 5 linhas em `saida.spec.ts:192-196` (anotação `folga`). Nenhuma asserção existente alterada.

---

## Spec-Anchored Acceptance Criteria

| Critério | Resultado esperado (spec) | Evidência `file:line` + asserção | Resultado |
|---|---|---|---|
| BSV-39 aceite 1 / DIE-01 | carregamento inicial ≤ 143 360 B; limite do BUD-01 continua 150 KiB | `apps/site/e2e/saida.spec.ts:163` `ORCAMENTO_KIB = 150`; `:201` `expect(total).toBeLessThanOrEqual(ORCAMENTO_KIB * 1024)`; medido nesta execução: `JS 127218 B (17 arquivos) + CSS 16043 B = 143261 B` (celular e desktop) | ✅ PASS (143 261 ≤ 143 360; ver gap 3: o alvo de 10 KiB é medido, não afirmado — por desenho da spec) |
| DIE-02 | folga anotada no relatório | `apps/site/e2e/saida.spec.ts:193-196` anotação `folga`; lida no JSON do reporter: `folga 10339 B (10.1 KiB)` | ✅ PASS |
| DIE-03 / aceite 2 | inventário antes/depois, reproduzível | `apps/site/docs/bundle.md:9-12` (totais antes/depois), `:21-38` (por pedaço, depois), `:42-66` (por pedaço, antes — seção "Do que era feito", conferida pelo Verifier: bytes brutos de `CoB8Oudm`, `MkdQRX7D`, `BWnVuBX-`, `CI4vqqd7`, `entry/app`, `BaNbYf_w`, `entry/start` iguais aos do build de `7256b65`, soma da tabela = 153 553 B); CSS antes/depois; `apps/site/package.json:17` `"inventario"`; `pnpm inventario` rodado pelo Verifier reproduz 143 261 B / folga 10 339 B e os mesmos bytes por arquivo | ✅ PASS (gap 2 fechado na 2ª rodada) |
| aceite 3 / DIE-04 | gates verdes, e2e existentes intactos, teste novo por carga sob demanda | gates acima; diff de `e2e/` só acrescenta. Nenhum carregamento sob demanda novo foi introduzido (o rodapé saiu do JS, não virou import dinâmico) → coberto por DIE-07/08/09 | ✅ PASS |
| aceite 4 / DIE-05 | `manifest.json` antes de qualquer chunk; 3 chunks de `n` mais alto antes dos demais, mesma ordem | `apps/site/e2e/dieta.spec.ts:32` `expect(pedidos.slice(0, 4)).toEqual(['manifest', 'chunk 4', 'chunk 3', 'chunk 2'])`; `:33` resto `['chunk 0','chunk 1']`; reforçado por `src/lib/dados/sincronizador.test.ts` (SIN-01, pré-existente). `sincronizador.ts` não foi tocado pelo diff | ✅ PASS |
| aceite 5 / DIE-06 | home, `/elas/`, `/busca/`, `/desejos/` em 390 e 1280 px iguais aos de antes | prints lado a lado em `.specs/features/BSV-39/prints/` (18 arquivos). **Verificação independente do Verifier**: builds `7256b65` × `616c80f` servidos lado a lado, screenshot de página inteira em 8 cenas × 2 larguras (home, elas, busca `?q=protetor` com 2 expiradas, desejos com favoritos, menu "Mais" aberto, foco no card, hover em "Ver mais ofertas", painel de filtros): **0 pixels diferentes nas 16 comparações**; guarda automática (2ª rodada): `apps/site/e2e/dieta.spec.ts:104` `toHaveCSS('filter', 'grayscale(1)')`, `:105-108` `font-variant-numeric` `tabular-nums`, `:113` `box-shadow` `rgb(29, 78, 216) 0px 0px 0px 2px`, `:116-119` sombra do menu "Mais"; estilo computado (`box-shadow`, `filter`, `translate`, `transform`, `font-variant-numeric`, `outline`) de todos os elementos igual, a menos das sombras transparentes de largura zero que o Tailwind compunha | ✅ PASS |
| DIE-07 | exatamente um rodapé por página, igual ao de antes, dentro do contêiner | `apps/site/e2e/dieta.spec.ts:47` `toHaveLength(1)`; `:53` `expect(conteiner).toContain(rodape)`; `:54` depois do `<script`; `:56` `rodapes.size === 1`. Verifier: as 54 páginas do build têm o mesmo `<footer>` de `7256b65` (sem comentários de hidratação) e o mesmo HTML de corpo, a menos dos nomes de classe trocados e de espaços | ✅ PASS |
| DIE-08 | clique em "Lista de desejos" navega sem recarregar; rodapé continua único | `apps/site/e2e/dieta.spec.ts:72` URL `/desejos/`; `:74` `marca === 39` (sem recarga); `:75` e `:78` `footer` `toHaveCount(1)` (inclusive após `goBack`) | ✅ PASS |
| DIE-09 | código do rodapé fora do JS inicial da home | `apps/site/e2e/dieta.spec.ts:92` `expect(codigo).not.toContain('Sobre a Besave')` sobre o fecho transitivo de `modulepreload`/`import()` da home; `:96` sanidade `vistos.size > 5` | ✅ PASS |
| Edge case | hidratação falha → página de erro sem rodapé | documentado em `spec.md`; comportamento do kit (limpa o contêiner). Sem teste — aceitável (mesmo comportamento da página de erro padrão) | ⚠️ não testado, não exigido |
| Real (dono) | PageSpeed celular e computador ≥ 90; navegação no celular | fora do alcance do Verifier | ⏳ bloqueia o merge (execução real do dono) |

**Status**: ✅ todos os ACs com evidência.

---

## Regras da spec

| regra | evidência | resultado |
|---|---|---|
| 1. nada visível/fluxo muda | 0 px de diferença em 16 cenas; 292 e2e | ✅ |
| 2. primeira pintura: ordem manifest + 3 chunks | `dieta.spec.ts:32`; `sincronizador.ts` intocado | ✅ |
| 3. sem dependência de runtime; adapter-static, prerender e CSS embutido mantidos | `package.json` só ganhou o script `inventario`; `pnpm-lock.yaml` inalterado; `vite.config.ts:21` `adapter-static` `fallback: undefined`; `:25` `inlineStyleThreshold: 32_768`; `src/routes/+layout.ts:1` `prerender = true`; `build-head/index.html` tem 1 `<style>`, 17 `modulepreload` (mesma contagem de antes), 0 `.map` no build | ✅ |
| fora de escopo: `besave.css` | `build/assets/besave.css` byte a byte idêntico entre `7256b65` e `616c80f` (`cmp`) | ✅ |
| regra 11 (evidência) | diff sem `C:\Users`, token, ARN | ✅ |

---

## Avaliação crítica das decisões

1. **Utilitários `@utility` em `app.css:51-73`**: valores equivalentes aos do Tailwind 4.3.3 (`shadow-lg`/`2xl` = mesmas camadas; `ring-2` = `0 0 0 2px` com offset 0 e cor `--cor-foco` = `--color-foco`; `brightness(95%)`; `grayscale(100%)`; `translate: 0 -50%` = `--tw-translate-x` 0; `tabular-nums`). Nenhum elemento que recebeu um deles combina outra sombra/anel/filtro/transform, então a composição `--tw-*` não fazia diferença. Confirmado por estilo computado e pixels. Variantes (`hover:`, `has-focus-visible:`) funcionam com `@utility`. Risco: nomes próprios não são autoexplicativos para quem vier depois e não têm guarda de teste (gap 1).
2. **Preflight vendorizado (`src/lib/estilo/preflight.css`)**: comparado com `node_modules/tailwindcss/preflight.css` 4.3.3 — o restante é cópia literal (só comentários removidos). Busca em `src/` por `hr, abbr, code, kbd, samp, pre, sub, sup, table, progress, select, optgroup, textarea, meter, output, datalist` e `input type=file/date/time/number/range/color`: **nenhuma ocorrência**; o único `<input>` é `type="search"` (`Busca.svelte:58`), sem `required`/`pattern` (não fica `:-moz-ui-invalid`), e `::-webkit-search-decoration` foi mantido. Também saiu `::-webkit-calendar-picker-indicator` (só `datalist`/datas; sem uso). Risco: upgrade do Tailwind não atualiza a cópia — o cabeçalho do arquivo avisa.
3. **`build.modulePreload: false`** (`vite.config.ts:10`): o kit continua emitindo os 17 `<link rel="modulepreload">` da home (contagem igual à base); some só o `__vite__mapDeps`/preload dos imports dinâmicos (resta em `entry/app`, para CSS de rota). Efeito: pedaços sob demanda (filtros, aviso de novas, setas) buscam suas dependências em cascata — latência pequena, sem mudança de fluxo (e2e de filtros/novas/setas verdes). Ganho medido pelo Verifier: sem ele o total vai a 145 163 B (folga 8 437 B), ou seja, **esse corte sozinho é o que põe o ticket abaixo de 143 360 B**.
4. **Rodapé via `hooks.server.ts:12,19` no `<!--rodape-->` de `app.html:18`**: roda no prerender (e no dev server, pelo mesmo hook); fica dentro do `display: contents`, depois da raiz do Svelte; o roteador do kit intercepta o clique (DIE-08 prova sem recarga). Diferença observada: na ordem do DOM o `<footer>` agora vem depois do `<div>`/`<script>` finais do kit (antes vinha antes) — sem efeito visual (0 px). Página de erro do cliente fica sem rodapé (edge case documentado).
5. **`discloseVersion: false`** (`vite.config.ts:16`): efetivo — `__svelte` some do JS (`grep`: base 1 arquivo, head 0). Só detecção de versão por extensões.
6. **`source('./')` + `@source not './**/*.test.ts'`** (`app.css:6-7`): Tailwind deixa de escanear `e2e/` e testes; o HTML das 54 páginas e os pixels iguais mostram que nenhuma classe usada sumiu.

---

## Discrimination Sensor

Worktree temporário (`git worktree add --detach` em scratchpad, `616c80f`), `pnpm build` por mutante, e2e na porta 4272. Sem `git stash`.

| # | Mutante | Arquivo | Testes rodados | Resultado |
|---|---|---|---|---|
| M1 | rodapé injetado em `</body>` (fora do contêiner) | `src/hooks.server.ts:19` | `dieta.spec.ts` | ✅ morto (`dieta.spec.ts:42`, 2/8 falham) |
| M2 | `<Rodape />` de volta no `PaginaOfertas` (cliente) | `PaginaOfertas.svelte` | `dieta` + `saida` | ✅ morto (DIE-07, DIE-08, DIE-09; 6 falhas) |
| M3 | `<!--rodape-->` removido do `app.html` | `src/app.html:18` | `dieta.spec.ts` | ✅ morto (DIE-07, DIE-08) |
| M10 | rodapé só nas páginas de área (volta o `if (!p) return resolve(event)`) | `src/hooks.server.ts` | `dieta.spec.ts` | ✅ morto (DIE-07, DIE-08) |
| M4b | classe `foto-grayscale` → `foto-cinza` | `FotoOferta.svelte:31` | `busca.spec.ts` | ✅ morto (`toHaveClass(/grayscale/)`) |
| M7 | chunks em ordem crescente | `sincronizador.ts:52` | `dieta.spec.ts` | ✅ morto (`dieta.spec.ts:32`) |
| M6 | `PRIMEIROS = 2` | `sincronizador.ts:9` | `dieta` + `home` (e2e); `sincronizador.test.ts` | ⚠️ sobrevive aos e2e (a ordem dos pedidos é a mesma); ✅ morto pelo `pnpm test` (SIN-01). Morto pela suíte |
| M5 | sem `modulePreload: false` | `vite.config.ts:10` | `saida` + `dieta` | ⚪ sobrevive — esperado: BUD-01 é 150 KiB por regra da spec; total medido 145 163 B (> 143 360). Ver gap 3 |
| M4 | `foto-grayscale` com `filter: none` | `app.css:65-67` | **suíte e2e inteira** (1ª rodada); `dieta.spec.ts` atualizado (2ª) | 1ª: ❌ sobrevive (292 passed). **2ª: ✅ morto** — `dieta.spec.ts:100` falha nos 2 projetos, `Expected: "grayscale(1)" / Received: "none"` |
| M8 | `anel-foco` com cor `red` | `app.css:59-61` | **suíte e2e inteira** (1ª rodada); `dieta.spec.ts` atualizado (2ª) | 1ª: ❌ sobrevive (292 passed). **2ª: ✅ morto** — `dieta.spec.ts:100` falha nos 2 projetos, `Expected: "rgb(29, 78, 216) 0px 0px 0px 2px" / Received: "rgb(255, 0, 0) 0px 0px 0px 2px"` |

**Sensor depth**: lightweight ampliado (10 mutantes).
**Result**: 9 mortos (8 pelos e2e + 1 pelo vitest), 1 equivalente/fora do alcance por desenho (M5), 0 sobreviventes. 2ª rodada: cópia isolada (`git worktree add --detach` + `dieta.spec.ts` copiado), controle sem mutante 10 passed, porta 4276; `git status --porcelain` do worktree real igual antes e depois.
**Isolamento**: `git status --porcelain` do worktree real vazio antes e depois (igual). O worktree temporário foi desregistrado (`git worktree remove --force` + `prune`); restaram no scratchpad da sessão 3 binários nativos `.node` hardlinkados do store do pnpm que o Windows não deixou apagar ("Acesso negado", em uso por outros processos); nada fora do scratchpad.

---

## Code Quality

| Princípio | Status |
|---|---|
| Mínimo de código / sem escopo extra | ✅ |
| Mudanças cirúrgicas, só `apps/site/` | ✅ |
| Padrões do repo (Svelte 5, Tailwind) | ✅ (`@utility` é mecanismo do Tailwind; preflight vendorizado é cópia do Tailwind, não CSS ad hoc de componente) |
| Regra 7 (sem dependência nova) | ✅ |
| Spec-anchored: asserções miram o resultado da spec | ✅ |
| Todo teste novo mapeia a um DIE | ✅ (`dieta.spec.ts` → DIE-05, 07, 08, 09; anotação → DIE-02) |
| Diretrizes: `CLAUDE.md`, `apps/site/CLAUDE.md`, `docs/specs/BSV-39.md` | ✅ |

---

## Gaps (ranqueados; nenhum bloqueia)

1. ~~**Menor — utilitários próprios sem guarda de equivalência.**~~ **Fechado (2ª rodada):** teste novo `apps/site/e2e/dieta.spec.ts:99-120` mata M4 e M8.
2. ~~**Menor (doc) — inventário "antes" só em totais.**~~ **Fechado (2ª rodada):** seção "Do que era feito (antes, `develop` em 7256b65)" em `apps/site/docs/bundle.md`, conferida contra o build da base.
3. **Informativo — o alvo de 10 KiB não é gate.** O BUD-01 afirma ≤ 150 KiB (como a spec manda) e só anota a folga; M5 mostra que perder um corte (≈ 1,9 KB) leva a 145 163 B sem nenhum teste falhar. É o desenho pedido pelo dono; registrar no PR que o 143 360 B é medida desta entrega, não trava.

Observações sem ação: ordem do DOM do `<footer>` agora depois do `<div>`/`<script>` final do kit (0 px de diferença); `PRIMEIROS` só é discriminado pelo vitest (SIN-01), não pelo e2e de ordem.

---

## Requirement Traceability Update

| Requirement | Previous | New |
|---|---|---|
| DIE-01 | Verifying | ✅ Verified (medido 143 261 B) |
| DIE-02 | Verifying | ✅ Verified |
| DIE-03 | Verifying | ✅ Verified |
| DIE-04 | Verifying | ✅ Verified |
| DIE-05 | Verifying | ✅ Verified |
| DIE-06 | Verifying | ✅ Verified (prints + diff de pixels independente + `dieta.spec.ts:99-120`) |
| DIE-07 | Verifying | ✅ Verified |
| DIE-08 | Verifying | ✅ Verified |
| DIE-09 | Verifying | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (merge bloqueado só pela execução real do dono: PageSpeed ≥ 90 e navegação no celular depois do deploy)

**Spec-anchored check**: 9/9 DIE e 5/5 critérios automáticos do dono com evidência; 0 spec-precision gaps
**Sensor**: 10 mutantes — 9 mortos, 1 equivalente por desenho (M5), 0 sobreviventes
**Gate**: 292 e2e passed, 166 vitest passed; lint, check, build ok
