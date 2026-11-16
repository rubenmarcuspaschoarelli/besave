# BSV-62 Tasks

## Execution Plan

### Phase 1: SQL e frases
T1 → T2

### Phase 2: Legendas
T3 → T4

### Phase 3: Espelho e documentação
T5 → T6

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
```

## Task Breakdown

### T1: SQL da fila e do canal 2 ✅
**What**: `bsv-62.sql` com checagem 0 (charset AL32UTF8, canal 2 e tabela ainda inexistentes), `CANAL_ENVIO` 2, `PARAMETROS_ENVIO` 2, `SQ_ENVIO_WHATSAPP`, `ENVIO_WHATSAPP`, índice, `GRANT`s comentados, desfazer.
**Where**: `apps/worker/sql/bsv-62.sql`, `apps/worker/tests/envio_whatsapp_sql.rs`
**Depends on**: none
**Reqs**: SQL-01
**Tests**: `apps/worker/tests/envio_whatsapp_sql.rs` (DDL lido como texto: colunas, únicos, índice, sem FK de oferta, sem segredo)
**Gate**: `cargo test --test envio_whatsapp_sql`

### T2: Frases de aviso ✅
**What**: `apps/worker/frases_canal.json` (as 12 frases e 11 ícones da spec), `envio/frases.rs` (`Frases::embutidas`, `carregar_ou_embutidas`, `escolher` por SHA-256). A leitura de `BESAVE_FRASES_CANAL` no binário entra na T3, com `Contexto.frases`.
**Where**: `apps/worker/frases_canal.json`, `apps/worker/src/envio/frases.rs`, `apps/worker/src/envio/mod.rs`
**Depends on**: T1
**Reqs**: FRA-01, FRA-02, FRA-03, FRA-04, FRA-05
**Tests**: `apps/worker/tests/envio_frases.rs`, `apps/worker/tests/envio_frases_log.rs`
**Gate**: `cargo test --test envio_frases --test envio_frases_log`

### T3: Layout novo do Telegram
**What**: `legenda(o, caiu, p, frases)` com as duas linhas em branco e a frase; `BESAVE_FRASES_CANAL` lida no início da execução; `legenda_encerrada` com a linha em branco; `ajustar`/`caber` recebem a regra de tamanho; `Contexto.frases`; testes de layout da BSV-40/50 atualizados.
**Where**: `apps/worker/src/envio/legenda.rs`, `apps/worker/src/envio/aviso.rs`, `apps/worker/src/envio/rodada.rs`, `apps/worker/src/envio/binario.rs`, `apps/worker/tests/envio_legenda.rs`, testes que montam `Contexto`
**Depends on**: T2
**Reqs**: LAY-01, LAY-02, LIM-01, ENC-01, ISO-01
**Tests**: `apps/worker/tests/envio_legenda.rs`, `apps/worker/tests/envio_aviso.rs`
**Gate**: `cargo test --test envio_legenda --test envio_aviso --test envio_execucao --test envio_http --test envio_site`

### T4: Legenda do WhatsApp
**What**: `legenda_whatsapp(o, caiu, p, frases)` na marcação do WhatsApp, limpeza de `* _ ~ \``, `utm_source=whatsapp`, limite 1024 caracteres e 4000 bytes.
**Where**: `apps/worker/src/envio/legenda.rs`, `apps/worker/tests/envio_legenda_whatsapp.rs`
**Depends on**: T3
**Reqs**: WA-01, WA-02, LIM-01, LIM-02, FRA-01
**Tests**: `apps/worker/tests/envio_legenda_whatsapp.rs`
**Gate**: `cargo test --test envio_legenda_whatsapp --test envio_legenda`

### T5: Espelho na fila do WhatsApp
**What**: `FonteEnvio::enfileirar_whatsapp` (fake e Oracle; ORA-00001 = duplicata), `Contexto.espelho_whatsapp`, linha `P` depois do `confirmar`, WARN na falha, contadores no relatório, `BESAVE_ENVIO_ESPELHO_WHATSAPP` no binário, prévia do WhatsApp no `--sim`.
**Where**: `apps/worker/src/envio/fonte.rs`, `apps/worker/src/envio/oracle.rs`, `apps/worker/src/envio/rodada.rs`, `apps/worker/src/envio/binario.rs`, testes
**Depends on**: T4
**Reqs**: ESP-01, ESP-02, ESP-03, ESP-04, ESP-05
**Tests**: `apps/worker/tests/envio_espelho.rs`, `apps/worker/tests/envio_espelho_log.rs`
**Gate**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`

### T6: CONTRATO 1.7.0 e README
**What**: CONTRATO §11 (layout, "Legenda do WhatsApp", frases, fila), versão 1.7.0 no cabeçalho, `package.json` e `package-lock.json`; teste de versão do contrato; README do worker.
**Where**: `docs/CONTRATO.md`, `packages/contract/package.json`, `packages/contract/package-lock.json`, `apps/worker/tests/envio_modelo.rs`, `apps/worker/README.md`
**Depends on**: T5
**Reqs**: CON-01, DOC-01
**Tests**: `apps/worker/tests/envio_modelo.rs` (versão 1.7.0)
**Gate**: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` e `cd packages/contract && npm ci && npm run validate`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| SQL-01 | `tests/envio_whatsapp_sql.rs` | T1 |
| FRA-01..05 | `tests/envio_frases.rs`, `tests/envio_frases_log.rs` | T2 |
| LAY-01, LAY-02, LIM-01, ENC-01 | `tests/envio_legenda.rs` | T3 |
| ISO-01 | `tests/envio_aviso.rs` (legenda do aviso inalterada) | T3 |
| WA-01, WA-02, LIM-01, LIM-02 | `tests/envio_legenda_whatsapp.rs` | T4 |
| ESP-01..05 | `tests/envio_espelho.rs`, `tests/envio_espelho_log.rs` | T5 |
| CON-01 | `tests/envio_modelo.rs` | T6 |
| DOC-01 | revisão do README | T6 |

## Gate Check Commands

| Level | Command |
| ----- | ------- |
| quick | `cd apps/worker && cargo test --test <arquivo>` |
| build | `cd apps/worker && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |
| contract | `cd packages/contract && npm ci && npm run validate` |
