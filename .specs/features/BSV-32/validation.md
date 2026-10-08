# BSV-32 — validation

**Verificador:** Verifier sub-agente independente (autor ≠ verificador). Commit verificado: 85976e3, branch `rubenmarcus/rub-25-bsv-32-novas-ofertas`.
Mutantes aplicados um a um, com reversão por `git checkout`; `git status` final limpo (só `package.json` e `pnpm-lock.yaml` da raiz, que já estavam não rastreados antes).

**Veredito: PASS** com 3 lacunas de teste não bloqueantes (L1–L3) e o item "Real (dono)" pendente.

## Gates (apps/site)
| gate | resultado |
|---|---|
| `pnpm install --frozen-lockfile` | OK |
| `pnpm lint` | OK |
| `pnpm check` | OK |
| `pnpm test` | 13 arquivos, 114 testes, OK (duas execuções) |
| `pnpm build` | OK |
| `pnpm e2e` | 96 passed (celular 390 px e desktop 1280 px) |
| `desempenho.test.ts` x3, sem carga | 6/6 verdes nas 3 execuções (tests ≈ 1,9–2,0 s) |

## Critérios e saídas
| item | resultado | evidência |
|---|---|---|
| S1 botão fixo abaixo do topo, "1 nova oferta"/"N novas ofertas", N = total pendente, laranja/branco, `aria-live="polite"`, some com N=0 | PASS | `AvisoNovas.svelte:43-54` (sticky, `top={topo}` = altura de `[data-topo]` medida em 13-19; `aria-live` em 45; `{#if n > 0}`; texto em 53; `bg-destaque text-sobre-destaque`). N: `vitrine.novasEm`, `vitrine.svelte.ts:31-33`. Contraste AA: `novas.spec.ts` (NOV-06, razão ≥ 4,5) |
| S2 tocar: confirmar, rolagem suave (instantânea com reduced-motion), foco no título | PASS | `AvisoNovas.svelte:30-38` (`confirmarNovas`, `matchMedia`, `scrollTo`, `focus`); e2e NOV-06 confere 2 cards no topo, aviso some e `#titulo-recentes` focado (`PaginaOfertas.svelte:82`) |
| S3 título da aba "(N) " e volta ao normal | PASS | `vitrine.svelte.ts:10-13`; efeito em `AvisoNovas.svelte:23-27`; vitest NOV-05, e2e NOV-06 (`toHaveTitle`) |
| S4 home e áreas (só as da área); não em /desejos/ nem 404 | PASS | `AvisoNovas` só é montado em `PaginaOfertas.svelte:64`; `desejos/+page.svelte` e `404.html` não o importam; por área em `vitrine.svelte.ts:36-48`; e2e NOV-07/08/09 |
| S5 estado em `vitrine.svelte.ts`, sem mudar API de `dados.ts` | PASS | `git show --stat HEAD`: nada em `lib/dados*`; `novasTotal`, `#novasPorArea`, `novasEm`, `recontarNovas`, `confirmarNovas` (linhas 24-53) |
| Regra 1 sem fetch novo | PASS | `grep fetch` em `vitrine.svelte.ts` e `AvisoNovas.svelte`: nenhum; usa o evento do sincronizador existente (`vitrine.svelte.ts:72-76`) |
| Regra 2 expiradas e mudança só de preço não contam | PASS | Pendência vem de `Catalogo` (`dados/catalogo.ts:140-145`: expirada vai à base; id já na base não vira pendente); `recontarNovas` exclui visíveis (`vitrine.svelte.ts:42-45`); NOV-01 e e2e (1012 expirado, "2 novas") |
| Regra 3 sem dependência nova | PASS | `package.json`/lock do app não aparecem no diff do commit |
| Fronteira BSV-31 | PASS | Commit toca 5 arquivos: `AvisoNovas.svelte` (novo), `vitrine.svelte.ts` (só partes de novas), `PaginaOfertas.svelte` (+2 linhas: import `:7` e `<AvisoNovas {area} />` `:64`), mais 2 arquivos de teste. Nada em Grade, filtros, ordens ou `lib/dados/` |
| AC Vitest | PASS | `vitrine.test.ts` NOV-01..05 |
| AC Playwright 390/1280 | PASS | `novas.spec.ts` NOV-06..09, nos dois projetos |

## Sensor de discriminação
| # | arquivo / mutação | resultado |
|---|---|---|
| a | `vitrine.svelte.ts` `novasEm` devolve sempre o total | MORTO (NOV-02) |
| a2 | idem, `porArea` conta MEU_LAR como ELAS | MORTO (NOV-02). Uma 1ª variante (ELAS→MEU_LAR) sobreviveu porque a única nova de ELAS é expirada: fraqueza do fixture, não do teste |
| b | remover `!c.x` em `recontarNovas` | SOBREVIVEU — equivalente: expirada nova entra na base (`catalogo.ts:142-144`) e já aparece em `lista({mostrarExpiradas:true})` |
| b2 | `mostrarExpiradas:false` | SOBREVIVEU — equivalente pelo mesmo motivo, e `!c.x` ainda guarda a conta. A exclusão de expirada na contagem total é pelo `Catalogo` (coberta por NOV-01 e `catalogo.test.ts`) |
| c | `visiveis` nunca preenchido (tudo que está na lista passa a contar como nova, o caso do id só com preço mudado) | MORTO (NOV-02) |
| d | `confirmarNovas` sem `recontarNovas` (não zera) | MORTO (NOV-03) |
| d2 | sem `cat.confirmarNovas()` | MORTO (NOV-03) |
| d3 | sem `versao++` | MORTO (NOV-03) |
| e | `tituloComNovas` sem tirar o "(N)" | MORTO (NOV-05) |
| e2 | `n >= 0` (prefixa "(0)") | MORTO (NOV-05) |
| f | `AvisoNovas` montado em `/desejos/` | MORTO (NOV-09, ambos os projetos) |
| g | rolagem sempre `smooth` (ignora reduced-motion) | SOBREVIVEU — lacuna L1 |
| h | `aria-live` removido | SOBREVIVEU — lacuna L2 (nenhum teste olha o atributo) |
| i | `{#if n >= 0}` (botão com N=0) | MORTO (NOV-06 e NOV-07) |
| j | `n === 1 ?` removido (singular) | SOBREVIVEU — lacuna L3 (nenhum cenário tem N=1) |
| k | remover `focus()` | MORTO (NOV-06 `toBeFocused`) |
| l | `top` fixo em 0 (aviso sobre o cabeçalho) | SOBREVIVEU — lacuna L4: o teste mede com scroll em 0, onde o aviso fica abaixo do topo de qualquer jeito |
| m | efeito do título sem aplicar "(N)" | MORTO (NOV-06) |
| n | remover `scrollTo` | SOBREVIVEU — lacuna L5 (o teste não confere a rolagem) |
| o | `toLocaleString` trocado por `n` | SOBREVIVEU — equivalente para N < 1000 (nenhum teste usa milhar) |
| p | evento `'novas'` sem recontar | SOBREVIVEU em vitest (o `#evento` é privado; não há teste unitário) — equivalente na prática: `'atualizado'` sempre precede e recalcula |
| q | evento `'atualizado'` sem recontar (mantendo `'novas'`) | MORTO no e2e (NOV-06/08); vitest não o exerce. Retirar os dois eventos: MORTO |
| r | tocar sem `confirmarNovas()` | MORTO (NOV-06) |

## Lacunas (não bloqueiam; sugestões, nada foi alterado)
- **L1 reduced-motion:** nenhum teste exerce `prefers-reduced-motion`. Sugestão: e2e com `page.emulateMedia({reducedMotion:'reduce'})`, tocar e checar `scrollY` imediato.
- **L2 aria-live:** sugestão: `await expect(page.locator('[data-aviso-novas]')).toHaveAttribute('aria-live','polite')`.
- **L3 singular:** sugestão: vitest/e2e com 1 nova ("1 nova oferta"); o e2e atual só cobre 2.
- **L4 sem sobreposição ao rolar:** sugestão: rolar a página antes de publicar e checar que o botão fica abaixo de `[data-topo]` (a posição do botão depende de `top={topo}`).
- **L5 rolagem até "Mais recentes":** sugestão: depois do clique, checar que o título está dentro da janela (`scrollY` > 0 ou `boundingBox().y` perto do topo).

## Pendente
- **Real (dono):** home aberta no celular por 10–15 min com o robô publicando; o aviso aparece com o número certo; tocar mostra as novas no topo; o título da aba no computador mostra "(N)". Bloqueia o merge. Prints do aviso (celular e desktop) para a PR.

## Decisões / lições propostas (para o dono)
- Num fixture, a nova expirada de uma área não prova que a contagem por área descarta expiradas (a barreira é o `Catalogo`); o teste de contagem por área é forte o bastante pela troca de área (a2).

## Adendo do autor (pós-Verifier)
L1 e L2 fechadas: `e2e/novas.spec.ts` NOV-10 (aria-live) e NOV-11 (rolagem `instant` com `reducedMotion: reduce`, `smooth` sem). Reexecutado: `pnpm lint` e `pnpm e2e` (102 passed). L3–L5 seguem como lacunas não bloqueantes. Os testes NOV-10/NOV-11 não foram revalidados por mutante.

## Defeito achado nos prints (pós-Verifier)
Ao tirar os prints, o botão aparecia achatado (altura 0): o contêiner `h-0` esticava o item flex. Os testes e os mutantes não pegaram porque só mediam a posição `y`. Corrigido com `items-start` em `AvisoNovas.svelte`; `e2e/novas.spec.ts` NOV-06 agora exige altura ≥ 32 px e botão inteiro na janela, e reprova com a correção removida (confirmado). Gates reexecutados: lint, check, test (114), build, e2e (102) verdes. Prints em `prints/` (catálogo sintético; imagens quebradas são do fixture).
