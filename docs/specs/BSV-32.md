# BSV-32 · Site: aviso de novas ofertas

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` · **Depende de:** BSV-30b (no ar).
**Roda em paralelo com a BSV-31; esta entra primeiro** (ver "Fronteira com a BSV-31").
MANIFEST.md §3.1 item 4; AD-063, AD-066, AD-067

## Contexto
A camada de dados (BSV-35) já faz polling do manifest a cada 5 min com a aba visível, guarda ids novos
como pendentes (fora da lista) e conta `novas()`; `confirmarNovas()` os coloca na lista. Falta a tela:
hoje a pessoa com a página aberta nunca vê ofertas que chegaram depois.

## Objetivo
Quando chegam ofertas novas com a página aberta, aparece um botão "N novas ofertas" no topo; ao tocar, elas
entram no início da lista e a página sobe até elas.

## Saídas
1. `lib/componentes/AvisoNovas.svelte`: botão fixo logo abaixo do topo (não cobre o cabeçalho), texto
   "1 nova oferta" / "N novas ofertas" (N = `novas()`, total pendente, AD-066), cor de destaque (laranja,
   texto branco), `aria-live="polite"`. Some quando N = 0.
2. Ao tocar: `confirmarNovas()`, rolagem suave até o início de "Mais recentes" (instantânea com
   `prefers-reduced-motion`), foco no título da seção.
3. **Título da aba:** "(N) " antes do título enquanto houver pendentes; volta ao normal ao confirmar.
4. Aparece na home e nas páginas de área (contando só as novas da área), não em `/desejos/` nem na 404.
5. Estado de "novas" (contagem reativa, confirmar) em `lib/vitrine.svelte.ts`, sem mudar a API do
   `lib/dados.ts`.

## Fronteira com a BSV-31 (para não conflitar)
- Esta PR cria `AvisoNovas.svelte`, mexe só nas partes de "novas" de `vitrine.svelte.ts` e acrescenta
  **uma linha** em `PaginaOfertas.svelte` para montar o aviso. Nada em `Grade`, filtros, ordens ou
  `lib/dados/`.
- Entra primeiro; a BSV-31 rebaseia em cima.

## Regras
1. Nada de fetch novo: usa o sincronizador existente (polling, aba visível, AD-062).
2. Expiradas e ids que só mudaram de preço não contam (AD-063).
3. Sem dependência nova.

## Fora de escopo
Notificação push, som, aviso com a aba em segundo plano além do título, filtros (BSV-31).

## Critério de aceite
- Vitest: contagem reativa acompanha `novas()`; confirmar zera e coloca os ids na lista; título com "(N) ".
- Playwright (390 px e 1280 px), com manifest e chunks fixos servidos pelo teste: primeira carga sem aviso;
  troca do manifest com 3 ids novos (1 expirado) e avanço do relógio do polling → "2 novas ofertas";
  tocar → os 2 cards no topo da grade, aviso some, título sem "(2)"; em `/elas/` com 2 novas de Meu Lar
  → nenhum aviso; em `/desejos/` → nenhum aviso; contraste AA do botão.
- Gates: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- **Real (dono):** deixar a home aberta no celular por 10–15 min com o robô publicando; o aviso aparece com
  o número certo; tocar mostra as novas no topo; o título da aba no computador mostra "(N)".

## Definition of done
PR com prints do aviso (celular e desktop), `validation.md` do Verifier independente, testes verdes.
