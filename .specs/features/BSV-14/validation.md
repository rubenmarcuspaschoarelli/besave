# BSV-14 Validation

**Date**: 2026-10-01 (rodada 2)
**Spec**: `.specs/features/BSV-14/spec.md` (escopo do dono: `docs/specs/BSV-14.md`)
**Diff range**: `e24a757..6a5f3a8` (commits `cce0f85..6a5f3a8`, branch `rubenmarcus/rub-14-bsv-14-telegram`)
**Verifier**: sub-agente independente (autor ≠ verificador)

## Validation: BSV-14 - PASS ✅

- Todos os 23 ACs têm evidência `arquivo:linha`, e os valores testados batem com a spec.
- Gate verde: 273 passados, 0 falhos.
- Sensor: 19 de 19 mutantes mortos.
- Os gaps 1, 3, 4 e 5 da rodada 1 foram fechados em `6a5f3a8`.
- A execução real do dono (Agendador + Telegram) continua bloqueando o merge (spec → Success Criteria).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Trava | ✅ Done | `87fb4ad` |
| T2 Logs | ✅ Done | `a6341ba` |
| T3 Alerta | ✅ Done | `2d63907` |
| T4 Cliente HTTPS | ✅ Done | `e27ce96`; `Cargo.lock` ganha só o pacote `dotenvy` (permitido) |
| T5 Execução | ✅ Done | `4956161` |
| T6 `--ciclo`/`--env-file` | ✅ Done | `d07ac25` |
| T7 Scripts + README | ✅ Done | `21e2fe3` |
| T8 `.env` malformado sem ecoar a linha (fix da rodada 1) | ✅ Done | `6a5f3a8` |

---

## Spec-Anchored Acceptance Criteria

Caminhos relativos a `apps/worker/`.

### P1: Modo ciclo e configuração

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| CIC-01 `--ciclo` = `gerar()` do `--publicar --sim` | escreve no destino | `tests/execucao.rs:333` `p.ler("manifest.json").unwrap().is_some()`; `:334` `kvs.listar()… == vec![1, 2]`; código `src/execucao.rs:119` `publicar(…, true)` | ✅ PASS (o binário completo depende de AWS/Oracle → execução real do dono) |
| CIC-02 `--env-file` inexistente ou ilegível → 2 + mensagem nomeando `--env-file` | código 2, texto com `--env-file` | inexistente: `tests/cli_ciclo.rs:94` `Some(2)`, `:96` `stderr.contains("--env-file")`, `:97` `contains("nao-existe.env")`; ilegível (malformado): `tests/cli_ciclo.rs:209-220` `Some(2)` e `stderr.contains("--env-file")` | ✅ PASS |
| CIC-03 ambiente vence o `.env` | valor do ambiente usado | `tests/cli_ciclo.rs:113` `Some(2)` + `:115` `log.contains("do_ambiente")` (o `.env` tem `BESAVE_FONTE=fake`) | ✅ PASS |
| CIC-04 config → 2; execução → 1; sucesso/pulado → 0 | 2 / 1 / 0 | `tests/execucao.rs:239` `== 2`; `:250` `== 1`; `:154` `== 0`; `tests/cli_ciclo.rs:142` `Some(0)` (pulado); `:178` `Some(2)` | ✅ PASS |
| CIC-05 linha malformada → 2, sem ecoar a linha no log nem no stderr | código 2; `SEGREDO` ausente dos dois | `tests/cli_ciclo.rs:212` `.env` com `TELEGRAM_BOT_TOKEN=123:SEGREDO\q x y`; `:221` `!stderr.contains("SEGREDO")`; `:223` `log.contains("fase=env_file")`; `:224` `!log.contains("SEGREDO")`. Código: `src/main.rs:105-114` `erro_env_file` troca `LineParse` por "linha malformada (posição N)"; `:123` em uso | ✅ PASS (M19 morto) |

### P1: Trava

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| TRV-01 trava ocupada → 0 + INFO "ciclo anterior em andamento" | código 0, linha INFO | `tests/cli_ciclo.rs:142` `Some(0)`; `:146` `INFO && "ciclo anterior em andamento"`; `tests/trava.rs:58` `is_none()` | ✅ PASS |
| TRV-02 arquivo com PID e início | `pid=<pid>`, `inicio=<iso>` | `tests/trava.rs:72` `contains(format!("pid={}", process::id()))`; `:75` `contains("inicio=2026-09-21T14:13:20Z")` | ✅ PASS |
| TRV-03 órfão tomado com WARN | `Some` + 1 WARN | `tests/trava.rs:87` `is_some()`; `:89` `warns.len() == 1`; `:90` `contains("pid=999999")`; negativo `:103` | ✅ PASS |
| TRV-04 soltar e readquirir | `Some` após o drop | `tests/trava.rs:60` `adquirir(&p, AGORA + 1).unwrap().is_some()`; `:76` `contains("fim=")` | ✅ PASS |

### P1: Logs em arquivo

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| LOG-01 `besave-worker.AAAA-MM-DD.log` do dia de Brasília | virada às 03:00 UTC | `tests/logs.rs:36-43` `VIRADA - 1 → 2026-09-30`, `VIRADA → 2026-10-01`; padrão `%LOCALAPPDATA%\besave\logs` via `tests/cli_ciclo.rs:67`; `BESAVE_LOG_DIR` `tests/cli_ciclo.rs:203` | ✅ PASS |
| LOG-02 remove > 14 dias, mantém o resto | 09-16 sai, 09-17 fica | `tests/logs.rs:65-71` `removidos == [08-01, 09-16]`; `:72-82` restantes; fuso `:90` | ✅ PASS |
| LOG-03 linha `relatorio` em `chave=valor` | 1 linha, pares `k=v` | `tests/execucao.rs:173` `len() == 1`; `:175-185` campos; `:189-193` todos `k=v` | ✅ PASS |
| LOG-04 falha → ERROR com `fase=` e `variante=` | 1 linha ERROR | `tests/execucao.rs:129-131` `len() == 1`, `fase=leitura_fonte`, `variante=Fonte::ConfigInvalida` | ✅ PASS |

### P1: Alerta no Telegram

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| ALR-01 mensagem `⚠️ Besave worker: falha no ciclo` + variante, fase, -03:00, host | texto exato | `tests/alerta.rs:83` `len() == 1`; `:85` `starts_with(…)`; `:86-89` `erro: Redirects::Kvs`, `fase: redirects`, `21/09/2026 11:13 (-03:00)`, `host: MAQUINA-1`; `tests/execucao.rs:294-299` | ✅ PASS |
| ALR-02 < 2 h → 0; 2 h → 1 | limite 7200 s | `tests/alerta.rs:101-104` (7199 → 1 envio; 7200 → 2) | ✅ PASS |
| ALR-03 recuperado após N falhas (desde HH:MM), zera; seguinte não envia | texto exato | `tests/alerta.rs:137-141` `== "✅ Besave worker: recuperado após 3 falhas (desde 11:13)"`; `:150`; `:164` | ✅ PASS |
| ALR-04 sem `http`, token, `C:\Users\` | ausência | `tests/alerta.rs:181-183`; `tests/execucao.rs:310` | ✅ PASS |
| ALR-05 envio falho → mesmo código + WARN | código 1 mantido | `tests/execucao.rs:208`, `:211`, `:223`; `tests/alerta.rs:210` | ✅ PASS |
| ALR-06 nenhuma → INFO; só uma → 2 | INFO / 2 | `tests/cli_ciclo.rs:118`, `:161`, `:163`; `tests/alerta.rs:262`, `:276-284` | ✅ PASS |
| ALR-07 token fora do `Debug` | sem token | `tests/alerta.rs:298`; `tests/telegram.rs:41` | ✅ PASS |

### P2: Agendador e documentação (por leitura)

| Criterion | Spec-defined outcome | Evidência | Result |
| --------- | -------------------- | --------- | ------ |
| AGD-01 | 5 min indefinido, logon + 1 min, IgnoreNew, 20 min, interativo, parâmetros, sem senha | `scripts/registrar-tarefa.ps1:23-24`, `:43`, `:44-45`, `:48`, `:49`, `:55`, `:57-64`. Montado em memória sem registrar: `Interval=PT5M Duration=` (indefinido), `Delay=PT1M`, `IgnoreNew`, `PT20M`, `Interactive`. O parser do PowerShell não acha erro; nenhum `-Password`. Sem boot: agora justificado nas Assumptions (`spec.md` → "Gatilho de boot") | ✅ PASS |
| AGD-02 | remove a tarefa | `scripts/remover-tarefa.ps1:20` `Unregister-ScheduledTask … -Confirm:$false` | ✅ PASS |
| AGD-03 | BotFather, `chat_id`, variáveis, registrar/remover, logs | `README.md:349`, `:352`, `:381`, `:399`, `:413`, `:416` | ✅ PASS |

**Status**: ✅ 23/23 ACs com evidência que bate com a spec; nenhuma ressalva de precisão.

---

## Edge Cases

- [x] `alerta.json` corrompido → WARN + estado vazio: `tests/alerta.rs:247-248`.
- [x] Duas variantes na mesma janela → um envio cada: `tests/alerta.rs:119-120`.
- [x] Recuperado que falha mantém o estado: `tests/alerta.rs:230-235`.
- [x] Linha malformada do `.env` não vaza no log/stderr (CIC-05): `tests/cli_ciclo.rs:221`, `:224`.

---

## Owner scope (`docs/specs/BSV-14.md`) vs spec derivada

| # | Desvio | Classificação |
| - | ------ | ------------- |
| D1 | Flag `--ciclo` em vez de subcomando | Justificado (o dono aceita; Assumptions "Forma do modo") |
| D2 | Sem `tracing-appender` | Justificado (Assumptions "Log em arquivo"; crate permitida, não exigida) |
| D3 | `File::try_lock` em vez de `fs2` | Justificado ("ou equivalente"; Assumptions "Trava") |
| D4 | Órfão = sem `fim=` com a trava livre | Justificado (Assumptions "Trava": o SO solta quando o processo morre) |
| D5 | Gatilho só de logon | Justificado desde `6a5f3a8` (Assumptions "Gatilho de boot") |
| D6 | `contains` em vez de regex | Equivalente |
| D7 | Alerta também em código 2 | Justificado (Assumptions) |
| D8 | "Tokens nunca em log" | Coberto desde `6a5f3a8` (CIC-05 + Assumptions "Erro do `.env`") |
| D9 | `hyper-rustls` do SDK em vez de `reqwest` | Justificado; só `dotenvy` entra no lock |

---

## Gate Check

- **Gate command** (em `apps/worker`, `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=2`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- **Gate**: exit 0. **273 passed, 0 failed, 3 ignored** (os 3 ignorados são de antes: `ciclo.rs`, `imagens.rs`, `paginas.rs`).
- **Test count**: 272 na rodada 1 → 273 (+1: `env_file_malformado_sai_com_2_sem_ecoar_a_linha`). São 36 testes novos do BSV-14 no total; nenhum teste foi apagado ou enfraquecido.

---

## Discrimination Sensor

**Sensor depth**: expandido. São 19 mutações manuais cobrindo os ramos de risco (estado persistido, concorrência, dados sensíveis, código de saída).
**Result**: 19/19 killed - PASS ✅

Os mutantes rodaram numa worktree temporária (`git worktree add --detach <scratchpad>/wt HEAD`, fora do repo), um por vez:
- cada mutante aplica uma troca exata de texto, roda `cargo test --test <alvo>` só nos testes relevantes e restaura o arquivo;
- ambiente sem AWS (sem região/perfis, IMDS desligado, `AWS_ENDPOINT_URL=http://127.0.0.1:9`) e sem `TELEGRAM_*`;
- `CARGO_BUILD_JOBS=2`, alvo `C:\cargo-target\besave` compartilhado (só a crate `worker` recompila);
- os binários do topo de `debug/` (`besave-worker.exe` e afins) ganharam backup antes e foram restaurados depois, e o `cargo test --test cli_ciclo` da árvore real passou (7/7).

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| M1 | `src/alerta.rs:197` | janela `<` → `<=` | ✅ (alerta: 1 falha) |
| M2 | `src/alerta.rs:206` | não registra o envio entregue | ✅ (alerta: 2 falhas) |
| M3 | `src/alerta.rs:227` | zera o estado com o "recuperado" falho | ✅ (alerta: 1) |
| M4 | `src/logs.rs:10` | retenção 13 dias | ✅ (logs: 2) |
| M5 | `src/logs.rs:10` | retenção 15 dias | ✅ (logs: 1) |
| M6 | `src/logs.rs:48` | limite em data UTC | ✅ (logs: 1) |
| M7 | `src/trava.rs:52` | não detecta o órfão | ✅ (trava: 1) |
| M8 | `src/trava.rs:79` | não solta no Drop (handle duplicado vazado) | ✅ (trava: 4) |
| M9 | `src/trava.rs:78` | Drop sem `fim=` | ✅ (trava: 2) |
| M10 | `src/execucao.rs:194` | `concluir` devolve 1 para erro de config | ✅ (execucao: 1) |
| M11 | `src/execucao.rs:192` | alerta muda o código para 0 | ✅ (execucao: 2) |
| M12 | `src/execucao.rs:91` | `variante_de` aceita espaço/`:`/`/`/`\`/`.` (vaza texto) | ✅ (execucao: 2) |
| M13 | `src/execucao.rs:69` | `ErroGeracao::Fonte` → fase `imagens` | ✅ (execucao: 2) |
| M14 | `src/execucao.rs:119` | `sim=false` (não escreve) | ✅ (execucao: 1) |
| M15 | `src/main.rs:119` | `dotenvy::from_path_override` (`.env` vence) | ✅ (cli_ciclo: 1) |
| M16 | `src/main.rs:343` | ciclo pulado sai com 1 | ✅ (cli_ciclo: 1) |
| M17 | `src/alerta.rs:75` | `TELEGRAM_*` pela metade → desligado | ✅ (alerta: 1) |
| M18 | `src/alerta.rs:52` | `Debug` mostra o token | ✅ (alerta: 1) |
| M19 | `src/main.rs:123` | `erro_env_file` → `e.to_string()` (ecoa a linha) | ✅ (cli_ciclo: 1) |

**Isolamento**: o `git status --porcelain` da árvore real antes do sensor (`?? .specs/features/BSV-14/validation.md`) é idêntico ao de depois (`diff` vazio). A worktree foi removida e podada.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / no scope creep | ✅ (`gerar()` intacto; sem loop interno) |
| Surgical changes | ✅ (`apps/worker/` + `.specs/features/BSV-14/`) |
| Matches patterns | ✅ |
| Spec-anchored outcome check | ✅ 23/23 |
| Every test maps to a requirement | ✅ |
| Guidelines (`CLAUDE.md`, `apps/worker/CLAUDE.md`) | ✅ (byte de controle de `main.rs` corrigido; nenhum outro byte de controle em `src/`/`tests/`) |

---

## Gaps

Nenhum gap bloqueante. Observações:
- **Merge bloqueado pela execução real do dono** (spec → Success Criteria): 6 execuções com resultado 0 em 30 min, 6 linhas `relatorio`, um alerta com `BESAVE_KVS_ARN` inválido e o "recuperado" depois. Sem isso, nada valida o gatilho do Agendador, o TLS do Telegram nem o caminho Oracle/AWS do `--ciclo`.
- `erro_env_file` (`src/main.rs:105-114`) mantém o texto de `Io`/`EnvVar`. O `io::Error` do Windows não traz conteúdo do arquivo, então não há vazamento conhecido.

---

## Histórico

### Rodada 1 (2026-10-01, `e24a757..21e2fe3`): FAIL

- Gate: 272 passed, 0 failed, 3 ignored. 22/22 ACs com evidência.
- Sensor **não executado**: a compilação num alvo de build separado foi encerrada pelo sistema por falta de memória antes de qualquer mutação.
- Gaps:
  1. Major: o `LineParse` do `dotenvy` ecoava a linha do `.env` (inclusive o token) no log (`src/main.rs:106-111`), reproduzido com o binário real.
  2. Sensor pendente.
  3. CIC-02 "ilegível" sem teste.
  4. Gatilho de boot fora das Assumptions.
  5. Byte `\x08` em `src/main.rs:228`.
- Os gaps 1, 3, 4 e 5 foram corrigidos em `6a5f3a8`; o 2 foi feito nesta rodada.

---

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| CIC-01..05, TRV-01..04, LOG-01..04, ALR-01..07, AGD-01..03 | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (do lado do código; a execução real do dono continua bloqueando o merge)

**Spec-anchored check**: 23/23 ACs batem com a spec
**Sensor**: 19/19 mutações mortas
**Gate**: 273 passed, 0 failed, 3 ignored
