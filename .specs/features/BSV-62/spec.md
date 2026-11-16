# BSV-62 Legenda nova (Telegram e WhatsApp) e fila do canal do WhatsApp Specification

Fonte: `docs/specs/BSV-62.md`. Contrato: `docs/CONTRATO.md` §11 (`OfertaCanal`) e §2.3 (slug de área).

## Problem Statement

O dono quer a mesma oferta do Telegram no canal do WhatsApp, pelos mesmos critérios, com um layout novo
nos dois canais: linha em branco depois do título e, depois do link, uma frase de aviso (ícone + frase)
que varia por oferta e vem de um JSON editável. Não há API de canal no WhatsApp: o `besave-envio` monta a
legenda e a põe numa fila no Oracle; o publicador (BSV-63) só executa.

## Goals

- [ ] Layout novo da legenda do Telegram (post e "Oferta encerrada").
- [ ] Frase de aviso escolhida por hash do id, de `frases_canal.json` embutido ou de `BESAVE_FRASES_CANAL`.
- [ ] Legenda do WhatsApp na marcação do WhatsApp, ≤ 1024 caracteres e ≤ 4000 bytes.
- [ ] Espelho: post de oferta confirmado no Telegram → linha `P` em `ENVIO_WHATSAPP`.
- [ ] SQL `bsv-62.sql`, CONTRATO 1.7.0, README.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Publicador do WhatsApp | BSV-63 |
| Avisos e "Oferta encerrada" no WhatsApp | spec |
| Seleção própria do WhatsApp | spec, regra 1 |
| Reeditar posts antigos do Telegram | spec |
| Legenda do aviso (BSV-41) | não muda |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Linha da frase no Telegram | `{icone} <i>{frase escapada}</i>` (ícone fora do itálico) | Igual ao modelo do WhatsApp (`{icone} _{frase}_`) | n |
| Encerrada | `⛔ <b>Oferta encerrada</b>\n<s>{título}\n\n{linhas}</s>` | Linha em branco depois do título, sem frase e sem link (Saída 4) | n |
| Hash | `u64` big-endian dos 8 primeiros bytes de `SHA-256("{id}:{sal}")`, sal `frase` / `icone`; índice = `h mod n` | Saída 3 | n |
| Validação das frases | trim; vazia ou > 120 caracteres → descartada com WARN; ícone vazio → descartado com WARN; lista vazia depois disso → arquivo inválido | Saída 3 | n |
| Arquivo inválido | WARN e embutido; embutido inválido (não acontece: há teste) → erro de configuração (código 2) | Saída 3; sem `unwrap` | n |
| `BESAVE_ENVIO_ESPELHO_WHATSAPP` inválida (não inteira) | WARN no início e espelho desligado; não é erro de configuração | O WhatsApp nunca atrasa o Telegram (Saída 2) | n |
| Limpeza do WhatsApp | remove `*`, `_`, `~`, `` ` `` do título, destaque e frase; sequências de espaço viram um; trim | Saída 5; cupom fora (decisão do dono, 16/11) | y |
| Cupom no WhatsApp | vai inteiro na crase (`BE_SAVE` → `` `BE_SAVE` ``); a regex do §4.3 já exclui `*`, `~` e a crase | Decisão do dono, 16/11: código não é formatado no WhatsApp | y |
| Relatório | `espelhados` e `espelho_falhas` no fim da linha `relatorio` | Diagnóstico pelo log (lição 8) | n |
| `--sim` | com o espelho ligado, a prévia mostra também a legenda do WhatsApp | Teste real passo 2 | n |
| Duplicata | Oracle ORA-00001 em `ENVIO_WHATSAPP` → `Ok(false)`, sem log | Saída 2 | n |

**Open questions:** none.

---

## User Stories

### P1: Legenda nova e fila do WhatsApp ⭐ MVP

Como dono, quero o layout novo com frase de aviso nos dois canais e cada oferta do Telegram enfileirada para o WhatsApp.

**Acceptance Criteria (EARS):**

- **SQL-01** `apps/worker/sql/bsv-62.sql` SHALL create `CANAL_ENVIO` 2 (`WhatsApp`, nome do canal), `PARAMETROS_ENVIO` 2 (40, 8, 22), `SQ_ENVIO_WHATSAPP`, `ENVIO_WHATSAPP` (colunas, `UK (ID_CANAL, ID_OFERTA)`, FK de canal, sem FK de oferta, `CK ST_ENVIO IN ('P','E','D','X')`), índice `(ID_CANAL, ST_ENVIO, DT_FILA)`, checagem 0 e `GRANT`s comentados, sem telefone, link, token, IP ou host.
- **FRA-01** THE envio SHALL pick `frase = frases[h(id,"frase") mod n]` and `icone = icones[h(id,"icone") mod m]`; the same id SHALL give the same pair on every call and in both channels.
- **FRA-02** FOR 1.000 consecutive ids THE choice SHALL use every frase and every ícone, no frase SHALL exceed 15% of ids, and consecutive ids SHALL NOT follow list order (`id mod n` fails).
- **FRA-03** THE ícone `🏃‍♂️` SHALL appear whole (multi-code-point item).
- **FRA-04** WHEN `BESAVE_FRASES_CANAL` points to a valid file THE envio SHALL use only its frases; WHEN the file is missing, unreadable, malformed or has an empty list THE envio SHALL log a WARN and use the embedded file.
- **FRA-05** WHEN a frase is empty or longer than 120 characters THE loader SHALL drop it with a WARN.
- **LAY-01** THE Telegram caption SHALL be `<b>{título}</b>`, blank line, optional lines (destaque, preço, caiu, cupom), link, blank line, `{icone} <i>{frase}</i>`; optional empty lines vanish, both blank lines stay.
- **LAY-02** THE frase SHALL be HTML-escaped in Telegram (`<&>` → `&lt;&amp;&gt;`).
- **WA-01** THE WhatsApp caption SHALL follow the Saída 5 template (`*título*`, `🔥 *-pct%*  ~R$ de~  *R$ por*  🔁 _(Recorrência)_`, `📉 *Caiu mais o preço!!!*`, ``🎟️ Cupom: `X` ``, `Promoção {Loja}: https://besave.io/{id}?utm_source=whatsapp`, `{icone} _{frase}_`) with the same line rules as Telegram.
- **WA-02** THE WhatsApp caption SHALL remove `*`, `_`, `~`, `` ` `` from título, destaque and frase and collapse repeated spaces; the cupom SHALL go unchanged inside backticks (`BE_SAVE` → `` `BE_SAVE` ``).
- **ENV-62** `infra/vps/envio.env.example` SHALL carry `# BESAVE_ENVIO_ESPELHO_WHATSAPP=2` and `# BESAVE_FRASES_CANAL=<caminho>` commented, each with one explanation line.
- **LIM-01** WHEN the caption exceeds the limit THE envio SHALL drop coupons from the end (keep 1), then cut the title; the frase SHALL never be cut; Telegram ≤ 1024 UTF-16 units.
- **LIM-02** THE WhatsApp caption SHALL be ≤ 1024 characters AND ≤ 4000 UTF-8 bytes.
- **ENC-01** THE "Oferta encerrada" caption SHALL have a blank line after the title, no frase and no link.
- **ISO-01** THE aviso caption (BSV-41) SHALL NOT change.
- **ESP-01** WHEN `BESAVE_ENVIO_ESPELHO_WHATSAPP=<canal>` and Telegram confirms an oferta post THE envio SHALL insert one `P` row with the WhatsApp caption, `ID_ENVIO_TELEGRAM` and `DS_AREA_SLUG` (CONTRATO §2.3, `MEU_LAR` → `meu-lar`).
- **ESP-02** WHEN Telegram fails, or the variable is absent THE envio SHALL insert no row.
- **ESP-03** WHEN the insert fails THE envio SHALL log a WARN (`id`, motivo), keep `ENVIO_TELEGRAM` confirmed and finish with code 0.
- **ESP-04** WHEN the same oferta is inserted twice THE fila SHALL keep 1 row, without error.
- **ESP-05** Avisos and "Oferta encerrada" edits SHALL NOT be mirrored.
- **CON-01** CONTRATO §11 SHALL describe the new layout, "Legenda do WhatsApp", frases, `utm_source=whatsapp` and the fila; contract version 1.7.0 (`package.json`).
- **DOC-01** The worker README SHALL document `BESAVE_ENVIO_ESPELHO_WHATSAPP`, `BESAVE_FRASES_CANAL` (trocar/incluir frase sem recompilar), the SQL and how to pause the mirror.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SQL-01 | P1 | T1 | Done |
| FRA-01 | P1 | T2 | Done |
| FRA-02 | P1 | T2 | Done |
| FRA-03 | P1 | T2 | Done |
| FRA-04 | P1 | T2 | Done |
| FRA-05 | P1 | T2 | Done |
| LAY-01 | P1 | T3 | Done |
| LAY-02 | P1 | T3 | Done |
| LIM-01 | P1 | T3/T4 | Done |
| ENC-01 | P1 | T3 | Done |
| ISO-01 | P1 | T3 | Done |
| WA-01 | P1 | T4 | Done |
| WA-02 | P1 | T4 | Done |
| LIM-02 | P1 | T4 | Done |
| ESP-01 | P1 | T5 | Done |
| ESP-02 | P1 | T5 | Done |
| ESP-03 | P1 | T5 | Done |
| ESP-04 | P1 | T5 | Done |
| ESP-05 | P1 | T5 | Done |
| CON-01 | P1 | T6 | Done |
| DOC-01 | P1 | T6 | Done |
| ENV-62 | P1 | T8 | Done |

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker`.
- [ ] `npm run validate` verde em `packages/contract`.
- [ ] Teste real do dono (bloqueia o merge): SQL, `--sim` na inst2, 2 h de espelho, troca de frase sem recompilar.
