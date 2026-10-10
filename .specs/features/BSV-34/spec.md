# BSV-34 Specification — página de busca `/busca/`

Fonte: `docs/specs/BSV-34.md` (PR #66, ainda não mergeada em `develop`). Escopo: `apps/site/` e, só o
formulário de busca no topo da página da oferta, `apps/worker/templates/` (+ testes e goldens) e
`apps/site/src/lib/estilo/besave.css`. CONTRATO §3; AD-020, AD-061, AD-067, AD-088, AD-090, AD-093, AD-095.

## Problem Statement

A busca filtra a grade da página em que a pessoa está e não tem endereço próprio: não dá para
compartilhar "ofertas de protetor solar", e a página da oferta (HTML do worker) não tem campo de busca.

## Goals

- [ ] `/busca/?q=protetor` mostra resultados com contagem, filtros e ordem, e o link pode ser compartilhado.
- [ ] Do topo de qualquer página do site, e da página da oferta, chega-se à `/busca/`.
- [ ] Bundle inicial da home continua ≤ 150 KiB (AD-090).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Relevância por pontuação, correção ortográfica, autocomplete, busca no servidor, histórico | spec |
| Busca dentro da grade da home e das áreas | spec: um comportamento só, sempre `/busca/` |
| Execução real (deploy do site, `besave-ciclo`, PageSpeed) | "Real (dono)": bloqueia o merge |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Selo da expirada no card | "Encerrada" em todo card (lista de desejos inclusive), no lugar de "Expirada"; as asserções antigas de "Expirada" (Card.test, desejos.spec) passam a "Encerrada" | Spec pede "Encerrada" na busca; o card é o mesmo componente e o status do contrato é `ENCERRADA`; dois textos para o mesmo estado confundem | y (dono, 10/10) |
| Subpágina `/{slug}/{publico}/` | A busca leva só `&area={slug}` | Spec fala só da área; o público vira filtro na `/busca/` se a pessoa quiser | n (proposta) |
| Filtros da home/área ao ir para a busca | Não são levados | Spec não pede; a busca começa no padrão "Recentes" | n (proposta) |
| `q` < 2 caracteres no topo fora da `/busca/` | Não navega; Enter navega sempre (mostra sugestões) | Spec: "digitar 2+ caracteres leva"; "Enter também envia" | y (spec) |
| Espera entre teclas na `/busca/` | Resultados na hora; URL com `replaceState` 300 ms depois da última tecla; Enter grava na hora | Busca local é ≤ 20 ms (DES-02); a espera é para não encher o histórico/URL a cada tecla | y |
| Botão para tirar a área | "Buscar em todas as áreas" | Texto direto, testável por nome | y |
| Sugestões (`q` vazio ou < 2) | Título "Buscar ofertas", links das 10 áreas (`/{slug}/`) e faixa "Maiores descontos de hoje" (da área, se houver `area`) | Spec | y |
| Contagem | "N ofertas para “q”" / "1 oferta para “q”", com " em {Área}" quando há área; região `aria-live="polite"` | Spec + regra 3 | y |
| Parcial | Enquanto o catálogo não está completo: "Buscando em X de Y ofertas…", X = cards nos chunks carregados, Y = soma de `qtd` do manifest | BSV-35 (resultado parcial) | y |
| Página da oferta | `<form class="busca" role="search" action="/busca/" method="get">` com `<label>` oculto, `input name="q"` e botão de lupa, entre o logo e as áreas; no celular ocupa a linha de baixo do cabeçalho (sem lupa que abre: a spec só aceita, não exige) | Sem JS; campo visível é mais simples e acessível | y |
| Testes antigos da busca na home/área (HOM-05, ARE-05, busca < 2 na home) | Reescritos para o comportamento novo (navegar para `/busca/`) | A spec troca o comportamento; manter os antigos seria testar o que deixou de existir | y (spec) |

**Open questions:** none — as propostas acima vão para revisão do dono no PR.

---

## User Stories

### P1: Página `/busca/` ⭐ MVP

1. BUS-01: WHEN a `/busca/` abre com `q` normalizado de 2+ caracteres THEN a página SHALL mostrar só cards cujo título/cupom/loja casa com todos os termos e o texto "N ofertas para “q”".
2. BUS-02: WHEN há `?area={slug}` válido THEN o resultado SHALL conter só cards da área, o texto SHALL terminar com " em {Rótulo}" e um botão "Buscar em todas as áreas" SHALL tirar `area` da URL e do resultado.
3. BUS-03: WHEN há filtros na URL (`ordem`, `publico`, `loja`, `preco`, `cupom`) THEN eles SHALL ser aplicados ao resultado e, ao mudar um filtro, a URL SHALL manter `q` e `area` com o mesmo formato da BSV-31.
4. BUS-04: The resultado SHALL listar as expiradas depois de todas as ativas, cada uma com o selo "Encerrada" e foto em cinza.
5. BUS-05: WHILE o catálogo não está completo, the página SHALL mostrar "Buscando em X de Y ofertas…" e o resultado parcial.
6. BUS-06: WHEN `q` normalizado tem menos de 2 caracteres THEN a página SHALL mostrar sugestões: links das 10 áreas e a faixa "Maiores descontos de hoje", sem grade de resultados.
7. BUS-07: IF a busca não acha nada THEN a página SHALL mostrar "Nenhuma oferta para “q”", as dicas "Confira a grafia" e "Use menos palavras", e os links das áreas.
8. BUS-08: The página SHALL ter `<meta name="robots" content="noindex">`, `<title>` "Busca: {q} · Besave" (sem `q`: "Busca · Besave") e não entrar no sitemap.
9. BUS-09: The grade SHALL mostrar 40 cards e "Ver mais ofertas" SHALL acrescentar 40.
10. BUS-10: WHEN a página é recarregada THEN `q`, `area` e filtros SHALL ser restaurados da URL.

### P1: Campo de busca do topo (site)

11. TOP-01: WHEN a pessoa digita no topo de uma página que não é a `/busca/` e o texto normalizado chega a 2+ caracteres THEN o site SHALL navegar no cliente para `/busca/?q=…`, com o foco no campo e o texto digitado (inclusive o que foi digitado durante a navegação).
12. TOP-02: WHEN a página é de área (`/{slug}/` ou `/{slug}/{publico}/`) THEN a navegação SHALL levar `&area={slug}`.
13. TOP-03: WHEN a pessoa digita na `/busca/` THEN os resultados SHALL atualizar e a URL SHALL ser trocada com `replaceState` (sem entrada nova no histórico).
14. TOP-04: WHEN a pessoa tecla Enter THEN o campo SHALL enviar para `/busca/?q=…` (com `area` em página de área); sem JavaScript o formulário SHALL fazer `GET /busca/`.
15. TOP-05: The home e as áreas SHALL deixar de filtrar a grade pela busca.
16. TOP-06: WHEN a pessoa volta no navegador a partir da `/busca/` THEN SHALL voltar à página de onde veio.
17. TOP-07: The formulário SHALL ter `role="search"` e rótulo "Buscar ofertas"; a contagem SHALL estar numa região `aria-live`.

### P1: Formulário na página da oferta (worker)

18. OFE-01: The página da oferta SHALL ter, no cabeçalho, `<form … role="search" action="/busca/" method="get">` com `<input name="q">` rotulado e botão de envio, sem JavaScript.
19. OFE-02: The página SHALL continuar ≤ 30 KB e determinística (mesmo input → mesmos bytes).
20. OFE-03: The `besave.css` SHALL ter regra para cada classe nova do formulário.
21. OFE-04: WHEN a pessoa digita na página da oferta e envia THEN o navegador SHALL abrir `/busca/?q=…`.

### P1: Orçamento

22. BUD-01: The bundle inicial da home SHALL ser ≤ 150 KiB brutos (JS inicial + CSS embutido), medido antes e depois.

---

## Edge Cases

- IF `area` na URL não é slug válido THEN SHALL ser ignorada (busca em todas as áreas).
- IF `q` só tem pontuação ou espaços THEN SHALL contar como vazio (sugestões).
- WHEN a busca só acha expiradas THEN elas SHALL aparecer (em cinza, "Encerrada"), sem estado vazio.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| BUS-01 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-02 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-03 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-04 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-05 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-06 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-07 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-08 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-09 | P1: Página /busca/ | T1–T5 | Pending |
| BUS-10 | P1: Página /busca/ | T1–T5 | Pending |
| TOP-01 | P1: Campo do topo | T3–T4 | Pending |
| TOP-02 | P1: Campo do topo | T3–T4 | Pending |
| TOP-03 | P1: Campo do topo | T3–T4 | Pending |
| TOP-04 | P1: Campo do topo | T3–T4 | Pending |
| TOP-05 | P1: Campo do topo | T3–T4 | Pending |
| TOP-06 | P1: Campo do topo | T3–T4 | Pending |
| TOP-07 | P1: Campo do topo | T3–T4 | Pending |
| OFE-01 | P1: Página da oferta | T6 | Pending |
| OFE-02 | P1: Página da oferta | T6 | Pending |
| OFE-03 | P1: Página da oferta | T6 | Pending |
| OFE-04 | P1: Página da oferta | T6 | Pending |
| BUD-01 | P1: Orçamento | T7 | Pending |

**Coverage:** 22 total, 22 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Gates do site (`lint`, `check`, `test`, `build`, `e2e`) e do worker (`fmt`, `clippy`, `test`) verdes.
- [ ] Bundle da home ≤ 153.600 B, com antes (153.245 B) e depois no PR.
