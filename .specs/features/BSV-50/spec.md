# BSV-50 Worker: cupom com vários códigos e faixa "Encerrada"

Fonte: `docs/specs/BSV-50.md`. Contrato: CONTRATO §3, §4, §11; AD-093, AD-096, AD-102.
Escopo: `apps/worker`, `packages/contract`, `docs/CONTRATO.md`, classes novas em `apps/site/src/lib/estilo/besave.css`.

## Problem Statement

`DS_CUPOM` às vezes traz vários códigos separados por `|`. O worker valida o campo inteiro, não casa
`^[A-Z0-9_-]+$` e omite o cupom (~150 ofertas por ciclo em 20/10). A faixa da página encerrada diz
"Oferta expirada", enquanto cards e busca dizem "Encerrada".

## Goals

- [ ] Toda oferta com ao menos um código válido aparece com cupom no site e no canal.
- [ ] A página mostra todos os códigos, cada um copiável.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Cupons da tabela `CUPOM`, filtro por cupom | spec |
| Mudança no robô; cupom no card além do primeiro | spec |

## Assumptions & Open Questions

Open questions: nenhuma.

| Decisão | Padrão escolhido | Motivo |
| ------- | ---------------- | ------ |
| `OfertaCanal.cupom` | Substituído por `cupons` | §11 passa a ter só a lista |
| `cupons` no schema | Campo opcional (fora de `required`) | Compatível; o worker sempre emite |
| Markup do cupom | Um `<p class="cupom">` por código dentro de `<div class="cupons">` | Mantém o markup de 1 cupom e as classes existentes |
| Classe da faixa | `expirada` continua | Spec permite |

## User Stories

- Como visitante, copio qualquer um dos códigos na página da oferta.
- Como leitor do canal, vejo todos os códigos na legenda.

## Requirements

| ID | Requisito (EARS) |
| -- | ---------------- |
| SEP-01 | QUANDO `DS_CUPOM` tem partes separadas por `|`, O worker DEVE aplicar trim e maiúsculas e manter só as que casam `^[A-Z0-9_-]{1,30}$`. |
| SEP-02 | O worker DEVE remover códigos duplicados mantendo a ordem. |
| SEP-03 | SE houver mais de 5 códigos válidos, ENTÃO o worker DEVE manter os 5 primeiros e logar WARN com o id. |
| SEP-04 | SE uma parte for inválida, ENTÃO o worker DEVE descartá-la e logar WARN com id e parte. |
| SEP-05 | SE nenhuma parte for válida ou o campo for vazio/ausente, ENTÃO a oferta DEVE ficar sem cupom. |
| CARD-01 | O card DEVE levar em `c` o primeiro código válido. |
| PAG-01 | A `OfertaPagina` DEVE ter `cupons` (0 a 5) e `cupom` igual ao primeiro, ou null. |
| TPL-01 | QUANDO a oferta ativa tem códigos, A página DEVE listar cada um com seu botão de copiar. |
| TPL-02 | O botão principal DEVE continuar com o primeiro código; sem JavaScript DEVE ser link para `/ir/{id}` com "Ir para a loja". |
| TPL-03 | QUANDO a oferta está encerrada, A faixa DEVE dizer "Encerrada" e NÃO "Oferta expirada". |
| TPL-04 | O HTML da oferta DEVE ter ≤ 30 KB e os mesmos bytes para o mesmo input. |
| CAN-01 | A `OfertaCanal` DEVE ter `cupons` e a legenda DEVE mostrá-los todos (`Cupons: A · B · C`). |
| CAN-02 | SE a legenda passar de 1.024 caracteres, ENTÃO o worker DEVE cortar códigos do fim (mantendo 1) antes de cortar o título. |
| CON-01 | O contrato DEVE estar na 1.6.0, com `cupons` no schema e nas fixtures da `OfertaPagina`, na mesma PR do worker. |

## Requirement Traceability

| ID | Teste |
| -- | ----- |
| SEP-01 | `cupons.rs` |
| SEP-02 | `cupons.rs` |
| SEP-03 | `cupons.rs` |
| SEP-04 | `cupons.rs` |
| SEP-05 | `cupons.rs` |
| CARD-01 | `card.rs` |
| PAG-01 | `pagina.rs` |
| TPL-01 | `template_oferta.rs` |
| TPL-02 | `template_oferta.rs` |
| TPL-03 | `template_oferta.rs` |
| TPL-04 | `template_oferta.rs` |
| CAN-01 | `envio_legenda.rs` |
| CAN-02 | `envio_legenda.rs` |
| CON-01 | `npm run validate, chunks.rs, envio_modelo.rs` |
