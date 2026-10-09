# BSV-33 Specification — subpáginas de público, texto por área e páginas no sitemap

Fonte: `docs/specs/BSV-33.md`. Escopo: `apps/site/` + `apps/worker/` (só o sitemap). CONTRATO §2.2, §2.3;
MANIFEST §1, §6; AD-020, AD-041, AD-086, AD-088.

## Problem Statement

As páginas `/{slug}/` existem (BSV-30b), mas não estão no sitemap e, para o Google, são um título e uma
grade carregada por JavaScript. Não existem páginas por público, e o filtro de público só vive na query.

## Goals

- [ ] Cada área e cada combinação área × público tem página própria, com texto curto no HTML prerenderizado.
- [ ] O sitemap lista a home, as áreas com volume e só as subpáginas com volume e conteúdo diferente da área.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Página de busca | BSV-34 |
| Textos longos ou por público nas 40 combinações | spec |
| Links de público na página de oferta; ItemList/Product no JSON-LD | spec |
| Classificar ofertas em "Eles" | robô, fora do repo |
| `robots.txt`, template da oferta, dados do card | spec, regras 2 e 3 |
| Execução real (sitemap no bucket, Search Console, celular) | "Real (dono)" |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Título da subpágina | `<title>` "Ofertas de {Área} · {Público} · Besave"; `<h1>` "{Área} · {Público}" | `<h1>` vem da spec; `<title>` segue o padrão da área | y (dono, 09/10) |
| Breadcrumb visível na área | "Início › {Área}" também em `/{slug}/` | JSON-LD vale para as duas; mesma navegação | y (dono, 09/10) |
| Texto da subpágina sem frase própria | Só o texto da área | Spec: frase só para subpáginas com volume | y |
| Subpáginas com frase (dados de 08/10/2026, ativas) | `elas/unissex`, `meu-lar/feminino`, `esporte-vida/unissex`, `esporte-vida/feminino`, `esporte-vida/masculino`, `familia/infantil`, `familia/unissex` | Contagem dos chunks públicos com os limiares do item 5 | y (dados) |
| Estado vazio | Área ou subpágina com 0 ofertas no catálogo, sem busca e sem filtro: texto + "Ainda não temos ofertas aqui" + links para as outras áreas | Spec item 3 | y |
| `?publico=` em subpágina | Também redireciona para `/{slug}/{x}/` (o público da query vence e sai da query) | Mesma regra de `/{slug}/?publico=x` | y (dono, 09/10) |
| "Limpar filtros" na subpágina | Volta a `/{slug}/` sem query | "Todos" + padrão dos demais | y |
| Contagem "ativas" do sitemap | Cards publicados sem `x` (mesma base de `manifest.areas`) | CONTRATO §7 | y |
| Troca de público na área | Navegação com nova entrada no histórico e `reset: false` (rolagem e foco mantidos); só o redirect de `?publico=` usa `replace` | Trocar de público é trocar de página; o voltar do navegador volta ao público anterior | y (dono, 09/10) |
| Bundle da home (BUD-01) | Painel de filtros do celular em `PainelFiltros.svelte`, importado ao tocar em "Filtros" | Pedido do dono: sem aumentar o limite; 149,9 → 150,2 KiB com a T4 | y (dono) |
| Onde nasce o JSON-LD | `hooks.server.ts` (`transformPageChunk`) no prerender, com a mesma `trilha()` do cabeçalho | `{@html}` levava a home a 150,3 KiB e `<svelte:element>` a 155,2 KiB (runtime no chunk compartilhado); o hook custa 0 B no cliente. Na navegação no cliente o `<head>` mantém o JSON-LD da primeira página (crawler lê o HTML prerenderizado) | y (dono, 09/10) |
| `lastmod` da home sem ativas | Sem `<lastmod>` | Protocolo: `lastmod` é opcional | y (dono, 09/10) |
| Ordem no `sitemap-paginas.xml` | Home, depois cada área na ordem do enum seguida das suas subpáginas na ordem do enum `Publico` | Determinístico (AD-041) | y |
| Posição no index | `sitemap-paginas.xml` depois dos `sitemap-{n}.xml` | Index só muda de bytes quando muda de lista | y |

**Open questions:** none.

---

## User Stories

### P1: Subpáginas de público ⭐ MVP

1. SUB-01: WHEN `/{slug}/{publico}/` é pedido com slug das 10 áreas e público em {`feminino`, `masculino`, `unissex`, `infantil`} THEN o build SHALL ter a página prerenderizada (200) com `<h1>` "{Área} · {Público}", `<title>`, description e `canonical` `https://besave.com.br/{slug}/{publico}/` próprios.
2. SUB-02: IF o slug ou o público está fora da lista (`/elas/xyz/`, `/xyz/feminino/`) THEN a resposta SHALL ser 404.
3. SUB-03: The subpágina SHALL mostrar breadcrumb visível Início › {Área} › {Público}, com links para `/` e `/{slug}/`.
4. SUB-04: The grade da subpágina SHALL ter só cards da área e do público do caminho, e o botão do público SHALL aparecer marcado.

### P1: Público como caminho ⭐ MVP

1. PUB-01: WHEN, em `/{slug}/` ou `/{slug}/{publico}/`, a pessoa toca um público THEN o site SHALL navegar para `/{slug}/{publico}/` mantendo os demais filtros na query.
2. PUB-02: WHEN a pessoa toca "Todos" (ou "Limpar filtros") numa subpágina THEN o site SHALL navegar para `/{slug}/` (com os demais filtros, ou sem filtros na query no "Limpar"; parâmetros alheios como `q` e `utm_*` ficam, como na BSV-31).
3. PUB-03: WHEN `/{slug}/?publico=x` (x válido) é aberto THEN o site SHALL ir para `/{slug}/x/` por substituição (sem nova entrada no histórico), mantendo os demais parâmetros.
4. PUB-04: WHILE na home THE público SHALL continuar em `?publico=` (sem navegação).

### P1: Texto por área ⭐ MVP

1. TXT-01: The `src/lib/conteudo/areas.ts` SHALL ter 2–3 frases para cada uma das 10 áreas e uma frase para cada subpágina com volume (tabela acima).
2. TXT-02: The texto SHALL estar no HTML prerenderizado (sem JavaScript), abaixo do `<h1>`, nas áreas e subpáginas.
3. TXT-03: WHEN a área (ou subpágina) não tem ofertas e não há busca nem filtro THEN a página SHALL mostrar o texto e "Ainda não temos ofertas aqui" com links para outras áreas.
4. TXT-04: The texto e as subpáginas SHALL ficar fora do bundle inicial da home, que SHALL continuar ≤ 150 KiB (BUD-01 da BSV-31).

### P1: JSON-LD ⭐ MVP

1. JLD-01: The área e a subpágina SHALL ter um `<script type="application/ld+json">` `BreadcrumbList` válido (JSON, `@context` schema.org, `itemListElement` com `position` 1..n, `name` e `item` absoluto), no HTML prerenderizado.

### P1: Sitemap de páginas (worker) ⭐ MVP

1. SMP-01: The worker SHALL gerar `sitemap-paginas.xml` (XML válido, namespace sitemaps 0.9) e listá-lo em `sitemap.xml`.
2. SMP-02: The sitemap de páginas SHALL ter `/` sempre e `/{slug}/` das áreas com ≥ 10 ativas (área com 9 fica fora).
3. SMP-03: The sitemap de páginas SHALL ter `/{slug}/{publico}/` só com ≥ 20 ativas **e** ≤ 90% das ativas da área (20 e 90% entram; 19, ou 91%, ficam fora).
4. SMP-04: The `<lastmod>` de cada URL SHALL ser a data em Brasília (AAAA-MM-DD, −03:00) do maior `dp` entre as ativas da página (home: todas).
5. SMP-05: WHEN um segundo ciclo roda sem mudança THEN o worker SHALL fazer 0 uploads de sitemap; os `sitemap-{n}.xml` de ofertas não mudam de conteúdo.
6. SMP-06: The limiares SHALL ser constantes nomeadas.

---

## Edge Cases

- Expirada (`x:1`) não conta como ativa nem entra no `lastmod`.
- `dp` às 01:00Z é o dia anterior em Brasília (`lastmod` vira a data −03:00).
- Área com 0 ativas: fora do sitemap; página continua prerenderizada.

## Implicit-requirement sweep

- Persistência: hash do `sitemap-paginas.xml` no `_estado/paginas.json` (chave `sitemap*`, já suportada).
- Ordem de publicação: filhos antes do index (MANIFEST §6 passo 3).
- Demais dimensões N/A (sem auth, pagamento, concorrência nova).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SMP-01 | Sitemap | T2 | Done |
| SMP-02 | Sitemap | T1 | Done |
| SMP-03 | Sitemap | T1 | Done |
| SMP-04 | Sitemap | T1 | Done |
| SMP-05 | Sitemap | T2 | Done |
| SMP-06 | Sitemap | T1 | Done |
| SUB-01 | Subpáginas | T3 | Done |
| SUB-02 | Subpáginas | T3 | Done |
| SUB-03 | Subpáginas | T3 | Done |
| SUB-04 | Subpáginas | T3 | Done |
| PUB-01 | Público | T4 | Done |
| PUB-02 | Público | T4 | Done |
| PUB-03 | Público | T4 | Done |
| PUB-04 | Público | T4 | Done |
| TXT-01 | Texto | T5 | Done |
| TXT-02 | Texto | T5 | Done |
| TXT-03 | Texto | T5 | Done |
| TXT-04 | Texto | T5 | Done |
| JLD-01 | JSON-LD | T6 | Done |

**Coverage:** 19 total, 19 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Gates: site `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`; worker `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`.
- [ ] `sitemap-paginas.xml` gerado com dados reais no PR; prints de uma subpágina; tamanho final do bundle no PR.
- [ ] Real (dono): `sitemap.xml` no bucket lista `sitemap-paginas.xml`; Search Console "Sucesso"; `/elas/masculino/` no celular.
