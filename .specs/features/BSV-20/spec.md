# BSV-20 — Template HTML da página de oferta (estático, SEO-first)

Fonte: `docs/specs/BSV-20.md`. Contrato: `docs/CONTRATO.md` §2.3, §4, §5, §6, §7.1; `docs/MANIFEST.md` §1, §7.

## Problem Statement

A página `/oferta/{id}/` é HTML estático gerado pelo worker (AD-002). Falta o template que
transforma um `OfertaPagina` em página completa, indexável e leve, para oferta ativa e encerrada.
BSV-21 liga o template à geração; aqui entram só template, CSS, render e testes.

## Goals

- [ ] `TemplateOferta::renderizar(&OfertaPagina)` produz a página da spec, estável byte a byte.
- [ ] `cargo run --bin render-oferta -- fixture.json > out.html` para inspeção no browser.
- [ ] `besave.css` com as classes documentadas para BSV-30.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Geração em massa, gravação em `oferta/{id}/index.html`, sitemap | BSV-21 |
| `Area::Outros` no modelo do worker | BSV-13 (o template já conhece `OUTROS` pela tabela) |
| Placeholders `.webp` | BSV-13 |
| Header definitivo, design system, busca | BSV-30 |
| Botão copiar cupom, ofertas similares, comentários, compartilhamento | spec do ticket |
| Lighthouse | Dono, no browser (critério de aceite) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Motor de template | `minijinja` 2.x, sem features padrão (`builtins`, `serde`, `json`); template embutido com `include_str!`, `UndefinedBehavior::Strict` | Spec pede minijinja; `json` habilita `tojson` (escape seguro em `<script>`); embutido evita I/O por página em BSV-21 | n |
| Entrada do render | `&OfertaPagina` (tipo do worker), não JSON solto | BSV-21 já produz `OfertaPagina`; fixtures desserializam com `deny_unknown_fields` | n |
| Hora exibida | Horário de Brasília (UTC−3 fixo; sem horário de verão desde 2019): `12:40Z` → "publicada em 24/09/2026 às 09:40"; `<time datetime>` guarda o ISO UTC | O exemplo da spec repete o horário UTC da fixture; mostrar UTC ao público brasileiro erra em 3 h | n |
| Placeholder | `/img/placeholder/{slug}.webp` (slug da área, ex. `tech`, `meu-lar`) | MANIFEST §1 usa `{area}` como slug nos paths de área; BSV-13 deve gravar com o mesmo nome — alinhar no PR | n |
| Tabela única | `apps/worker/templates/areas.json` (áreas: valor, rótulo, slug; públicos: valor, slug; lojas: rótulo). Teste compara com a tabela markdown de CONTRATO §2.3 e com `enums.schema.json` | "Gerado a partir de §2.3" sem duplicar à mão: o teste falha se divergir | n |
| Rótulo da loja | Amazon, Shopee, Mercado Livre (na mesma tabela) | Contrato não define rótulo de loja | n |
| Imagem | `width="600" height="600"`, `object-fit: contain` em caixa quadrada | Robô entrega natural ≤ 1024 px com proporção variável (AD-031); caixa fixa evita layout shift | n |
| Faixa de preço | Posição `(por − min) × 100 ÷ (max − min)` em inteiro, limitada a 0..100 | `preco_por` pode estar fora de [min, max] | n |
| Validação HTML | `npx html-validate` sobre os goldens (script de dev, documentado), sem dependência Rust nova | Spec aceita "no teste ou script de dev" | n |
| Regenerar goldens | `cargo run --bin render-oferta -- <json> > tests/fixtures/paginas/<nome>.html` (manual) | Spec: comando documentado, não automático | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Página renderizada ⭐ MVP

**User Story**: Como visitante e como buscador, quero a página da oferta completa em HTML estático.

**Why P1**: É o entregável do ticket.

**Acceptance Criteria**:

1. WHEN `oferta-pagina-ok.json` é renderizado THEN the output SHALL ser igual byte a byte a `tests/fixtures/paginas/oferta-pagina-ok.html`.  <!-- PAG-01 -->
2. WHEN a variante encerrada é renderizada THEN the output SHALL ser igual byte a byte a `tests/fixtures/paginas/oferta-pagina-encerrada.html`.  <!-- PAG-02 -->
3. The `<head>` SHALL conter `<title>` = título + " | Besave", `description` = primeiros 155 caracteres da descrição do produto (ou do título), `canonical` e `og:url` = `https://besave.com.br/oferta/{id}/`, `og:title`, `og:description`, `og:image` = `https://besave.com.br/img/ofertas/{id}.webp`, stylesheet `/assets/besave.css` e viewport com `viewport-fit=cover`.  <!-- PAG-03 -->
4. The page SHALL conter JSON-LD `schema.org/Product` com `offers.@type = Offer`, `price` em reais decimal (`"199.90"`), `priceCurrency = BRL`, `availability` InStock (ativa) / Discontinued (encerrada) e `url` canônica.  <!-- PAG-04 -->
5. WHILE `status = ATIVA` the page SHALL não conter `noindex` e o CTA SHALL ser `<a href="/ir/{id}" rel="nofollow sponsored">`.  <!-- PAG-05 -->
6. WHILE `status = ENCERRADA` the page SHALL conter `<meta name="robots" content="noindex">`, `<body class="encerrada">`, faixa "Oferta expirada" logo após o `<h1>` e CTA sem `href` com `aria-disabled="true"`.  <!-- PAG-06 -->
7. The page SHALL ter cabeçalho com "Besave" → `/` e links `/{slug}/` para as 10 áreas de CONTRATO §2.3, e rodapé com links para `/{slug_area}/` e `/`.  <!-- PAG-07 -->
8. The imagem SHALL ser `/img/ofertas/{id}.webp` com `width`, `height`, `loading="eager"`, `alt` = título e `onerror` de uma linha para `/img/placeholder/{slug}.webp`; o `onerror` SHALL ser o único JavaScript da página.  <!-- PAG-08 -->
9. The bloco de preço SHALL mostrar `preco_de` riscado quando não nulo, `preco_por`, selo `-{desconto_pct}%` quando não nulo, rótulo da loja e "publicada em dd/mm/aaaa às hh:mm" (Brasília) renderizado no servidor.  <!-- PAG-09 -->
10. WHEN `cupom` não é nulo THEN the page SHALL mostrar o código numa caixa; WHEN nulo THEN nenhuma caixa.  <!-- PAG-10 -->
11. WHEN `nota` e `qt_avaliacoes` são ambos não nulos THEN the page SHALL mostrar a nota com 1 casa decimal e a quantidade; senão, nenhum bloco de avaliação.  <!-- PAG-11 -->
12. The `<dl>` de detalhes SHALL ter uma linha por campo não nulo (marca, fabricante, modelo, país, gênero, faixa etária) e nenhuma linha para nulos.  <!-- PAG-12 -->
13. WHEN `preco_min < preco_max` (ambos não nulos) THEN the page SHALL mostrar a faixa de preço com a posição em percentual; senão, nenhuma faixa.  <!-- PAG-13 -->
14. WHEN o título contém `<script>` THEN the page SHALL exibi-lo como texto escapado (inclusive dentro do JSON-LD).  <!-- PAG-14 -->
15. The page SHALL ter exatamente um `<h1>`.  <!-- PAG-15 -->

**Independent Test**: `cargo test --test template_oferta`.

---

### P1: Tabela de rótulos e CSS ⭐ MVP

**User Story**: Como BSV-30, quero uma tabela única de rótulos e um CSS com interface documentada.

**Why P1**: Evita rótulos duplicados e fixa o contrato de classes.

**Acceptance Criteria**:

1. The `areas.json` SHALL ter as 10 áreas na ordem do enum, com rótulo e slug iguais a CONTRATO §2.3, e os 4 públicos com slug em minúsculas.  <!-- TAB-01 -->
2. The HTML de `oferta-pagina-ok` SHALL ter ≤ 30 720 bytes e `besave.css` comprimido (Brotli) SHALL ter ≤ 20 480 bytes.  <!-- TAB-02 -->
3. The `apps/worker/templates/README.md` SHALL listar as classes e variáveis usadas pelo template.  <!-- TAB-03 -->

**Independent Test**: `cargo test --test template_oferta`.

---

### P2: Binário de desenvolvimento

**User Story**: Como dono, quero gerar `out.html` de uma fixture para abrir no browser.

**Why P2**: Inspeção visual e Lighthouse.

**Acceptance Criteria**:

1. WHEN `render-oferta <fixture.json>` roda THEN it SHALL imprimir no stdout o mesmo HTML de `TemplateOferta::renderizar`.  <!-- BIN-01 -->
2. IF o arquivo não existe ou não é `OfertaPagina` THEN it SHALL sair com código ≠ 0 e mensagem no stderr.  <!-- BIN-02 -->

**Independent Test**: `cargo test --test render_oferta`.

---

## Requirement Traceability

| Requirement ID | Story | Task | Status |
| -------------- | ----- | ---- | ------ |
| PAG-01 | P1: Página | T4 | Pending |
| PAG-02 | P1: Página | T4 | Pending |
| PAG-03 | P1: Página | T2 | Implemented |
| PAG-04 | P1: Página | T2 | Implemented |
| PAG-05 | P1: Página | T2 | Implemented |
| PAG-06 | P1: Página | T2 | Implemented |
| PAG-07 | P1: Página | T2 | Implemented |
| PAG-08 | P1: Página | T2 | Implemented |
| PAG-09 | P1: Página | T2 | Implemented |
| PAG-10 | P1: Página | T2 | Implemented |
| PAG-11 | P1: Página | T2 | Implemented |
| PAG-12 | P1: Página | T2 | Implemented |
| PAG-13 | P1: Página | T2 | Implemented |
| PAG-14 | P1: Página | T2 | Implemented |
| PAG-15 | P1: Página | T2 | Implemented |
| TAB-01 | P1: Tabela e CSS | T1 | Implemented |
| TAB-02 | P1: Tabela e CSS | T3 | Implemented |
| TAB-03 | P1: Tabela e CSS | T4 | Pending |
| BIN-01 | P2: Binário | T4 | Pending |
| BIN-02 | P2: Binário | T4 | Pending |

**Coverage:** 20 total, 20 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker`.
- [ ] `npx html-validate` sem erros nos dois goldens.
- [ ] Lighthouse mobile (dono): Performance ≥ 95, SEO ≥ 95, Acessibilidade ≥ 90.
