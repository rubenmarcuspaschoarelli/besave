# BSV-37 · Site: filtros compactos no computador e setas na faixa de descontos

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` · **Depende de:** BSV-33 (mergeada).
Roda em paralelo com a BSV-38 (que mexe só em `src/lib/estilo/besave.css` do site).
AD-075, AD-086, AD-088; WORKFLOW lições 15, 17, 19

## Contexto
No computador, a barra de filtros da BSV-31 ocupa até quatro linhas de botões acima de "Mais recentes" e
polui a página (no celular, o botão "Filtros" e o painel funcionam bem e não mudam). A faixa "Maiores
descontos de hoje" mostra a barra de rolagem do navegador no computador. O bundle inicial da home está em
149,7 KiB, a 0,3 KiB do gate de 150 KiB.

## Objetivo
No computador, ordem e filtros cabem na mesma linha do título "Mais recentes" e abrem as opções sob demanda;
a faixa de descontos navega por setas. O carregamento inicial da home não cresce (de preferência, diminui).

## Saídas
1. **Linha compacta (≥ 1024 px)** na altura do título: `Mais recentes · N de M ofertas` à esquerda e, à direita,
   `Ordem: Recentes ▾`, `Público ▾`, `Loja ▾`, `Preço ▾` e um interruptor estilizado `Só com cupom`.
   - Cada item é um botão de divulgação (`aria-expanded`, `aria-controls`). Ao clicar, abre **uma faixa logo
     abaixo da linha** com as opções daquele item (os mesmos botões de hoje); só uma faixa aberta por vez.
   - Ao escolher uma opção, a faixa fecha e o item mostra o valor (`Público: Feminino`, `Preço: Até R$ 50`);
     sem escolha, mostra só o nome. Clicar de novo no item reabre.
   - Esc ou clique fora fecha a faixa e devolve o foco ao item. "Limpar filtros" aparece na linha quando houver
     filtro ativo.
   - Nas páginas de área/subpágina, o público continua navegando pelo caminho (BSV-33).
2. **Celular e tablet (< 1024 px):** sem mudança (botão "Filtros" + painel da BSV-31).
3. **Carregamento sob demanda:** as faixas de opções são carregadas só no primeiro clique (como o painel do
   celular). A linha compacta é o único código de filtro no carregamento inicial.
4. **Faixa "Maiores descontos de hoje":**
   - Computador (`hover` e ponteiro fino): barra de rolagem oculta; setas ‹ › nas laterais, que rolam uma
     largura visível por clique (suave; instantâneo com `prefers-reduced-motion`); a seta some (ou fica
     desativada) no início e no fim; acessíveis por teclado com rótulo ("Ver descontos anteriores/seguintes").
   - Celular: arrastar com o dedo, sem barra visível; sem setas.

## Regras
1. Sem dependência nova. Estado dos filtros e URL (`?ordem=…`) iguais à BSV-31: só a apresentação muda.
2. Gate do bundle inicial ≤ 150 KiB brutos continua no CI; registrar no PR o valor antes/depois.
3. Contraste AA, foco visível, área de clique ≥ 44 px também nos itens da linha.
4. Testes de tempo por último e sem carga (lição 17); o autor olha os prints antes da PR (lição 19).

## Fora de escopo
Mudanças no celular, novos filtros, página de busca (BSV-34), página da oferta (BSV-38).

## Critério de aceite
- Playwright 1280 px: a barra de filtros ocupa uma linha com o título; clicar `Público ▾` abre a faixa com as
  opções; escolher `Feminino` fecha a faixa, mostra `Público: Feminino` e filtra a grade; abrir `Loja ▾` fecha
  a faixa de público; Esc fecha e devolve o foco; clique fora fecha; `Só com cupom` liga e desliga; URL igual à
  da BSV-31; "Limpar filtros" volta ao padrão; nada da faixa de opções é baixado antes do primeiro clique.
- Playwright 390 px: comportamento da BSV-31 inalterado (testes existentes passam sem mudança).
- Faixa de descontos 1280 px: sem barra de rolagem visível; seta › rola e a ‹ aparece; no fim a › some/desativa;
  teclado (Tab + Enter) funciona. 390 px: sem setas, rola com toque.
- Bundle inicial da home ≤ 150 KiB (teste do CI) e, se possível, menor que 149,7 KiB.
- Gates: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- **Real (dono):** no computador, a home com a linha compacta; abrir e escolher cada filtro; setas na faixa;
  no celular, nada mudou; PageSpeed celular da home ≥ 90.

## Definition of done
PR com prints 1280 px (linha fechada, faixa aberta, valor escolhido) e 390 px, tamanho do bundle antes/depois,
`validation.md` do Verifier independente, testes verdes.
