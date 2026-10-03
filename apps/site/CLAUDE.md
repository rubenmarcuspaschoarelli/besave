# apps/site — SvelteKit estático: home, áreas, busca

`adapter-static`. Lê `manifest.json` e chunks (MANIFEST.md §3.1). Não renderiza página de oferta — ela é HTML do worker.

## Regras
- Svelte 5 com runes (`$state`, `$derived`, `$effect`, `$props`). Sem stores legados, sem `export let`.
- Tailwind; sem CSS ad hoc. O build também emite `besave.css` compartilhado, consumido pelo template do worker — mudar classes usadas pelo template é mudança de contrato (avisar no PR).
- Lista virtualizada (`@tanstack/svelte-virtual`); imagens `loading="lazy"`, `width`/`height` fixos (sem layout shift).
- Novas ofertas nunca entram no topo sozinhas: toast "N novas ofertas" (MANIFEST.md §3.1 item 4).
- Preços em centavos → formatar com `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`.
- Fetch de dados só via um módulo (`lib/dados.ts`); componentes não fazem fetch.
- Rotas de área/público (`/elas/`, `/elas/feminino/`) prerender.
- Testes: Vitest para lógica (manifest diff, filtro, busca); Playwright para os fluxos da spec.

## Comandos
pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build

## Orçamentos
bundle inicial ≤ 150 KB · Lighthouse mobile ≥ 90 · scroll 60 fps com 500 cards
