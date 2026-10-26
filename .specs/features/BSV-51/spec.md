# BSV-51 Robô do WhatsApp: destravar sobreposição e avisar captura parada Specification

Fonte: `docs/specs/BSV-51.md`. AD-107, AD-108; lições 14, 29, 31.

## Problem Statement

Em 22/10 um aviso do WhatsApp Web (`#wa-popovers-bucket`) interceptou o clique no grupo: o robô girou
5h30 sem capturar e ninguém foi avisado (o alerta do worker é de 8 h).

## Goals

- [ ] Clique interceptado → Escape → botão de fechar conhecido → novo clique, com log do que fechou.
- [ ] Clique com tempo máximo de segundos; falha é erro tratado da volta.
- [ ] N voltas cegas seguidas → recarrega o WhatsApp Web e o resgate roda depois.
- [ ] Captura parada de dia (> 45 min sem abrir grupo) avisa no Telegram; "voltou" uma vez.

## Out of Scope

Robô das lojas, OpenWA, rodízio, janela noturna, alertas do worker; execução real na VPS (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Quais cliques | Os de `abrir_grupo` (busca e item): são os únicos do rodízio e do catch-up | `grep .click(` no monitor | n |
| Tempo do clique | 5 s por tentativa, 3 tentativas (clique; Escape; fechar) | Segundos, não o padrão de 30 s | n |
| Voltas até recarregar | `destravar.recarregar_voltas`, padrão 8 (~10 min) e repete a cada 8 | Volta cega ≈ 75 s com cliques curtos | n |
| Chaves do alerta | `alerta.sem_abrir_minutos` (45), `alerta.telegram_token`, `alerta.telegram_chat_id` | Opcionais; sem token/chat só log | n |
| Janela noturna | Dentro dela o relógio do alerta é zerado a cada volta | Ao sair da janela não alerta por causa do sono | n |
| Lista de "fechar" | Textos `fechar`, `ok`, `agora não`, `close`, `not now` (sem acento/caixa) e `aria-label` igual, só dentro de `#wa-popovers-bucket` e `[role="dialog"]` | Regra 3: lista fechada | n |

Open questions: none

---

## User Stories

### P1: Destravar e avisar ⭐ MVP

**Acceptance Criteria**:

1. DES-01: WHEN o clique em `abrir_grupo` é interceptado, THE SYSTEM SHALL tentar `Escape` e clicar de novo; se ainda interceptado, SHALL clicar no botão de fechar permitido e clicar de novo.
2. DES-02: WHEN algo foi fechado, THE SYSTEM SHALL registrar no log o texto resumido do aviso.
3. DES-03: IF nenhuma tentativa resolve, THEN THE SYSTEM SHALL levantar erro dentro de 3 × 5 s, sem laço.
4. DES-04: THE SYSTEM SHALL NOT clicar em botão fora da lista fechada (sair do grupo, apagar, responder, cancelar...).
5. DES-05: WHEN não há interceptação, THE SYSTEM SHALL clicar uma vez, sem Escape nem busca de botão (comportamento idêntico).
6. REC-01: WHEN `recarregar_voltas` voltas cegas seguidas se completam, THE SYSTEM SHALL recarregar a página, esperar `#pane-side` e marcar o resgate pendente.
7. REC-02: THE SYSTEM SHALL NOT alterar contador nem marcadores por destravar ou recarregar.
8. ALE-01: WHEN, fora da janela noturna, passam mais de `sem_abrir_minutos` sem abrir grupo, THE SYSTEM SHALL enviar uma mensagem ao Telegram, e lembrete a cada 2 h.
9. ALE-02: WHILE dentro da janela noturna, THE SYSTEM SHALL NOT alertar.
10. ALE-03: WHEN um grupo volta a abrir depois do alerta, THE SYSTEM SHALL enviar "voltou" uma única vez.
11. ALE-04: IF faltar token ou chat, THEN THE SYSTEM SHALL só logar; falha de envio não derruba o robô nem registra o token.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| DES-01 | Destravar e avisar | Execute | Done |
| DES-02 | Destravar e avisar | Execute | Done |
| DES-03 | Destravar e avisar | Execute | Done |
| DES-04 | Destravar e avisar | Execute | Done |
| DES-05 | Destravar e avisar | Execute | Done |
| REC-01 | Destravar e avisar | Execute | Done |
| REC-02 | Destravar e avisar | Execute | Done |
| ALE-01 | Destravar e avisar | Execute | Done |
| ALE-02 | Destravar e avisar | Execute | Done |
| ALE-03 | Destravar e avisar | Execute | Done |
| ALE-04 | Destravar e avisar | Execute | Done |

## Success Criteria

- [ ] Testes do critério de aceite verdes no CI `tools`; Verifier independente PASS; teste real do dono na VPS.
