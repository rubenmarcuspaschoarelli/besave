# BSV-14 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (sem `design.md`; `docs/specs/BSV-14.md` fixa o comportamento; decisões em `spec.md` → Assumptions)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `apps/worker/CLAUDE.md`, `docs/specs/BSV-14.md` (testes nunca tocam Oracle, AWS nem Telegram; `cargo test` sem rede; testes derivam da spec).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Trava (`trava.rs`) | unit | TRV-01..04 | `apps/worker/tests/trava.rs` | `cargo test` |
| Logs (`logs.rs`) | unit | LOG-01, LOG-02 | `apps/worker/tests/logs.rs` | `cargo test` |
| Alerta (`alerta.rs`, domínio + estado) | unit | ALR-01..07 + edge cases | `apps/worker/tests/alerta.rs` | `cargo test` |
| Telegram HTTP (`telegram.rs` I/O) | unit (só a montagem do pedido) | ALR-04, ALR-07 no cliente real | `apps/worker/tests/telegram.rs` | `cargo test` |
| Execução (`execucao.rs`, orquestração) | unit | CIC-04, LOG-03, LOG-04, ALR-01..03, ALR-05 | `apps/worker/tests/execucao.rs` | `cargo test` |
| Binário (`main.rs`) | integration | CIC-01..04, TRV-01, ALR-06 | `apps/worker/tests/cli_ciclo.rs` | `cargo test` |
| Scripts PowerShell / README | none | AGD-01..03: revisão + execução real do dono | - | build gate only |

## Gate Check Commands

> Generated from `CLAUDE.md` (Comandos). Rodar em `apps/worker/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test` |
| Full | After tasks with e2e/integration tests | `cargo test` |
| Build | After phase completion or config/entity-only tasks | `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` |

---

## Execution Plan

10 tarefas (T8 = correção do Verifier; T9–T10 = ajuste do dono), execução inline, sem sub-agentes.

### Phase 1: Blocos

```
T1 → T2 → T3 → T4
```

### Phase 2: Integração

```
T4 → T5 → T6 → T7 → T8 → T9 → T10
```

---

## Task Breakdown

### T1: Trava de arquivo

**What**: `Trava::adquirir(caminho, agora) -> Result<Option<Trava>>` com `File::try_lock`; conteúdo `pid=… inicio=…`; órfão tomado com `WARN`; `Drop` trunca e solta.
**Where**: `apps/worker/src/trava.rs`
**Depends on**: None
**Reuses**: `conversao::iso_utc`
**Requirement**: TRV-01, TRV-02, TRV-03, TRV-04

**Done when**:

- [x] Segunda aquisição com a primeira viva → `None`; depois do drop → `Some`
- [x] Arquivo com PID e horário; arquivo órfão tomado com `WARN`
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T2: Arquivo de log do dia e retenção

**What**: `logs::arquivo_do_dia(dir, agora)` e `logs::limpar_antigos(dir, agora) -> Vec<PathBuf>` (14 dias, data de Brasília no nome).
**Where**: `apps/worker/src/logs.rs`
**Depends on**: T1
**Reuses**: `conversao::iso_utc`
**Requirement**: LOG-01, LOG-02

**Done when**:

- [x] Nome `besave-worker.AAAA-MM-DD.log` com a data de Brasília (virada às 03:00 UTC)
- [x] Remove só logs com mais de 14 dias; outros arquivos ficam
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T3: Alerta: configuração, mensagens e anti-spam

**What**: `ConfigTelegram` (`Debug` mascarado, `de(env)`), trait `Telegram`, `EstadoAlerta` em JSON, `Alertas::falha`/`sucesso` com janela de 2 h por variante e "recuperado"; textos das mensagens; host sanitizado.
**Where**: `apps/worker/src/alerta.rs`
**Depends on**: T2
**Reuses**: `conversao::iso_utc`
**Requirement**: ALR-01, ALR-02, ALR-03, ALR-04, ALR-05, ALR-06, ALR-07

**Done when**:

- [x] Falha → 1 envio; mesma variante < 2 h → 0; ≥ 2 h → 1; variante diferente → 1
- [x] Sucesso após N falhas → "recuperado após N falhas (desde HH:MM)"; seguinte → 0
- [x] Envio falho não registra; JSON corrompido → estado vazio
- [x] Mensagem sem `http`, token, `C:\Users\`; `Debug` sem token; config pela metade → erro
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T4: Cliente HTTPS do Telegram

**What**: `TelegramHttp` (implementa `Telegram`) com `hyper-util` + `hyper-rustls`, POST `sendMessage` JSON, timeout 10 s, erro sem URL; dependências declaradas sem pacote novo no lock.
**Where**: `apps/worker/src/telegram.rs`, `apps/worker/Cargo.toml`, `apps/worker/Cargo.lock`
**Depends on**: T3
**Reuses**: runtime `current_thread` como em `aws.rs`
**Requirement**: ALR-04, ALR-07

**Done when**:

- [x] Corpo do pedido tem `chat_id` e `text`; caminho `/bot{token}/sendMessage`
- [x] `Display` do erro não contém o token
- [x] `Cargo.lock` sem `[[package]]` novo
- [x] Gate build passa

**Tests**: unit
**Gate**: build

---

### T5: Execução do ciclo: falha, relatório e conclusão

**What**: `execucao::Falha { codigo, fase, variante }`, `falha_de_geracao`, `variante_de`, `linha_relatorio`, `concluir(resultado, alertas)` → código de saída + logs + alerta.
**Where**: `apps/worker/src/execucao.rs`
**Depends on**: T4
**Reuses**: `plano::publicar`, `alerta::Alertas`
**Requirement**: CIC-04, LOG-03, LOG-04, ALR-01, ALR-02, ALR-03, ALR-05

**Done when**:

- [x] Fonte fake que erra → código 1, `ERROR` com `fase=leitura_fonte`, 1 envio; repetição < 2 h → 0; sucesso → 1 "recuperado"
- [x] Sucesso → linha `relatorio` com `chave=valor`
- [x] Telegram falhando → mesmo código e `WARN`
- [x] Gate quick passa

**Tests**: unit
**Gate**: quick

---

### T6: `--ciclo` e `--env-file` no binário

**What**: flag `--ciclo`, `--env-file` (dotenvy, lido antes do clap), dirs padrão (`LOCALAPPDATA`), log em arquivo + stderr, trava, retenção, códigos 0/1/2.
**Where**: `apps/worker/src/main.rs`, `apps/worker/Cargo.toml`, `apps/worker/Cargo.lock`
**Depends on**: T5
**Reuses**: `trava`, `logs`, `alerta`, `execucao`, `telegram`
**Requirement**: CIC-01, CIC-02, CIC-03, CIC-04, TRV-01, ALR-06

**Done when**:

- [x] `.env` inexistente → 2 com mensagem nomeando `--env-file`
- [x] Ambiente vence o `.env`
- [x] Trava ocupada → 0 e "ciclo anterior em andamento" no log
- [x] `TELEGRAM_*` pela metade → 2
- [x] Gate build passa

**Tests**: integration
**Gate**: build

---

### T7: Scripts do Agendador e README

**What**: `registrar-tarefa.ps1`, `remover-tarefa.ps1`, seção do README.
**Where**: `apps/worker/scripts/`, `apps/worker/README.md`
**Depends on**: T6
**Reuses**: nenhum
**Requirement**: AGD-01, AGD-02, AGD-03

**Done when**:

- [x] Script registra/atualiza com os gatilhos e limites da spec, sem senha
- [x] README com BotFather, `chat_id`, variáveis, tarefa e logs
- [x] Gate build passa

**Tests**: none
**Gate**: build

---

### T8: `.env` malformado sem ecoar a linha (fix do Verifier)

**What**: `erro_env_file` troca o `LineParse` do `dotenvy` por mensagem sem o conteúdo; teste com token numa linha inválida; byte de controle no comentário de `pastas`.
**Where**: `apps/worker/src/main.rs`
**Depends on**: T7
**Reuses**: nenhum
**Requirement**: CIC-02, CIC-05

**Done when**:

- [x] `.env` malformado → código 2, `fase=env_file`, sem o token no log e no stderr
- [x] Gate build passa

**Tests**: integration
**Gate**: build

---

### T9: `besave-ciclo` sem console (ajuste do dono)

**What**: caminho do `--ciclo` movido para `ciclo::executar` na lib (`Opcoes { stderr, ao_publicar }`); `fake_demo` em `fonte.rs`; `src/bin/besave-ciclo.rs` com `windows_subsystem = "windows"`; destino local + relógio fixo para o teste.
**Where**: `apps/worker/src/ciclo.rs`, `apps/worker/src/bin/besave-ciclo.rs`, `apps/worker/src/main.rs`, `apps/worker/src/fonte.rs`
**Depends on**: T8
**Reuses**: `execucao`, `trava`, `logs`, `alerta`, `telegram`
**Requirement**: CIC-06, CIC-07

**Done when**:

- [x] Mesma linha `relatorio` (sem `t_*`/`tempo_ms`) nos dois binários, fonte fake, destino local
- [x] `besave-ciclo` sem stdout/stderr; argumento inválido → 2
- [x] `BESAVE_AGORA` ignorado sem destino local
- [x] Gate build passa

**Tests**: integration
**Gate**: build

---

### T10: Agendador aponta para `besave-ciclo.exe`; README

**What**: `registrar-tarefa.ps1` recebe o `besave-ciclo.exe`; README atualizado.
**Where**: `apps/worker/scripts/registrar-tarefa.ps1`, `apps/worker/README.md`
**Depends on**: T9
**Reuses**: nenhum
**Requirement**: AGD-01, AGD-03

**Done when**:

- [ ] Script aceita/recomenda `besave-ciclo.exe` e avisa se receber `besave-worker.exe`
- [ ] README: dois binários, sem janela, `BESAVE_DESTINO_LOCAL`/`BESAVE_AGORA`
- [ ] Gate build passa

**Tests**: none
**Gate**: build
