# BSV-45 — Imagem de oferta reenviada por hash, não por existência de chave

Fonte: `docs/specs/BSV-45.md` (escopo); MANIFEST §1, §6; CONTRATO §6; AD-028, AD-041, AD-042, AD-044.
Pasta: `apps/worker/` + `docs/MANIFEST.md`. Depende de BSV-13b, BSV-21 e BSV-47 (em `develop`).

## Problem Statement

O worker decide o envio de imagem por existência de chave: lista `img/ofertas/` a cada ciclo (60
`ListObjectsV2` para 59.597 chaves) e pula o id cujas duas chaves já existem. Imagem trocada no espelho
com o mesmo id nunca sobe (caso de 19/10/2026, 15 ofertas da diaenoite). A página de oferta já resolve
isso por hash (`_estado/paginas.json`); a imagem passa a usar o mesmo molde.

## Goals

- [ ] Imagem trocada no espelho sobe sozinha no ciclo seguinte, sem apagar chave no S3.
- [ ] Ciclo sem mudança: 0 upload de imagem, 0 listagem de `img/ofertas/`, índice não regravado.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| `img/produtos/`, `img/avisos/` | Aviso já tem `_estado/avisos.json` |
| Invalidação de CloudFront pelo worker | Ticket próprio; decisão proposta no PR |
| Backfill do `capture-store-pages` | Já existe |
| Reduzir `paginas.json` / `redirects.json` | Fora do ticket |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Hash | `hash16` do SHA-256 de `{id}.webp` ++ `{id}-small.webp` lidos do espelho | Spec §Saídas 1; `ajustar_small` é determinística, a origem identifica o par | y |
| Marca da última listagem | Chave reservada `_relistado_em` no próprio `imagens.json` (segundos Unix UTC, texto); chaves `_*` desconhecidas são ignoradas | A reconciliação periódica precisa de relógio persistido; um arquivo só, sem chave nova no S3 | n |
| Índice sem `_relistado_em` | Conta como "nunca reconciliado": lista uma vez e grava a marca | Índice escrito por versão sem a marca não pode ficar eternamente sem reconciliar | n |
| Formato inválido | Não é objeto JSON de strings; chave de id (só dígitos) com valor que não seja 16 hex minúsculos; `_relistado_em` não numérico | Spec: "valor fora do formato" reconstrói | n |
| Reconstrução com bucket intacto | Id com as duas chaves no bucket e fora do índice recebe o hash da origem **sem upload** | Spec regra 5: 1º ciclo após o deploy = 0 uploads | y |
| Reconciliação com índice intacto | Na listagem periódica, id cujo par não está inteiro no bucket sobe de novo, mesmo com hash igual | Spec regra 1 (chave apagada à mão volta depois da janela) | y |
| Reconciliação única do expurgo (BSV-47) | Se `fila.reconciliado()` é falso, o ciclo lista `img/ofertas/` (a reconciliação precisa dos ids) | `FilaExpurgo::reconciliar` consome a listagem; roda uma vez na vida do bucket | n |
| Falha de upload | O bloco que falhou não entra no índice; blocos já enviados entram e o índice é gravado antes de o erro subir | Spec regra 2 sem perder o progresso dos blocos bons | n |
| `reenviadas` | Id que já estava no índice com hash diferente e subiu; também conta em `publicadas` | Distingue imagem trocada de imagem nova | n |
| `executar` do expurgo | Ganha `&mut IndiceImagens`; depois de cada `DeleteObjects` o índice é gravado **antes** da fila | Queda entre os dois grava fila com id já fora do índice (repete o delete, inofensivo); a ordem inversa deixaria hash velho e a reentrada do id não subiria | n |
| Config | `ConfigImagens` dentro de `ConfigSite`: `BESAVE_IMAGENS_RELISTAR` (`0`/`1`/`true`/`false`) e `BESAVE_IMAGENS_RELISTAR_HORAS` (inteiro ≥ 0, padrão 24); `0` horas = lista todo ciclo | `gerar` não muda de assinatura | n |
| Placeholders | Listados todo ciclo (`img/placeholder/`, 1 chamada), comportamento atual | Spec §Saídas 3 | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Imagem trocada sobe sozinha ⭐ MVP

**User Story**: Como dono, quero que trocar a foto no espelho local faça o site servir a nova, sem apagar chave à mão.

**Acceptance Criteria**:

1. IMG-01: WHEN o arquivo de um id já publicado muda no espelho com o mesmo nome THEN `publicar_imagens` SHALL gravar as duas chaves do id, reportar `reenviadas = 1` e SHALL NOT remover chave nenhuma.
2. IMG-02: WHEN o id não está no índice e o bucket não tem as chaves THEN `publicar_imagens` SHALL gravar as duas chaves, contar em `publicadas` (e não em `reenviadas`) e pôr o id no índice com o hash da origem.
3. IMG-03: The índice `_estado/imagens.json` SHALL ser um objeto plano `id → hash16` (SHA-256 de `{id}.webp` ++ `{id}-small.webp`, 16 hex), gravado com `Content-Type: application/json` e `Cache-Control: no-store`, sem nenhuma URL.
4. IMG-04: WHEN o índice muda THEN o worker SHALL gravá-lo depois dos uploads de imagem do ciclo; WHEN não muda THEN SHALL NOT gravá-lo.

### P1: Ciclo sem mudança não lista

**Acceptance Criteria**:

1. IDE-01: WHEN o espelho não mudou e o índice é válido e recente THEN o 2º ciclo SHALL fazer 0 uploads de imagem, 0 listagens de `img/ofertas/` e 0 gravações do índice; o relatório SHALL trazer `reaproveitadas` igual ao número de ids.
2. IDE-02: WHILE o índice é válido THEN `publicar_imagens` SHALL listar `img/placeholder/` todo ciclo; placeholder ausente SHALL ser publicado e presente SHALL NOT ser republicado.

### P1: Reconstrução e reconciliação

**Acceptance Criteria**:

1. REC-01: IF o índice está ausente THEN o ciclo SHALL listar `img/ofertas/` uma vez, SHALL NOT gravar imagem cujo par já está no bucket, SHALL gravar o índice com o hash de cada id, e o ciclo seguinte SHALL NOT listar.
2. REC-02: IF o índice é JSON inválido, não é objeto de strings ou tem valor de id fora de 16 hex THEN o ciclo SHALL registrar `WARN`, reconstruir como em REC-01 e SHALL NOT retornar erro.
3. REC-03: WHEN `BESAVE_IMAGENS_RELISTAR=1` THEN o ciclo SHALL listar `img/ofertas/` mesmo com índice válido.
4. REC-04: WHEN `BESAVE_IMAGENS_RELISTAR_HORAS=0` THEN todo ciclo SHALL listar; com o padrão (24) SHALL NOT listar antes de 24 h da última listagem registrada no índice e SHALL listar depois.
5. REC-05: WHEN uma chave de imagem é apagada do bucket com o índice intacto THEN ela SHALL NOT voltar antes da janela de reconciliação e SHALL voltar no 1º ciclo depois dela.
6. REC-06: The config SHALL rejeitar `BESAVE_IMAGENS_RELISTAR` e `BESAVE_IMAGENS_RELISTAR_HORAS` inválidas com `ErroConfigSite`.

### P1: Falhas não entram no índice

**Acceptance Criteria**:

1. FAL-01: IF o id não tem origem no espelho THEN `publicar_imagens` SHALL contá-lo em `sem_origem`, SHALL NOT gravá-lo no índice e SHALL tentá-lo de novo no ciclo seguinte.
2. FAL-02: IF o `gravar_lote` falha THEN os ids do bloco SHALL NOT entrar no índice, os blocos já enviados SHALL entrar, e o ciclo seguinte SHALL reenviar os do bloco que falhou.
3. FAL-03: IF a origem não é WebP ou a recodificação falha THEN o id SHALL ficar fora do índice (e, se já estava, SHALL manter o hash anterior).

### P1: Expurgo pela fila (BSV-47)

**Acceptance Criteria**:

1. EXP-01: WHEN um id sai do conjunto publicado THEN ele SHALL continuar no índice até a fila apagar as imagens dele.
2. EXP-02: WHEN a fila apaga as imagens de um id na janela THEN as 2 chaves SHALL sair do bucket **e** o id SHALL sair do índice gravado.
3. EXP-03: WHEN o mesmo id volta ao conjunto depois do expurgo THEN as imagens SHALL subir de novo.
4. EXP-04: WHEN o id é reativado antes da janela THEN ele SHALL sair da fila, SHALL continuar no índice e SHALL NOT ser reenviado.

### P1: Orçamento e relatório

**Acceptance Criteria**:

1. ORC-01: The índice com 30.000 ids SHALL ter no máximo 1 MB.
2. REL-01: The linha do ciclo agendado SHALL trazer `t_imagens_listagem` e `imagens_reenviadas`; o `--publicar` SHALL imprimir `imagens_reenviadas`.

---

## Edge Cases

- WHEN o índice tem ids que não estão nem no conjunto publicado nem na fila THEN `gerar` SHALL mantê-los (só a fila remove).
- WHEN há chaves estranhas em `img/ofertas/` THEN a listagem SHALL só contá-las (comportamento da BSV-13b).

Dimensions: estado persistido (IMG-03/04, REC); falha de dependência externa (FAL-02); idempotência (IDE-01); transição de estado (EXP); observabilidade (REL-01); dados sensíveis (IMG-03). Auth, rate limit, concorrência: N/A porque o worker roda um ciclo por vez, único escritor do índice.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IMG-01 | P1: Imagem trocada | Execute | Done |
| IMG-02 | P1: Imagem trocada | Execute | Done |
| IMG-03 | P1: Imagem trocada | Execute | Done |
| IMG-04 | P1: Imagem trocada | Execute | Done |
| IDE-01 | P1: Sem mudança | Execute | Done |
| IDE-02 | P1: Sem mudança | Execute | Done |
| REC-01 | P1: Reconstrução | Execute | Done |
| REC-02 | P1: Reconstrução | Execute | Done |
| REC-03 | P1: Reconstrução | Execute | Done |
| REC-04 | P1: Reconstrução | Execute | Done |
| REC-05 | P1: Reconstrução | Execute | Done |
| REC-06 | P1: Reconstrução | Execute | Done |
| FAL-01 | P1: Falhas | Execute | Done |
| FAL-02 | P1: Falhas | Execute | Done |
| FAL-03 | P1: Falhas | Execute | Done |
| EXP-01 | P1: Expurgo | Execute | Done |
| EXP-02 | P1: Expurgo | Execute | Done |
| EXP-03 | P1: Expurgo | Execute | Done |
| EXP-04 | P1: Expurgo | Execute | Done |
| ORC-01 | P1: Orçamento | Execute | Done |
| REL-01 | P1: Orçamento | Execute | Done |

**Coverage:** 21 total, 21 mapped to steps, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde, sem rede.
- [ ] Execução real do dono (3 ciclos) conforme a spec do ticket.
