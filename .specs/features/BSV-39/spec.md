# BSV-39 — Dieta do carregamento inicial da home

Fonte: `docs/specs/BSV-39.md`. Pasta: `apps/site/`.

## Problem Statement

O gate BUD-01 (JS inicial bruto + CSS embutido da home) está em 153 553 B, a 47 B do limite de
153 600 B (150 KiB, AD-090). A próxima melhoria na home trava no CI.

## Goals

- [ ] Carregamento inicial da home ≤ 143 360 B (folga ≥ 10 KiB), sem mudança visível nem de fluxo.
- [ ] Inventário antes/depois no repositório (`apps/site/docs/bundle.md`) e no PR.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Design, funções novas, trocar Svelte/SvelteKit/Tailwind | spec: fora de escopo |
| `besave.css` da página de oferta, imagens | spec: fora de escopo |
| Mudar `adapter-static`, prerender ou CSS embutido como estratégia (AD-086) | Regra 3 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Cortes escolhidos pelo inventário | (1) utilitários equivalentes sem os conjuntos `--tw-*` de sombra/anel/filtro/translate/números; (2) Tailwind só escaneia `src/` sem testes; (3) preflight sem regras de elementos que o site não usa; (4) `build.modulePreload: false`; (5) rodapé renderizado só no prerender; (6) `discloseVersion: false` | Maior ganho por risco: nenhum muda pixel nem fluxo; o runtime Svelte+Kit (~93 KB) é fixo | n (PR) |
| Rodapé fora da hidratação | Renderizado em `hooks.server.ts` (`svelte/server`) e injetado no `<!--rodape-->` do `app.html`, dentro do contêiner do kit e depois da raiz do Svelte | É estático e igual em toda página; dentro do contêiner o kit continua tratando o clique em "Lista de desejos" (navegação sem recarregar) | n (PR) |
| Import dinâmico do campo de busca | Descartado | Medido: 110 B de ganho (o `destino-busca` minificado tem 195 B) e o Rolldown redividiu chunks; não paga um gatilho novo | y |
| `grayscale` da expirada | Utilitário `foto-grayscale` (`filter: grayscale(1)`) | O e2e existente procura `/grayscale/` na classe; o utilitário do Tailwind puxa 13 variáveis `--tw-*` | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Folga no orçamento ⭐ MVP

**User Story**: Como dono, quero ≥ 10 KiB de folga no carregamento inicial da home para a próxima melhoria passar no CI.

**Acceptance Criteria**:

1. DIE-01: The site SHALL ter carregamento inicial da home (medida do BUD-01) ≤ 143 360 B, com o limite do BUD-01 em 150 KiB.
2. DIE-02: WHEN o BUD-01 roda THEN the test SHALL anotar no relatório a folga em bytes até 150 KiB.
3. DIE-03: The repository SHALL ter o inventário antes/depois por pedaço inicial (arquivo, bruto, gzip, conteúdo) e do CSS embutido em `apps/site/docs/bundle.md`, reproduzível por `pnpm inventario`.

### P1: Nada visível nem de fluxo muda

1. DIE-04: The site SHALL passar todos os e2e existentes sem alteração de asserção.
2. DIE-05: WHEN a home abre THEN the site SHALL pedir `manifest.json` antes de qualquer chunk e os 3 chunks de `n` mais alto antes dos demais, na mesma ordem de hoje.
3. DIE-06: The site SHALL renderizar home, `/elas/`, `/busca/?q=protetor` e `/desejos/` em 390 e 1280 px com os mesmos pixels de antes (prints lado a lado no PR), incluindo os estados que usam os utilitários trocados (foco do card, menu "Mais", setas da faixa, painel de filtros, expirada em cinza, hover dos botões de destaque).
4. DIE-07: The site SHALL ter exatamente um rodapé em cada página do build, igual ao de antes, dentro do contêiner do app.
5. DIE-08: WHEN o visitante clica em "Lista de desejos" no rodapé THEN the site SHALL navegar para `/desejos/` sem recarregar a página, e o rodapé SHALL continuar único.
6. DIE-09: The site SHALL não levar o código do rodapé no JS inicial da home.

---

## Edge Cases

- IF a hidratação falha e o kit remonta a página de erro THEN the site SHALL ficar sem rodapé, como a página de erro padrão já fica hoje (o kit limpa o contêiner).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| DIE-01 | P1: folga | Execute | Verifying |
| DIE-02 | P1: folga | Execute | Verifying |
| DIE-03 | P1: folga | Execute | Verifying |
| DIE-04 | P1: nada muda | Execute | Verifying |
| DIE-05 | P1: nada muda | Execute | Verifying |
| DIE-06 | P1: nada muda | Execute | Verifying |
| DIE-07 | P1: nada muda | Execute | Verifying |
| DIE-08 | P1: nada muda | Execute | Verifying |
| DIE-09 | P1: nada muda | Execute | Verifying |

**Coverage:** 9 total, 9 mapped, 0 unmapped

---

## Success Criteria

- [ ] `pnpm install --frozen-lockfile && pnpm lint && pnpm check && pnpm test && pnpm build && pnpm e2e` verdes.
- [ ] BUD-01 ≤ 143 360 B.
