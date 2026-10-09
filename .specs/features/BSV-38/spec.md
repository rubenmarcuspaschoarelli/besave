# BSV-38 Specification — página da oferta: copiar o cupom e ir para a loja

Fonte: `docs/specs/BSV-38.md`. Escopo: `apps/worker/templates/` (+ testes do template e goldens),
`apps/site/src/lib/estilo/besave.css` (+ e2e), `infra/deploy-site/` (só o cache do CSS) e MANIFEST §4.
CONTRATO §4, §7.1; AD-014, AD-034, AD-041, AD-087, AD-093.

## Problem Statement

Na página da oferta o cupom é só texto: quem quer usá-lo seleciona e copia à mão antes de ir à loja.

## Goals

- [ ] Com cupom e oferta ativa, um toque copia o código e abre a loja em aba nova; também dá para só copiar.
- [ ] Sem JavaScript a página funciona como hoje (link comum para `/ir/{id}`).
- [ ] CSS novo chega ao celular em ≤ 5 min (`assets/besave.css` com `max-age=300`).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Cupom nos cards da lista | decisão do dono (spec) |
| Métricas de cópia | spec |
| Cupons da tabela CUPOM | spec (F3/F4) |
| Execução real (deploy do site, ciclo, celular) | "Real (dono)" — bloqueia o merge |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Sem cupom: `target="_blank"` | Sim, com `rel="nofollow sponsored noopener"` | Spec permite "por coerência"; o comportamento do CTA fica igual com e sem cupom | y (spec) |
| Classes novas | `copiar` (botão do ícone), `copiado` (estado do botão, posto pelo script), `confirmacao` (aviso `role="status"`) | Nomes de domínio curtos; `aviso` já é a página do aviso (BSV-41) | y |
| Aviso vazio no HTML | `<p class="confirmacao" role="status"></p>` sempre presente com cupom ativo; o script põe e tira o texto | Região viva precisa existir antes da mensagem para o leitor de tela anunciar | y |
| Botão principal com cópia negada | Não seleciona o texto (a pessoa está saindo para a aba nova); só o ícone seleciona | Spec: seleção é fallback do ícone; o CTA não pode atrasar | y (dono, 09/10) |
| Texto do botão | HTML diz "Ir para a loja"; o script troca para "Copiar cupom e ir para a loja" quando `navigator.clipboard.writeText` existe | Sem JS ou sem clipboard o botão não promete cópia que não faz | y (dono, 09/10, revisão) |
| Ícone | SVG embutido (`aria-hidden`), sem arquivo externo | Spec: sem arquivo externo; render determinístico | y |
| Fontes e favicon | Mantêm `public, max-age=3600, stale-while-revalidate=86400` | Spec item 4 | y |

**Open questions:** none.

---

## User Stories

### P1: Copiar o cupom ⭐ MVP

1. CUP-01: WHEN a oferta é ativa e tem cupom THEN o HTML SHALL ter, ao lado do código, um `<button>` com `aria-label="Copiar cupom"`, ícone SVG e atributo `hidden`.
2. CUP-02: WHEN a oferta é ativa e tem cupom THEN o CTA SHALL ser `<a class="cta" href="/ir/{id}" target="_blank" rel="nofollow sponsored noopener">Ir para a loja</a>` no HTML.
3. CUP-03: WHEN a oferta é ativa e tem cupom THEN o HTML SHALL ter uma região `role="status"` vazia e um único `<script>` sem `type` (além do JSON-LD) que não contém o código do cupom nem nenhum dado da oferta.
4. CUP-04: WHEN a oferta é ativa e não tem cupom THEN o CTA SHALL ser "Acesse a oferta" com `href="/ir/{id}"`, `target="_blank"` e `rel="nofollow sponsored noopener"`, sem botão de copiar, sem região de status e sem script além do JSON-LD.
5. CUP-05: WHEN a oferta está encerrada (com ou sem cupom) THEN o CTA SHALL continuar `aria-disabled="true"` sem `href`, sem botão de copiar, sem região de status e sem script além do JSON-LD.
6. CUP-06: The página SHALL ter ≤ 30 KB, mesmo input → mesmos bytes, e nenhuma URL `http` além das do domínio besave.com.br e do schema.org.
7. CUP-07: WHEN o script roda THEN o botão de copiar SHALL ficar visível e, IF `navigator.clipboard.writeText` existe, o CTA SHALL passar a "Copiar cupom e ir para a loja" (sem a API continua "Ir para a loja" e não tenta copiar); WHEN ele é clicado THEN o código lido do DOM SHALL ir para o clipboard e o aviso SHALL mostrar "Cupom copiado!" e sumir em ~2 s.
8. CUP-08: IF o clipboard falta ou recusa no clique do ícone THEN o texto do código SHALL ficar selecionado.
9. CUP-09: WHEN o CTA é clicado THEN o código SHALL ir para o clipboard e uma aba nova SHALL abrir em `/ir/{id}`; IF o clipboard recusa THEN a aba SHALL abrir do mesmo jeito.
10. CUP-10: WHEN o JavaScript está desligado THEN o ícone SHALL ficar oculto e o CTA SHALL ser um link "Ir para a loja" para `/ir/{id}`.
11. CUP-11: The `besave.css` SHALL ter regra para `.copiar`, `.copiado` e `.confirmacao`, área de toque do ícone ≥ 44 px e `.copiar[hidden]` oculto.

### P1: Cache do CSS (AD-087)

12. DEP-01: The `publicar.mjs` SHALL gravar `assets/besave.css` com o comando inteiro `s3 cp build/assets/besave.css s3://{bucket}/assets/besave.css --cache-control "public, max-age=300" --content-type "text/css; charset=utf-8"`; fontes e favicon SHALL manter `public, max-age=3600, stale-while-revalidate=86400`.
13. DEP-02: MANIFEST §4 SHALL registrar `assets/besave.css` com `public, max-age=300`.

---

## Edge Cases

- WHEN o cupom tem `<`, `&` ou aspas THEN o código SHALL sair escapado (AD-034) e o script, que lê do DOM, não muda.
- WHEN o clique no ícone se repete dentro de 2 s THEN o aviso SHALL continuar visível e o temporizador recomeçar.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CUP-01 | Copiar o cupom | Execute | Pending |
| CUP-02 | Copiar o cupom | Execute | Pending |
| CUP-03 | Copiar o cupom | Execute | Pending |
| CUP-04 | Copiar o cupom | Execute | Pending |
| CUP-05 | Copiar o cupom | Execute | Pending |
| CUP-06 | Copiar o cupom | Execute | Pending |
| CUP-07 | Copiar o cupom | Execute | Pending |
| CUP-08 | Copiar o cupom | Execute | Pending |
| CUP-09 | Copiar o cupom | Execute | Pending |
| CUP-10 | Copiar o cupom | Execute | Pending |
| CUP-11 | Copiar o cupom | Execute | Pending |
| DEP-01 | Cache do CSS | Execute | Pending |
| DEP-02 | Cache do CSS | Execute | Pending |

---

## Success Criteria

- [ ] `cargo test` (template_oferta), `pnpm test`, `pnpm e2e` e `infra/functions npm test` verdes.
- [ ] Prints com cupom, sem cupom e encerrada, celular e computador.
