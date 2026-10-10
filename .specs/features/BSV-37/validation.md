# Validation BSV-37 — PASS (rodada 2)

**Veredito: PASS.** A lacuna 1 da rodada 1 (CMP-10 intermitente) foi corrigida no commit 178ad84, que só mexe em
testes. Ele também fecha uma segunda corrida, a do teste de rolagem suave. Repeti os dois testes 30 vezes em cada
projeto: 60/60 e 60/60. Os gates completos estão verdes. Reamostrei 7 mutantes, incluindo um que força
`behavior: 'instant'`, e os 7 morreram. As lacunas 2 a 5 são decisão ou precisão do dono e não bloqueiam o PASS.
O merge continua bloqueado pela verificação real do dono.

- **Data:** 2026-10-09
- **Verificou:** Verifier independente, como sub-agente (autor ≠ verificador). Não alterei código nem testes do repositório.
- **Spec:** `docs/specs/BSV-37.md` (dono) e `.specs/features/BSV-37/spec.md` (EARS: CMP-01..11, CEL-01, SET-01..04, BUD-01)
- **Faixa de diff:** `origin/develop..178ad84` = `3f998f2`, `14e9d5e`, `4bbcdec`, `178ad84` (4 commits) sobre
  `origin/develop` em `2acdad0`. `git diff 4bbcdec 178ad84 -- apps/site/src` está vazio: o código é o mesmo da
  rodada 1; mudaram só `e2e/compacta.spec.ts` (+2 linhas) e `e2e/setas.spec.ts`. `src/lib/dados/` não mudou no ticket.

## Histórico das rodadas

| Rodada | Faixa | Veredito | Achados |
| --- | --- | --- | --- |
| 1 | `origin/develop..4bbcdec` (3 commits) | FAIL | Gates verdes (e2e 228/228). Bundle 153 245 B (−25 B). 20 mutantes, 20 mortos. CMP-10 intermitente: 3 falhas em 30 repetições (`evaluateAll` sem esperar a faixa vinda do `import()`). Lacunas 2 a 5 ficaram como decisão ou precisão do dono. |
| 2 | `origin/develop..178ad84` (4 commits) | PASS | CMP-10 espera `toHaveCount(5)` antes de medir (`compacta.spec.ts:280`). O teste de rolagem suave registra as posições de cada evento de scroll e exige uma intermediária (`setas.spec.ts:86-97`). Repetições: 60/60 e 60/60. Gates verdes. 7 mutantes reamostrados (M21 novo), 7 mortos. |

### Os testes da rodada 2

- **CMP-10** (`compacta.spec.ts:280`): `await expect(faixa(page).getByRole('button')).toHaveCount(5)` antes do
  `evaluateAll`. A asserção de altura (`:284-285`) não mudou. O teste ficou estável e não ficou mais fraco: a
  contagem 5 já era exigida (`toHaveLength(5)`).
- **Rolagem suave** (`setas.spec.ts:81-98`): antes o teste lia o `scrollLeft` uma vez logo depois do clique e
  exigia que ainda estivesse abaixo do alvo, o que dependia de tempo. Agora `expect.poll` espera o alvo (`:93`) e o
  teste exige que algum evento de scroll tenha passado por uma posição entre 0 e o alvo (`:97`). Uma rolagem
  instantânea dispara um único evento já no alvo e é reprovada; o mutante M21 confirma. Julgo a mudança equivalente
  em intenção e mais robusta, não um enfraquecimento.

---

## Checagem ancorada na spec

| Critério / requisito | O que a spec define | Evidência `arquivo:linha` (asserção) | Status |
| --- | --- | --- | --- |
| 1280 px: barra numa linha com o título (CMP-01) | itens na mesma linha do "Mais recentes", à direita; sem "Filtros"; nenhuma opção visível | `apps/site/e2e/compacta.spec.ts:65-67` (sobreposição vertical e `x` à direita do título); `:69` `opcao('Filtros').toBeHidden()`; `:70-71` opções `toHaveCount(0)`; `:73-74` `aria-expanded='false'` | ✅ no estado padrão. ⚠️ Com filtros escolhidos a linha quebra (lacuna 2) |
| `Público ▾` abre a faixa logo abaixo, com `aria-expanded`/`aria-controls` (CMP-02) | faixa com as 5 opções, logo abaixo da linha | `compacta.spec.ts:82` `aria-expanded='true'`; `:83-86` o alvo de `aria-controls` fica visível; `:87-89` 5 botões; `:96-98` posição entre a linha (≤ 24 px abaixo) e a grade | ✅ |
| Escolher `Feminino` fecha a faixa, mostra `Público: Feminino` e filtra (CMP-04) | faixa fechada; nome `Público: Feminino`; grade só FEMININO; URL `?publico=feminino` | `compacta.spec.ts:106` `faixa toHaveCount(0)`; `:107` `toHaveAccessibleName('Público: Feminino')`; `:109` URL; `:111-114` contagem e grade; `:116` sem escolha mostra só `Loja`; `:119-121` reabre ao clicar de novo | ✅ |
| `Preço: Até R$ 50` (CMP-04) | rótulo exato | `compacta.spec.ts:129` `toHaveAccessibleName('Preço: Até R$ 50')`; `:132-137` ordem + URL `?ordem=preco&preco=ate50` | ✅ |
| Abrir `Loja ▾` fecha a faixa de público (CMP-03) | uma faixa por vez | `compacta.spec.ts:146-149` Público `aria-expanded='false'`, Loja `true`, `faixa toHaveCount(1)`, Feminino `toHaveCount(0)` | ✅ |
| Esc fecha e devolve o foco (CMP-05) | faixa fechada, foco no item | `compacta.spec.ts:166-167` `toHaveCount(0)` + `loja toBeFocused()` | ✅ |
| Clique fora fecha (CMP-06) | faixa fechada | `compacta.spec.ts:180-182` (clique na margem: fecha e foco no item); `:188-190` (clique na busca: fecha e o foco fica na busca, decisão da tabela) | ✅ |
| `Só com cupom` liga e desliga (CMP-07) | `aria-pressed` alterna; `?cupom=1` | `compacta.spec.ts:196-206` | ✅ |
| URL igual à BSV-31 | `?publico=`, `?ordem=&preco=`, `?cupom=1` | `compacta.spec.ts:109`, `:133`, `:199`; `filtros.spec.ts` (URL-01..05), que passa no desktop | ✅ |
| "Limpar filtros" na linha volta ao padrão (CMP-08) | aparece na linha com filtro ativo; um só; volta ao padrão | `compacta.spec.ts:213-216` (dentro de `[data-compacta]`, `toHaveCount(1)`); `:221-228`; `:233` ausente no padrão | ✅ |
| Nada da faixa é baixado antes do 1º clique (CMP-09) | nenhum JS com o código das opções antes do clique | `compacta.spec.ts:250-251` `comFaixa(js)` = `[]` após `networkidle`; `:255` chega depois do clique | ✅ |
| Itens ≥ 44 px e foco `--cor-foco` (CMP-10, regra 3) | ≥ 44 px; contorno `#1d4ed8` | `compacta.spec.ts:266-267`; `:276` `'solid rgb(29, 78, 216)'` (= `--cor-foco` em `src/lib/estilo/tokens.css:15`); `:280` espera as 5 opções, `:284-285` alturas | ✅ (rodada 2: 60/60 em repetição) |
| Área: público navega pelo caminho (CMP-11) | `/elas/masculino/?loja=shopee`; "Todos" volta a `/elas/` | `compacta.spec.ts:291-292`, `:301` | ✅ |
| 390 px sem mudança (CEL-01) | testes existentes passam com o mesmo fluxo | ver "Testes existentes" abaixo; tablet 800 px: `compacta.spec.ts:311-316` | ✅ |
| Faixa 1280: sem barra (SET-01) | sem barra visível | `setas.spec.ts:30` `{ barra: 0, estilo: 'none' }` (desktop `:40`, toque `:145`) | ✅ |
| › rola e ‹ aparece; no fim › some (SET-02) | as duas setas trocam de estado | `setas.spec.ts:45-46`, `:54-55`, `:58-59`; cabe inteira: nenhuma seta, `:113-114` | ✅ |
| Rola uma largura visível; instantâneo com `reduced-motion` (SET-03) | `scrollLeft` = `min(clientWidth, max)` | `setas.spec.ts:53`; 500 px com dois cliques `:128`, `:132`, `:135`; suave: alvo `:93` e posição intermediária `:97` | ✅ |
| Teclado (Tab + Enter) (SET-03) | Tab chega na seta e Enter rola | `setas.spec.ts:68-77` (o foco passa para a seta oposta: edge case da spec) | ✅ |
| Rótulos "Ver descontos anteriores/seguintes" | rótulo acessível | `setas.spec.ts:7-8` + `getByRole(..., exact)` | ✅ |
| 390 px: sem setas, rola com toque (SET-04) | sem setas; o arrasto rola | `setas.spec.ts:146-147` `toHaveCount(0)`; `:161` `scrollLeft > 100` com toque CDP | ✅ |
| Bundle ≤ 150 KiB e, se possível, < 149,7 KiB (BUD-01) | ≤ 153 600 B; < 153 270 B | `saida.spec.ts:194` `toBeLessThanOrEqual(150*1024)`; medido 153 245 B (abaixo) | ✅ gate. ⚠️ O "< 153 270 B" não tem asserção (o dono escreveu "se possível") |
| Contraste AA (regra 3) | AA | sem teste do trilho do interruptor (`bg-suave`/`bg-marca` com bolinha branca) | ⚠️ revisão visual do dono |
| Real (dono) | linha compacta, cada filtro, setas, celular, PageSpeed ≥ 90 | — | ⏳ **bloqueia o merge** |

### Testes existentes (390 px "sem mudança") e testes de desktop alterados

- **Fluxo de 390 px intacto.** Os blocos `celular (390 px)` (`filtros.spec.ts:300`) e `celular: teclado no painel`
  (`:346`) não mudaram. O que mudou foram os helpers de nível superior (`escolher`, `pressionado`, `tocar` e
  BAR-09), que ganharam o ramo `abrirNaLinha`. Esse ramo devolve `false` sem fazer nada quando `[data-compacta]`
  não está visível (`e2e/linha-compacta.ts:25`). No celular, então, o caminho é o mesmo de antes. A única mudança
  fora do ramo é sintática: `pressionado` virou `async` e as chamadas passaram a usar `await`. A asserção de 390 px
  de BAR-04 ficou igual (`filtros.spec.ts:225`, `toHaveCount(3)`). Projeto `celular`: tudo verde.
- **PNL-03 substituído** (`filtros.spec.ts:424`). O teste antigo exigia as 17 opções visíveis no desktop, e isso é
  justamente o que a BSV-37 elimina. O novo exige os 5 itens visíveis **e** as opções ausentes, então ficou mais
  forte. Mudança legítima de requisito, não enfraquecimento.
- **BAR-04 com ramo** (`filtros.spec.ts:221-225`). No desktop, a contagem de 3 pressionados passou a verificar
  o texto dos itens (`Ordem: Recentes▾` e o nome puro). Legítimo: no desktop as opções só existem com a faixa aberta.
  Os botões pressionados continuam verificados um a um nas linhas anteriores, com `pressionado()` abrindo a faixa.

---

## Gates (rodada 2, o runner decide)

| Gate | Resultado |
| --- | --- |
| `pnpm install --frozen-lockfile` | ✅ lockfile em dia |
| `pnpm lint` (prettier + eslint) | ✅ |
| `pnpm check` | ✅ 474 arquivos, 0 erros, 0 avisos |
| `pnpm test` | ✅ 148 = 141 em 15 arquivos (sem os de tempo) + `desempenho.test.ts` 7/7, rodado **por último**, depois de remover o worktree de mutantes, sem e2e rodando (lição 17) |
| `pnpm build` | ✅ |
| `pnpm e2e` | ✅ 228 passaram, 0 falharam, 0 pulados, 0 flaky (celular + desktop), em 176 s |
| CMP-10 com `--repeat-each 30` (2 projetos) | ✅ **60/60** (rodada 1: 3 falhas em 30) |
| Rolagem suave com `--repeat-each 30` (2 projetos) | ✅ **60/60** |

**Servidor do e2e.** A 4173 pertence a outro worktree. Rodei com um config no scratchpad que reexporta o
`playwright.config.ts` do site com porta 4188, `reuseExistingServer: false`, `--strictPort`, `webServer.cwd = apps/site`
e `testDir`/`outputDir` absolutos. O relatório JSON das duas rodadas confirma o `webServer` em `--port 4188`, com cwd
`REDACTED/orca/workspaces/besave/rub-29-bsv-37-…/apps/site`. Com `strictPort` e sem reuso, um servidor de fora faria a
execução falhar em vez de ser usado.

Contagem de testes: e2e 228 nas duas rodadas (o autor também registrou 228). Nenhum teste foi removido. O PNL-03 foi
substituído no mesmo lugar, como descrito acima.

## Bundle (BUD-01)

Valor da annotation `bundle` em `e2e/saida.spec.ts:180`, nos dois projetos (iguais nas rodadas 1 e 2):
`JS 130739 B (18 arquivos) + CSS 22506 B = 153245 B (149.7 KiB)`.
Antes (`develop` 2acdad0): 153 270 B. **Diferença: −25 B.** Gate de 153 600 B: folga de 355 B. Bate com `evidencia.md`.

---

## Sensor de discriminação

### Rodada 2 (178ad84)

Mesmo método da rodada 1: worktree temporário `git worktree add --detach <scratchpad>/mut 178ad84`, `node_modules`
ligado por junção, `vite build` e Playwright `compacta`, `setas`, `filtros`, `publico` e `saida` nos dois projetos,
na porta 4189. Controle (M0): 140/140. Um lote de 7 mutantes.

| # | Mutação | Resultado | Teste que matou |
| --- | --- | --- | --- |
| M21 (novo) | `SetasFaixa.svelte`: rolagem sempre `behavior: 'instant'` | ✅ morto | `setas.spec.ts:81` (rolagem suave, posição intermediária `:97`) |
| M11 | sempre suave (ignora `prefers-reduced-motion`) | ✅ morto | `setas.spec.ts:37`, `:63`, `:122` |
| M16 | interruptor com `min-h-8` | ✅ morto | `compacta.spec.ts:259` (CMP-10), `filtros.spec.ts:274` |
| M1 | faixa não fecha ao escolher | ✅ morto | `compacta.spec.ts:102` |
| M8 | `GruposFiltros` importado estaticamente | ✅ morto | `compacta.spec.ts:237` + `saida.spec.ts:180` |
| M9 | › não some no fim | ✅ morto | `setas.spec.ts:37`, `:63`, `:122` |
| M17 | `fechar` nunca devolve o foco | ✅ morto | `compacta.spec.ts:158`, `:174` |

**Placar da rodada 2: 7 mutantes, 7 mortos, 0 sobreviventes.** Sem ruído: nenhuma falha alheia às mutações (na
rodada 1, o CMP-10 tinha falhado à toa em M2 e M11).
**Placar acumulado: 21 mutantes distintos, 21 mortos, 0 sobreviventes, 0 equivalentes.**

### Rodada 1 (4bbcdec): os números de linha de `setas.spec.ts` são os daquele commit

Worktree temporário com `git worktree add --detach <scratchpad>/mut HEAD`, fora do repositório, e `node_modules`
ligado por junção. Um mutante por vez, com substituição exata de string (o script aborta se não acha o trecho).
Depois: `vite build` e Playwright `compacta`, `setas`, `filtros`, `publico` e `saida` nos dois projetos, na porta 4189.
Controle sem mutação (M0): 140/140 verdes. Lotes de 8, 7 e 6.

| # | Arquivo | Mutação | Resultado | Teste que matou |
| --- | --- | --- | --- | --- |
| M1 | `BarraFiltros.svelte` | faixa não fecha ao escolher (sem `fechar(true)`) | ✅ morto | `compacta.spec.ts:102` (CMP-04) |
| M2 | `FaixaFiltros.svelte` | Esc fecha sem devolver o foco | ✅ morto | `compacta.spec.ts:158` (CMP-05) |
| M3 | `FaixaFiltros.svelte` | clique fora não fecha | ✅ morto | `compacta.spec.ts:174` (CMP-06) |
| M4 | `BarraFiltros.svelte` | `aria-expanded` verdadeiro em todos os itens com qualquer faixa aberta | ✅ morto | `compacta.spec.ts:141` (CMP-03) + 4 de `filtros`/`publico` |
| M5 | `BarraFiltros.svelte` | item não mostra o valor (só a ordem mostra) | ✅ morto | `compacta.spec.ts:102`, `:125`, `:210`, `:287` |
| M6 | `BarraFiltros.svelte` | "Limpar filtros" fora da linha no computador | ✅ morto | `compacta.spec.ts:210` (CMP-08), `:259`, `filtros.spec.ts:211`, `publico.spec.ts:192` |
| M7 | `BarraFiltros.svelte` | sem `aria-controls` | ✅ morto | `compacta.spec.ts:78` (CMP-02) |
| M8 | `BarraFiltros.svelte` | `GruposFiltros` importado estaticamente | ✅ morto | `compacta.spec.ts:237` (CMP-09) + `saida.spec.ts:180` (bundle) |
| M9 | `SetasFaixa.svelte` | › não some no fim | ✅ morto | `setas.spec.ts:37`, `:63`, `:113` |
| M10 | `SetasFaixa.svelte` | rola `scrollWidth` em vez de `clientWidth` | ✅ morto | `setas.spec.ts:113` (500 px) |
| M11 | `SetasFaixa.svelte` | ignora `prefers-reduced-motion` (sempre suave) | ✅ morto | `setas.spec.ts:37`, `:63`, `:113` |
| M12 | `FaixaDescontos.svelte` | setas carregadas também no toque | ✅ morto | `setas.spec.ts:134` (SET-04) |
| M13 | `FaixaDescontos.svelte` | barra de rolagem visível | ✅ morto | `setas.spec.ts:37`, `:134` (SET-01) |
| M14 | `BarraFiltros.svelte` | breakpoint 640 em vez de 1024 (matchMedia + classes) | ✅ morto | `compacta.spec.ts:309` (tablet 800 px) |
| M15 | `SetasFaixa.svelte` | a seta que some não passa o foco para a outra | ✅ morto | `setas.spec.ts:63` |
| M16 | `BarraFiltros.svelte` | interruptor com `min-h-8` (32 px) | ✅ morto | `compacta.spec.ts:259` (CMP-10), `filtros.spec.ts:274` |
| M17 | `BarraFiltros.svelte` | `fechar` nunca devolve o foco | ✅ morto | `compacta.spec.ts:158`, `:174` |
| M18 | `BarraFiltros.svelte` | cupom só liga, nunca desliga | ✅ morto | `compacta.spec.ts:194` (CMP-07), `filtros.spec.ts:125` |
| M19 | `filtros.ts` | `valorEscolhido` só para a ordem | ✅ morto | 10 falhas e2e (CMP-04/08/11) |
| M20 | `SetasFaixa.svelte` | "fim" detectado 400 px antes | ✅ morto | `setas.spec.ts:37`, `:63`, `:81`, `:113` |

**Placar da rodada 1: 20 mutantes, 20 mortos, 0 sobreviventes, 0 equivalentes.**
Ruído: em M2 e M11 o `compacta.spec.ts:259` (projeto `celular`) também falhou sem relação com a mutação. Era a
intermitência corrigida na rodada 2. Nenhum mutante dependeu só dessa falha para morrer.

**Isolamento (as duas rodadas):** o `git status --porcelain` do worktree real ficou igual antes e depois (vazio, e
na rodada 2 só com este `validation.md` não rastreado). Removi
primeiro a junção (`rmdir`, sem tocar no alvo, e o `node_modules` real continua íntegro). Depois rodei
`git worktree remove --force`, `rm -rf` do que sobrou por causa de caminho longo e `git worktree prune`. Os worktrees
temporários não aparecem mais em `git worktree list`.

---

## Qualidade do código

- Mudanças restritas a `apps/site/` e `.specs/features/BSV-37/`. Sem dependência nova. Estado e URL dos filtros
  inalterados (`filtros.ts` só ganhou rótulos e `valorEscolhido`).
- O código sob demanda está num só ponto (`filtros-sob-demanda.ts`). O prerender traz as duas variantes e o CSS escolhe;
  depois de montar, só a do tamanho atual fica no DOM. Não há layout shift entre elas no desktop (o título é o mesmo).
- Observação, sem lacuna: em < 1024 px o módulo sob demanda (`CSe0GToy.js`, 4 181 B, com o painel) agora é importado
  **ao montar**, não ao tocar em "Filtros", porque os grupos ocultos no DOM vêm dele. Fica fora do bundle inicial
  medido, mas no celular é um pedido a mais depois da hidratação. Impacto pequeno; o dono confere no PageSpeed.
- Testes novos derivam dos critérios da spec e não espelham a implementação (posição medida, nome acessível, URL, grade).

---

## Lacunas (ranqueadas; nenhuma bloqueia o PASS)

1. ~~**CMP-10 intermitente**~~ **resolvida na rodada 2** (`compacta.spec.ts:280`; 60/60 em repetição). A segunda
   corrida, do teste de rolagem suave, também foi resolvida (`setas.spec.ts:86-97`; 60/60).
2. **[Decisão do dono] A linha quebra com filtros escolhidos.** Medi no build real (`[data-compacta]` contra
   `#titulo-recentes`):
   - em **1024 px**, dois valores longos já levam os itens para uma segunda linha, abaixo do título
     (`?ordem=desconto&loja=mercado-livre`);
   - em **1280 px**, isso acontece com os quatro grupos escolhidos (`…&preco=acima200&cupom=1`).

   Os itens continuam numa linha só, abaixo do título, o que ainda é bem menos que as quatro linhas de antes. Mas o
   critério "a barra ocupa uma linha com o título" só está testado no estado padrão (`compacta.spec.ts:57`). O dono
   decide se aceita a quebra ou se quer rótulos mais curtos no item; em qualquer caso, convém um teste do pior caso.
3. **[Precisão] BUD-01 "< 153 270 B" sem asserção.** Só o gate de 150 KiB é automático. O valor de 153 245 B foi
   medido e registrado (folga de 25 B).
4. **[Precisão] Contraste AA do interruptor** (trilho `bg-suave`, bolinha branca, rótulo ao lado) não é testado.
   Fica para a revisão visual do dono.
5. **[Suposição] Tablet de 640 a 1023 px** passou a usar "Filtros" + painel, onde antes mostrava a barra larga.
   Isso segue o texto da spec, mas é uma mudança visível nessa faixa. A suposição está marcada como "n" na tabela
   do `spec.md`; o dono valida.

## Bloqueia o merge

- **Verificação real do dono:**
  - no computador: a home com a linha compacta; abrir e escolher cada filtro (Ordem, Público, Loja, Preço,
    Só com cupom, Limpar); Esc e clique fora; setas na faixa de descontos;
  - no celular: nada mudou (botão "Filtros" + painel, faixa arrastada com o dedo, sem setas);
  - **PageSpeed celular da home ≥ 90.**
- Lacuna 2: decisão do dono sobre a quebra da linha com filtros escolhidos (não bloqueia o PASS, que segue o critério da spec no estado padrão).
