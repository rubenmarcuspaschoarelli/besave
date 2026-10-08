# BSV-31 · Site: filtros, ordens e faixa de preço

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` · **Depende de:** BSV-30b (no ar).
**Roda em paralelo com a BSV-32; esta entra depois** e rebaseia em cima dela.
CONTRATO.md §2, §3; AD-061, AD-064, AD-067, AD-074, AD-075

## Contexto
A home e as páginas de área mostram "Mais recentes" com busca e "Ver mais" (40 por vez). A camada de dados
já sabe filtrar por área, público e loja e ordenar por recentes, desconto e preço, mas a tela não oferece
isso. O dono decidiu: faixas de preço em botões, filtros guardados no endereço, sem virtualização.

## Objetivo
Na grade "Mais recentes" (home e áreas), a pessoa escolhe ordem, público, loja, faixa de preço e "só com
cupom"; a escolha fica no endereço e sobrevive a recarregar, compartilhar e ao botão voltar.

## Saídas
1. **Camada de dados** (`lib/dados/`): `Filtro` ganha `faixa?: 'ate50' | '50a100' | '100a200' | 'acima200'`
   (sobre `pp`, em centavos: ≤ 5000; 5001–10000; 10001–20000; > 20000) e `soComCupom?: boolean` (card com
   `c`). `lista` e `buscar` respeitam os dois. Testes de unidade de cada um.
2. **`BarraFiltros.svelte`** acima da grade:
   - Ordem: Recentes (padrão) · Maior desconto · Menor preço.
   - Público: Todos · Feminino · Masculino · Unissex · Infantil.
   - Loja: Todas · Amazon · Mercado Livre · Shopee.
   - Preço (botões): Até R$ 50 · R$ 50–100 · R$ 100–200 · Acima de R$ 200 (tocar de novo desmarca).
   - Só com cupom (alternar).
   - "Limpar filtros" quando houver algum ativo; contador "N ofertas" do resultado.
   - Celular: botão "Filtros" abre um painel (folha inferior) com as opções e "Ver N ofertas"; a ordem fica
     visível fora do painel. Desktop: tudo numa linha que quebra se precisar.
3. **Endereço:** `?ordem=desconto&publico=feminino&loja=amazon&preco=ate50&cupom=1` (valores em minúsculas;
   padrão não vai para a URL). Trocar filtro usa `replaceState`; abrir uma URL com filtros já aplica;
   valor inválido é ignorado. Busca continua como hoje (não vai para a URL; BSV-34).
4. Filtros valem para a grade "Mais recentes"; a faixa "Maiores descontos de hoje" não muda. "Ver mais"
   volta a 40 itens quando o filtro muda.
5. Estado vazio: "Nenhuma oferta com esses filtros" + "Limpar filtros".

## Fronteira com a BSV-32 (para não conflitar)
- Não mexer em `AvisoNovas.svelte` nem nas partes de "novas" de `vitrine.svelte.ts`.
- Em `PaginaOfertas.svelte`, mexer só no bloco da grade "Mais recentes" e no estado dos filtros.
- Rebase em `origin/develop` depois do merge da BSV-32, antes do push.

## Regras
1. Sem virtualização e sem dependência nova (decisão do dono).
2. Filtros não disparam fetch: tudo sobre o catálogo em memória.
3. Botões acessíveis: `aria-pressed`, área de toque ≥ 44 px, foco visível, contraste AA.
4. Orçamentos: bundle inicial ≤ 150 KB; trocar um filtro com 30 mil cards ≤ 50 ms (mediana, teste de unidade
   com aquecimento, lição 15).

## Fora de escopo
Página de busca e busca na URL (BSV-34), subpáginas de público e SEO (BSV-33), faixa de preço livre, aviso de
novas (BSV-32), mostrar expiradas na grade.

## Critério de aceite
- Vitest: `faixa` nas quatro fronteiras (5000/5001, 10000/10001, 20000/20001); `soComCupom`; combinação de
  filtros com ordem; leitura e escrita da URL (padrão fora da URL, inválido ignorado); tempo ≤ 50 ms.
- Playwright (390 px e 1280 px): "Maior desconto" ordena a grade; "Shopee" só mostra Shopee; "Até R$ 50" só
  preços ≤ R$ 50; "Só com cupom" só cards com cupom; combinação Feminino + Amazon; URL reflete a escolha;
  recarregar mantém; voltar do navegador restaura; abrir `/elas/?loja=shopee` já filtrado; "Limpar" volta ao
  padrão e limpa a URL; estado vazio; painel "Filtros" no celular abre, aplica e fecha.
- Gates: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- **Real (dono):** no ar, combinar filtros em `/elas/` no celular; compartilhar um link filtrado e abrir em
  outro aparelho; PageSpeed celular da home ≥ 90 nas quatro categorias.

## Definition of done
PR com prints (celular com o painel aberto, desktop com filtros), `validation.md` do Verifier independente,
testes verdes.
