# BSV-30 Validation

**Verdict**: PASS
**Result**: PASS

**Date**: 2026-10-08 (3ª rodada, depois do ciclo de correção 2 de 3)
**Spec**: `.specs/features/BSV-30/spec.md` (+ `docs/specs/BSV-30.md`, critério de aceite do dono)
**Diff range**: `e140b49..d7d4c5b` (commits `260dfa5`..`d7d4c5b`, 11 commits; correções em `e7e67a9..74ad967` e `74ad967..d7d4c5b`)
**Verifier**: Verifier independente, sub-agente; autor ≠ verificador. Só leu, rodou e escreveu este arquivo.

Todos os ACs da spec estão cobertos com `file:line` e asserção que bate com a saída definida. Os gates do
site estão verdes. O sensor matou todos os mutantes: 4/4 nesta rodada, 34/34 distintos no acumulado.
A execução real do dono (deploy, Lighthouse, `curl -I`) continua bloqueando o merge (ver Observações).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Tailwind, tokens, Lato | ✅ Done | `260dfa5` |
| T2 formato + config | ✅ Done | `dbb363b` |
| T3 favoritos | ✅ Done | `1933f12` |
| T4 Card | ✅ Done | `027ae9c`, `e7e67a9` |
| T5 Home | ✅ Done | `d6910c5` |
| T6 Lista de desejos | ✅ Done | `eca13b5` |
| T7 404 + besave.css | ✅ Done | `0b6b3a0` |
| T8 Worker sem CSS | ✅ Done | `8874bc9` |
| Fix ciclo 1 | ✅ Done | `74ad967` (selo, placeholder, "Carregando…", HOM-06) |
| Fix ciclo 2 | ✅ Done | `d7d4c5b` (rodapé, ordem de "Mais recentes") |

---

## Spec-Anchored Acceptance Criteria

Caminhos relativos a `apps/site/` quando não indicado. Linhas conferidas em `d7d4c5b`.

### Tokens

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| TOK-01 | 11 cores + raio 10px | `src/lib/estilo/besave-css.test.ts:28-43` - `toMatch(new RegExp(`--cor-${nome}:\\s*${valor}(fff)?[;}]`))`; `toMatch(/--raio:\s*10px/)` | ✅ |
| TOK-02 | Lato 700/900 de `/assets/fontes/`, `swap`; corpo em fonte do sistema | `src/lib/estilo/besave-css.test.ts:47-55`; `e2e/saida.spec.ts:64-66` corpo `toMatch(/^system-ui/)`; `:69` woff2 900 baixado | ✅ |
| TOK-03 | logo "Besave", Lato 900, cor marca | `e2e/saida.spec.ts:58-61` - `toHaveCSS('font-weight','900')`, `toHaveCSS('color','rgb(11, 110, 79)')` | ✅ |

### Utilitários e configuração

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| TEM-01 | "há N h" (floor) / "há N min", nunca < 1 | `src/lib/formato.test.ts:11-13`, `:17-19` | ✅ |
| TEM-02 | "há N d" | `src/lib/formato.test.ts:24-25` | ✅ |
| TEM-03 | `2026-10-01T02:00:00Z` → "em 30/09" (Brasília) | `src/lib/formato.test.ts:30` - `toBe('em 30/09')` | ✅ |
| TEM-04 | sem `dp` usa `dt` | `src/lib/formato.test.ts:37`; `src/lib/componentes/Card.test.ts:69` (com `dp`, ignora `dt`) | ✅ |
| CFG-01 | sem link → não listado | `src/lib/config.test.ts:30-37,41`; render: `e2e/home.spec.ts:170` - `rodape.getByText(r, { exact: true })` `toHaveCount(0)`, `:172` sem "Aplicativos" | ✅ |
| CFG-02 | flag `false` → sem botão | `src/lib/config.test.ts:46-47` | ✅ |
| CFG-03 | padrões (`null`, `false`, `https://t.me/besaveofertas`) | `src/lib/config.test.ts:10-25` | ✅ |

### Favoritos

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| FAV-01 | id na memória e em `besave:favoritos` | `src/lib/favoritos.test.ts:21,30-32` | ✅ |
| FAV-02 | remove e atualiza storage | `src/lib/favoritos.test.ts:41-43` | ✅ |
| FAV-03 | nova instância restaura | `src/lib/favoritos.test.ts:55-56` | ✅ |
| FAV-04 | remover inexistente não muda | `src/lib/favoritos.test.ts:73-74` | ✅ |
| FAV-05 | lixo → vazio; só inteiros ≥ 1 | `src/lib/favoritos.test.ts:82,89` - `toEqual([])`, `toEqual([3, 8])` | ✅ |
| FAV-06 | 2× → 1 | `src/lib/favoritos.test.ts:99-100` | ✅ |

### Card

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| CAR-01 | selo `-33%`, "de" riscado | `src/lib/componentes/Card.test.ts:27-28` - `toMatch(/<span data-selo[^>]*>-33%<\/span>/)`, `<s>R$ 299,90</s>` | ✅ |
| CAR-02 | sem `pd`: nem selo nem "de" | `src/lib/componentes/Card.test.ts:35-38` - `not.toContain('data-selo')`, `not.toMatch(/-[^\s<>"]*%/)`, sem `<s>` | ✅ |
| CAR-03 | `/oferta/{id}/`, sem `/ir/`, sem cupom | `src/lib/componentes/Card.test.ts:46-48` | ✅ |
| CAR-04 | `-small.webp`, lazy, w/h fixos; erro → placeholder da área | `src/lib/componentes/Card.test.ts:55-61`; `e2e/home.spec.ts:192` - `toHaveAttribute('src', `/img/placeholder/${slug[area]}.webp`)` com `/img/**` em 404 | ✅ |
| CAR-05 | preço "por", loja, `haQuanto(dp)` | `src/lib/componentes/Card.test.ts:67-70` | ✅ |
| CAR-06 | expirada em cinza | `src/lib/componentes/Card.test.ts:79-80` | ✅ |

### Home (Playwright, 390 px e 1280 px)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| HOM-01 | ordem das seções; faixa com 8; "Mais recentes" em ordem de `lista()` (dp desc) | `e2e/home.spec.ts:17-30` - y crescente, `toHaveCount(8)`; `:94` - `primeiros.slice(0, 3)` `toEqual(['1009','1008','1007'])` | ✅ |
| HOM-02 | topo fixo | `e2e/home.spec.ts:38` | ✅ |
| HOM-03 | barra fechada persiste | `e2e/home.spec.ts:47,50` | ✅ |
| HOM-04 | área filtra; Outros só no "Mais" | `e2e/home.spec.ts:56,62,69` | ✅ |
| HOM-05 | "protetor" | `e2e/home.spec.ts:83` | ✅ |
| HOM-06 | 40 + 40, sem expiradas | `e2e/home.spec.ts:91,96,99` (40 → 80); `:100-102` sem a 147 (expirada), com 146 e 148 | ✅ |
| HOM-07 | ♡ atualiza contador | `e2e/home.spec.ts:112-117` | ✅ |
| HOM-08 | clique → `/oferta/{id}/` | `e2e/home.spec.ts:126` | ✅ |
| HOM-09 | 2 col. a 390, 5 a 1280 | `e2e/home.spec.ts:134` | ✅ |
| HOM-10 | só manifest/chunks; sem `/ir/`; fetch só na camada de dados | `e2e/home.spec.ts:156-157`; único `fetch(` em `src/lib/dados/navegador.ts:6` | ✅ |
| HOM-11 | aviso de afiliado, canal, redes/apps só com link | `e2e/home.spec.ts:163-172` | ✅ |

### Lista de desejos

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| DES-01 | card por favorito | `e2e/desejos.spec.ts:26-27,37-38` | ✅ |
| DES-02 | fora do catálogo completo → "saiu do ar" + Remover; antes disso "Carregando…" | `e2e/desejos.spec.ts:45-50`; `:64-68` | ✅ |
| DES-03 | vazio → aviso + link `/` | `e2e/desejos.spec.ts` (`lista vazia mostra aviso…`) | ✅ |

### 404, CSS e worker

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| ERR-01 | 404 com `noindex`, texto, `/`, canal | `e2e/saida.spec.ts:12-22` | ✅ |
| ERR-02 | sem fallback | `e2e/saida.spec.ts:33` | ✅ |
| CSS-01 | `build/assets/besave.css` com tokens + `@font-face` | `e2e/saida.spec.ts:38-41`; `src/lib/estilo/besave-css.test.ts:28-55` | ✅ |
| CSS-02 | regra para toda classe dos templates | `src/lib/estilo/besave-css.test.ts:65-67`; `apps/worker/tests/template_oferta.rs:523-524` | ✅ |
| CSS-03 | brotli ≤ 20 KB | `src/lib/estilo/besave-css.test.ts:73` (1 616 B) | ✅ |
| WRK-01 | sem `assets/besave.css` | `apps/worker/tests/ciclo.rs:320`; `apps/worker/tests/dry_run.rs:276-277`; `apps/worker/tests/geracao.rs:679` | ✅ |
| WRK-02 | índice sem `_css`; antigo ignorado | `apps/worker/tests/ciclo.rs:327,559-578` | ✅ |
| WRK-03 | fmt/clippy/test | gates da 1ª rodada (worker fora do diff das correções) | ✅ |

### Critério de aceite do dono (`docs/specs/BSV-30.md`)

| Item | Result |
| ---- | ------ |
| Vitest: favoritos, config, "há X h" em Brasília, card sem `pd` | ✅ |
| Playwright 390/1280: topo fixo, barra, área, busca, ♡ + `/desejos/`, "Ver mais" +40, card → `/oferta/{id}/`, 2/5 colunas | ✅ |
| `/404.html` com `noindex`; build sem fallback | ✅ |
| Worker `cargo test` verde sem a fase de CSS | ✅ |
| Gates pnpm e cargo | ✅ |
| Real (dono): deploy, Lighthouse ≥ 90, oferta com visual novo, `curl -I …/assets/besave.css` | ⏳ dono, bloqueia o merge |

**Status**: ✅ 44/44 ACs cobertos com asserção que bate com a spec.

---

## Regras do CLAUDE.md

| Regra | Evidência | Result |
| ----- | --------- | ------ |
| Sem `/ir/` na home | `e2e/home.spec.ts:157`; `build/index.html` sem `/ir/` | ✅ |
| Fetch só pela camada de dados | `src/lib/dados/navegador.ts:6` | ✅ |
| Prerender sem fallback | `src/routes/+layout.ts:1`; `e2e/saida.spec.ts:33` | ✅ |
| Dependências novas | `tailwindcss`/`@tailwindcss/vite` 4.3.3, `@playwright/test` 1.63.0 (justificar no PR, regra 7) | ✅ |
| Lato OFL | `static/assets/fontes/OFL.txt` + 2 woff2 | ✅ |
| Classes do template não renomeadas | seletores do CSS antigo (`git show e140b49:apps/worker/assets/css/besave.css`) ⊂ novos; só entram `.aviso`, `.canal` | ✅ |
| Testes do worker que liam o CSS do worker | agora leem `apps/site/src/lib/estilo/besave.css` (`apps/worker/tests/template_oferta.rs:503-505`); a garantia de classes continua (W3 morto) | ✅ |

---

## Discrimination Sensor

Worktree temporário em `HEAD` (`git worktree add --detach <scratch>/verif`), deps instaladas lá; cada
mutante revertido com `git checkout -- <arquivo>`; worktree removido no fim. `git status --porcelain` do
worktree real antes e depois: `?? .specs/features/BSV-30/evidencias/` e `?? .specs/features/BSV-30/validation.md`.

### 3ª rodada (sobre `d7d4c5b`)

| # | Arquivo | Mutação | Teste que matou | Result |
| - | ------- | ------- | --------------- | ------ |
| M21 | `src/lib/componentes/Rodape.svelte:13` | todas as redes, sem `comLink` (`<a>` sem `href`, texto visível) | `e2e/home.spec.ts:161` (2 projetos) | ✅ Killed |
| N4 | `src/routes/+page.svelte:35` | `slice(0, limite)` → `slice(1, limite + 1)` | `e2e/home.spec.ts:90` (2 projetos) | ✅ Killed |
| N6 | `src/routes/+page.svelte:34` | `lista(f).reverse()` (mais antigas primeiro) | `e2e/home.spec.ts:90` | ✅ Killed |
| N7 | `src/lib/componentes/Rodape.svelte:14` | todos os apps, sem `comLink` | `e2e/home.spec.ts:161` | ✅ Killed |

**Sensor depth**: expandido. **Rodada**: 4/4 mortos. **Acumulado**: 34/34 mutantes distintos mortos
(site e worker), contando os sobreviventes de rodadas anteriores que passaram a ser mortos.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ |
| No scope creep | ✅ |
| Matches patterns (runes, Tailwind, nomes em português) | ✅ |
| Spec-anchored outcome check | ✅ |
| Per-layer coverage | ⚠️ edge cases sem e2e: manifest falhou, faixa vazia, busca < 2 caracteres (implementados; ver Edge Cases) |
| Every test maps to a requirement | ✅ |
| Guidelines: `CLAUDE.md`, `apps/site/CLAUDE.md`, `apps/worker/CLAUDE.md` | ✅ |

---

## Edge Cases

- [x] localStorage que lança → memória: `src/lib/favoritos.test.ts:113-129`.
- [x] Catálogo incompleto → "Carregando…": `e2e/desejos.spec.ts:54-68`.
- [x] Busca < 2 caracteres → lista normal: `src/routes/+page.svelte:21`. Sem teste (não bloqueante).
- [x] Faixa vazia → "Sem descontos novos nas últimas 24 h": `src/lib/componentes/FaixaDescontos.svelte:24`. Sem teste (não bloqueante).
- [x] Manifest falhou → aviso: `src/routes/+page.svelte:73-76`. Sem teste (não bloqueante).

---

## Gate Check (3ª rodada, worktree real em `d7d4c5b`)

| Gate | Resultado |
| ---- | --------- |
| `pnpm install --frozen-lockfile` | exit 0 |
| `pnpm lint` | exit 0 |
| `pnpm check` | 0 erros, 0 avisos (437 arquivos) |
| `pnpm test` | **105/105** |
| `pnpm build` | exit 0 |
| `pnpm e2e` | **42/42** (21 testes × celular 390 px e desktop 1280 px) |
| worker (`cargo fmt --check`, `clippy -D warnings`, `cargo test`) | 1ª rodada em `e7e67a9`: ok, ok, 435 passed / 0 failed / 3 ignored. Não rodei de novo: `e7e67a9..d7d4c5b` não toca `apps/worker` nem `src/lib/estilo/besave.css` |

Contagem: Vitest 70 (base) → 105; Playwright 0 → 21 (×2). Nenhum teste apagado ou enfraquecido nas
correções; em `d7d4c5b` a asserção do rodapé ficou mais estrita (`getByText` exato no lugar do regex
`\W`) e "Ver mais" ganhou a asserção de ordem.

---

## Lacunas remanescentes (não bloqueantes)

1. Edge cases sem teste automatizado: manifest ilegível, faixa vazia, busca < 2 caracteres. O código foi
   lido e está correto; sugiro e2e em ticket futuro (BSV-30-TEST ou BSV-31).
2. Bundle, contraste AA e ausência de layout shift dependem do Lighthouse do dono. Bundle medido
   localmente: 133 893 B brutos / 51 226 B gzip (≤ 150 KB).
3. Playwright fora do CI (`ci.yml` fora da pasta do ticket), como a spec registrou.
4. `apps/worker/src/publicador.rs:72,116` mantém `META_CSS`, sem uso pelo worker; limpeza futura.

---

## Observações

1. **Desempenho (BSV-35)**: na 1ª rodada, `desempenho.test.ts` falhou uma vez com o `cargo test`
   competindo pela CPU. Sem carga, passou 4 de 4 vezes na suíte completa e também isolado. Não rodei o
   commit base. Não conto como regressão da BSV-30.
2. **Bloqueia o merge, só a execução real do dono comprova**: deploy com `SITE_DEPLOY_ATIVO`; home com
   ofertas reais; Lighthouse mobile ≥ 90 nas quatro categorias (print); página de oferta com o visual
   novo; `curl -I https://besave.com.br/assets/besave.css` → 200 `text/css`.
3. Evidências em `evidencias/` são PNG; este relatório não cita caminhos absolutos (`<scratch>`).

---

## Histórico das rodadas

### 2ª rodada (sobre `74ad967`): veredito negativo
Gates: Vitest 105/105, Playwright 42/42. Sensor: 9/11. Sobreviveram:
- **M21**: o regex `(^|\W)X(\W|$)` não discriminava, porque o `textContent` do rodapé junta os itens
  sem espaço.
- **N4**: a grade podia pular a oferta mais recente.

Ambos corrigidos em `d7d4c5b` e mortos na 3ª rodada. Mortos na 2ª: M3, M3b, N1, M20, N5, N2, M22, N3, P5.

### 1ª rodada (sobre `e7e67a9`): veredito negativo
Gates: Vitest 105/105 (uma execução com 3 falhas de desempenho sob carga), Playwright 38/38, worker
435/0/3. Sensor: 21/26.

Sobreviveram:
- **M3**: selo "-null%" sem `pd`.
- **M7/M20**: `onerror` não trocava a imagem pelo placeholder.
- **M21**: rodapé listava redes sem link.
- **M22**: "saiu do ar" aparecia antes do catálogo completo.
- **Asserção vazia** em HOM-06: o id 77 nunca cairia nos 80 primeiros.

Corrigidos em `74ad967` (exceto M21, que só foi corrigido em `d7d4c5b`).

Mortos:
- **Site:**
  - M1: `haQuanto` em UTC
  - M2: `haQuanto` usando `dt`
  - M4: Card com `/ir/`
  - M4b: "de" com `pd !== undefined`
  - M5: favoritos sem dedup
  - M6: `lerIds` aceitando string
  - M8: expirada sem `grayscale`
  - M9: flags ignoradas
  - M10: `.cupom` removida
  - M11: `<=` no limite de 24 h
  - M12: cupom no card
  - M13: topo sem `sticky`
  - M14: `POR_VEZ = 30`
  - M15: área não filtra
  - M16: "Outros" na barra
  - M17: grade com 4 colunas em `lg`
  - M18: barra não persiste
  - M19: 404 sem `noindex`
  - M23: contador só com mais de 1
- **Worker:**
  - W1: worker volta a gravar `assets/besave.css`
  - W2: `_css` volta ao índice
  - W3: `.cupom` removida, visto pelo worker

---

## Summary

**Overall**: ✅ Ready para revisão do PR; o merge continua bloqueado pela execução real do dono.
**Spec-anchored check**: 44/44 ACs batem com a saída da spec.
**Sensor**: 3ª rodada 4/4; acumulado 34/34 mutantes distintos mortos.
**Gate**: Vitest 105/105, Playwright 42/42, lint/check/build ok; worker 435/0/3 (sem mudança desde a 1ª rodada).
