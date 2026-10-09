# BSV-33 · Site e worker: subpáginas de público, texto por área e páginas no sitemap

**Papel:** Frontend Svelte + Backend Rust · **Pasta:** `apps/site/` + `apps/worker/` (só o sitemap; os dois
dependem da mesma lista de slugs, CONTRATO §2.3) · **Depende de:** BSV-31 (mergeada).
CONTRATO.md §2.2, §2.3; MANIFEST.md §1, §6; AD-020, AD-041, AD-086, AD-088

## Contexto
As páginas `/{slug}/` existem (BSV-30b), mas não estão no sitemap e não têm texto próprio: para o Google
são um título e uma grade carregada por JavaScript. Ofertas ativas por área e público (08/10/2026):
Elas 18.626 (91% feminino), Meu Lar 5.021 (98% unissex), Esporte & vida 1.446, Tech 685, Outros 246,
Família 98, Pets 29, Cultura 20, Players 11, **Eles 0**. Metade das 40 combinações área × público tem menos
de 10 ofertas, e várias quase repetem a área inteira (`/elas/feminino/`, `/meu-lar/unissex/`).

## Objetivo
Cada área e cada combinação área × público tem página própria com texto curto; o sitemap lista a home, as
áreas com ofertas e só as subpáginas que têm volume e conteúdo diferente da área.

## Saídas
1. **Site, subpáginas `/{slug}/{publico}/`** (`publico` em minúsculas: `feminino`, `masculino`, `unissex`,
   `infantil`), prerenderizadas para as 40 combinações; slug ou público fora da lista → 404. Mesmo layout da
   área, com o público aplicado: `<h1>` "{Área} · {Público}", `<title>`, description e `canonical` próprios;
   breadcrumb visível (Início › Área › Público).
2. **Público vira caminho nas páginas de área:** em `/{slug}/` e `/{slug}/{publico}/`, os botões de público
   da barra de filtros (BSV-31) navegam para `/{slug}/{publico}/` (ou de volta a `/{slug}/` em "Todos"),
   mantendo os demais filtros na query. Na home, público continua `?publico=`. `/{slug}/?publico=x` redireciona
   no cliente para `/{slug}/x/` (com `replace`).
3. **Texto por área e subpágina** em `src/lib/conteudo/areas.ts`: 2–3 frases para cada uma das 10 áreas e uma
   frase para cada subpágina com volume (lista do item 4), em português simples, sem promessa de preço; o
   agente redige e o dono revisa no PR. O texto vai no HTML prerenderizado (não depende de JavaScript), abaixo
   do `<h1>`. Área sem ofertas mostra o texto e "Ainda não temos ofertas aqui" com links para outras áreas.
4. **JSON-LD `BreadcrumbList`** nas áreas e subpáginas.
5. **Worker, sitemap de páginas:** novo `sitemap-paginas.xml` no index (`sitemap.xml`), com:
   - `/` sempre;
   - `/{slug}/` das áreas com ≥ 10 ofertas ativas;
   - `/{slug}/{publico}/` com ≥ 20 ativas **e** ≤ 90% das ativas da área (hoje ~7 subpáginas);
   - `lastmod` = data (Brasília, AAAA-MM-DD) do maior `dp` entre as ativas da página.
   Limiares como constantes nomeadas. Só regravado quando o conteúdo muda (AD-041); os `sitemap-{n}.xml` de
   ofertas não mudam.

## Regras
1. Sem dependência nova. Bundle inicial da home continua ≤ 150 KiB (teste da BSV-31): texto e subpáginas
   ficam nas rotas de área, fora do bundle da home.
2. Nenhuma mudança no template da oferta nem nos dados do card.
3. `robots.txt` não muda; nenhuma página nova com `noindex` (a curadoria é feita pelo sitemap).
4. Testes nunca gravam no bucket de produção.

## Fora de escopo
Página de busca (BSV-34); textos longos ou por público em todas as 40 combinações; links de público na página
de oferta; ItemList/Product no JSON-LD das listas; classificar ofertas em "Eles" (robô).

## Critério de aceite
- Site (Playwright, 390 px e 1280 px): `/elas/masculino/` 200 com `<h1>`, `canonical` e breadcrumb, grade só
  ELAS + MASCULINO; `/elas/xyz/` e `/xyz/feminino/` → 404; em `/elas/`, tocar "Masculino" leva a
  `/elas/masculino/` mantendo `?loja=`; "Todos" volta a `/elas/`; `/elas/?publico=infantil` vai para
  `/elas/infantil/`; texto da área presente no HTML sem JavaScript (requisição direta); `/eles/` mostra o
  estado sem ofertas; JSON-LD válido.
- Worker (testes de unidade): com contagens sintéticas, o sitemap de páginas inclui a home, áreas ≥ 10, e
  exclui subpágina com 19 ativas, subpágina com 91% da área e área com 9; inclui subpágina com 20 e 90%;
  `lastmod` pelo maior `dp`; segundo ciclo sem mudança → 0 uploads de sitemap; XML válido.
- Gates: site `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`;
  worker `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`.
- **Real (dono):** depois do deploy do site e do `besave-ciclo` novo, `https://besave.com.br/sitemap.xml`
  lista `sitemap-paginas.xml`; ele tem a home, as áreas com ofertas e as subpáginas esperadas; enviar o
  sitemap no Search Console e conferir "Sucesso"; `/elas/masculino/` no celular.

## Definition of done
PR com os textos para revisão do dono, o `sitemap-paginas.xml` gerado com dados reais (no PR), prints de uma
subpágina, `validation.md` do Verifier independente, testes verdes.
