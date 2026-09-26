# BSV-13 — Worker: imagens WebP (`{id}-small` e `{id}`), placeholders e `Area::Outros`

Fonte: `docs/specs/BSV-13.md`. Contrato: `docs/CONTRATO.md` §2.3, §6, §7; `docs/MANIFEST.md` §1, §4, §6, §7.

## Problem Statement

O robô já grava, por oferta, `{BESAVE_IMAGENS_DIR}/{id}/{id}.webp` e `{id}/{id}-small.webp`. O
worker não publica nenhuma imagem: `gerar()` pula direto para chunks/manifest e o card/página
não têm imagem nem placeholder. O contrato 1.3 acrescentou a área `OUTROS`
(`packages/contract/mapeamento.json` e `enums.schema.json` já têm; o enum Rust do worker não).

## Goals

- [ ] `Area::Outros` existe no enum Rust, mapeia "OUTROS"/"OUTRO" e entra em `manifest.areas` quando há ativas.
- [ ] `gerar()` publica imagens (passo 1 de MANIFEST §6) antes dos chunks, reaproveitando o que já existe e nunca bloqueando a oferta por falta de imagem.
- [ ] `cargo test` passa sem rede; orçamento de `-small` (≤ 25 600 B) é gate de teste.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Imagens de produto (`img/produtos/`) | Fora da spec (linha "Fora de escopo") |
| CDN de imagens externa | Idem |
| HTML da página/lista usando a imagem | BSV-20/21 |
| Agendamento do ciclo | BSV-14 |
| Geração dos WebP pelo robô Python | Já entregue fora deste ticket; worker só copia |
| Teste de upload real contra S3/CloudFront | Dono roda depois (`--publicar --sim`) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | --------------- | --------- | ---------- |
| `BESAVE_IMAGENS_DIR` no binário | Novo arg `--imagens-dir` (`env = "BESAVE_IMAGENS_DIR"`), `PathBuf` obrigatório junto com `--gerar` e `--publicar` (mesmo padrão de `--mapeamento`); `--dry-run` não usa (não chama `gerar()`) | A spec lista a env como entrada de `gerar()`; sem ela não há como cumprir a regra 1 (imagens primeiro). Ausência da pasta em si (não da env) é tratada por id via `sem_origem`, não bloqueia | n |
| Assinatura de `gerar()` | Ganha `dir_imagens: &Path`; chama `publicar_imagens(&ids_publicaveis, dir_imagens, pub_)` como primeiro passo, antes de particionar/gravar chunks | Regra "gerar() passa a publicar imagens no passo 1 da ordem de MANIFEST §6"; `ids_publicaveis` = ids dos cards que passaram por `publicavel` (ativos + expirados ≤ 7 dias, mesmo conjunto do card) | n |
| Nome de arquivo do placeholder por área | `Area` ganha `fn chave_area(&self) -> &'static str` que devolve o mesmo texto do serde (`"TECH"`, `"MEU_LAR"`, …, `"OUTROS"`); placeholder sobe em `img/placeholder/{chave_area}.webp` e o asset versionado é `apps/worker/assets/placeholder/{chave_area}.webp` | Consistência com `manifest.areas` (chaves já em `SCREAMING_SNAKE_CASE`); evita inventar um segundo slug distinto do slug de URL do site (que é outro contrato, §2.3, não usado por chave de imagem) | n |
| Quais placeholders sobem sempre | Os 10 (uma por variante de `Area`, incluindo `OUTROS`), reaproveitados pelo mesmo critério de existência das imagens de oferta (rule 4) | Regra 5: "o worker publica os 10 placeholders uma vez, reaproveitando pelo mesmo critério" | y |
| Assinatura WebP | 12 primeiros bytes: `RIFF` (bytes 0-3), tamanho (4-7, ignorado), `WEBP` (bytes 8-11) | Formato de contêiner RIFF/WebP documentado; único jeito de detectar ".webp com conteúdo JPEG" sem decodificar a imagem inteira | y |
| Recodificação (`ajustar_small`) | Crate `image` 0.25.10 (feature `webp`, via `image-webp`) decodifica e recodifica; verificado em docs.rs que o encoder embutido só faz VP8L (sem perdas, sem parâmetro de qualidade) — um encoder lossy real exigiria a crate `webp`/`libwebp-sys` (toolchain C nativa), fora da regra 9. Em vez de "qualidade 80→40", `ajustar_small` reduz o lado maior progressivamente (320 → ×¾ a cada volta, piso 32 px) e recodifica sem perdas a cada tentativa, até caber em 25 600 B | Regra 3 (cumprida via outro mecanismo: mesmo resultado — ≤ 25 600 B, WebP válido, lado ≤ 320 px) e regra 9 (uma única dependência pura-Rust, sem toolchain nativa) | y |
| `maior_small` / `maior_grande` | `u64`: maior tamanho em bytes, entre os ids publicados nesta execução, de cada uma das duas chaves (após `ajustar_small` quando houver; `0` se nenhuma imagem publicada) | Simetria com `maior_chunk` (`geracao.rs`) e com o critério de aceite "relatório com `maior_small` ≤ 25 600 bytes" — é um tamanho, não uma contagem | y |
| Paralelismo (regra 8) | Pool de até 16 tarefas `tokio` em voo dentro de `PublicadorS3::publicar_imagens_paralelo` (um `join_set` limitado), usado só pelo caminho de imagens; `PublicadorLocal`/`PublicadorMemoria` continuam sequenciais (a lib `publicar_imagens` genérica sobre `&mut dyn Publicador` é sequencial; o S3 ganha um método extra usado só por `main.rs` quando o destino é `PublicadorS3`) | `dyn Publicador` é `&mut` e síncrono (BSV-11/12); paralelizar atrás do trait exigiria mudar a assinatura de todo `Publicador`. Regra 8 pede o pool "no `PublicadorS3`", não no trait — isolar ali evita reabrir BSV-11/12 | n |
| Extensão de `RelatorioImagens.falhas` | `Vec<(i64, MotivoFalhaImagem)>` com `MotivoFalhaImagem::NaoWebp` (única variante hoje, `Display` = `"nao_webp"`) | Regra 2: "falhas com motivo `nao_webp`"; enum aberto para futuros motivos sem quebrar o tipo | y |
| Tamanho e geração dos placeholders | 10 arquivos WebP reais, ≤ 8 KB cada, 320×320, fundo neutro (cor sólida por área) + rótulo textual com uma fonte de pixels 5×7 embutida (sem crate de fonte nova); gerados por `apps/worker/examples/gerar_placeholders.rs` (usa só a dependência `image` já justificada por `ajustar_small`), rodado uma vez e os 10 `.webp` resultantes commitados em `assets/placeholder/` | Regra explícita da spec ("o agente cria 10 imagens simples... com o rótulo da área"); um `example` committed é reproduzível e revisável, ao contrário de um script descartável fora do repo; evita 2ª dependência (crate de fonte) para texto | y |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: `Area::Outros` no enum Rust ⭐ MVP

**User Story**: Como worker, quero reconhecer a área `OUTROS` para não rejeitar ofertas sem
classificação e para o manifest contá-las.

**Why P1**: Bloqueia tudo: sem a variante, o card com `DS_COMUNIDADE = "Outros"` é rejeitado
(`AreaSemMapeamento`) mesmo com `mapeamento.json` já mapeando "OUTROS"→"OUTROS".

**Acceptance Criteria**:

1. The `Area` enum SHALL ter a variante `Outros` serializada como `"OUTROS"` (round-trip com as fixtures do contrato 1.3 em `packages/contract/fixtures/`).  <!-- AREA-01 -->
2. WHEN uma linha tem `DS_COMUNIDADE = "Outros"` THEN `para_card` SHALL produzir `a: "OUTROS"` (sem rejeição).  <!-- AREA-02 -->
3. WHEN há ao menos uma oferta ativa com área `OUTROS` THEN `manifest.areas` SHALL incluir a chave `OUTROS` com a contagem, e o `manifest.json` gerado SHALL validar contra `manifest.schema.json` (npm `validate`).  <!-- AREA-03 -->
4. The `Mapeamento::carregar` SHALL carregar `packages/contract/mapeamento.json` sem erro (já contém `"OUTROS": "OUTROS"` e `"OUTRO": "OUTROS"`).  <!-- AREA-04 -->

**Independent Test**: `cargo test --test card --test geracao`.

---

### P1: Chaves e origem das imagens ⭐ MVP

**User Story**: Como worker, quero funções puras que traduzam um id para as chaves do bucket e
para os caminhos de origem do robô.

**Why P1**: Base de tudo que segue; sem elas não há como copiar nem testar isoladamente.

**Acceptance Criteria**:

1. The `chave_small(id)` SHALL devolver `"img/ofertas/{id}-small.webp"` e `chave_grande(id)` SHALL devolver `"img/ofertas/{id}.webp"`.  <!-- CHV-01 -->
2. The `origem(dir, id)` SHALL devolver `({dir}/{id}/{id}-small.webp, {dir}/{id}/{id}.webp)`.  <!-- CHV-02 -->

**Independent Test**: `cargo test --test imagens`.

---

### P1: Cópia direta dentro do orçamento ⭐ MVP

**User Story**: Como worker, quero subir a imagem do robô sem reprocessar quando ela já está
dentro do orçamento.

**Why P1**: É o caminho comum (regra 2); reprocessar sempre gastaria CPU e mudaria pixels sem
necessidade.

**Acceptance Criteria**:

1. WHEN a fixture `{id}/{id}-small.webp` (12 KB, assinatura WebP válida) e `{id}/{id}.webp` (90 KB) existem THEN `publicar_imagens` SHALL gravar os bytes idênticos aos de origem em `chave_small(id)` e `chave_grande(id)`, com a `Meta` que `meta_para("img/ofertas/{id}-small.webp")` devolve, e SHALL contar o id em `publicadas`.  <!-- CPY-01 -->
2. IF os bytes de um arquivo `.webp` não começam com a assinatura RIFF/WEBP (`RIFF` em 0..4, `WEBP` em 8..12) THEN `publicar_imagens` SHALL registrar `falhas` com `MotivoFalhaImagem::NaoWebp` para aquele id, SHALL não gravar nenhuma chave para ele, SHALL não entrar em pânico e SHALL continuar processando os ids seguintes.  <!-- CPY-02 -->

**Independent Test**: `cargo test --test imagens`.

---

### P1: Orçamento estourado — recodificação ⭐ MVP

**User Story**: Como worker, quero recodificar a imagem pequena quando o robô entregou algo
maior que 25 600 B, para não estourar o orçamento do card.

**Why P1**: `-small.webp` acima do orçamento quebraria o gate de MANIFEST §7.

**Acceptance Criteria**:

1. WHEN a fixture `{id}-small.webp` tem 40 KB THEN `ajustar_small` SHALL devolver bytes com assinatura WebP válida, ≤ 25 600 B, com o lado maior ≤ 320 px.  <!-- ORC-01 -->
2. WHEN `ajustar_small` é usado por `publicar_imagens` para um id THEN esse id SHALL ser contado em `reprocessadas` e um `WARN` SHALL ser emitido com o id.  <!-- ORC-02 -->
3. WHEN a fixture `{id}.webp` (imagem grande) excede 300 000 B THEN `publicar_imagens` SHALL publicá-la sem alteração e SHALL emitir `WARN`; ao final, `RelatorioImagens.maior_grande` SHALL ser o maior número de bytes entre as `{id}.webp` publicadas na execução.  <!-- ORC-03 -->

**Independent Test**: `cargo test --test imagens`.

---

### P1: Reaproveitamento e ausência de origem ⭐ MVP

**User Story**: Como worker, quero pular ids já publicados e usar o placeholder da área quando
faltar a origem, sem nunca bloquear a oferta.

**Why P1**: Idempotência (regra 4) e resiliência (regra 5) são requisito do worker desde BSV-10.

**Acceptance Criteria**:

1. WHEN `existe(chave_small(id))` e `existe(chave_grande(id))` são ambos verdadeiros no destino THEN `publicar_imagens` SHALL não gravar nada para aquele id e SHALL contá-lo em `reaproveitadas`, mesmo que os bytes de origem tenham mudado.  <!-- REU-01 -->
2. IF a pasta `{dir}/{id}/` não existe, ou existe com só um dos dois arquivos THEN `publicar_imagens` SHALL não publicar nenhuma chave para o id, SHALL contá-lo em `sem_origem` e SHALL não retornar erro.  <!-- REU-02 -->
3. The `publicar_imagens` SHALL publicar os 10 placeholders de `apps/worker/assets/placeholder/*.webp` em `img/placeholder/{area}.webp` na primeira execução e SHALL reaproveitá-los (via o mesmo critério de `existe`) nas execuções seguintes.  <!-- REU-03 -->
4. WHEN `publicar_imagens` roda uma segunda vez com o mesmo destino e a mesma lista de ids THEN `publicadas` SHALL ser 0 e `reaproveitadas` SHALL ser igual ao número de ids com origem completa.  <!-- REU-04 -->

**Independent Test**: `cargo test --test imagens`.

---

### P1: Integração em `gerar()` e expurgo ⭐ MVP

**User Story**: Como dono, quero que o ciclo publique imagens antes dos chunks e apague as duas
chaves de imagem quando a oferta expurga.

**Why P1**: Sem isso o passo 1 de MANIFEST §6 fica sem efeito e o expurgo deixaria lixo no bucket.

**Acceptance Criteria**:

1. WHEN `gerar` roda com `dir_imagens` THEN a chamada a `publicar_imagens` SHALL acontecer antes da gravação de qualquer chunk.  <!-- GER-01 -->
2. The `Relatorio` de `gerar` SHALL incluir os campos de `RelatorioImagens` (publicadas, reaproveitadas, sem_origem, reprocessadas, falhas, bytes, maior_small, maior_grande).  <!-- GER-02 -->
3. WHEN uma oferta presente no manifest anterior sai do resultado da fonte (expurgo, CONTRATO §7) THEN a execução seguinte de `gerar` SHALL remover `img/ofertas/{id}-small.webp` e `img/ofertas/{id}.webp` do destino.  <!-- GER-03 -->
4. IF um id não tem origem de imagem (`sem_origem`) THEN `gerar` SHALL publicar o card e a página normalmente (a ausência de imagem SHALL não gerar rejeição nem impedir a publicação da oferta).  <!-- GER-04 -->

**Independent Test**: `cargo test --test geracao --test ciclo`.

---

### P2: Paralelismo de upload no `PublicadorS3`

**User Story**: Como dono, quero que a primeira carga de ~50 mil objetos de imagem não vire o
gargalo do ciclo.

**Why P2**: Sem paralelismo o `HeadObject`+`PutObject` sequencial domina o tempo total, mas não
bloqueia a corretude funcional coberta pelas histórias P1.

**Acceptance Criteria**:

1. The `PublicadorS3` SHALL expor um caminho de publicação de imagens que dispara até 16 pares `HeadObject`/`PutObject` em voo simultaneamente.  <!-- PAR-01 -->
2. The `PublicadorLocal` e `PublicadorMemoria` SHALL continuar processando `publicar_imagens` sequencialmente (sem pool).  <!-- PAR-02 -->

**Independent Test**: revisão de `src/aws.rs` (sem teste de rede); `cargo clippy` limpo.

---

## Edge Cases

- IF `BESAVE_IMAGENS_DIR`/`--imagens-dir` está ausente em `--gerar` ou `--publicar` THEN o binário SHALL sair com erro nomeando a variável, sem panic (mesmo padrão de `AWS-03` em BSV-12).
- WHEN um id tem `-small.webp` com assinatura WebP válida mas maior que 25 600 B **e** o `{id}.webp` também é inválido (não-WebP) THEN o id SHALL aparecer em `reprocessadas` (para o small) e em `falhas` (para o grande), sem interromper os outros ids.
- WHEN a lista de ids publicáveis está vazia THEN `publicar_imagens` SHALL ainda publicar/reaproveitar os 10 placeholders e devolver um relatório com as demais contagens em 0.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| AREA-01 | P1: Area::Outros | T1 | Implemented |
| AREA-02 | P1: Area::Outros | T1 | Implemented |
| AREA-03 | P1: Area::Outros | T1 | Implemented |
| AREA-04 | P1: Area::Outros | T1 | Implemented |
| CHV-01 | P1: Chaves e origem | T2 | Implemented |
| CHV-02 | P1: Chaves e origem | T2 | Implemented |
| CPY-01 | P1: Cópia direta | T3 | Implemented |
| CPY-02 | P1: Cópia direta | T3 | Implemented |
| ORC-01 | P1: Orçamento estourado | T4 | Implemented |
| ORC-02 | P1: Orçamento estourado | T4 | Implemented |
| ORC-03 | P1: Orçamento estourado | T4 | Implemented |
| REU-01 | P1: Reaproveitamento | T5 | Pending |
| REU-02 | P1: Reaproveitamento | T5 | Pending |
| REU-03 | P1: Reaproveitamento | T5 | Pending |
| REU-04 | P1: Reaproveitamento | T5 | Pending |
| GER-01 | P1: Integração em gerar() | T6 | Pending |
| GER-02 | P1: Integração em gerar() | T6 | Pending |
| GER-03 | P1: Integração em gerar() | T6 | Pending |
| GER-04 | P1: Integração em gerar() | T6 | Pending |
| PAR-01 | P2: Paralelismo | T7 | Pending |
| PAR-02 | P2: Paralelismo | T7 | Pending |

**Coverage:** 21 total, 21 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde em `apps/worker`, sem rede.
- [ ] `Area::Outros` round-trip com as fixtures 1.3; `manifest.json` de teste valida contra `manifest.schema.json`.
- [ ] Real (dono, fora deste agente): `--publicar --sim` com `BESAVE_IMAGENS_DIR` real; `curl -I` de `<id>-small.webp` e `<id>.webp` → 200, `image/webp`, `immutable`; relatório com `maior_small` ≤ 25 600 B.
