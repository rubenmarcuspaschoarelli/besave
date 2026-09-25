# BSV-11 — Worker: geração de chunks + manifest em disco (sem S3)

Fonte: `docs/specs/BSV-11.md`. Contrato: `docs/MANIFEST.md` §2, §3, §4, §6, §7; `docs/CONTRATO.md` §3, §7;
`packages/contract/schema/{chunk,manifest}.schema.json`.

## Problem Statement

BSV-10 converte linhas do Oracle em `OfertaCard`, mas nada vira arquivo. O site precisa de chunks
imutáveis endereçados por hash e de um `manifest.json` que aponte para eles. Este ticket gera esses
arquivos numa pasta local com o layout do bucket, atrás de um trait `Publicador` que BSV-12 vai
implementar para o S3.

## Goals

- [ ] `BESAVE_FONTE=fake cargo run -- --gerar --saida <dir>` produz `data/chunks/{n}-{hash}.json.br`, `manifest.json` e os `.meta.json`.
- [ ] Chunks e manifest gerados validam contra `chunk.schema.json` e `manifest.schema.json`.
- [ ] Segunda execução sem mudança não grava nem remove nenhum chunk.
- [ ] 30 000 cards geram em ≤ 10 s em memória (`cargo test`).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Upload S3, KVS de redirects | BSV-12 |
| Imagens | BSV-13 |
| Agendamento | BSV-14 |
| Páginas HTML, sitemap, apagar `oferta/{id}/` no expurgo | BSV-21 |
| Índice de busca (`busca` fica `null`) | BSV-34 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Quais linhas viram card | As que passam em `para_card` **e** têm `id_produto ≥ 1` (mesmas rejeições do `--dry-run`); o produto não é buscado | Card cuja página é rejeitada apontaria para `/oferta/{id}/` inexistente; contagens ficam iguais às do `--dry-run` (critério "coerente com BSV-10") sem 30k consultas a PRODUTO | n |
| `total_ofertas` | Número de cards publicados nos chunks (ativos + expirados `x:1`) = soma de `qtd` | MANIFEST §2 não define; é o total que o cliente vai ter após baixar tudo | n |
| Chaves de `areas` | Só áreas com ≥ 1 card ativo; área ausente = 0 | Igual ao exemplo do MANIFEST §2; schema não exige as 9 | n |
| `serializar_chunk` e `comprimir_br` | Retornam `Result<_, ErroChunk>` em vez de tupla / `Vec<u8>` | `serde_json::to_vec` e `BrotliCompress` são falíveis; a regra "sem `unwrap`" vence a assinatura ilustrativa da spec | n |
| Orçamento de 61 440 B | Todos os chunks são serializados e comprimidos antes de qualquer gravação; se algum excede, `gerar` falha sem gravar nada | Regra 6 ("não publica"); evita chunks órfãos de uma execução abortada | n |
| "Manifest anterior" (regra 5) | O `manifest.json` lido no início da execução. Órfão = chave em `data/chunks/` que não está no manifest novo nem nesse anterior | Com o anterior protegendo 1 ciclo, o chunk antigo some na 3ª execução, como pede o critério de aceite | n |
| `manifest.prev.json` | Cópia byte a byte do `manifest.json` anterior, gravada depois dos chunks e antes do manifest novo, com os mesmos headers do manifest; não é gravado na primeira execução | Spec pede guardar o anterior na saída | n |
| Idempotência (regra 7) | Sem mudança na fonte: 0 chunks gravados, 0 removidos; `manifest.json` e `manifest.prev.json` são regravados | Os dois são manifests; nenhum objeto imutável muda | n |
| `manifest.json` anterior ilegível ou fora do schema do `Manifest` | `gerar` falha com erro nomeando `manifest.json`, sem gravar nada | Tratar como ausente apagaria chunks que clientes com manifest em cache ainda pedem | n |
| Headers (`Meta`) | Chunks: `application/json`, `br`, `public, max-age=31536000, immutable`. Manifest e prev: `application/json`, sem encoding, `public, max-age=300, stale-while-revalidate=60` | MANIFEST §4 | n |
| `.meta.json` | `<chave>.meta.json` ao lado do arquivo: `{"content_type":…,"content_encoding":…\|null,"cache_control":…}`; `listar` não devolve sidecars; `remover` apaga o sidecar junto | Os headers são metadado do objeto, não objeto do bucket | n |
| `contrato` | `version` do `packages/contract/package.json` embutido com `include_str!` e lido com `serde_json` | Spec regra 3; evita constante que diverge | n |
| `versao` | `YYYYMMDDhhmmss` de `agora` (UTC); duas execuções no mesmo segundo dão a mesma `versao` | Worker roda a cada 5–10 min; não vale guarda extra | n |
| `id ≤ 0` | Cai em `n = 0` | `ID_OFERTA` é PK de sequência (≥ 1); schema do card já exige `id ≥ 1` | n |
| Falha em `remover` órfão | `gerar` retorna erro (o manifest já foi gravado e é consistente); o próximo ciclo tenta de novo | Erro visível no log/exit code, sem estado inconsistente | n |
| Relatório no binário | Linhas `chave: valor` no stdout, como o `--dry-run` | Mesmo formato já testado em BSV-10 | n |
| Dependência de teste `jsonschema` (dev, sem features padrão) | Valida chunk e manifest gerados contra os schemas do contrato | Critério de aceite pede validação contra schema; alternativa (Node + ajv) depende de `npm ci` no CI do worker. Sem `default-features` para não puxar HTTP/TLS | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Publicador ⭐ MVP

**User Story**: Como worker, quero gravar objetos por um trait `Publicador` para trocar disco por S3 (BSV-12) sem mexer na geração.

**Why P1**: A geração só fala com o trait; os testes usam a implementação em memória.

**Acceptance Criteria**:

1. WHEN `PublicadorLocal::gravar(chave, bytes, meta)` é chamado THEN o publicador SHALL gravar `bytes` em `raiz/chave` (criando pastas) e os headers em `raiz/chave.meta.json`.  <!-- PUB-01 -->
2. WHEN `ler(chave)` é chamado THEN o publicador SHALL devolver os bytes gravados, ou `None` se a chave não existe; `existe` SHALL devolver `true`/`false` na mesma condição.  <!-- PUB-02 -->
3. WHEN `listar(prefixo)` é chamado THEN o publicador SHALL devolver as chaves (separador `/`) que começam com `prefixo`, sem os sidecars `.meta.json`.  <!-- PUB-03 -->
4. WHEN `remover(chave)` é chamado THEN o publicador SHALL apagar o objeto e seu `.meta.json`.  <!-- PUB-04 -->
5. The `PublicadorMemoria` SHALL ter o mesmo comportamento de PUB-02..04 e expor os headers gravados por chave.  <!-- PUB-05 -->

**Independent Test**: `cargo test --test publicador`.

---

### P1: Chunks ⭐ MVP

**User Story**: Como site, quero chunks por faixa de id, comprimidos e com nome por hash, para cachear para sempre e baixar só o que mudou.

**Why P1**: É o dado da lista.

**Acceptance Criteria**:

1. WHEN `particionar` recebe cards com ids 999, 1000, 1999, 2000 THEN a função SHALL colocá-los em `n` = 0, 1, 1, 2.  <!-- CHK-01 -->
2. The chunk SHALL conter os cards ordenados por `id` crescente, qualquer que seja a ordem de entrada.  <!-- CHK-02 -->
3. WHEN `serializar_chunk` recebe os cards de `chunk-ok.json` THEN a função SHALL devolver o JSON compacto idêntico à fixture compactada e hash `89590e56ef6361dc` (16 hex do SHA-256 do JSON).  <!-- CHK-03 -->
4. WHEN um chunk gerado é descomprimido com Brotli THEN o resultado SHALL ser o JSON do chunk e SHALL validar contra `chunk.schema.json`.  <!-- CHK-04 -->
5. The chunk SHALL ser gravado em `data/chunks/{n}-{hash}.json.br` com `Content-Type: application/json`, `Content-Encoding: br` e `Cache-Control: public, max-age=31536000, immutable`.  <!-- CHK-05 -->

**Independent Test**: `cargo test --test chunks`.

---

### P1: Manifest ⭐ MVP

**User Story**: Como site, quero um `manifest.json` que liste os chunks atuais para saber o que baixar.

**Why P1**: Único arquivo mutável; sem ele o cliente não acha os chunks.

**Acceptance Criteria**:

1. WHEN `gerar` termina THEN o `manifest.json` gravado SHALL validar contra `manifest.schema.json`.  <!-- MAN-01 -->
2. The manifest SHALL ter `contrato` = `version` de `packages/contract/package.json`, `versao` = `YYYYMMDDhhmmss` UTC de `agora`, `gerado_em` = ISO 8601 UTC de `agora` e `busca: null`.  <!-- MAN-02 -->
3. The manifest SHALL listar os chunks ordenados por `n`, cada um com `ids` = [menor id, maior id] reais do chunk, `qtd` = número de cards, `bytes` = tamanho comprimido e `arquivo` = chave gravada.  <!-- MAN-03 -->
4. The manifest SHALL ter `areas` = contagem por área só dos cards sem `x`, e `total_ofertas` = total de cards publicados.  <!-- MAN-04 -->
5. The `manifest.json` SHALL ser a última gravação da execução, com `Cache-Control: public, max-age=300, stale-while-revalidate=60`.  <!-- MAN-05 -->
6. IF algum chunk comprimido tem mais de 61 440 bytes THEN `gerar` SHALL falhar com `ErroGeracao::ChunkAcimaDoOrcamento` e não gravar nenhum objeto.  <!-- MAN-06 -->
7. IF a gravação de um chunk falha THEN `gerar` SHALL retornar o erro sem gravar `manifest.json`.  <!-- MAN-07 -->
8. WHEN `gerar` termina THEN o `Relatorio` SHALL trazer lidas, válidas, rejeitadas por motivo, chunks escritos / reaproveitados / removidos, bytes totais comprimidos, maior chunk e `versao`.  <!-- MAN-08 -->

**Independent Test**: `cargo test --test geracao`.

---

### P1: Ciclo incremental ⭐ MVP

**User Story**: Como dono, quero que cada ciclo só grave o que mudou e limpe o que ninguém mais pede.

**Why P1**: Idempotência é requisito do worker (CLAUDE.md) e define o custo de upload em BSV-12.

**Acceptance Criteria**:

1. WHEN `gerar` roda duas vezes sem mudança na fonte THEN a segunda execução SHALL ter `chunks_escritos == 0` e `chunks_removidos == 0`, e nenhuma chave `data/chunks/` SHALL ser gravada.  <!-- CIC-01 -->
2. WHEN uma oferta do chunk 5 muda THEN a execução seguinte SHALL gravar só o novo chunk 5 e manter os demais `arquivo` do manifest iguais.  <!-- CIC-02 -->
3. WHEN um chunk sai do manifest THEN o arquivo antigo SHALL continuar em `data/chunks/` após a execução em que saiu e SHALL ser removido na execução seguinte.  <!-- CIC-03 -->
4. WHEN existe `manifest.json` anterior THEN `gerar` SHALL gravar uma cópia dele em `manifest.prev.json`.  <!-- CIC-04 -->
5. WHEN uma oferta sai da fonte (expurgo) THEN o chunk da sua faixa SHALL mudar de hash; IF a faixa fica vazia THEN o `n` SHALL sumir do manifest.  <!-- CIC-05 -->
6. WHEN a fonte tem 30 000 cards válidos THEN `gerar` com `PublicadorMemoria` SHALL terminar em ≤ 10 s no perfil de teste.  <!-- CIC-06 -->

**Independent Test**: `cargo test --test ciclo`.

---

### P1: Binário `--gerar` ⭐ MVP

**User Story**: Como dono, quero `cargo run -- --gerar --saida ./out` para ver a árvore que irá ao bucket.

**Why P1**: Critério de aceite do ticket e verificação contra o Oracle real.

**Acceptance Criteria**:

1. WHEN `--gerar --saida <dir>` roda com `BESAVE_FONTE=fake` THEN o binário SHALL criar `<dir>/manifest.json`, `<dir>/manifest.json.meta.json` e ≥ 1 `<dir>/data/chunks/*.json.br`, imprimir o relatório e sair com código 0.  <!-- CLI-01 -->
2. IF `--gerar` e `--dry-run` são passados juntos THEN o binário SHALL sair com erro, sem panic.  <!-- CLI-02 -->
3. IF `--gerar` é passado sem `--saida` THEN o binário SHALL sair com erro, sem panic.  <!-- CLI-03 -->

**Independent Test**: `BESAVE_FONTE=fake cargo run -- --gerar --saida <tmp>`.

---

## Edge Cases

- WHEN a fonte não entrega nenhuma oferta válida THEN o manifest SHALL ter `chunks: []`, `total_ofertas: 0` e `areas: {}`.
- WHEN todas as ofertas de uma área estão expiradas THEN a área SHALL estar ausente de `areas`, mas os cards SHALL continuar no chunk com `x:1`.
- WHEN `data/chunks/` já tem um arquivo com o nome do chunk (execução anterior) THEN `gerar` SHALL contá-lo como reaproveitado e não regravá-lo.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PUB-01 | P1: Publicador | T1 | Implemented |
| PUB-02 | P1: Publicador | T1 | Implemented |
| PUB-03 | P1: Publicador | T1 | Implemented |
| PUB-04 | P1: Publicador | T1 | Implemented |
| PUB-05 | P1: Publicador | T1 | Implemented |
| CHK-01 | P1: Chunks | T2 | Implemented |
| CHK-02 | P1: Chunks | T2 | Implemented |
| CHK-03 | P1: Chunks | T2 | Implemented |
| CHK-04 | P1: Chunks | T2 | Implemented |
| CHK-05 | P1: Chunks | T3 | Pending |
| MAN-01 | P1: Manifest | T3 | Pending |
| MAN-02 | P1: Manifest | T3 | Pending |
| MAN-03 | P1: Manifest | T3 | Pending |
| MAN-04 | P1: Manifest | T3 | Pending |
| MAN-05 | P1: Manifest | T3 | Pending |
| MAN-06 | P1: Manifest | T3 | Pending |
| MAN-07 | P1: Manifest | T3 | Pending |
| MAN-08 | P1: Manifest | T3 | Pending |
| CIC-01 | P1: Ciclo | T4 | Pending |
| CIC-02 | P1: Ciclo | T4 | Pending |
| CIC-03 | P1: Ciclo | T4 | Pending |
| CIC-04 | P1: Ciclo | T4 | Pending |
| CIC-05 | P1: Ciclo | T4 | Pending |
| CIC-06 | P1: Ciclo | T4 | Pending |
| CLI-01 | P1: Binário | T5 | Pending |
| CLI-02 | P1: Binário | T5 | Pending |
| CLI-03 | P1: Binário | T5 | Pending |

**Coverage:** 27 total, 27 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker` sem Oracle.
- [ ] Contra o Oracle real (dono roda), `--gerar` imprime lidas/válidas/rejeitadas iguais às do `--dry-run` e todos os chunks ≤ 61 440 B.
