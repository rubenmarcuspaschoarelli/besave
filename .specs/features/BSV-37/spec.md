# BSV-37 — Filtros compactos no computador e setas na faixa de descontos

Fonte: `docs/specs/BSV-37.md`. Pasta: `apps/site/`.

## Problem Statement

No computador, a barra de filtros da BSV-31 ocupa até quatro linhas de botões acima da grade e a faixa
"Maiores descontos de hoje" mostra a barra de rolagem do navegador. O bundle inicial da home está a
0,3 KiB do gate de 150 KiB.

## Goals

- [ ] ≥ 1024 px: título "Mais recentes" e todos os filtros numa linha; opções abertas sob demanda.
- [ ] Faixa de descontos sem barra de rolagem, com setas no computador.
- [ ] Bundle inicial da home ≤ 150 KiB e menor que 149,7 KiB (153 270 B).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Mudanças no celular (< 640 px) | spec: "sem mudança" |
| Novos filtros, nova URL | Regra 1: só a apresentação muda |
| Página de busca (BSV-34), página da oferta (BSV-38) | outros tickets |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Tablet 640–1023 px: hoje mostra a barra larga (sem botão "Filtros"); a spec diz "< 1024 px: sem mudança (botão Filtros + painel)" | < 1024 px usa botão "Filtros" + painel (o painel e o botão passam de `sm` para `lg`) | O parêntese da spec descreve o comportamento desejado; a barra larga de quatro linhas é o problema que o ticket resolve; "a linha compacta é o único código de filtro no carregamento inicial" | y (dono, 09/10) |
| Clique fora "devolve o foco ao item" | Devolve só se o clique não pôs o foco em outro elemento (campo de busca, link) | Não roubar o foco de onde o usuário clicou; Esc sempre devolve | y (dono, 09/10) |
| `Só com cupom` como interruptor | `button` com `aria-pressed`, desenhado como trilho + bolinha | Mesma semântica da BSV-31 (botão alternado); testes existentes leem `aria-pressed` | y (dono, 09/10) |
| Seta no início/fim | Some (`hidden`); se estava com foco, o foco vai para a seta oposta | Spec aceita "some ou desativa"; foco não se perde no `body` | y (dono, 09/10) |
| "Computador" na faixa | `(hover: hover) and (pointer: fine)`, sem largura mínima | Texto da spec | y |
| Contador "N ofertas" (`aria-live`) no computador | Continua no DOM só para leitor de tela (`sr-only`); o visível é "N de M ofertas" do título | Anúncio da mudança de filtro sem duplicar texto | y (dono, 09/10) |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Linha compacta de filtros no computador ⭐ MVP

**User Story**: Como visitante no computador, quero ordem e filtros numa linha com o título, abrindo as
opções só quando preciso, para ver a grade sem quatro linhas de botões.

**Acceptance Criteria**:

1. CMP-01: WHILE a largura é ≥ 1024 px the site SHALL mostrar na mesma linha do título "Mais recentes" os itens `Ordem: Recentes`, `Público`, `Loja`, `Preço`, `Só com cupom`, sem botão "Filtros" e sem nenhum botão de opção visível.
2. CMP-02: WHEN o visitante clica num item (`Público`, `Loja`, `Preço`, `Ordem`) THEN the site SHALL abrir logo abaixo da linha uma faixa com as opções daquele item e marcar o item `aria-expanded="true"` com `aria-controls` apontando para a faixa.
3. CMP-03: WHEN o visitante abre outro item com uma faixa aberta THEN the site SHALL fechar a anterior (uma faixa aberta por vez).
4. CMP-04: WHEN o visitante escolhe uma opção THEN the site SHALL aplicar o filtro (grade e URL iguais à BSV-31), fechar a faixa e mostrar no item `Nome: Valor` (`Público: Feminino`, `Preço: Até R$ 50`); sem escolha, só o nome.
5. CMP-05: WHEN o visitante tecla Esc com a faixa aberta THEN the site SHALL fechar a faixa e pôr o foco no item.
6. CMP-06: WHEN o visitante clica fora da linha e da faixa THEN the site SHALL fechar a faixa.
7. CMP-07: WHEN o visitante clica em `Só com cupom` THEN the site SHALL alternar o filtro de cupom (`?cupom=1`) e o `aria-pressed`.
8. CMP-08: WHILE há filtro ou ordem fora do padrão the site SHALL mostrar "Limpar filtros" na linha, e WHEN clicado THEN the site SHALL voltar ao padrão.
9. CMP-09: The site SHALL não baixar o código das faixas de opções antes do primeiro clique num item.
10. CMP-10: The site SHALL dar aos itens da linha altura ≥ 44 px e contorno de foco na cor `--cor-foco`.
11. CMP-11: WHILE numa página de área, WHEN o visitante escolhe um público na faixa THEN the site SHALL navegar pelo caminho (`/elas/masculino/`), como na BSV-33.

**Independent Test**: Playwright 1280 px em `e2e/compacta.spec.ts`.

### P1: Celular inalterado

1. CEL-01: WHILE a largura é < 640 px the site SHALL manter o comportamento da BSV-31 (testes de 390 px existentes passam com o mesmo fluxo).

### P1: Setas na faixa de descontos

**User Story**: Como visitante no computador, quero setas para percorrer a faixa de descontos, sem a barra de rolagem.

1. SET-01: The site SHALL não mostrar barra de rolagem na faixa (computador e celular).
2. SET-02: WHERE o ponteiro é fino e há hover, the site SHALL mostrar as setas "Ver descontos anteriores" e "Ver descontos seguintes" enquanto houver o que rolar naquele sentido; no início a anterior some, no fim a seguinte some.
3. SET-03: WHEN o visitante aciona uma seta (clique ou Tab + Enter) THEN the site SHALL rolar uma largura visível naquele sentido (limitada ao fim), instantâneo com `prefers-reduced-motion: reduce`.
4. SET-04: WHERE o ponteiro é de toque, the site SHALL não mostrar setas e a faixa SHALL rolar com o gesto de arrastar.

### P1: Bundle

1. BUD-01: The site SHALL manter o bundle inicial da home ≤ 150 KiB (teste existente) e menor que 153 270 B.

---

## Edge Cases

- IF a seta com foco some ao chegar na borda THEN the site SHALL pôr o foco na seta oposta.
- IF a faixa tem cards que cabem sem rolar THEN the site SHALL não mostrar seta nenhuma.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CMP-01 | P1: linha compacta | T1 | Verifying |
| CMP-02 | P1: linha compacta | T1 | Verifying |
| CMP-03 | P1: linha compacta | T1 | Verifying |
| CMP-04 | P1: linha compacta | T1 | Verifying |
| CMP-05 | P1: linha compacta | T1 | Verifying |
| CMP-06 | P1: linha compacta | T1 | Verifying |
| CMP-07 | P1: linha compacta | T1 | Verifying |
| CMP-08 | P1: linha compacta | T1 | Verifying |
| CMP-09 | P1: linha compacta | T1 | Verifying |
| CMP-10 | P1: linha compacta | T1 | Verifying |
| CMP-11 | P1: linha compacta | T1 | Verifying |
| CEL-01 | P1: celular | T1 | Verifying |
| SET-01 | P1: setas | T2 | Verifying |
| SET-02 | P1: setas | T2 | Verifying |
| SET-03 | P1: setas | T2 | Verifying |
| SET-04 | P1: setas | T2 | Verifying |
| BUD-01 | P1: bundle | T1, T2, T3 | Verifying |

**Coverage:** 17 total, 17 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` verdes.
- [ ] Bundle < 153 270 B.
