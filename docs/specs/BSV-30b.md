# BSV-30b · Site: páginas de área e ajustes de desempenho

**Papel:** Frontend Svelte · **Pasta:** `apps/site/` · **Depende de:** BSV-30 (no ar), BSV-17 (deploy).
CONTRATO.md §2.3; MANIFEST.md §1, §4; AD-020, AD-075, AD-078, AD-079

## Contexto
O site novo está no ar (PageSpeed celular: Desempenho 98). Dois problemas apareceram no uso real:
1. A página de oferta (template do worker) linka o menu e "Mais ofertas de {Área}" para `/{slug}/`, mas
   essas páginas eram da BSV-33 e não existem: o visitante cai na 404. Toda página de oferta tem esses links.
2. O PageSpeed aponta três ajustes baratos: fontes com cache de 1 h, CSS bloqueando a renderização e a
   imagem principal da grade com `loading="lazy"`.

## Objetivo
`/{slug}/` existe para as 10 áreas, mostrando as ofertas da área no mesmo layout da home; e o primeiro
carregamento fica mais rápido sem mudar o desenho.

## Saídas
1. **Rota de área** prerenderizada para os 10 slugs do CONTRATO §2.3 (`entries` explícitas; slug fora da
   lista → 404, sem fallback, AD-020). Mesmo layout da home, com:
   - `<h1>` "Ofertas de {Rótulo}" (Lato), `<title>` "Ofertas de {Rótulo} · Besave",
     `<meta name="description">` curta e `<link rel="canonical" href="https://besave.com.br/{slug}/">`;
     indexável (sem `noindex`);
   - "Maiores descontos de hoje" e "Mais recentes" filtrados pela área; busca da página filtra dentro dela;
   - botão de área ativo; "Outros" tem página (`/outros/`), mas o botão continua só no menu "Mais".
2. **Botões de área viram links** (`/` para "Todas", `/{slug}/` para cada área), na home e nas páginas de
   área, em vez de filtrar no lugar. Favoritos, barra do canal e rodapé iguais.
3. **Fontes com cache longo:** a Lato entra pelo CSS/import do build (nome com hash em `_app/immutable/`,
   cache de 1 ano); remover as cópias de `static/assets/fontes/` que deixarem de ser usadas.
4. **CSS inline:** `kit.inlineStyleThreshold` com valor que embuta o CSS da página (hoje ~5 KB gzip,
   ~20 KB bruto) no HTML; medir antes/depois.
5. **Imagem principal:** as 4 primeiras fotos da grade "Mais recentes" sem `loading="lazy"`; a primeira com
   `fetchpriority="high"`. As demais e a faixa continuam `lazy`.

## Regras
1. Nenhuma mudança no worker nem no template da oferta: os links `/{slug}/` passam a funcionar sozinhos.
2. Nenhuma dependência nova.
3. Orçamentos da BSV-30 continuam: bundle inicial ≤ 150 KB; Lighthouse mobile ≥ 90 nas quatro categorias.
4. Os prefixos `{slug}/*` já estão na policy do deploy (BSV-17); nada muda na infra.

## Fora de escopo
Subpáginas de público (`/{slug}/{publico}/`), texto de SEO por área e área no sitemap (BSV-33);
filtros, ordens e faixa de preço (BSV-31).

## Critério de aceite
- Playwright (390 px e 1280 px): os 10 `/{slug}/` respondem 200 com o `<h1>` certo e `canonical`;
  `/elas/` só mostra cards de ELAS (grade e faixa); `/xyz/` → 404; clicar em "Meu Lar" na home leva a
  `/meu-lar/` com o botão ativo; "Todas" volta a `/`; busca em `/elas/` não traz cards de outra área.
- Build: a fonte sai em `_app/immutable/**` com hash; o HTML da home tem o CSS embutido (sem
  `<link rel="stylesheet">` para o CSS da página); as 4 primeiras imagens da grade sem `loading="lazy"` e a
  primeira com `fetchpriority="high"`.
- Gates: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- **Real (dono):** depois do deploy, `curl -I https://besave.com.br/{slug}/` → 200 nos 10 slugs; numa página
  de oferta, "Mais ofertas de {Área}" e o menu abrem a área com ofertas; PageSpeed celular da home e de
  `/elas/` ≥ 90 nas quatro categorias (prints); a fonte responde com `max-age=31536000, immutable`.

## Definition of done
PR com prints de `/elas/` (celular e desktop), PageSpeed antes/depois, `validation.md` do Verifier
independente, testes verdes.
