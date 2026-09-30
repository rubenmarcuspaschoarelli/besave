# BSV-12c — Índice local da KVS de redirects

Fonte: `docs/specs/BSV-12c.md` (escopo); MANIFEST §5, §6.
Pasta: `apps/worker/`. Depende de BSV-12 e BSV-13b (ambos em `develop`).

## Problem Statement

Um ciclo sem mudança leva ~530 s, e `t_redirects_listagem` responde por ~490 s. `gerar()` lista a
KVS inteira (~11,6 mil chaves, paginada) **duas vezes** por ciclo: uma no início (base do expurgo
de imagens) e outra em `sincronizar_redirects` (diff). Com ciclo de 5 min (BSV-14) isso não cabe.

## Goals

- [ ] Ciclo sem mudança: 0 `listar()`, 1 `DescribeKeyValueStore`, 0 `UpdateKeys`; total real < 60 s.
- [ ] A KVS só é listada quando o índice não é confiável, e no máximo uma vez por ciclo.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Agendamento | BSV-14 |
| Mudança da CloudFront Function | spec: fora de escopo |
| Trocar a KVS por outro armazenamento | spec: fora de escopo |
| Suprimir o `WARN` de reconstrução no `--gerar` local | O espelho local usa `RedirectsMemoria` nova a cada execução; ver assunções |
| `PublicadorPlano` repassar `existem`/`gravar_lote` | achado da BSV-13b, ticket futuro |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Contrato do trait | `Redirects` ganha `descrever() -> EstadoKvs { item_count, etag }` (= `DescribeKeyValueStore`) e `aplicar` passa a devolver o `EstadoKvs` da última `UpdateKeys` | Spec §3 prefere o `ETag` devolvido pela `UpdateKeys`; um `Describe` final abriria janela para absorver escrita externa no índice. O SDK 1.111 devolve `item_count` e `e_tag` em `UpdateKeysOutput` | y |
| Uma única listagem | No modo `reconstrucao`, a listagem do início de `gerar()` é a base do diff e do expurgo; `sincronizar` não lista de novo | Hoje são duas listagens por ciclo; a spec pede "1 `listar()` completo" na reconstrução | y |
| Base do expurgo de imagens | Modo `indice`: ids do índice; modo `reconstrucao`: ids da listagem | O índice espelha o conjunto publicado, igual à KVS (decisão da BSV-12) | y |
| Ordem das checagens | ausente → `indice_ausente`; JSON inválido ou sem os campos → `indice_ilegivel`; `ETag` diferente → `etag_divergente`; `ItemCount` diferente → `item_count_divergente` | `ETag` muda em toda escrita, então é o sinal principal; `ItemCount` é a segunda trava da spec §2 | n |
| Falha de leitura do índice (erro de S3, não conteúdo) | Propaga como erro e aborta o ciclo antes de qualquer escrita | Não é "índice ilegível": o bucket está inacessível e o manifest também falharia. Mesmo tratamento da leitura de `manifest.json` | n |
| Diff | Por hash16 (SHA-256, 8 bytes em hex, `paginas::hash16`) da URL trimada | Spec §1; mesma função do índice de páginas | n |
| Quando gravar o índice | Sempre que os bytes novos diferem dos lidos (ausente, ilegível, divergente ou diff aplicado); igual → não grava | Regra de idempotência do worker: ciclo sem mudança só sobe os manifests | y |
| Chaves não numéricas na KVS | Contam no `ItemCount` (é o número da KVS), mas não entram em `urls` | `listar()` já as ignora; o índice guarda o `ItemCount` que a própria KVS devolve | n |
| `--publicar` sem `--sim` | `RedirectsPlano::descrever` repassa ao destino; `aplicar` registra as ops e devolve `descrever()` do destino; o índice vira uma op `gravar` no plano | O plano não escreve nada, mas mostra a gravação do índice | n |
| `RedirectsMemoria` | `ETag` = `m{n}`, com `n` = escritas desde a criação (`aplicar` e `inserir_bruto`); `ItemCount` = todas as chaves; contadores de `listar` e `descrever`; `definir_etag` força o `ETag` (teste de `item_count_divergente`) | Spec: "`ETag` que muda a cada escrita"; `inserir_bruto` simula escrita por fora | n |
| `--gerar` local | `RedirectsMemoria::new()` a cada execução → toda execução local reconstrói (motivo `etag_divergente` a partir da 2ª) e loga `WARN` | O espelho local não tem KVS; o comportamento é correto (a KVS em memória está vazia) | y |
| Teste SIT-01 (`primeira_execucao_publica_...`) | A lista esperada de chaves do site ganha `_estado/redirects.json` | Objeto novo exigido pela spec; nenhuma asserção enfraquecida | y |
| Testes com `impl Redirects` próprio (`tests/geracao.rs`, `tests/plano.rs`) e o literal de `RelatorioRedirects` | Ganham `descrever` e o novo retorno de `aplicar`; o literal recebe `modo`/`motivo` | Mudança de assinatura do trait | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Ciclo sem listar a KVS ⭐ MVP

**User Story**: Como dono, quero que um ciclo sem mudança não percorra a KVS inteira, para caber no ciclo de 5 min.

**Acceptance Criteria**:

1. IDX-01: WHEN o índice é válido e nada mudou THEN `gerar` SHALL fazer 0 chamadas a `listar()`, 1 a `descrever()` e 0 a `aplicar()`, e reportar `modo = indice`.
2. IDX-02: WHEN, com índice válido, o conjunto publicado tem 3 URLs novas, 1 alterada e 2 removidas THEN `gerar` SHALL chamar `aplicar` uma vez, com exatamente esses 4 puts e 2 deletes.
3. IDX-03: WHEN um diff é aplicado THEN o índice gravado SHALL conter o `ETag` e o `ItemCount` que a KVS tem depois da escrita e um hash16 por id publicado.
4. IDX-04: WHEN nada mudou e o índice é válido THEN `gerar` SHALL NOT gravar `_estado/redirects.json`.
5. IDX-05: The worker SHALL gravar o índice em `_estado/redirects.json` com `Content-Type: application/json` e `Cache-Control: no-store`.
6. IDX-06: The índice SHALL NOT conter URL em claro (nenhuma ocorrência de `http` no JSON).
7. IDX-07: WHILE em modo `indice`, `gerar` SHALL tirar do índice o conjunto de ids anteriores usado no expurgo de imagens e fazer 0 chamadas a `listar()` no ciclo inteiro (dono, revisão de 30/09/2026); WHEN um id sai do conjunto publicado THEN `gerar` SHALL remover as duas imagens desse id.

**Independent Test**: dois `gerar` seguidos sobre o mesmo `PublicadorMemoria` + `RedirectsMemoria`; o 2º não lista.

### P1: Reconstrução quando o índice não é confiável

**User Story**: Como dono, quero que qualquer dúvida sobre o índice caia no caminho completo, porque a KVS é a verdade para o CloudFront.

**Acceptance Criteria**:

1. REC-01: IF o índice não existe THEN `gerar` SHALL listar a KVS exatamente 1 vez, reportar `modo = reconstrucao` com motivo `indice_ausente` e gravar o índice; e o ciclo seguinte SHALL reportar `modo = indice`.
2. REC-02: IF o `ETag` da KVS difere do índice THEN `gerar` SHALL reconstruir com motivo `etag_divergente` e deixar a KVS igual ao conjunto publicado.
3. REC-03: IF o `ETag` bate mas o `ItemCount` difere THEN `gerar` SHALL reconstruir com motivo `item_count_divergente`.
4. REC-04: IF o índice não é um JSON com `kvs_item_count`, `kvs_etag` e `urls` THEN `gerar` SHALL reconstruir com motivo `indice_ilegivel`, sem abortar, e regravar o índice.
5. REC-05: WHEN reconstrói THEN o worker SHALL registrar um `WARN` com o motivo.
6. REC-06: IF gravar o índice falha THEN `gerar` SHALL retornar erro e SHALL NOT gravar `manifest.json`.

**Independent Test**: índice ausente, corrompido e KVS alterada por `inserir_bruto`.

### P1: Relatório

**User Story**: Como dono, quero ver no relatório qual caminho o ciclo tomou.

**Acceptance Criteria**:

1. REL-01: `RelatorioRedirects` SHALL trazer `modo` (`indice` | `reconstrucao`) e `motivo` (`indice_ausente` | `indice_ilegivel` | `etag_divergente` | `item_count_divergente`, só na reconstrução), com esses textos exatos no `Display`.
2. REL-02: WHEN o `--publicar` termina THEN o binário SHALL imprimir `redirects_modo: <modo>` e `redirects_motivo_reconstrucao: <motivo | ->`.

---

## Edge Cases

- WHEN o conjunto publicado fica vazio em modo `indice` THEN todos os ids do índice SHALL virar deletes (IDX-02 × vazio).
- IF a KVS falha em `aplicar` THEN `gerar` SHALL retornar erro sem gravar índice nem manifest (comportamento da BSV-12 mantido).
- WHEN o índice tem a URL de um id com hash diferente THEN esse id SHALL virar put (IDX-02, "alterada").

Dimensions: estado persistido (IDX-03..05, REC-04); falha de dependência externa (REC-06, edge de `aplicar`); idempotência (IDX-01, IDX-04); integridade de transição de estado (REC-01..03); observabilidade (REC-05, REL-01..02); dados sensíveis (IDX-06). Auth, rate limit e concorrência: N/A because o worker é o único escritor previsto da KVS e roda um ciclo por vez; escrita externa cai em REC-02.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IDX-01 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-02 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-03 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-04 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-05 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-06 | P1: Ciclo sem listar | Step 2 | Pending |
| IDX-07 | P1: Ciclo sem listar | Step 2 | Pending |
| REC-01 | P1: Reconstrução | Step 2 | Pending |
| REC-02 | P1: Reconstrução | Step 2 | Pending |
| REC-03 | P1: Reconstrução | Step 2 | Pending |
| REC-04 | P1: Reconstrução | Step 2 | Pending |
| REC-05 | P1: Reconstrução | Step 2 | Pending |
| REC-06 | P1: Reconstrução | Step 2 | Pending |
| REL-01 | P1: Relatório | Step 2 | Pending |
| REL-02 | P1: Relatório | Step 3 | Pending |

**Coverage:** 15 total, 15 mapped to steps, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde, sem rede.
- [ ] Execução real do dono: 1ª `--publicar --sim` → `reconstrucao` (`indice_ausente`); 2ª → `indice`, `t_redirects` < 5 s, total < 60 s; `curl -I https://<cf>/ir/<id novo>` → 302.
