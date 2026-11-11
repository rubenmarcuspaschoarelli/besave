# BSV-59 Robô das lojas: Shopee pela API de afiliados Specification

Fonte: `docs/specs/BSV-59.md`. Depende da BSV-55 (linha retida, `PausaLojas`, Telegram). Lições 11, 14, 16, 29.

## Problem Statement

A Shopee é capturada pelo navegador (página do produto com seletores de hash e gerador de link de afiliado
com sessão). Os dois quebram: em 30 dias metade das ofertas da Shopee caiu em `bloqueado_ou_login`,
`pagina_sem_produto` ou ficou retida por sessão de afiliado. A API GraphQL de afiliados da Shopee devolve o
produto (`productOfferV2`) e gera o link (`generateShortLink`) sem navegador.

## Goals

- [ ] Com `shopee_afiliado.habilitado: true`, linha da Shopee é capturada pela API, sem abrir página nem gerador.
- [ ] Falha passageira da API retém a linha e entra na pausa da Shopee com aviso; falha do item vira `'9'` com motivo.
- [ ] `habilitado: false` ou bloco ausente = fluxo de hoje.
- [ ] Credencial nunca sai em log, exceção, CSV ou Telegram.

## Out of Scope

Vitrine da API, colunas novas (`productCatIds`, `shopName`, faixa de variantes), remover o código do navegador,
`subIds`, gates de login no arranque (`--sem-perguntas` já não pergunta), execução real na inst1 (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Corpo enviado | `json.dumps({"query": q}, separators=(",", ":"))` uma vez; os mesmos bytes UTF-8 assinados e enviados | Spec saída 2 | y |
| Ids na query | Inteiros embutidos no texto da query (`shopId: 1, itemId: 2`), sem `variables` | Forma provada pelo dono; ids validados como dígitos | n |
| Comparação do `itemId` | `str(node.itemId) == str(item_id)` (aceita número ou texto no JSON) | Int64 pode vir como texto | n |
| `price` inválido | Vazio, não numérico, não finito ou ≤ 0 → `item_divergente` | Spec, critério Produto | y |
| `taxa_comissao_afiliado` | `"0.13"` → `"13%"`, `"0.135"` → `"13,5%"` (percentual com vírgula, como a página mostra no ML/Amazon) | "mesmo formato que Amazon/ML" | n |
| `avaliacao_nota`, `quantidade_vendida` | Texto da API sem conversão (`"4.6"`, `"1351"`); o `oracle_db` converte como hoje | Spec tabela | y |
| `url_final` | URL do item resolvida (último `Location`), como o navegador gravaria; `url_besave` como hoje | DS_URL_FINAL é referência | n |
| Imagem | `download_image(imageUrl, <img_root>/<captura>/img_1.jpg)`; falha da imagem não derruba a linha | Spec tabela; imagem é best-effort hoje | n |
| `shortLink` ausente sem `errors` | `api_indisponivel` (retida) | Sem link a oferta não vai ao site | n |
| Resolução: pedido | `HEAD` sem seguir redirect, só para hosts `shopee.com.br`/`*.shopee.com.br`; destino fora disso → `url_nao_reconhecida` | Medição com `curl -sI` | n |
| Resolução: rede | Timeout, erro de rede, HTTP 5xx/429 → `api_indisponivel` (retida); 2xx/4xx sem `Location` → `url_nao_reconhecida` | Falha passageira nunca vira `'9'` | n |
| Saltos | Até 3 pedidos; ids ainda ausentes → `url_nao_reconhecida` | Spec saída 3 | y |
| Aviso da pausa | Motivo `shopee_api`: "Shopee em pausa: API de afiliados <motivo> (<mensagem>)"; `api_credencial` acrescenta "conferir app_id/app_secret" | Spec saída 5 | n |
| Config | Lido a cada lote (`_processar_lote`), como `redirecionamento` | Ligar/desligar sem reiniciar o processo além do robô | n |

Open questions: none

---

## User Stories

### P1: Shopee pela API ⭐ MVP

**Acceptance Criteria**:

1. CFG-01: WHEN o bloco `shopee_afiliado` falta ou `habilitado` não é `true`, THE SYSTEM SHALL capturar a Shopee pelo navegador como hoje.
2. ASS-01: THE SYSTEM SHALL enviar `Authorization: SHA256 Credential=<app_id>, Timestamp=<ts>, Signature=<hex>`, com `<hex>` = SHA-256 de `app_id + ts + payload + app_secret`, e o corpo SHALL ser byte a byte o `payload` assinado.
3. RES-01: WHEN a URL é `s.shopee.com.br`, THE SYSTEM SHALL pedir sem seguir redirect, ler o `Location` e repetir até 3 pedidos, extraindo `shopId`/`itemId` de `/<x>/<shop>/<item>` ou `-i.<shop>.<item>` (inclusive em `/universal-link/`).
4. RES-02: IF após 3 pedidos não há ids, ou o destino não tem ids, THEN THE SYSTEM SHALL marcar `'9' url_nao_reconhecida`.
5. PRO-01: WHEN `productOfferV2(shopId, itemId)` devolve 1 nó do item, THE SYSTEM SHALL preencher `produto_titulo`, `preco_1` (Decimal, 2 casas), `avaliacao_nota`, `quantidade_vendida`, `taxa_comissao_afiliado`, `id_produto_afiliado` (`<shop>.<item>`) e baixar `imageUrl` em `img_1.jpg`.
6. PRO-02: IF a resposta tem 0 nós, THEN THE SYSTEM SHALL marcar `'9' fora_do_programa`; IF o nó é de outro item, há mais de 1 nó ou `price` é vazio/não numérico, THEN SHALL marcar `'9' item_divergente`.
7. LNK-01: THE SYSTEM SHALL gerar o link com `originUrl` exatamente `https://shopee.com.br/product/<shop>/<item>` e gravar o `shortLink` em `url_afiliado`.
8. NAV-01: WHILE `habilitado` é `true`, THE SYSTEM SHALL NOT navegar para a Shopee nem chamar o gerador do navegador.
9. ERR-01: WHEN a resposta HTTP 200 traz `errors` com código `10020`, THE SYSTEM SHALL classificar `api_credencial` com a mensagem; `10030` → `api_limite`; outro código → `api_indisponivel`; timeout, erro de rede, HTTP ≠ 200 ou JSON ilegível → `api_indisponivel`.
10. FAL-01: IF o motivo é `api_indisponivel`, `api_credencial` ou `api_limite`, THEN THE SYSTEM SHALL reter a linha (`shopee_api_indisponivel`, `oracle=retida(0)`), nada gravado, ponteiro travado.
11. PAU-01: WHEN a Shopee soma 3 falhas seguidas da API, THE SYSTEM SHALL pausá-la com 1 aviso com o motivo (e "conferir app_id/app_secret" em `api_credencial`), seguir Amazon/ML, e WHEN volta SHALL avisar "voltou" e processar a retida.
12. SEG-01: THE SYSTEM SHALL NOT escrever `app_id`, `app_secret` nem a assinatura em stdout, log, exceção, CSV ou Telegram.
13. DOC-01: THE SYSTEM SHALL documentar no README (seção Shopee) o que a API traz e o que se perdeu, `habilitado`, onde fica a credencial e cada motivo; e o bloco em `config.example.json`; e o SQL das retidas antigas.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CFG-01 | P1 | Execute | Pending |
| ASS-01 | P1 | Execute | Done |
| RES-01 | P1 | Execute | Pending |
| RES-02 | P1 | Execute | Pending |
| PRO-01 | P1 | Execute | Done |
| PRO-02 | P1 | Execute | Done |
| LNK-01 | P1 | Execute | Done |
| NAV-01 | P1 | Execute | Pending |
| ERR-01 | P1 | Execute | Done |
| FAL-01 | P1 | Execute | Pending |
| PAU-01 | P1 | Execute | Pending |
| SEG-01 | P1 | Execute | Pending |
| DOC-01 | P1 | Execute | Pending |

## Success Criteria

- [ ] `pytest` e `ruff check vps/ tests/` verdes em `tools/`; Verifier independente PASS; teste real do dono na inst1.
