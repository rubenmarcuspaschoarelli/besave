# BSV-68 — Caractere invisível na URL da oferta

Fonte: `docs/specs/BSV-68.md` (branch `docs/bsv-68-url-invisivel`). Escopo: `tools/capture-chat-groups/wa/parser.py`,
`tools/capture-store-pages/` (`main.py`, `core/shopee_api.py`, `core/url.py`) e testes.

## Problem Statement
Links do WhatsApp chegam com U+2060 (word joiner) dentro do `href`. A URL suja abre página inexistente
(oferta perdida) ou prende a linha da Shopee como `api_indisponivel` para sempre (`UnicodeEncodeError`).

## Goals
- Nenhuma URL com caractere Unicode `Cf` chega à captura, nem nova nem já na fila.
- Nenhuma linha retida para sempre por URL que não codifica.

## Out of Scope
- Reprocessar linhas de 27/11; emoji colado à URL; idade máxima de linha retida.

## Assumptions & Open Questions
- `unicodedata` (stdlib) define `Cf`; a versão Unicode do Python 3.12 cobre U+00AD, U+200B–U+200F, U+202A–U+202E, U+2060–U+2064, U+FEFF.
- Só a remoção de `Cf` gera a linha de log `[url]`; espaço nas pontas já era tirado pelo `.strip()` de antes e não loga.
- Vários códigos na linha de log ficam separados por `, ` (a spec mostra só um).

Open questions: nenhuma.

## User Stories

### P1: URL limpa na captura ⭐ MVP
Como dono, quero que link com caractere invisível vire a URL certa, para não perder oferta nem prender linha.

## Requirements

| ID | Requisito (EARS) |
|---|---|
| URL-01 | THE `limpar_url(texto)` SHALL remover todo caractere de categoria `Cf` em qualquer posição, depois `strip()`, e devolver `''` para `None`/vazio, sem mudar nenhum outro caractere. |
| URL-02 | THE função SHALL existir nos dois robôs (`wa/parser.py` e `core/url.py`) com o mesmo corpo e a mesma tabela de teste. |
| WA-01 | WHEN `parse_campos` recebe `links`, THE parser SHALL limpar cada link antes de `eh_link_whatsapp` e da escolha do 1º link, descartando link que fica vazio. |
| LJ-01 | WHEN `_adaptar_linhas` adapta uma linha, THE robô SHALL usar `limpar_url(DS_URL_ORIGEM)` como `url`. |
| LJ-02 | WHEN a limpeza removeu caractere `Cf`, THE robô SHALL imprimir `[url] linha {ID}: removidos {n} caractere(s) invisivel(is) ({U+XXXX, ...})` com códigos distintos em ordem de aparição; IF nada foi removido THEN nada é impresso. |
| SH-01 | IF `abrir` levanta `UnicodeError` THEN `resolver` SHALL devolver `(None, URL_NAO_RECONHECIDA)` e imprimir `shopee api: url_nao_reconhecida (resolver: UnicodeEncodeError)` (nome real da exceção). |
| SH-02 | IF `abrir` levanta outro `ValueError`/`OSError`/`HTTPException` THEN `resolver` SHALL continuar devolvendo `API_INDISPONIVEL`. |
| SH-03 | WHEN uma linha suja passa por `_adaptar_linhas` e pela captura Shopee, THE `abrir` SHALL receber URL sem caractere `Cf`. |

## Acceptance Criteria
1. WHEN a tabela da Saída 5 é aplicada THEN a lista de pares resultante SHALL ser igual à tabela inteira, nos dois robôs (URL-01, URL-02).
2. WHEN `links == ["https://chat.whatsapp.com/Abc⁠", "https://meli.la/AbC123⁠"]` THEN `url` SHALL ser `https://meli.la/AbC123`; WHEN `links == ["⁠"]` THEN `url` SHALL ser `""` (WA-01).
3. WHEN `DS_URL_ORIGEM` tem U+2060 THEN `url` SHALL vir limpa e o log SHALL ser a linha inteira esperada; WHEN limpa THEN sem log (LJ-01, LJ-02).
4. WHEN `abrir` levanta `UnicodeEncodeError` THEN `(None, URL_NAO_RECONHECIDA)`; WHEN `OSError` THEN `API_INDISPONIVEL` (SH-01, SH-02).
5. WHEN a linha suja segue `_adaptar_linhas` → `_processar_lote` THEN as URLs recebidas por `abrir` SHALL não ter `Cf` (SH-03).

## Requirement Traceability
| ID | Status |
|---|---|
| URL-01 | T1 |
| URL-02 | T1 |
| WA-01 | T1 |
| LJ-01 | T2 |
| LJ-02 | T2 |
| SH-01 | T3 |
| SH-02 | T3 |
| SH-03 | T3 |
