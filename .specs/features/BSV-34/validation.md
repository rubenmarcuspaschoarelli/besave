# BSV-34 Validation

## Validation: BSV-34 - PASS ✅

**Result**: PASS — rodada 2. Os 3 sobreviventes da rodada 1 (B2, B11, M3) morrem com os testes do commit 2c83964 (T7); 3 mutantes novos nas mesmas áreas também morrem; gates do site verdes na HEAD nova; 22/22 ACs com evidência. Fica uma observação de precisão (BUS-08, sitemap por construção) e o aviso da folga de 47 B no bundle.

_Rodada 1 (mesmo dia, HEAD ae0c97f): FAIL, 12/15 mortos, lacunas G1–G4. Histórico abaixo._

**Date**: 2026-10-11
**Spec**: `.specs/features/BSV-34/spec.md` (e a spec do dono `docs/specs/BSV-34.md` em `origin/docs/bsv-34`, PR #66)
**Diff range**: `origin/develop..HEAD` = `dea16fb..2c83964` (7 commits: 66cd029, 1486fcc, 0bd6365, 0504131, 4206479, ae0c97f, 2c83964). O 2c83964 só acrescenta testes (`apps/site/e2e/home.spec.ts`, `apps/site/e2e/area.spec.ts`, `apps/site/src/lib/busca.test.ts`) e `tasks.md`; nenhum código de produção mudou (conferido no `git show --stat`).
**Verifier**: Verifier independente, sub-agente; autor ≠ verificador. Não escreveu o código nem os testes; não alterou o worktree real (só este arquivo).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | `lerBusca`/`escreverBusca`/`destinoBusca` |
| T2 | ✅ Done | `ativasPrimeiro`, `ofertasCarregadas`/`ofertasTotal` |
| T3 | ✅ Done | rota `/busca/`, campo do topo |
| T4 | ✅ Done | selo "Encerrada" |
| T5 | ✅ Done | formulário no template do worker |
| T6 | ✅ Done | bundle medido, 12 prints |
| T7 | ✅ Done | testes das lacunas G1–G4 da rodada 1 (2c83964) |

---

## Spec-Anchored Acceptance Criteria

| AC | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -- | ---------------------------- | ---------------------- | --------- |
| BUS-01 | só cards que casam; "N ofertas para “q”" | `apps/site/e2e/busca.spec.ts:24` - `toHaveText('32 ofertas para “protetor”')`; `:26` ids == conjunto da fixtura com `\bprotetor`; `:27-28` cada `h3` casa `/protetor/i` | ✅ PASS |
| BUS-02 | só a área; sufixo " em {Rótulo}"; botão "Buscar em todas as áreas" tira `area` da URL e do resultado | `apps/site/e2e/busca.spec.ts:79` - `toHaveText(\`${elas.length} ofertas para “protetor” em Elas\`)`; `:80` ids == só ELAS; `:81-84` clique → `toHaveURL(/\/busca\/\?q=protetor$/)`, contagem 32, botão some; unit `apps/site/src/lib/busca.test.ts:120-124` | ✅ PASS |
| BUS-03 | filtros da URL aplicados; mudar filtro mantém `q`/`area` no formato BSV-31 | `apps/site/e2e/busca.spec.ts:55-57` (`&loja=shopee` → contagem e ids só Shopee); `:66-71` "Limpar filtros" → `toHaveURL(/\/busca\/\?q=protetor&area=elas$/)`; unit `apps/site/src/lib/busca.test.ts:100-118` (`'/busca/?q=protetor&area=esporte-vida&ordem=preco&loja=mercado-livre'`) | ✅ PASS |
| BUS-04 | expiradas depois das ativas, selo "Encerrada", foto em cinza | unit `apps/site/src/lib/dados/busca.test.ts` `:125-131` `toEqual([3, 5, 1, 2, 4])` etc. nas 3 ordens; e2e `apps/site/e2e/busca.spec.ts:193` `lista.slice(-2)).toEqual(expiradas)`, `:197` `toContainText('Encerrada')`, `:198` `toHaveClass(/grayscale/)`; quem chama: `apps/site/src/routes/busca/+page.svelte:37` (mutante B8 morto) | ✅ PASS |
| BUS-05 | "Buscando em X de Y ofertas…" + resultado parcial | `apps/site/e2e/busca.spec.ts:172-176` - `toHaveText(\`Buscando em ${primeiros.length} de ${total} ofertas…\`)` + contagem/ids parciais; `:178-179` completo some o aviso; unit `apps/site/src/lib/dados/catalogo.test.ts:284-301` `[2,5]`, chunk antigo não conta | ✅ PASS |
| BUS-06 | `q` < 2 normalizado → 10 links de área + "Maiores descontos de hoje", sem grade | `apps/site/e2e/busca.spec.ts:96-105` - para `?q=p`, `?q=-+-`, sem `q`: `toHaveCount(10)`, heading `/Maiores descontos de hoje/`, `GRADE` `toHaveCount(0)` | ✅ PASS |
| BUS-07 | "Nenhuma oferta para “q”", "Confira a grafia", "Use menos palavras", áreas | `apps/site/e2e/busca.spec.ts:112-117` - `toHaveText('Nenhuma oferta para “xyzabc”')`, `toContainText('Confira a grafia')`, `toContainText('Use menos palavras')`, 10 links | ✅ PASS |
| BUS-08 | `noindex`; título "Busca: {q} · Besave" / "Busca · Besave"; fora do sitemap | `apps/site/e2e/busca.spec.ts:29-30` (`content`=`noindex`, `toHaveTitle('Busca: protetor · Besave')`); `:45-47` HTML prerenderizado `<meta name="robots" content="noindex"` e `<title>Busca · Besave</title>`. Sitemap: por construção (`apps/worker/src/site.rs:334` só gera `/`, áreas e subpáginas; o site não gera sitemap) | ✅ PASS (⚠️ sitemap sem asserção específica, por construção) |
| BUS-09 | 40 cards; "Ver mais ofertas" +40 | `apps/site/e2e/busca.spec.ts:126-128` - `toHaveCount(40)` → clique → `toHaveCount(80)` | ✅ PASS |
| BUS-10 | recarregar restaura `q`, `area`, filtros | `apps/site/e2e/busca.spec.ts:58-61` (reload mantém URL, contagem e ids); unit `apps/site/src/lib/busca.test.ts:76-82`, `:59-63` (`q` de 1 caractere: `toBe('/busca/?q=p')`) e ida e volta | ✅ PASS |
| TOP-01 | 2+ chars → `/busca/?q=…` no cliente, foco, texto (inclusive o digitado durante a navegação) | `apps/site/e2e/home.spec.ts:126-129` - `pressSequentially('protetor')`, `toHaveURL(/\/busca\/\?q=protetor$/)`, `toHaveValue('protetor')`, `toBeFocused()`; fronteira `apps/site/e2e/bordas.spec.ts:46,55-56`; digitado durante a navegação: `apps/site/e2e/home.spec.ts:281-298` (segura `**/_app/immutable/**`, digita `pr` + `otetor`, URL ainda `/`, solta → `toHaveValue('protetor')` `:294`, foco, `?q=protetor`, contagem) | ✅ PASS (B2 e N2 mortos; 15× sem falha) |
| TOP-02 | página de área leva `&area={slug}` (subpágina também) | `apps/site/e2e/area.spec.ts:81` `toHaveURL(/\/busca\/\?q=protetor&area=elas$/)`; `:100` subpágina `/elas/unissex/` → `?q=pr&area=elas`; `:105` home sem área; unit `apps/site/src/lib/busca.test.ts:155-158` | ✅ PASS |
| TOP-03 | digitar na `/busca/` atualiza resultados e troca URL com replace | `apps/site/e2e/busca.spec.ts:137-145` - contagem nova, `toHaveURL(/\?q=protetor\+solar$/)`, `history.length` igual (`toBe(entradas)`) | ✅ PASS |
| TOP-04 | Enter envia (com `area` em página de área); sem JS, `GET /busca/` | Enter na home: `apps/site/e2e/home.spec.ts:142-147` `toHaveURL(/\/busca\/\?q=p$/)`; Enter na `/busca/`: `apps/site/e2e/busca.spec.ts:142-144`. Enter em área: `apps/site/e2e/area.spec.ts:136-145` `toHaveURL(/\/busca\/\?q=p&area=elas$/)` + sugestões. Sem JS no campo do site: `apps/site/e2e/area.spec.ts:148-158` (`javaScriptEnabled: false`, `/` e `/elas/`, Enter → `toHaveURL(/\/busca\/\?q=protetor$/)`) | ✅ PASS (B11, N1, N3 mortos) |
| TOP-05 | home e áreas não filtram mais a grade | `apps/site/e2e/bordas.spec.ts:44-52` - com 1 char, URL fica `/`, grade == os 40 primeiros, "Mais recentes"; código de busca removido de `PaginaOfertas.svelte` | ✅ PASS |
| TOP-06 | voltar retorna à página de origem | `apps/site/e2e/home.spec.ts:135-138` - `goBack()`, `toHaveURL(/\/$/)`, "Mais recentes", 40 cards | ✅ PASS |
| TOP-07 | `role="search"`, rótulo "Buscar ofertas", contagem `aria-live` | `apps/site/e2e/busca.spec.ts:37-40` - `getByRole('search').getByRole('searchbox', { name: 'Buscar ofertas' })`, `toHaveAttribute('aria-live', 'polite')` | ✅ PASS |
| OFE-01 | `<form … role="search" action="/busca/" method="get">`, `name="q"` rotulado, botão de envio, sem JS | `apps/worker/tests/template_oferta.rs:723-751` - `assert_eq!(tag(topo, "<form"), r#"<form class="busca" role="search" action="/busca/" method="get">"#)` (`:728`), posição entre logo e menu (`:733-734`), `name="q"` (`:736`), label, `<button class="buscar" type="submit"`, sem `<script`/`on*` | ✅ PASS |
| OFE-02 | ≤ 30 KB e determinístico | `apps/worker/tests/template_oferta.rs:762-763` - `html.len() <= 30 * 1024`, `assert_eq!(html, render(&o))` (3 variantes); goldens byte a byte `:142` | ✅ PASS |
| OFE-03 | regra no `besave.css` para cada classe nova | `apps/worker/tests/template_oferta.rs:529` `classes_do_template_existem_no_css` (genérico: toda classe do HTML tem regra); `apps/site/src/lib/estilo/besave-css.test.ts` `temRegra` | ✅ PASS |
| OFE-04 | digitar e enviar na página da oferta abre `/busca/?q=…` | `apps/site/e2e/oferta-busca.spec.ts:16-25` - com e sem JS, `toHaveURL(/\/busca\/\?q=protetor\+solar$/)`; lupa `:31-32` | ✅ PASS |
| BUD-01 | bundle inicial da home ≤ 150 KiB, antes/depois | `apps/site/e2e/saida.spec.ts:182-197` `expect(total).toBeLessThanOrEqual(ORCAMENTO_KIB * 1024)` (`:163` = 150). Medido: **antes 153.245 B** (JS 130.739 + CSS 22.506, worktree de develop `dea16fb`), **depois 153.553 B** (JS 131.047 + CSS 22.506), +308 B, folga de 47 B | ✅ PASS (folga mínima) |

**Status**: 22/22 ACs com evidência e discriminados; 1 parte por construção (BUS-08/sitemap, observação).

### Testes antigos alterados (conferidos contra a spec e as decisões do dono)

| Teste | Mudança | Veredito |
| ----- | ------- | -------- |
| HOM-05 `apps/site/e2e/home.spec.ts:119` | de "filtra a grade" para "navega para /busca/" com foco, texto, ids exatos e voltar | ✅ manda a spec (TOP-01/05/06); asserção de ids exatos mantida |
| ARE-05 `apps/site/e2e/area.spec.ts:68` | navega com `&area=elas`; ids == ELAS (agora com expiradas, coerente com BUS-04); botão tira a área; subpágina; home sem área | ✅ não enfraquecido |
| bordas "menos de 2 caracteres" `apps/site/e2e/bordas.spec.ts:36` | saiu `not.toContainText('Resultados')` (texto não existe mais); entrou `toHaveURL(/\/$/)`; fronteira 2 chars → URL `/busca/?q=pr` | ✅ |
| CAR-06 `apps/site/src/lib/componentes/Card.test.ts:73-81` | "Expirada" → "Encerrada" + `not.toContain('Expirada')` | ✅ decisão do dono 10/10; ficou mais forte |
| DES-01 `apps/site/e2e/desejos.spec.ts:38` | "Expirada" → "Encerrada" | ✅ decisão do dono 10/10 |
| lista de HTML `apps/site/e2e/saida.spec.ts:52` | + `busca/index.html` | ✅ rota nova, igualdade exata mantida |
| CUP-01/04/05 `apps/worker/tests/template_oferta.rs:598,657,685` | `<button` → `<button class="copiar"`; `"copiar"`/`"Copiar"` continuam na lista de ausentes | ✅ decisão do dono 11/10; intenção ("sem botão de copiar") preservada |

---

## Gate Check

### Rodada 2 (HEAD 2c83964)

| Gate | Comando | Resultado |
| ---- | ------- | --------- |
| site install | `pnpm install --frozen-lockfile` | ✅ |
| site lint | `pnpm lint` | ✅ |
| site check | `pnpm check` | ✅ 481 arquivos, 0 erros, 0 avisos |
| site test | `pnpm test` | ✅ 166/166 (17 arquivos), testes de tempo inclusos, sem oscilação nesta rodada |
| site build | `pnpm build` | ✅ |
| site e2e | `E2E_PORTA=4195 pnpm e2e` | ✅ 284 passed (2,5 min), 0 failed, 0 flaky, 0 skipped |
| testes novos repetidos (lição 25) | Playwright `-g` nos 3 testes novos de e2e (G1, G2, G4), `--repeat-each=15`, build limpo | ✅ 120/120 |
| bundle | `saida.spec.ts` "bundle inicial da home" | ✅ 153.553 B (JS 131.047 + CSS 22.506) ≤ 153.600 B; antes 153.245 B; +308 B |
| worker | não rodado de novo: 2c83964 não toca `apps/worker` (ver rodada 1) | ✅ (rodada 1) |
| html-validate | idem | ✅ (rodada 1) |

Contagens antes → depois (develop `dea16fb` → 2c83964): vitest 149 → 166 (+17); Playwright 242 → 284 (+42, os dois projetos); `template_oferta.rs` 26 → 28. Nenhum teste removido; nenhum skip.

### Rodada 1 (HEAD ae0c97f), mantida

| Gate | Resultado |
| ---- | --------- |
| site lint, check, build | ✅ |
| site test, 1ª execução com a máquina ocupada | ❌ 162/165: DES-01 (4690 ms), DES-02 (1394 ms), DES-03 (1393 ms) — carga de outras sessões (lições 15/17) |
| site test, testes de tempo isolados e por último | ✅ 7/7 (DES-01/02/03, DAD-04) |
| site test, completo de novo | ✅ 165/165 |
| site e2e (`E2E_PORTA=4195`) | ✅ 276 passed |
| worker: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (`CARGO_TARGET_DIR` compartilhado, `CARGO_BUILD_JOBS=2`) | ✅ fmt ok, clippy ok, 456 passed, 0 failed, 3 ignored (`template_oferta`: 28) |
| `npx --yes html-validate apps/worker/tests/fixtures/paginas/*.html` | ✅ exit 0 |

---

## Discrimination Sensor

Cópia isolada nas duas rodadas: `git worktree` temporário a partir da HEAD, no scratchpad (REDACTED), removido ao fim. `git status --porcelain` do worktree real igual antes e depois (rodada 1: vazio; rodada 2: só `?? .specs/features/BSV-34/validation.md`). Sem `git stash`. Site: vitest do arquivo, ou `pnpm build` + Playwright `-g` com `E2E_PORTA=4195`, nos 2 projetos (390 e 1280 px). Worker: `cargo test --test template_oferta` com `CARGO_BUILD_JOBS=1`.

### Rodada 2 (HEAD 2c83964): sobreviventes refeitos + mutantes novos

| # | Mutante | Arquivo:linha | Teste que matou | Resultado |
| - | ------- | ------------- | --------------- | --------- |
| M3 | `escreverBusca` só grava `q` com 2+ caracteres | `apps/site/src/lib/busca.ts:22` | `apps/site/src/lib/busca.test.ts:59` "q de 1 caractere fica na URL" | ✅ morto (era sobrevivente) |
| B2 | teclas durante a navegação não atualizam `passagem.texto` | `apps/site/src/lib/componentes/Busca.svelte:27` | `apps/site/e2e/home.spec.ts:281` (390: URL; 1280: `toHaveValue`) | ✅ morto (era sobrevivente) |
| B11 | `action="/busca/"` do campo do site → `"/"` | `apps/site/src/lib/componentes/Busca.svelte:35` | `apps/site/e2e/area.spec.ts:151` "sem JavaScript" (`/` e `/elas/`) | ✅ morto (era sobrevivente) |
| N1 | Enter ignora a área (`goto(destinoBusca(q))` em vez de `ir`) | `apps/site/src/lib/componentes/Busca.svelte:41` | `apps/site/e2e/area.spec.ts:136` "Enter em /elas/" | ✅ morto |
| N2 | `/busca/` ignora o texto levado (`q = e.q`) | `apps/site/src/routes/busca/+page.svelte:97` | `apps/site/e2e/home.spec.ts:281` (`toHaveValue`) | ✅ morto |
| N3 | `name="q"` → `name="busca"` no campo do site | `apps/site/src/lib/componentes/Busca.svelte:57` | `apps/site/e2e/area.spec.ts:151` sem JS e `:136` Enter | ✅ morto |

**Result rodada 2**: 6/6 mortos.

### Rodada 1 (HEAD ae0c97f), mantida

| # | Mutante | Arquivo:linha | Teste que matou | Resultado |
| - | ------- | ------------- | --------------- | --------- |
| M1 | `ativasPrimeiro` devolve a lista sem reordenar | `apps/site/src/lib/dados/busca.ts:51` | `busca.test.ts` BUS-04 | ✅ morto |
| M2 | `lerBusca` aceita também o valor do enum (`area=ELAS`) | `apps/site/src/lib/busca.ts:15` | `busca.test.ts` "área inválida é ignorada" | ✅ morto |
| M3 | `escreverBusca` só grava `q` com 2+ caracteres | `apps/site/src/lib/busca.ts:22` | — | ❌ sobreviveu → morto na rodada 2 |
| M4 | `ofertasCarregadas` conta chunk de arquivo antigo | `apps/site/src/lib/dados/catalogo.ts:228` | `catalogo.test.ts` BUS-05 | ✅ morto |
| M5 | `destinoBusca` não leva `area` | `apps/site/src/lib/destino-busca.ts:6` | `busca.test.ts` TOP-02 (+1) | ✅ morto |
| M6 | selo volta a "Expirada" | `apps/site/src/lib/componentes/Card.svelte:38` | `Card.test.ts` CAR-06 | ✅ morto |
| B1 | limiar do topo `>= 2` → `>= 1` | `apps/site/src/lib/componentes/Busca.svelte:66` | `bordas.spec.ts:36` | ✅ morto |
| B2 | teclas durante a navegação não atualizam `passagem.texto` | `apps/site/src/lib/componentes/Busca.svelte:27` | — | ❌ sobreviveu → morto na rodada 2 |
| B3 | `replace: true` → `false` | `apps/site/src/routes/busca/+page.svelte:68` | `busca.spec.ts:132` | ✅ morto |
| B4 | sem `<meta name="robots" content="noindex">` | `apps/site/src/routes/busca/+page.svelte:117` | `busca.spec.ts:19` e `:44` | ✅ morto |
| B8 | rota não chama `ativasPrimeiro` (filtro em quem chama, lição 23) | `apps/site/src/routes/busca/+page.svelte:37` | `busca.spec.ts:183` | ✅ morto |
| B11 | `action="/busca/"` do campo do site → `"/"` | `apps/site/src/lib/componentes/Busca.svelte:35` | — | ❌ sobreviveu → morto na rodada 2 |
| W1 | `action="/busca/"` → `"/"` no template | `apps/worker/templates/oferta.html:27` | `topo_tem_formulario_de_busca_sem_js`, `com_formulario_html_no_orcamento_e_deterministico`, goldens | ✅ morto |
| W2 | `name="q"` → `name="busca"` no template | `apps/worker/templates/oferta.html:29` | `topo_tem_formulario_de_busca_sem_js`, goldens | ✅ morto |
| W3 | lupa `type="submit"` → `type="button"` | `apps/worker/templates/oferta.html:30` | `topo_tem_formulario_de_busca_sem_js`, goldens | ✅ morto |

**Sensor depth**: ampliado (18 mutantes distintos em 2 rodadas). Nenhum equivalente.
**Result**: 18/18 mutantes distintos mortos na HEAD final (12 na rodada 1; 3 sobreviventes + 3 novos na rodada 2) - PASS ✅

---

## Code Quality

| Princípio | Status |
| --------- | ------ |
| Mínimo de código / sem escopo extra | ✅ (`destino-busca.ts` separado de `busca.ts` por causa do bundle, justificado no arquivo) |
| Mudanças cirúrgicas, só pastas autorizadas (`apps/site/`, `apps/worker/templates/` + testes/goldens, `besave.css`) | ✅ |
| Padrões do repo (Svelte 5 runes, Tailwind; CSS do worker no `besave.css`) | ✅ |
| Sem dependência nova | ✅ (`package.json` e lockfile intocados) |
| Asserções nos valores da spec | ✅ (textos exatos de contagem, URL exata, contagens exatas) |
| Testes mapeiam ACs | ✅ (comentários com ID em cada teste, inclusive os do T7) |
| T7 só testes | ✅ (`git show --stat 2c83964`: `home.spec.ts`, `area.spec.ts`, `busca.test.ts`, `tasks.md`) |
| Diretrizes: `CLAUDE.md`, `apps/site/CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` §6 | ✅ |

---

## Edge Cases

- [x] `area` inválida ignorada — `apps/site/e2e/busca.spec.ts:88-92`; unit `apps/site/src/lib/busca.test.ts` "área inválida é ignorada"
- [x] `q` só pontuação/espaços = vazio — `apps/site/e2e/busca.spec.ts:96` (`?q=-+-`); `apps/site/e2e/bordas.spec.ts:44` (`' p '`, `'-'`)
- [x] só expiradas aparecem sem estado vazio — `apps/site/e2e/busca.spec.ts:202-205`

---

## Lacunas e observações

Rodada 1 → rodada 2:

| Lacuna (rodada 1) | Situação |
| ----------------- | -------- |
| G1 — TOP-01, texto digitado durante a navegação | ✅ fechada: `apps/site/e2e/home.spec.ts:281`; B2 e N2 mortos; 15 repetições sem falha |
| G2 — TOP-04, campo do site sem JS | ✅ fechada: `apps/site/e2e/area.spec.ts:148-158`; B11 e N3 mortos |
| G3 — `q` de 1 caractere na URL | ✅ fechada: `apps/site/src/lib/busca.test.ts:59-63`; M3 morto |
| G4 — Enter em página de área | ✅ fechada: `apps/site/e2e/area.spec.ts:136-145`; N1 morto |

Observações que ficam (não bloqueiam o PASS):
1. **Precisão — BUS-08 "fora do sitemap"**: atendido por construção (`apps/worker/src/site.rs:334` gera só `/`, áreas e subpáginas; o site não gera sitemap), sem asserção que cite `/busca/`.
2. **BUD-01 com 47 B de folga** (153.553 de 153.600 B): qualquer byte a mais na home estoura o gate. Vale avisar no PR.
3. **Testes de tempo** (DES-01/02/03) falharam uma vez na rodada 1 com a máquina ocupada e passaram isolados; na rodada 2 passaram na suíte completa.

Bloqueia o merge, fora desta verificação: execução real do dono (deploy do site, `besave-ciclo` novo, PageSpeed celular ≥ 90), conforme a spec.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| BUS-01..10, TOP-01..07, OFE-01..04, BUD-01 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (falta só a execução real do dono)

**Spec-anchored check**: 22/22 ACs com evidência e discriminados; 1 observação de precisão (BUS-08, sitemap por construção)
**Sensor**: 18/18 mutantes distintos mortos na HEAD 2c83964 (rodada 2: 6/6)
**Gate**: site 166 vitest + 284 e2e (2c83964); worker 456 + html-validate ok (rodada 1, sem mudança no worker); bundle 153.553 B

**What works**: rota `/busca/` completa (contagem, área, filtros, expiradas no fim, parcial, sugestões, vazio, noindex, "Ver mais"); campo do topo com navegação, área, Enter e sem JS; formulário na página da oferta.
