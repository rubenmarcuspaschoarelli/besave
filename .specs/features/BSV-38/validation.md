# Validation — BSV-38

> As seções 1 a 4 registram a rodada 1, sobre `2acdad0..2e33dad`; a rodada 2 está na §7; a rodada 3 (delta da revisão do dono, `4124c50..93e88c4`) está na §8. A rodada 3b (`4124c50..HEAD`, com `0b35f36`), que dá o veredito atual, está na §9.

## Validation: BSV-38 - PASS

**Result**: PASS (rodada 3b). A rodada 3 reprovou com os sobreviventes R6 e R8. O commit `0b35f36`, só de teste, fechou as duas lacunas, e os dois mutantes morreram (§9).

A rodada 1 foi reprovada por 4 mutantes sobreviventes nos testes. O commit `e63af5b` (só testes) fechou as lacunas, e os 4 morreram junto com 4 mutantes novos (ver §7).

- **Quem verificou:** Verifier, sub-agente independente (autor ≠ verificador), modelo Claude Opus 5.5 (`claude-opus-5-5`), em 09/10/2026.
- **Diff:** `2acdad0..HEAD` (`0688297`, `f2b3b7b`, `2e33dad`; rodada 2: `e63af5b`), branch `rubenmarcus/rub-30-bsv-38-copiar-o-cupom-e-ir-para-a-loja`.
- **Fontes:** `docs/specs/BSV-38.md` (spec do dono) e `.specs/features/BSV-38/spec.md` (CUP-01..11, DEP-01..02).

## 1. Checagem ancorada na spec

| Req. | Resultado definido pela spec | Evidência `file:line` (asserção) | Resultado |
|---|---|---|---|
| CUP-01 | `<button>` com `aria-label="Copiar cupom"`, SVG e `hidden`, ao lado do código | `apps/worker/tests/template_oferta.rs:590` (`assert_eq!(botao, "<button class=\"copiar\" type=\"button\" aria-label=\"Copiar cupom\" hidden>")`), `:595-597` (svg, aria-hidden, um botão só) | PASS |
| CUP-02 | CTA `href="/ir/{id}" target="_blank" rel="nofollow sponsored noopener"`, texto "Copiar cupom e ir para a loja" | `apps/worker/tests/template_oferta.rs:605` (tag + texto inteiros), `:609` | PASS |
| CUP-03 | `role="status"` vazio; um `<script>` sem `type` (fora o JSON-LD), sem o código nem dado da oferta | `apps/worker/tests/template_oferta.rs:616-626` (`<p class="confirmacao" role="status"></p>`, 2 `<script`, sem `BESAVE10`/`5412`/`/ir/`/`http`/título), `:634-635` (cupom com `<&"'` sai escapado e o script é idêntico) | PASS |
| CUP-04 | Sem cupom: "Acesse a oferta", `target="_blank"`, `noopener`, sem ícone, status ou script | `apps/worker/tests/template_oferta.rs:643` (CTA inteiro), `:655` (ausências) | PASS |
| CUP-05 | Encerrada, com ou sem cupom: `aria-disabled="true"` sem `href`, sem cópia | `apps/worker/tests/template_oferta.rs:671` (CTA inteiro), `:685` (sem botão, status, script, `/ir/` nem `target=`), `:689`; o golden da encerrada não mudou no diff (PAG-02 byte a byte) | PASS |
| CUP-06 | ≤ 30 KB; mesmo input → mesmos bytes; nenhum `http` fora de besave.com.br e schema.org | `apps/worker/tests/template_oferta.rs:697-701` | PASS (⚠ o teste também aceita `http://www.w3.org/2000/svg`, que a spec não lista; o template não usa essa URL, então hoje não faz diferença) |
| CUP-07 | O script mostra o ícone; o clique copia o código do DOM; aviso "Cupom copiado!" que some em ~2 s | `apps/site/e2e/cupom.spec.ts:35` (visível), `:42` (clipboard = `BESAVE10`), `:44` (texto), `:45` (vazio em até 3,5 s) | ⚠ Lacuna de precisão: falta limite inferior para "~2 s" (mutante M7b sobreviveu) |
| CUP-08 | Clipboard ausente ou negado → o código fica selecionado | `apps/site/e2e/cupom.spec.ts:81` e `:92` (seleção = `BESAVE10`) | PASS. ⚠ `:82` e `:93` (`toHaveText('')`) fazem retry até 5 s e passam mesmo se a página mostrar "Cupom copiado!" falso (M27 sobreviveu) |
| CUP-09 | O CTA copia e abre a aba nova em `/ir/{id}`; com o clipboard negado, a aba abre igual | `apps/site/e2e/cupom.spec.ts:57-60` (aba nova em `/ir/5412`, a original continua, clipboard = código, aviso), `:77` (negado → aba abre) | PASS |
| CUP-10 | Sem JS: ícone oculto e CTA como link para `/ir/{id}` | `apps/site/e2e/cupom.spec.ts:105-112` (botão presente e oculto, `href`, `target`, aba abre) | PASS |
| CUP-11 | Regras para `.copiar`, `.copiado` e `.confirmacao`; toque ≥ 44 px; `.copiar[hidden]` oculto | `apps/site/src/lib/estilo/besave-css.test.ts:74` (classes), `:82-84` (44 px, `display:none`); `apps/site/e2e/cupom.spec.ts:37-38` (caixa real ≥ 44 px) | PASS (o teste unitário exige exatamente `44px`; 48 px falharia. É mais estrito que a spec, aceito) |
| DEP-01 | Comando inteiro do `besave.css` com `public, max-age=300`; fontes e favicon com `max-age=3600, swr=86400` | `infra/functions/test/deploy-site.test.mjs:158-168` (`deepEqual` do comando inteiro), `:170-184` (fonte e favicon, também com o comando inteiro) | PASS |
| DEP-02 | MANIFEST §4 com `assets/besave.css` → `public, max-age=300` | `docs/MANIFEST.md:108-109` (documento, sem teste) | PASS |
| Aceite do dono: "nenhum `http` de afiliado" | — | `apps/worker/tests/template_oferta.rs:701` | PASS |
| Edge: cupom com `<`, `&` e aspas sai escapado e o script não muda | — | `apps/worker/tests/template_oferta.rs:634-635` | PASS |
| Edge: clique repetido em até 2 s reinicia o temporizador | — | nenhum teste | ❌ GAP (M14 sobreviveu) |

### Ajustes em testes antigos (houve enfraquecimento?)
- **PAG-05** (`template_oferta.rs:247`): a tag inteira do CTA continua comparada, agora com `target`/`noopener`. Não enfraqueceu.
- **PAG-08** (`template_oferta.rs:299-328`): passou a usar a oferta **sem cupom**. Nesse caso continuam as checagens "único `<script>` é o JSON-LD" e "único handler inline é o `onerror`". No caso com cupom, a contagem de handlers inline deixou de existir. Isso é compensado pela comparação exata da tag `<button>` (CUP-01, `:590`), da tag `<a class="cta">` (CUP-02, `:605`) e pelo `!html.contains("javascript:")` só no caso sem cupom. Enfraquecimento pequeno; aceitável.
- **PAG-14** (`template_oferta.rs:487-491`): passou de "1 script" para "2 scripts, os mesmos da página base", e `scripts_js(html) == scripts_js(base)` garante que o título não injeta JS. Ficou equivalente ou mais forte.
- **PUB-06** e **fontes/favicon** (`deploy-site.test.mjs:158-184`): passaram de checagem flag por flag para o comando inteiro (lição 14). Ficaram mais fortes.

## 2. Gates (todos os do CI que o ticket toca, lição 21)

| Gate | Resultado |
|---|---|
| `apps/worker`: `cargo fmt --check` | OK |
| `apps/worker`: `cargo clippy --all-targets -- -D warnings` | OK, 0 avisos |
| `apps/worker`: `cargo test` | 454 passaram, 0 falharam, 3 ignorados (já existiam, fora do diff); `template_oferta`: 26/26 |
| `apps/site`: `pnpm install --frozen-lockfile` | OK |
| `apps/site`: `pnpm lint` (prettier + eslint) | OK |
| `apps/site`: `pnpm check` | 0 erros, 0 avisos (468 arquivos) |
| `apps/site`: `pnpm test` (vitest) | 16 arquivos, 147/147. DES-01/02 passaram nessa rodada |
| `apps/site`: `pnpm build` | OK |
| `apps/site`: `pnpm e2e` (Playwright) | 198/198; `e2e/cupom.spec.ts`: 10/10 (celular e desktop) |
| `infra/functions`: `npm test` | 67/67 |
| `npx html-validate tests/fixtures/paginas/*.html` (worker) | 0 erros |

## 3. Sensor de discriminação

Rodou num `git worktree` temporário em diretório temporário fora do repositório, com `CARGO_TARGET_DIR` próprio e `CARGO_BUILD_JOBS=2`, em lotes de 5 a 13 mutantes. Só os testes relevantes rodaram: `cargo test --test template_oferta`, `node --test test/deploy-site.test.mjs`, vitest `besave-css.test.ts` e `playwright test e2e/cupom.spec.ts`. Os mutantes de script foram aplicados no golden, que é o que o e2e lê. O controle (M0, sem mutação) passou no e2e. O primeiro M0/M3 falhou com a porta 4173 ocupada; os dois foram descartados e rodados de novo. Depois do sensor, o worktree temporário foi removido e o `git status --porcelain` do worktree real ficou igual ao de antes (vazio).

| # | Mutante | Alvo | Resultado |
|---|---|---|---|
| M1 | CTA com cupom sem `target="_blank"` | template | morto |
| M2 | `rel` sem `noopener` | template | morto |
| M8 | Script lê o cupom de string do template (`"{{ o.cupom }}"`) | template | morto |
| M9 | Botão de copiar também na encerrada (`copia` sem `not encerrada`) | template | morto |
| M19 | Sem cupom, CTA sem `target`/`noopener` | template | morto |
| M20 | Sem `role="status"` | template | morto |
| M21 | Botão sem `hidden` no HTML | template | morto |
| M22 | Texto do CTA volta a "Acesse a oferta" com cupom | template | morto |
| M3 | Script não remove o `hidden` | golden/e2e | morto (6 falhas) |
| M4 | `preventDefault` no CTA | golden/e2e | morto (4) |
| M5 | Ícone não seleciona o código na falha | golden/e2e | morto (4) |
| M6 | Aviso não some | golden/e2e | morto (2) |
| M7 | Aviso some em 50 ms | golden/e2e | morto (2) |
| **M7b** | **Aviso some em 500 ms** | golden/e2e | **sobreviveu** |
| **M14** | **Sem `clearTimeout` (clique repetido não reinicia)** | golden/e2e | **sobreviveu** |
| M15 | CTA não copia | golden/e2e | morto (2) |
| M16 | Texto "Copiado!" no lugar de "Cupom copiado!" | golden/e2e | morto (4) |
| **M18** | **Classe `copiado` nunca é posta** | golden/e2e | **sobreviveu** |
| M26 | CTA espera o clipboard e abre com `window.open` (bloqueia a navegação) | golden/e2e | morto (2) |
| **M27** | **"Cupom copiado!" aparece também quando a cópia falha** | golden/e2e | **sobreviveu** |
| M12 | `.copiar[hidden]{display:none}` removido | CSS | morto (unit + e2e) |
| M13 | `min-width`/`min-height` 40 px | CSS | morto (unit + e2e) |
| M28 | `min-*` 30 px + `padding` 8 px | CSS | morto (unit + e2e) |
| M10 | `besave.css` volta a ASSET | publicar.mjs | morto |
| M11 | Fontes passam a CURTO | publicar.mjs | morto |
| M23 | Constante do CSS aponta para outro arquivo | publicar.mjs | morto |
| M24 | CURTO ganha `stale-while-revalidate` | publicar.mjs | morto |
| M25 | Favicon passa a CURTO | publicar.mjs | morto |

**Total: 28 mutantes, 24 mortos, 4 sobreviveram, 0 equivalentes.**

## 4. Lacunas ranqueadas (tarefas de correção, só em teste)

1. **M27: aviso falso de cópia não é detectado** (CUP-08). `apps/site/e2e/cupom.spec.ts:82` e `:93` usam `toHaveText('')`, que faz retry e passa quando o aviso some sozinho em 2 s. Correção: assertar logo depois da seleção, sem retry. Por exemplo, `expect(await page.getByRole('status').textContent()).toBe('')`, ou `not.toHaveText('Cupom copiado!', { timeout: 0 })` antes de 2 s, ou checar ao longo de ~500 ms que o aviso nunca mostrou o texto.
2. **M7b: "~2 s" sem limite inferior** (CUP-07). `cupom.spec.ts:44-45` só limita por cima (≤ 3,5 s). Correção: depois de ~1,5 s o aviso ainda diz "Cupom copiado!", e some até ~3,5 s. Usar o relógio do Playwright (`page.clock`) para não depender de tempo real (lição 15).
3. **M14: edge case "clique repetido reinicia o temporizador"** (spec.md, Edge Cases) sem teste. Correção: clicar, esperar ~1,5 s, clicar de novo e confirmar que em t ≈ 2,5 s o aviso continua visível (com `page.clock`).
4. **M18: estado `.copiado` sem teste de comportamento.** A spec.md e o README do template definem `copiado` como "estado por ~2 s depois da cópia", mas só a existência da regra no CSS é testada. Correção: no teste do ícone, `toHaveClass(/copiado/)` depois do clique e ausência da classe quando o aviso some. Prioridade baixa: o critério de aceite do dono não fixa esse estado.
5. (Informativa) CUP-06 aceita `http://www.w3.org/2000/svg` (`template_oferta.rs:704`), e a spec não lista essa URL. Hoje não tem efeito. Remover a exceção ou registrá-la na spec.md.

O código de produção atende a todos os requisitos. As lacunas são de discriminação dos testes, então o FAIL se resolve só com mudança em `apps/site/e2e/cupom.spec.ts`, numa nova rodada do Verifier (máx. 3 ciclos).

## 5. Bloqueia o merge (execução real do dono, fora do Verifier)
- Deploy do site e `curl -I .../assets/besave.css` → `max-age=300`, **antes** do ciclo novo (regra 4 da spec).
- Primeiro `besave-ciclo` do binário novo: `paginas_publicadas` ≈ total e `tempo_ms` registrados no PR.
- Android e iPhone: o ícone copia; o botão abre a loja em aba nova; o cupom cola no campo da loja.

## 6. Lições propostas (para o dono consolidar em docs/WORKFLOW-AGENTES.md; não gravadas em LESSONS)
1. **Asserção de ausência com retry (`toHaveText('')`, `toBeHidden`) não prova que o estado nunca ocorreu** quando ele some sozinho por timer. Para "não mostra X na falha", asserte sem retry logo após a ação ou observe uma janela. (M27)
2. **Duração aproximada ("~2 s") pede limite inferior e superior**, de preferência com `page.clock`, para não virar teste de tempo frágil (lição 15). (M7b)
3. **Edge case listado na spec.md precisa de teste com o ID dele.** O Verifier procura pelo ID e, sem evidência, conta como não coberto. (M14)
4. **Porta fixa do `webServer` do Playwright é compartilhada entre worktrees:** com `CI=1`, a segunda sessão falha com "already used"; sem `CI`, reusa o servidor (e o build) de **outra** worktree. Rodar o mutante de controle antes do lote e checar a porta.

## 7. Rodada 2 (commit `e63af5b`, só testes)

**Veredito: PASS.** Rodada 2 de 3. O verificador é o mesmo sub-agente; o autor continua sendo outro.

### Mudanças conferidas
- `apps/site/e2e/cupom.spec.ts:29-31`: relógio controlado (`page.clock.install` + `pauseAt`) no `beforeEach` com JS.
- CUP-07 (`cupom.spec.ts:47-53`): `.copiado` posto no clique, aviso ainda visível aos 1,9 s (`:50`), vazio aos 2,1 s (`:52`) e `.copiado` retirado (`:53`). O "~2 s" agora tem limite inferior e superior.
- Edge case do clique repetido (`cupom.spec.ts:58-70`): clique, 1,5 s, novo clique, aviso visível 1,0 s depois (`:68`) e vazio 1,1 s depois disso (`:70`).
- CUP-08 com falha (`cupom.spec.ts:106-107`, `:119-120`): com o relógio parado, um aviso indevido não some sozinho, então `toHaveText('')` e `not.toContainClass('copiado')` passam a discriminar.
- CUP-06 (`apps/worker/tests/template_oferta.rs:702`): saiu a exceção `http://www.w3.org/2000/svg`. Só `besave.com.br` e `schema.org` são aceitos, como diz a spec.
- `toContainClass` em vez de `toHaveClass(regex)` está correto: as duas formas casam a classe sem depender da string inteira do atributo, e os mutantes M18/M31 confirmam que a asserção pega o erro.

### Gates reexecutados
| Gate | Resultado |
|---|---|
| `cargo fmt --check` / `cargo clippy --all-targets -- -D warnings` | OK / 0 avisos |
| `cargo test --test template_oferta` | 26/26 |
| `pnpm lint` / `pnpm check` | OK / 0 erros, 0 avisos |
| `pnpm build` + `playwright test e2e/cupom.spec.ts` | OK, 12/12 (celular e desktop; antes eram 10, o teste do clique repetido é novo) |
| `infra/functions npm test` | não mudou desde a rodada 1 (67/67) |

### Sensor (worktree temporário isolado, removido no fim; `git status --porcelain` do worktree real igual ao de antes)
Controle M0 sem mutação: passou.

| # | Mutante | Resultado |
|---|---|---|
| M27 | "Cupom copiado!" também quando o clipboard recusa | morto (2) |
| M7b | Aviso some em 500 ms | morto (3) |
| M14 | Sem `clearTimeout` (clique repetido não reinicia) | morto (2) |
| M18 | Classe `copiado` nunca é posta | morto (3) |
| M29 (novo) | Aviso some em 2500 ms | morto (4) |
| M32 (novo) | Aviso some em 1800 ms | morto (2) |
| M31 (novo) | Temporizador limpa o texto mas não tira `.copiado` | morto (2) |
| M35 (novo) | Sem `navigator.clipboard`, o `catch` mostra o aviso antes de selecionar | morto (2) |

**Total das duas rodadas: 32 mutantes distintos, todos mortos; nenhum sobrevivente e nenhum equivalente.**

### Lacunas restantes
Nenhuma que bloqueie. Continua bloqueando o merge só a execução real do dono (§5).

## 8. Rodada 3 (delta da revisão do dono)

**Veredito: FAIL.** Rodada 3 de 3. Pelo `docs/WORKFLOW-AGENTES.md` §1, sobe para o dono. O verificador é um sub-agente independente (autor ≠ verificador), modelo Claude Opus 5.5 (`claude-opus-5-5`), em 09/10/2026.

- **Diff:** `4124c50..93e88c4` (um commit, `93e88c4`): template, golden `oferta-pagina-ok.html`, `template_oferta.rs`, `cupom.spec.ts`, README do template e spec.md.
- **Pedido do dono:** (1) no HTML o botão com cupom diz "Ir para a loja", e o script troca para "Copiar cupom e ir para a loja" quando `navigator.clipboard.writeText` existe; (2) aprovado: se a cópia falha no botão principal, nada é selecionado e a loja abre do mesmo jeito.

### Checagem ancorada na spec (só o delta)

| Req. | Resultado definido pela spec | Evidência `file:line` (asserção) | Resultado |
|---|---|---|---|
| CUP-02 | CTA com cupom no HTML: `<a class="cta" href="/ir/{id}" target="_blank" rel="nofollow sponsored noopener">Ir para a loja</a>` | `apps/worker/tests/template_oferta.rs:605-608` (tag + texto inteiros), `:611` (o texto "Copiar cupom e ir para a loja" aparece 1 vez só) e `:612` (no script) | PASS |
| CUP-03 (texto novo no script) | O script contém o texto da troca e nenhum dado da oferta | `apps/worker/tests/template_oferta.rs:628-635` | PASS |
| CUP-07 (com API) | Com `writeText`, o CTA passa a "Copiar cupom e ir para a loja" | `apps/site/e2e/cupom.spec.ts:79` (`toHaveText`, casamento inteiro), `:81` e `:101` (`getByRole` com `exact: true`) | PASS |
| CUP-07 (sem API) | Sem a API, continua "Ir para a loja", não tenta copiar e a loja abre | `apps/site/e2e/cupom.spec.ts:124` (`toHaveText(IR)`), `:125-127` (aba em `/ir/5412`), `:129` (aviso vazio com o relógio parado) | PASS |
| CUP-09 | Com o clipboard recusado, a aba abre do mesmo jeito | `apps/site/e2e/cupom.spec.ts:101-104` | PASS |
| CUP-10 | Sem JS: ícone oculto e link "Ir para a loja" para `/ir/{id}` | `apps/site/e2e/cupom.spec.ts:148` (ícone oculto), `:149-152` (`exact: true`, texto, `href`, `target`), `:153-155` (a aba abre) | PASS |
| Decisão (2) do dono | Se a cópia falha no botão principal, nada fica selecionado | nenhuma asserção. Em `cupom.spec.ts:91-112` a seleção só é conferida (`:108`) depois do clique no ícone, que também seleciona | ❌ GAP (R6 sobreviveu) |

Casamento por substring: as três chamadas `getByRole('link', …)` do delta usam `exact: true` (`cupom.spec.ts:81`, `:101`, `:149`). As asserções de texto usam `toHaveText` com string, que compara o texto inteiro e não é substring. `getByRole('button', { name: 'Copiar cupom' })` não casa o link, porque o papel é outro. Não há falso positivo por substring.

### Gates
| Gate | Resultado |
|---|---|
| `apps/worker`: `cargo fmt --check` | OK |
| `apps/worker`: `cargo clippy --all-targets -- -D warnings` | OK, 0 avisos |
| `apps/worker`: `cargo test --test template_oferta` | 26/26 |
| Golden × render (`cargo run --bin render-oferta -- ../../packages/contract/fixtures/oferta-pagina-ok.json`, comparado com `cmp`) | idênticos byte a byte |
| `npx html-validate tests/fixtures/paginas/*.html` | 0 erros |
| `apps/site`: `pnpm lint` / `pnpm check` | OK / 0 erros, 0 avisos (468 arquivos) |
| `apps/site`: `pnpm build` + `playwright test e2e/cupom.spec.ts` (`CI=1`; porta 4173 livre antes, servida pelo preview deste worktree) | 12/12 (celular e desktop) |

O e2e completo fica com o autor, como pedido.

### Sensor de discriminação
Rodou num `git worktree` temporário (detached em `93e88c4`) no scratchpad da sessão, com `CARGO_TARGET_DIR` próprio, `CARGO_BUILD_JOBS=2` e `CI=1`. Cada mutante foi aplicado em `templates/oferta.html`; o golden `oferta-pagina-ok.html` foi regerado com `render-oferta`, como o autor faria; depois rodaram `cargo test --test template_oferta` e `playwright test e2e/cupom.spec.ts`. O controle R0, sem mutação, passou (26/26 e 12/12). No fim, o worktree temporário e o diretório de build foram removidos e rodou `git worktree prune`. O `git status --porcelain` do worktree real ficou vazio, igual ao de antes.

| # | Mutante | Rust | e2e | Resultado |
|---|---|---|---|---|
| R1 | HTML volta a "Copiar cupom e ir para a loja" | 1 falha (CUP-02) | 4 falhas | morto |
| R2 | O script não troca o texto | 2 falhas (CUP-02, CUP-03) | 4 falhas | morto |
| R3 | O script troca o texto mesmo sem clipboard | passa | 2 falhas (`cupom.spec.ts:124`) | morto |
| R4 | O listener de cópia no CTA é registrado mesmo sem clipboard (só a troca de texto fica no `if`) | passa | passa | **equivalente**: sem `navigator.clipboard`, `copiar` lança `TypeError`, o `catch` chama a função vazia e nada muda para quem vê a página |
| R5 | CTA sem cupom passa a "Ir para a loja" | 1 falha (CUP-04) | passa | morto |
| R6 | Falha de cópia no CTA seleciona o código (`copiar(selecionar)`) | passa | passa | **sobreviveu** |
| R7 | CTA encerrado passa a "Ir para a loja" | 2 falhas (CUP-05, golden da encerrada) | passa | morto |
| R8 | A troca exige só `navigator.clipboard`, sem conferir `writeText` | passa | passa | **sobreviveu** (prioridade baixa) |

**Total: 8 mutantes, 5 mortos, 2 sobreviveram (R6, R8) e 1 equivalente (R4).**

### Lacunas ranqueadas (só em teste)
1. **R6, decisão (2) do dono.** Em `cupom.spec.ts`, no teste "com o clipboard negado" (`:91`), entre `loja.close()` (`:105`) e o clique no ícone (`:107`), falta asseverar que nada ficou selecionado: `expect(await selecao(page)).toBe('')`. A rejeição do `writeText` resolve antes de a aba nova carregar, então a asserção sem retry discrimina. O mesmo vale para o teste sem `navigator.clipboard`, depois de `:128`.
2. **R8 (baixa).** CUP-07 diz "IF `navigator.clipboard.writeText` existe". Nenhum teste cobre `navigator.clipboard` presente sem `writeText`. Correção: um caso com `Object.defineProperty(Clipboard.prototype, 'writeText', { value: undefined })` que confira que o CTA diz "Ir para a loja". Esse navegador é raro entre os alvos, então a prioridade é baixa.

O código de produção do delta atende ao pedido do dono. As lacunas são só de teste, todas em `apps/site/e2e/cupom.spec.ts`. Como esta é a 3ª rodada, a decisão de corrigir e reverificar, ou de aceitar a lacuna R6, é do dono.

### Lição proposta (para o dono; não gravada em LESSONS)
- **Decisão negativa ("não seleciona", "não mostra") precisa de asserção de ausência logo depois da ação que poderia causá-la**, antes de outra ação produzir o mesmo estado. No teste do clipboard negado, o clique seguinte no ícone mascarava a seleção indevida do CTA (R6).

## 9. Rodada 3b (lacunas da rodada 3)

**Veredito: PASS.** O verificador é o mesmo sub-agente independente da rodada 3 (autor ≠ verificador), em 09/10/2026.

- **Diff:** `4124c50..HEAD` (`93e88c4` e `0b35f36`). O `0b35f36` só muda `apps/site/e2e/cupom.spec.ts` (+17 linhas, nenhuma asserção removida ou afrouxada).

### Mudanças conferidas
| Lacuna | Asserção nova | Evidência `file:line` | Resultado |
|---|---|---|---|
| R6, decisão (2) do dono: falha no botão principal não seleciona nada | `expect(await selecao(page)).toBe('')`, sem retry, logo depois de `loja.close()` e antes do clique no ícone | `apps/site/e2e/cupom.spec.ts:107` (clipboard negado), `:132` (sem API) | PASS |
| R8, CUP-07 "IF `writeText` existe" | `Clipboard.prototype.writeText = undefined`; o ícone aparece (o script rodou) e o CTA continua "Ir para a loja" (`toHaveText`, casamento inteiro) | `apps/site/e2e/cupom.spec.ts:143-155` (`:153`, `:154`) | PASS |

O `toBeVisible` do ícone (`:153`) evita falso positivo. Sem ele, um script que quebrasse antes da troca de texto também deixaria "Ir para a loja".

### Gates (worktree real)
| Gate | Resultado |
|---|---|
| `pnpm lint` / `pnpm check` | OK / 0 erros, 0 avisos (468 arquivos) |
| `pnpm build` | OK |
| `playwright test e2e/cupom.spec.ts` (`CI=1`, porta 4173 livre antes) | 1ª execução: 13/14. Falhou só "segundo clique antes de 2 s" `[celular]` (`:62`), um teste que o delta não tocou. Execuções seguintes: 14/14, e esse teste passou 20/20 com `--repeat-each 10`. Tratado como instabilidade de carga (outra sessão rodava Playwright em paralelo; lições 15 e 17), não como regressão |

Os gates do worker não mudaram desde a rodada 3: o `0b35f36` não toca em `apps/worker`.

### Sensor (worktree temporário detached em `0b35f36`, `node_modules` próprio via `pnpm install --frozen-lockfile --offline`, sem junção para o worktree real)
Os mutantes de script foram aplicados direto no golden `oferta-pagina-ok.html`, que é o que o e2e lê. O script do golden é idêntico ao do template.

| # | Mutante | e2e | Resultado |
|---|---|---|---|
| R0 | controle, sem mutação | 14/14 | passou |
| R6 | Falha no CTA seleciona (`copiar(selecionar)`) | 2 falhas (`:91`, celular e desktop) | morto |
| R9 (novo) | Listener do CTA sempre registrado e seleciona na falha (também sem API) | 4 falhas, nas asserções `:107` e `:132` | morto |
| R8 | A troca exige só `navigator.clipboard` | 2 falhas (`:143`) | morto |
| R3 (controle) | Troca o texto mesmo sem clipboard | 4 falhas (`:117`, `:143`) | morto |
| R2 (controle) | O script não troca o texto | 4 falhas (`:77`, `:91`) | morto |

**Rodadas 3 + 3b: 9 mutantes distintos (R1–R9). 8 mortos, 1 equivalente (R4) e nenhum sobrevivente.**

Limpeza: o worktree temporário foi removido e rodou `git worktree prune`. Fora deste worktree não sobrou nada além de um diretório temporário vazio que uma regra de proteção do ambiente não deixou apagar. O `git status --porcelain` do worktree real mostra só este arquivo.

### Lacunas restantes
Nenhuma que bloqueie. Continua bloqueando o merge a execução real do dono (§5). Observação: a instabilidade isolada do teste do clique repetido (`cupom.spec.ts:62`) com a máquina carregada deve ser acompanhada no e2e completo do autor.
