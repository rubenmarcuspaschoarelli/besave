# BSV-30b Specification — páginas de área e ajustes de desempenho

Fonte: `docs/specs/BSV-30b.md`. Escopo: `apps/site/`. CONTRATO §2.3; AD-020, AD-075, AD-078, AD-079.

## Problem Statement

Toda página de oferta (template do worker) linka o menu e "Mais ofertas de {Área}" para `/{slug}/`, e
essas páginas não existem: o visitante cai na 404. O PageSpeed aponta três ajustes baratos: fontes com
cache de 1 h (`/assets/fontes/`), CSS em `<link>` bloqueando a renderização e as primeiras fotos da grade
com `loading="lazy"`.

## Goals

- [ ] `/{slug}/` responde 200 para os 10 slugs do CONTRATO §2.3, com as ofertas da área no layout da home.
- [ ] Primeira pintura sem pedido de CSS nem de fonte com cache curto, sem mudar o desenho.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| `/{slug}/{publico}/`, texto de SEO por área, área no sitemap | BSV-33 |
| Filtros, ordens, faixa de preço | BSV-31 |
| Worker, template da oferta, infra, CI | spec, regras 1 e 4; os links `/{slug}/` passam a funcionar sozinhos |
| Execução real (deploy, `curl -I`, PageSpeed) | "Real (dono)" da spec |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Como a rota recusa slug fora da lista | Rota `src/routes/[area=area]/` com matcher em `src/params/area.ts` (aceita só os 10 slugs) + `entries` explícitas | Matcher faz o SvelteKit não casar a rota (404 no `preview`); no S3 não há arquivo e o CloudFront serve a 404 (AD-020) | y (spec: "slug fora da lista → 404, sem fallback") |
| `/?area=slug` da BSV-30 | Deixa de ser lido: a home sempre mostra todas | A spec troca o filtro no lugar por links; ninguém mais gera `?area=` (Areas passa a linkar `/{slug}/`) | n — proposto |
| Fontes das páginas do worker (`besave.css`) | `besave.css` também aponta para a Lato com hash em `/_app/immutable/assets/`; os `.woff2` de `static/assets/fontes/` saem do build; `OFL.txt` fica | Mesma fonte, um só arquivo publicado com cache de 1 ano. O deploy nunca apaga `assets/fontes/` do bucket (sem `--delete`), então HTML/CSS antigos em cache seguem achando a fonte; a limpeza de `_app/` tem carência de 7 dias (AD-079), maior que o cache do `besave.css` (1 h + swr 1 d) | n — proposto |
| Valor de `inlineStyleThreshold` | 32768 (CSS da página hoje 19.609 B brutos) | Folga de ~65% para o Tailwind crescer; teste de build falha se o CSS sair do HTML | y |
| Marcação do botão de área ativo | `<a aria-current="page">` com o mesmo visual do `aria-pressed` de hoje | Link não tem `aria-pressed`; `aria-current` é o atributo de navegação | y |
| "Mais recentes · {Área}" no `<h2>` | Removido; o `<h1>` visível "Ofertas de {Rótulo}" identifica a área | O span só existia para o filtro no lugar | y |
| Busca dentro da área | Mesmo campo do topo, filtra no lugar com `{ area }` | Spec: "busca da página filtra dentro dela" | y |
| Fixtura e2e | Títulos de MEU_LAR passam a conter "protetor" (`Protetor de colchão …`) | Hoje só ELAS tem "protetor": a busca em `/elas/` não discriminaria área | y |
| Imagens prioritárias | Só a grade "Mais recentes" (primeiras 4, inclusive em resultado de busca); faixa sempre `lazy` | Spec, saída 5 | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Página de área ⭐ MVP

**User Story**: Como visitante vindo de uma página de oferta, quero abrir `/{slug}/` e ver as ofertas daquela área, para continuar comprando nela.

**Acceptance Criteria**:

1. ARE-01: WHEN o build roda THEN o site SHALL gerar `{slug}/index.html` para exatamente os 10 slugs do CONTRATO §2.3 (`tech`, `players`, `meu-lar`, `elas`, `eles`, `cultura`, `familia`, `pets`, `esporte-vida`, `outros`) e nenhuma outra página nova.
2. ARE-02: WHEN `/{slug}/` é aberto THEN a página SHALL ter `<h1>` "Ofertas de {Rótulo}" em Lato, `<title>` "Ofertas de {Rótulo} · Besave", `<meta name="description">` não vazia citando o rótulo e `<link rel="canonical" href="https://besave.com.br/{slug}/">`.
3. ARE-03: The página de área SHALL NOT ter `<meta name="robots">` com `noindex`.
4. ARE-04: WHEN `/elas/` carrega o catálogo THEN a grade "Mais recentes" e a faixa "Maiores descontos de hoje" SHALL mostrar só cards de `a = ELAS`, e cada uma ao menos um card.
5. ARE-05: WHEN o visitante busca "protetor" em `/elas/` THEN os resultados SHALL ser só cards de ELAS cujo título contém o termo (e a home, com o mesmo termo, SHALL trazer cards de mais de uma área).
6. ARE-06: IF o path é `/{x}/` com `x` fora dos 10 slugs (ex.: `/xyz/`) THEN o servidor SHALL responder 404.
7. ARE-07: The página de área SHALL manter barra do canal, topo, ♡ e contador de favoritos, "Ver mais ofertas" e rodapé da home.

**Independent Test**: `pnpm build && pnpm e2e` — abrir `/elas/` e ver só ELAS.

### P1: Áreas como links ⭐ MVP

**User Story**: Como visitante, quero que os botões de área sejam links, para cada área ter URL própria.

**Acceptance Criteria**:

1. LNK-01: The navegação "Áreas" SHALL ter "Todas" como link para `/` e cada área visível como link para `/{slug}/`, em toda página que a mostra (home, área, desejos, 404).
2. LNK-02: WHEN o visitante clica em "Meu Lar" na home THEN o site SHALL ir para `/meu-lar/` com o link "Meu Lar" marcado `aria-current="page"` e só ele.
3. LNK-03: WHEN o visitante clica em "Todas" numa página de área THEN o site SHALL ir para `/` com "Todas" marcado `aria-current="page"`.
4. LNK-04: The link "Outros" SHALL existir só dentro do menu "Mais" e levar a `/outros/`; em `/outros/` o resumo "Mais ▾" SHALL ficar destacado.

**Independent Test**: e2e clicando nas pílulas.

### P1: Fontes com cache longo ⭐ MVP

**User Story**: Como dono, quero a Lato com nome de hash, para o CloudFront servir com cache de 1 ano.

**Acceptance Criteria**:

1. FNT-01: WHEN o build roda THEN os arquivos da Lato 700 e 900 SHALL sair em `build/_app/immutable/assets/` com hash no nome, e o CSS do site e o `besave.css` SHALL referenciá-los por `/_app/immutable/assets/…woff2`.
2. FNT-02: The build SHALL NOT conter `.woff2` em `assets/fontes/` (a licença `assets/fontes/OFL.txt` continua).
3. FNT-03: WHEN a home abre THEN a Lato 900 SHALL carregar de `/_app/immutable/assets/` e o logo e os títulos SHALL usar Lato (sem mudança de desenho).

### P1: CSS embutido ⭐ MVP

**User Story**: Como dono, quero o CSS da página no HTML, para não haver pedido de CSS bloqueando a renderização.

**Acceptance Criteria**:

1. CSS-04: WHEN o build roda THEN `index.html`, `{slug}/index.html`, `desejos/index.html` e `404.html` SHALL ter o CSS da página num `<style>` e nenhum `<link rel="stylesheet">`.
2. CSS-05: The tamanho do HTML da home SHALL ser medido antes/depois (bruto e gzip) e registrado no `validation.md`.

### P1: Imagem principal ⭐ MVP

**User Story**: Como visitante no celular, quero as primeiras fotos sem atraso, para o LCP cair.

**Acceptance Criteria**:

1. IMG-01: WHEN a grade "Mais recentes" renderiza THEN as 4 primeiras `<img>` SHALL não ter `loading="lazy"`, a primeira SHALL ter `fetchpriority="high"` e as outras três nenhum `fetchpriority`.
2. IMG-02: The quinta imagem em diante da grade e todas as da faixa SHALL ter `loading="lazy"` e nenhum `fetchpriority`.

---

## Edge Cases

- WHEN a área não tem oferta ativa THEN a página SHALL mostrar "Nenhuma oferta nesta área agora." (coberto pelo componente da home; sem teste novo).
- IF o manifest falha THEN a página de área SHALL mostrar o mesmo alerta da home (componente compartilhado).
- WHEN o visitante navega de `/elas/` para `/tech/` sem recarregar THEN busca e "Ver mais" SHALL voltar ao estado inicial (componente recriado por área).

## Implicit-requirement sweep (Medium)

- Falha externa (manifest/chunk): herdada da home, sem requisito novo.
- Cache/ciclo de vida: fontes com hash sob a carência de 7 dias do `_app/` (AD-079); arquivos antigos de `assets/fontes/` ficam no bucket.
- Remaining dimensions N/A for this scope (sem entrada de usuário além da busca já existente, sem auth, sem estado novo).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ARE-01 | P1: Página de área | Tasks | Pending |
| ARE-02 | P1: Página de área | Tasks | Pending |
| ARE-03 | P1: Página de área | Tasks | Pending |
| ARE-04 | P1: Página de área | Tasks | Pending |
| ARE-05 | P1: Página de área | Tasks | Pending |
| ARE-06 | P1: Página de área | Tasks | Pending |
| ARE-07 | P1: Página de área | Tasks | Pending |
| LNK-01 | P1: Áreas como links | Tasks | Pending |
| LNK-02 | P1: Áreas como links | Tasks | Pending |
| LNK-03 | P1: Áreas como links | Tasks | Pending |
| LNK-04 | P1: Áreas como links | Tasks | Pending |
| FNT-01 | P1: Fontes | Tasks | Pending |
| FNT-02 | P1: Fontes | Tasks | Pending |
| FNT-03 | P1: Fontes | Tasks | Pending |
| CSS-04 | P1: CSS embutido | Tasks | Pending |
| CSS-05 | P1: CSS embutido | Tasks | Pending |
| IMG-01 | P1: Imagem principal | Tasks | Pending |
| IMG-02 | P1: Imagem principal | Tasks | Pending |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Gates verdes: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- [ ] Bundle inicial ≤ 150 KB (JS + CSS da home); HTML da home com CSS embutido medido.
- [ ] Real (dono): 10 slugs 200 no ar, PageSpeed ≥ 90 na home e em `/elas/`, fonte com `max-age=31536000, immutable`.
