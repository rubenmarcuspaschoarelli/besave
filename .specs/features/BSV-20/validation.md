# BSV-20 Validation

**Verdict**: PASS ✅ (20/20 ACs com evidência; 21 testes do ticket verdes; sensor 22/22 mutantes mortos; Lighthouse mobile da página ativa 100/100/100 em Performance/Acessibilidade/SEO)

**Date**: 2026-09-26
**Spec**: `.specs/features/BSV-20/spec.md` + `docs/specs/BSV-20.md`
**Diff range**: `60b0ab4..f45940b` (6 commits: spec `44411a0`, T1 `9c09765`, T2 `c0ddc4b`, T3 `5c3ecbe`, T4 `6dbc8f9`, T5 `f45940b`; arquivos só em `apps/worker/` e `.specs/features/BSV-20/`)
**Verifier**: passe independente pelo fallback da skill (sem sub-agente nesta sessão), com sensor de discriminação em worktree temporário

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `areas.json` + `pagina_html` | ✅ Done | `9c09765` |
| T2 template completo | ✅ Done | `c0ddc4b` |
| T3 `besave.css` + orçamentos | ✅ Done | `5c3ecbe` |
| T4 `render-oferta`, goldens, README | ✅ Done | `6dbc8f9` |
| T5 grade sem overflow a 360 px | ✅ Done | `f45940b` (achado da inspeção visual) |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| PAG-01 golden ativa | render de `oferta-pagina-ok.json` == golden | `apps/worker/tests/template_oferta.rs:142` - `assert_eq!(html, golden("oferta-pagina-ok.html"))` | ✅ PASS |
| PAG-02 golden encerrada | render da variante encerrada == golden | `apps/worker/tests/template_oferta.rs:150` - `status == Encerrada` e `assert_eq!(render(&o), golden(...encerrada.html))` | ✅ PASS |
| PAG-03 head | title, description 155, canonical, og:*, CSS, viewport | `apps/worker/tests/template_oferta.rs:158` (literais completos); `:183` - 155 × `x` e 155 × `é`, fallback para o título sem produto | ✅ PASS |
| PAG-04 JSON-LD | Product/Offer, `price` "199.90", BRL, InStock/Discontinued, url canônica | `apps/worker/tests/template_oferta.rs:212` - parse com `serde_json`, campos um a um; `"0.05"`, `"1234.56"` | ✅ PASS |
| PAG-05 ativa | sem `noindex`; CTA `/ir/5412` `nofollow sponsored` | `apps/worker/tests/template_oferta.rs:243` - tag CTA literal; `<body>` sem classe | ✅ PASS |
| PAG-06 encerrada | `noindex`, `body.encerrada`, faixa após `h1`, CTA sem `href` + `aria-disabled` | `apps/worker/tests/template_oferta.rs:256`; template `apps/worker/templates/oferta.html:12`, `:38`, `:57` | ✅ PASS |
| PAG-07 cabeçalho/rodapé | 10 áreas de §2.3 por slug; rodapé área + home | `apps/worker/tests/template_oferta.rs:275` - compara com a tabela lida de `docs/CONTRATO.md`; `MEU_LAR` → `/meu-lar/` | ✅ PASS |
| PAG-08 imagem e JS | src, width/height, eager, alt, onerror → placeholder por slug; único JS | `apps/worker/tests/template_oferta.rs:298` - 1 `<script>` (ld+json), 1 handler `onerror`, sem `javascript:` | ✅ PASS |
| PAG-09 preço | de riscado, por, selo, loja, data em Brasília | `apps/worker/tests/template_oferta.rs:331` - `24/09/2026 às 09:40`; viradas de dia/mês/ano; `R$ 1.299,90`; Mercado Livre/Shopee | ✅ PASS |
| PAG-10 cupom | caixa só com cupom | `apps/worker/tests/template_oferta.rs:365` | ✅ PASS |
| PAG-11 avaliação | só com nota **e** quantidade; 1 casa | `apps/worker/tests/template_oferta.rs:377` - `4,6`, `4,0`, ausência com cada um nulo | ✅ PASS |
| PAG-12 ficha | linha só para não nulo/vazio; sem `<dl>` vazio | `apps/worker/tests/template_oferta.rs:396`; template `apps/worker/templates/oferta.html:74` | ✅ PASS |
| PAG-13 faixa | só com `min < max`; posição % limitada a 0..100 | `apps/worker/tests/template_oferta.rs:450` - `left:11%`, `0%`, `50%`, `100%`; ausente com igual, invertido e nulos | ✅ PASS |
| PAG-14 escape | `<script>` no título vira texto, inclusive no JSON-LD | `apps/worker/tests/template_oferta.rs:478` - 1 `</script>`; `h1` escapado literal; JSON-LD reparseado igual ao original | ✅ PASS |
| PAG-15 um h1 | exatamente um `<h1>` | `apps/worker/tests/template_oferta.rs:496` | ✅ PASS |
| TAB-01 tabela | 10 áreas iguais a §2.3 na ordem do enum; públicos minúsculos; lojas = enum | `apps/worker/tests/template_oferta.rs:75` | ✅ PASS |
| TAB-02 orçamentos | HTML ≤ 30 720 B; CSS br ≤ 20 480 B | `apps/worker/tests/template_oferta.rs:504` (HTML 3 688 B); `:520` classes do template têm regra no CSS | ✅ PASS |
| TAB-03 README | classes e variáveis para BSV-30 | `apps/worker/templates/README.md:27` (variáveis), `:48` (classes) | ✅ PASS (revisão) |
| BIN-01 binário | stdout == `renderizar` | `apps/worker/tests/render_oferta.rs:24` | ✅ PASS |
| BIN-02 erro | código ≠ 0 e mensagem | `apps/worker/tests/render_oferta.rs:40` - arquivo inexistente, chunk, sem argumento | ✅ PASS |

---

## Discrimination Sensor

Worktree temporário em `HEAD` (`git worktree add --detach`), `CARGO_TARGET_DIR` compartilhado; cada mutante aplicado, `cargo test --test template_oferta --test render_oferta`, arquivo restaurado. Worktree removido; `git status --porcelain` igual ao baseline.

| # | Mutante | Resultado |
| - | ------- | --------- |
| M01 | `noindex` na ativa em vez da encerrada | morto |
| M02 | `rel="nofollow"` sem `sponsored` | morto |
| M03 | description com 150 caracteres | morto |
| M04 | faixa com `<=` | morto |
| M05 | sem limite inferior 0% | morto |
| M06 | `<dl>` sem filtro de nulos | morto |
| M07 | `availability` sempre InStock | morto |
| M08 | hora em UTC | morto |
| M09 | sem separador de milhar | morto |
| M10 | caixa de cupom sempre | morto |
| M11 | avaliação com `or` | morto |
| M12 | `<` sem escape | morto |
| M13 | slug divergente em `areas.json` | morto |
| M14 | `og:image` apontando para `-small` | morto |
| M15 | centavos sem zero à esquerda no `price` | morto |
| M16 | regra `.cupom` removida do CSS | morto |
| M17 | CTA encerrado com `href` | morto |
| M18 | faixa "Oferta expirada" removida | morto |
| M19 | placeholder pelo valor do enum | morto |
| M20 | binário imprime no stderr | morto |
| M21 | description sem fallback para o título | morto |
| M22 | `<body>` sem classe `encerrada` | morto |

**22/22 mortos.**

---

## Gate

- `cargo fmt --check` e `cargo clippy --all-targets -- -D warnings`: verdes.
- `cargo test --test template_oferta --test render_oferta`: 21/21.
- `cargo test --no-fail-fast` (suíte inteira): 62 falhas **pré-existentes em `develop`**, todas por `unknown variant OUTROS` ao carregar `packages/contract/mapeamento.json` (contrato 1.3 adicionou `OUTROS`; `Area::Outros` no worker é escopo de BSV-13). Nenhum arquivo do contrato foi alterado nesta branch. O job `rust` do CI fica vermelho até BSV-13 entrar.
- `npx html-validate tests/fixtures/paginas/*.html` (`.htmlvalidate.json`): sem erros.

## Evidência manual (DoD)

- Screenshots (puppeteer-core + Chrome 153, `isMobile` a 360 px e desktop a 1280 px), ativa e encerrada: `scrollWidth == clientWidth` nas quatro; a 1280 px o painel fica à direita da foto.
- Lighthouse 12, mobile, servido local com gzip, URL do antivírus local (injeção de 212 KB) bloqueada:
  - ativa `/oferta/5412/`: Performance 100 · Acessibilidade 100 · Best Practices 79 · SEO 100 (FCP/LCP 1,3 s, TBT 0 ms, CLS 0)
  - encerrada `/oferta/5413/`: Performance 100 · Acessibilidade 100 · Best Practices 79 · SEO 66 (`is-crawlable`: `noindex` exigido pela spec)
  - Best Practices 79 = HTTP local (`is-on-https`) + erro de console da request bloqueada; some em HTTPS no CloudFront.
