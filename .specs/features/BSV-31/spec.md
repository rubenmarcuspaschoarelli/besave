# BSV-31 Specification — filtros, ordens e faixa de preço

Fonte: `docs/specs/BSV-31.md`. Escopo: `apps/site/`. CONTRATO §2, §3; AD-061, AD-064, AD-067, AD-074, AD-075.

## Problem Statement

A home e as páginas de área mostram "Mais recentes" com busca e "Ver mais" (40 por vez). A camada de dados
já filtra por área, público e loja e ordena por recentes, desconto e preço, mas a tela não oferece isso, e
não há filtro por faixa de preço nem por cupom.

## Goals

- [ ] Na grade "Mais recentes" (home e áreas) a pessoa escolhe ordem, público, loja, faixa de preço e "só com cupom".
- [ ] A escolha fica no endereço e sobrevive a recarregar, compartilhar e ao botão voltar.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Página de busca, `q` escrito na URL | BSV-34 |
| `/{slug}/{publico}/`, SEO de público | BSV-33 |
| Faixa de preço livre, mostrar expiradas na grade | spec, fora de escopo |
| Aviso de novas (`AvisoNovas.svelte`, partes de "novas" da vitrine) | BSV-32 (fronteira) |
| Virtualização, dependência nova | spec, regra 1 |
| Execução real (celular, link compartilhado, PageSpeed) | "Real (dono)" da spec |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Valor de URL de `MERCADO_LIVRE` | `loja=mercado-livre` | "Valores em minúsculas"; hífen como nos slugs de área (`meu-lar`, `esporte-vida`) | n — proposto |
| Valor de URL de "Menor preço" | `ordem=preco` (= `Ordem` da camada de dados) | Exemplo da spec usa `ordem=desconto`, mesmo nome da `Ordem` | y |
| Escrita na URL | `goto(u, { shallow: true, replace: true })` do SvelteKit 3 | `history.replaceState` direto conflita com o roteador (aviso do SvelteKit); `replaceState` de `$app/navigation` está `@deprecated` no SvelteKit 3 | y (código do kit 3.0.0) |
| Parâmetros alheios (`q`, `utm_*`) | Preservados; só `ordem`, `publico`, `loja`, `preco`, `cupom` são escritos ou apagados | Busca continua como hoje; links do canal levam `utm_source` | y |
| Filtros na busca | Valem também para os resultados da busca, que ocupam o lugar da grade | Spec: "`lista` e `buscar` respeitam os dois"; busca já usa o `Filtro` | y |
| Painel do celular | `<dialog>` modal (folha inferior), filtros aplicam ao tocar; "Ver N ofertas" fecha | `<dialog>` dá foco preso e Esc sem dependência; contagem ao vivo permite o "Ver N" | y |
| Corte celular/desktop | `sm` (640 px) do Tailwind | Mesmo corte das outras telas | y |
| Contador | "N ofertas" na barra (total do resultado); o "X de Y" do título continua | Spec pede contador na barra; "X de Y" já existe para o "Ver mais" | y |
| "Limpar filtros" e ordem | Aparece quando ordem **ou** algum filtro difere do padrão; volta os dois ao padrão. O estado vazio (BAR-08) depende só dos filtros | Spec: "Limpar volta ao padrão e limpa a URL"; ordem não esvazia a grade | y |
| Navegar para outra área | Filtros voltam ao padrão (componente recriado por área, como hoje) | Os links de área não levam a query | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Faixa de preço e cupom na camada de dados ⭐ MVP

**User Story**: Como site, quero filtrar o catálogo em memória por faixa de preço e por cupom, para a tela não precisar de fetch.

**Acceptance Criteria**:

1. DAD-01: WHEN `Filtro.faixa` é `ate50` THEN `lista` e `buscar` SHALL devolver só cards com `pp ≤ 5000`; `50a100` → `5001 ≤ pp ≤ 10000`; `100a200` → `10001 ≤ pp ≤ 20000`; `acima200` → `pp > 20000` (fronteiras 5000/5001, 10000/10001, 20000/20001).
2. DAD-02: WHEN `Filtro.soComCupom` é `true` THEN `lista` e `buscar` SHALL devolver só cards com `c`; ausente ou `false` não filtra.
3. DAD-03: WHEN filtros se combinam com uma ordem THEN `lista` SHALL devolver a interseção de todos, na ordem pedida.
4. DAD-04: WHEN um filtro muda com 30 mil cards no catálogo THEN `lista` SHALL responder em ≤ 50 ms (mediana de 5, após aquecimento).

### P1: Filtros no endereço ⭐ MVP

**User Story**: Como visitante, quero que o link guarde os filtros, para recarregar, compartilhar e voltar sem perdê-los.

**Acceptance Criteria**:

1. URL-01: WHEN a URL tem `ordem`, `publico`, `loja`, `preco`, `cupom` válidos (minúsculas) THEN a leitura SHALL produzir o filtro correspondente.
2. URL-02: IF um valor é inválido (ex.: `loja=xyz`, `cupom=0`, `ordem=recentes` em maiúsculas) THEN a leitura SHALL ignorá-lo (fica o padrão) sem afetar os outros.
3. URL-03: WHEN o filtro é escrito THEN valores padrão (ordem recentes, todos, sem faixa, sem cupom) SHALL ficar fora da URL, outros parâmetros (`q`, `utm_*`) SHALL ser preservados e a URL sem parâmetros SHALL não ter `?`.
4. URL-04: WHEN a pessoa troca um filtro THEN o endereço SHALL mudar por substituição (sem nova entrada no histórico).
5. URL-05: WHEN uma URL com filtros é aberta, recarregada ou volta pelo navegador THEN a grade SHALL já vir filtrada e os botões marcados.

### P1: Barra de filtros ⭐ MVP

**User Story**: Como visitante, quero botões de ordem, público, loja, preço e cupom acima da grade, para achar a oferta certa.

**Acceptance Criteria**:

1. BAR-01: The barra SHALL oferecer Ordem (Recentes padrão · Maior desconto · Menor preço), Público (Todos · Feminino · Masculino · Unissex · Infantil), Loja (Todas · Amazon · Mercado Livre · Shopee), Preço (Até R$ 50 · R$ 50–100 · R$ 100–200 · Acima de R$ 200) e "Só com cupom", cada botão com `aria-pressed` refletindo o estado.
2. BAR-02: WHEN um botão de preço marcado é tocado de novo THEN a faixa SHALL ser desmarcada; "Só com cupom" alterna.
3. BAR-03: WHEN "Maior desconto" / "Shopee" / "Até R$ 50" / "Só com cupom" / Feminino + Amazon são escolhidos THEN a grade SHALL mostrar só cards que casam, na ordem escolhida.
4. BAR-04: WHILE algum filtro difere do padrão THE barra SHALL mostrar "Limpar filtros", que volta tudo ao padrão e tira os parâmetros da URL.
5. BAR-05: The barra SHALL mostrar "N ofertas" com o total do resultado.
6. BAR-06: WHEN o filtro muda THEN o "Ver mais" SHALL voltar a 40 itens.
7. BAR-07: The faixa "Maiores descontos de hoje" SHALL NOT mudar com os filtros.
8. BAR-08: IF nenhum card casa com os filtros THEN a grade SHALL dar lugar a "Nenhuma oferta com esses filtros" e um botão "Limpar filtros".
9. BAR-09: The botões SHALL ter área de toque ≥ 44 px de altura e foco visível.

### P1: Painel no celular ⭐ MVP

**User Story**: Como visitante no celular, quero os filtros num painel, para a grade não ser empurrada para baixo.

**Acceptance Criteria**:

1. PNL-01: WHILE a largura é < 640 px THE barra SHALL mostrar a Ordem e um botão "Filtros"; Público, Loja, Preço e cupom SHALL ficar só no painel.
2. PNL-02: WHEN "Filtros" é tocado THEN um painel (folha inferior) SHALL abrir com as opções; escolher aplica na hora e "Ver N ofertas" (N do resultado) SHALL fechar o painel.
3. PNL-03: WHILE a largura é ≥ 640 px THE barra SHALL mostrar todos os grupos numa linha que quebra, sem botão "Filtros".

---

## Edge Cases

- WHEN a pessoa busca com filtros ativos THEN os resultados SHALL respeitar os filtros (DAD-01/02 em `buscar`).
- WHEN o catálogo ainda não carregou THEN a barra SHALL aparecer sem contador e a grade em esqueleto.
- IF a URL repete um parâmetro (`loja=amazon&loja=shopee`) THEN vale o primeiro (`URLSearchParams.get`).

## Implicit-requirement sweep (Medium)

- Persistência/estado: estado só na URL; sem storage novo.
- Entrada externa: parâmetros da URL validados contra listas fechadas (URL-02).
- Remaining dimensions N/A for this scope (sem chamada externa, auth, pagamento ou concorrência).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| DAD-01 | P1: Dados | T1 | Done |
| DAD-02 | P1: Dados | T1 | Done |
| DAD-03 | P1: Dados | T1 | Done |
| DAD-04 | P1: Dados | T1 | Done |
| URL-01 | P1: Endereço | T2 | Done |
| URL-02 | P1: Endereço | T2 | Done |
| URL-03 | P1: Endereço | T2 | Done |
| URL-04 | P1: Endereço | T3 | Pending |
| URL-05 | P1: Endereço | T3 | Pending |
| BAR-01 | P1: Barra | T3 | Pending |
| BAR-02 | P1: Barra | T3 | Pending |
| BAR-03 | P1: Barra | T3 | Pending |
| BAR-04 | P1: Barra | T3 | Pending |
| BAR-05 | P1: Barra | T3 | Pending |
| BAR-06 | P1: Barra | T3 | Pending |
| BAR-07 | P1: Barra | T3 | Pending |
| BAR-08 | P1: Barra | T3 | Pending |
| BAR-09 | P1: Barra | T3 | Pending |
| PNL-01 | P1: Painel | T4 | Pending |
| PNL-02 | P1: Painel | T4 | Pending |
| PNL-03 | P1: Painel | T4 | Pending |

**Coverage:** 21 total, 21 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Gates verdes: `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e`.
- [ ] Bundle inicial ≤ 150 KB.
- [ ] Real (dono): filtros em `/elas/` no celular, link filtrado aberto em outro aparelho, PageSpeed celular da home ≥ 90.
