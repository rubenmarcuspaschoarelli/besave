# BSV-13 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; a spec do ticket `docs/specs/BSV-13.md` fixa as funções, o trait reaproveitado e as regras; decisões em `spec.md` → Assumptions)
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-13.md` (testes nunca tocam Oracle nem AWS; falha em imagem não bloqueia a oferta; `cargo test` sem rede).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------- | --------------------- | ----------------- | ------------ |
| Enum `Area`/mapeamento (domínio) | unit | AREA-01..04 | `apps/worker/tests/{card,geracao}.rs` | `cargo test` |
| Imagens — chaves e origem (função pura) | unit | CHV-01, CHV-02 | `apps/worker/tests/imagens.rs` | `cargo test` |
| Imagens — cópia e validação (domínio) | unit | CPY-01, CPY-02 | `apps/worker/tests/imagens.rs` | `cargo test` |
| Imagens — orçamento/recodificação (domínio) | unit | ORC-01..03 | `apps/worker/tests/imagens.rs` | `cargo test` |
| Imagens — reaproveitamento/placeholder (domínio) | unit | REU-01..04 | `apps/worker/tests/imagens.rs` | `cargo test` |
| Geração com imagens (domínio, orquestração) | unit | GER-01..04 | `apps/worker/tests/{geracao,ciclo}.rs` | `cargo test` |
| Adaptador AWS paralelo (`aws.rs`) | none | build gate only; sem rede nos testes | - | build gate only |
| Gerador de placeholders (`examples/`) | none | build gate only (não é código de produção) | - | build gate only |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ------------ | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

Todas as tarefas cabem em um lote (≤ ~8): execução inline, sem sub-agentes.

### Phase 1: Base (enum + módulo de imagens)

```
T1 → T2
```

### Phase 2: Corpo de `publicar_imagens`

```
T2 → T3 → T4 → T5
```

### Phase 3: Integração e paralelismo

```
T5 → T6 → T7
```

---

## Task Breakdown

### T1: `Area::Outros` no enum e no manifest

**What**: Variante `Outros` em `Area` (serializa `"OUTROS"`); fixture/teste de round-trip; card com `DS_COMUNIDADE = "Outros"` não é mais rejeitado; `manifest.areas` inclui `OUTROS` quando há ativas.
**Where**: `apps/worker/src/modelo.rs`, `apps/worker/tests/card.rs`, `apps/worker/tests/geracao.rs`
**Depends on**: None
**Reuses**: `mapeamento.json`/`enums.schema.json` (já têm `OUTROS`, sem alteração)
**Requirement**: AREA-01, AREA-02, AREA-03, AREA-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Area::Outros` adicionada após `EsporteVida` (mesma ordem do enum do schema); round-trip serde para `"OUTROS"`
- [x] Teste: `DS_COMUNIDADE = "Outros"` → `para_card` produz `a: "OUTROS"`, sem `Rejeicao::AreaSemMapeamento`
- [x] Teste: `gerar()` com uma oferta ativa de área `OUTROS` → `manifest.areas` contém `"OUTROS": 1`; JSON do manifest valida contra `packages/contract/schema/manifest.schema.json` (via `jsonschema`, já dev-dependency)
- [x] `Mapeamento::carregar("../../packages/contract/mapeamento.json")` continua sem erro (teste existente)
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add Area::Outros to sync the Rust enum with contract 1.3`

---

### T2: Módulo `imagens.rs` — chaves, origem e assinatura WebP

**What**: Novo módulo `apps/worker/src/imagens.rs` com `chave_small(id)`, `chave_grande(id)`, `origem(dir, id)`, `Area::chave_area()` (helper em `modelo.rs`, reaproveitado pelo placeholder), verificação de assinatura RIFF/WEBP, e os tipos `ErroImagem`, `MotivoFalhaImagem`, `RelatorioImagens` (campos vazios/zerados; sem lógica de publicação ainda). Registra o módulo em `lib.rs`.
**Where**: `apps/worker/src/imagens.rs` (novo), `apps/worker/src/modelo.rs`, `apps/worker/src/lib.rs`, `apps/worker/tests/imagens.rs` (novo)
**Depends on**: T1
**Reuses**: padrão `thiserror` de `publicador.rs`/`redirects.rs`
**Requirement**: CHV-01, CHV-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `chave_small(5412)` == `"img/ofertas/5412-small.webp"`; `chave_grande(5412)` == `"img/ofertas/5412.webp"`
- [x] `origem(dir, 5412)` == `(dir/5412/5412-small.webp, dir/5412/5412.webp)`
- [x] Função de assinatura (`e_webp(bytes: &[u8]) -> bool`) testada com bytes válidos e inválidos (vazio, JPEG, `RIFF` sem `WEBP`)
- [x] `Area::chave_area()` cobre as 10 variantes (teste tabular reaproveitando a lista de `enums.schema.json`)
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): add image key/origin helpers and WebP signature check`

---

### T3: Cópia direta e rejeição de arquivo não-WebP

**What**: `publicar_imagens(ids, dir, pub_)` — corpo mínimo: para cada id, lê origem via `origem()`; se ambos os arquivos existem e têm assinatura WebP válida, grava em `chave_small`/`chave_grande` com a `Meta` de `meta_para` e conta em `publicadas`; arquivo inválido → `falhas` com `MotivoFalhaImagem::NaoWebp`, sem panic, continua o loop.
**Where**: `apps/worker/src/imagens.rs`, `apps/worker/tests/imagens.rs`
**Depends on**: T2
**Reuses**: `crate::publicador::{Publicador, meta_para}`
**Requirement**: CPY-01, CPY-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Fixture `{id}/{id}-small.webp` (12 KB) + `{id}/{id}.webp` (90 KB), assinatura válida → bytes idênticos publicados nas duas chaves; `PublicadorMemoria::meta()` bate com `meta_para` (via `META_IMAGEM`); `publicadas` inclui o id
- [x] Fixture com `.webp` cujos bytes são um JPEG (assinatura inválida) → `falhas` tem `(id, NaoWebp)`; nenhuma chave gravada para esse id; próximo id do lote ainda processado
- [x] Gate check passes: `cargo test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(worker): copy origin WebP images to bucket keys with signature check`

---

### T4: Orçamento estourado — `ajustar_small` e imagem grande acima de 300 KB

**What**: Dependência `image` (feature `webp`) no `Cargo.toml`; `ajustar_small(bytes) -> Result<Vec<u8>, ErroImagem>` decodifica, redimensiona lado maior a ≤ 320 px, tenta qualidade 80/70/60/50/40 até caber em 25 600 B; `publicar_imagens` chama `ajustar_small` quando `-small.webp` de origem > 25 600 B, conta em `reprocessadas` e emite `WARN`; `{id}.webp` > 300 000 B publicada sem alteração, `WARN`, e `RelatorioImagens.maior_grande` atualizado com o maior tamanho publicado.
**Where**: `apps/worker/Cargo.toml`, `apps/worker/Cargo.lock`, `apps/worker/src/imagens.rs`, `apps/worker/tests/imagens.rs`
**Depends on**: T3
**Reuses**: nada externo além da nova dependência
**Requirement**: ORC-01, ORC-02, ORC-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Fixture de ruído (comprime mal) acima de 25 600 B → `ajustar_small` devolve ≤ 25 600 B, assinatura WebP válida, lado maior ≤ 320 px
- [x] Esse id aparece em `reprocessadas` (efeito observável verificado; o `WARN` em si não é asserido — `tracing` não oferece captura sem dependência nova, registrado como limitação no PR)
- [x] Fixture `{id}.webp` de 350 KB (`AVISO_GRANDE + 50_000`) → publicada sem alteração (bytes idênticos); `maior_grande` reflete o maior valor da execução
- [x] `cargo clippy --all-targets -- -D warnings` limpo com a dependência nova
- [x] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**SPEC_DEVIATION**: o encoder WebP da crate `image` (via `image-webp`) só suporta VP8L sem perdas — sem parâmetro de qualidade. Em vez de "qualidade 80→40" (texto da spec do ticket), `ajustar_small` reduz a resolução progressivamente (320 → ×¾, piso 32 px) e recodifica sem perdas a cada tentativa. Mesmo critério de aceite (≤ 25 600 B, WebP válido, ≤ 320 px), sem trocar por um encoder com dependência nativa (`webp`/`libwebp-sys`), que violaria a regra 9 (só `image` permitida). Detalhe em `spec.md` → Assumptions.

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): recompress oversized small images to fit the 25KB budget`

---

### T5: Reaproveitamento, `sem_origem` e placeholders

**What**: `existe(chave_small) && existe(chave_grande)` → pula sem gravar, conta em `reaproveitadas` (nunca compara conteúdo); pasta ausente ou com só um arquivo → `sem_origem`, nada publicado, sem erro; publicação/reaproveitamento dos 10 placeholders (`img/placeholder/{Area::chave_area()}.webp`) a partir de `apps/worker/assets/placeholder/*.webp`; gera esses 10 arquivos reais via `apps/worker/examples/gerar_placeholders.rs` (fundo sólido por área + rótulo em fonte de pixels embutida, ≤ 8 KB, 320×320) e os comita.
**Where**: `apps/worker/src/imagens.rs`, `apps/worker/examples/gerar_placeholders.rs` (novo), `apps/worker/assets/placeholder/*.webp` (10 novos, binário), `apps/worker/tests/imagens.rs`
**Depends on**: T4
**Reuses**: `Area::chave_area()` (T2)
**Requirement**: REU-01, REU-02, REU-03, REU-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Id já publicado (ambas as chaves existem no destino) com origem "trocada" na fixture → nada gravado, contado em `reaproveitadas`
- [x] Pasta ausente e pasta com só `{id}.webp` (sem `-small`) → `sem_origem` nos dois casos, sem erro, sem gravação
- [x] `cargo run --example gerar_placeholders` produzido e os 10 `.webp` resultantes comitados em `assets/placeholder/` (226-356 B cada, bem abaixo de 8 KB)
- [x] Teste: primeira chamada de `publicar_imagens` publica os 10 placeholders; segunda chamada (mesmo destino) os reaproveita (0 gravações de placeholder)
- [x] Segunda execução completa de `publicar_imagens` com a mesma lista de ids → `publicadas == 0`, `reaproveitadas == N`
- [x] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): reuse existing images and publish area placeholders`

---

### T6: Integração em `gerar()` e expurgo das duas chaves

**What**: `gerar()` ganha `dir_imagens: &Path`; chama `publicar_imagens` com os ids publicáveis (ativos + expirados ≤ 7 dias, mesmo conjunto dos cards) como passo 1, antes de particionar/gravar chunks; `Relatorio` incorpora os campos de `RelatorioImagens`; expurgo (ids que saíram do resultado da fonte) remove `img/ofertas/{id}-small.webp` e `img/ofertas/{id}.webp` junto com o restante da limpeza já existente; `--imagens-dir`/`BESAVE_IMAGENS_DIR` novo no binário, obrigatório com `--gerar`/`--publicar`.
**Where**: `apps/worker/src/geracao.rs`, `apps/worker/src/main.rs`, `apps/worker/tests/{geracao,ciclo,dry_run}.rs`, `apps/worker/README.md`
**Depends on**: T5
**Reuses**: `publicar_imagens`, padrão de expurgo de chunks órfãos já em `gerar()`
**Requirement**: GER-01, GER-02, GER-03, GER-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Teste com histórico do `PublicadorMemoria`: `publicar_imagens` roda antes de qualquer `pub_.gravar` de chunk
- [x] `Relatorio` expõe `imagens: RelatorioImagens` preenchido
- [x] Teste de expurgo: id presente na KVS do ciclo anterior e ausente na fonte nesta execução → as duas chaves de imagem são removidas do `PublicadorMemoria`
- [x] Teste: id com `sem_origem` (sem pasta) ainda aparece no card/manifest publicado (nenhuma rejeição nova por causa de imagem)
- [x] `--gerar`/`--publicar` sem `--imagens-dir`/`BESAVE_IMAGENS_DIR` → erro nomeando a variável, sem panic (`dry_run.rs`)
- [x] README documenta `BESAVE_IMAGENS_DIR`, o layout `{id}/{id}[-small].webp` → `img/ofertas/{id}[-small].webp` e a política de orçamento
- [x] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**SPEC_DEVIATION**: `ids_anteriores` (conjunto a expurgar) vem de `redirects.listar()` lido no início de `gerar()`, não da lista de ids do `manifest.json` anterior (que só guarda faixas `[min,max]` por chunk, não ids individuais). Reason: a KVS já espelha exatamente o conjunto publicado do ciclo anterior (decisão de BSV-12), então é a fonte mais simples e correta sem reler chunks antigos; custa uma leitura extra de `ListKeys` por ciclo. Ajustes de testes pré-existentes: `chunk_acima_do_orcamento_falha_sem_gravar_nada` e a 1ª metade de `falha_na_kvs_nao_grava_manifest` agora toleram os 10 placeholders (gravados incondicionalmente por `publicar_imagens`, passo 1) e checam só a ausência de gravação de chunk/manifest; `tests/plano.rs` (3 testes) atualizados para as duas remoções de imagem de 5413 (GER-03), que somam às do chunk órfão pré-existente.

**Tests**: unit
**Gate**: build

**Commit**: `feat(worker): publish images as the first step of gerar() and purge on expiry`

---

### T7: Paralelismo de upload no `PublicadorS3`

**What**: Método específico em `PublicadorS3` (usado só pelo caminho de imagens em `main.rs`) que dispara até 16 pares `HeadObject`/`PutObject` em voo (um `JoinSet`/semáforo `tokio`); `PublicadorLocal` e `PublicadorMemoria` continuam sequenciais via o `publicar_imagens` genérico do lib.
**Where**: `apps/worker/src/aws.rs`, `apps/worker/src/main.rs`
**Depends on**: T6
**Reuses**: `ContextoAws` (runtime `tokio` já compartilhado)
**Requirement**: PAR-01, PAR-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `PublicadorS3` expõe o caminho paralelo (`publicar_imagens_paralelo`, limite de 16 em voo via `tokio::sync::Semaphore` + `JoinSet`)
- [x] `PublicadorLocal`/`PublicadorMemoria` inalterados (sequencial, via `imagens::publicar_imagens`)
- [x] Gate check passes: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

**Fix (1ª rodada do Verifier, pós-T7)**: 5 gaps corrigidos num commit `test(worker)` dedicado —
(1) edge case "small oversized + grande inválida → dual reprocessadas+falhas" era estruturalmente
impossível (checagem de assinatura roda antes do ramo de orçamento com `continue` antecipado);
corrigido como decisão consciente (id é unidade atômica) documentada em `spec.md` Edge Cases,
com teste confirmando o comportamento real; (2) reaproveitamento com só uma das duas chaves
presentes agora tem teste dedicado (mutante `&&`→`\|\|` sobrevivente); (3) limite exato de
`ORCAMENTO_SMALL` (25 600 B) agora tem teste de fronteira; (4) `--gerar` sem `BESAVE_IMAGENS_DIR`
agora tem teste (`dry_run.rs`); (5) `maior_small` agora é asserido num valor não-zero. AREA-01
também corrigida: a AC citava round-trip com fixtures compartilhadas que não usam `OUTROS`;
trocada por round-trip serde direto (`tests/modelo.rs`).

**SPEC_DEVIATION**: `main.rs` (`--publicar`) **não** foi religado para chamar `publicar_imagens_paralelo` nesta tarefa — continua usando o `gerar()` único (T6), que fala com `PublicadorS3` através do trait `Publicador` genérico e portanto publica imagens sequencialmente mesmo em S3. Reason: `gerar()` é o mesmo código para Local/Memória/S3 desde BSV-10/11 (testável sem AWS); trocar esse fluxo para usar um caminho S3-específico exigiria re-arquitetar a integração de imagens em `gerar()` (ex.: um hook/trait novo), fora do escopo desta spec. O método fica exposto e pronto (cumpre PAR-01 literalmente: "expõe um caminho"), mas a integração em `--publicar` é trabalho futuro — sinalizado ao dono no relatório final. Medição de desempenho real fica com o dono (critério de aceite da spec do ticket).

**Tests**: none
**Gate**: build

**Commit**: `perf(worker): parallelize S3 image uploads with a bounded task pool`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2
Phase 2:            T2 ------→ T3 ------→ T4 ------→ T5
Phase 3:                                             T5 ------→ T6 ------→ T7
```

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Area::Outros | 1 enum + 2 arquivos de teste | ✅ Granular |
| T2: chaves/origem/assinatura | 1 módulo novo, funções puras coesas | ✅ Granular (coeso) |
| T3: cópia direta + falha não-webp | 1 função (`publicar_imagens`, corpo inicial) | ✅ Granular |
| T4: recodificação + imagem grande | 1 função (`ajustar_small`) + 1 ramo de `publicar_imagens` | ✅ Granular (coeso, mesmo AC) |
| T5: reaproveitamento + placeholders | 2 ramos de `publicar_imagens` + assets | ✅ Granular (coeso, mesma AC) |
| T6: integração em gerar() + expurgo | 1 função (`gerar`) + CLI | ✅ Granular |
| T7: paralelismo S3 | 1 método em `aws.rs` | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ----------------------- | -------------- | ------ |
| T1 | None | (início da Fase 1) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | (início da Fase 2, após Fase 1) | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | (início da Fase 3, após Fase 2) | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | ---------------------------- | ---------------- | ---------- | ------ |
| T1: Area::Outros | Enum/mapeamento (domínio) | unit | unit | ✅ OK |
| T2: chaves/origem | Imagens — chaves e origem (domínio) | unit | unit | ✅ OK |
| T3: cópia direta | Imagens — cópia e validação (domínio) | unit | unit | ✅ OK |
| T4: recodificação | Imagens — orçamento (domínio) | unit | unit | ✅ OK |
| T5: reaproveitamento/placeholders | Imagens — reaproveitamento (domínio) | unit | unit | ✅ OK |
| T6: integração em gerar() | Geração com imagens (domínio) | unit | unit | ✅ OK |
| T7: paralelismo S3 | Adaptador AWS (`aws.rs`) | none (build gate only) | none | ✅ OK |
