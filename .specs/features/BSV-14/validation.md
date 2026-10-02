# BSV-14 Validation

**Date**: 2026-10-02 (rodada 7: fechamento do G3)
**Spec**: `.specs/features/BSV-14/spec.md` (27 ACs: CIC-01..08, TRV-01..04, LOG-01..05, ALR-01..07, AGD-01..03)
**Diff range**: rodada 7 `374845c..cbee68e`; feature inteira `e24a757..cbee68e`
**Verifier**: sub-agente independente (autor ≠ verificador)

## Validation: BSV-14 - PASS ✅

O G3 está fechado; não há gap aberto. Os 27 ACs têm evidência `arquivo:linha` (rodadas 2–7).
A execução real do dono (Agendador + Telegram) continua bloqueando o merge (spec → Success Criteria).

## Rodada 7

| Item | Evidência | Result |
| ---- | --------- | ------ |
| G3 / LOG-05 nos modos manuais | `apps/worker/tests/dry_run.rs:431-455` `modo_manual_loga_em_horario_de_brasilia`: stderr do `--dry-run` fake não vazio (`:436`); toda linha confere posição a posição com `AAAA-MM-DDTHH:MM:SS.mmm-03:00 ` (`:438-451`, `&l[23..29] == "-03:00"`); `:453` `assert!(formato(l))` | ✅ PASS |

**Sensor (rodada 7)**: worktree temporária a partir de `cbee68e`, `CARGO_BUILD_JOBS=2`, só `--test dry_run`.

| # | Mutação | Killed? |
| - | ------- | ------- |
| R18 | remove `.with_timer(HoraBrasilia::default())` dos modos manuais (`apps/worker/src/main.rs:75`) | ✅ morto (`modo_manual_loga_em_horario_de_brasilia`, `tests/dry_run.rs:453`) |

**Resultado (rodada 7)**: 1/1 morto. Acumulado do ticket: 19 + 11 + 2 + 2 (R11, R12) + 6 (R13–R18) = 40 mutantes, todos mortos depois das correções.
**Isolamento**: a worktree foi removida e podada, e os binários de `debug/` foram restaurados. O `git status --porcelain` da árvore real ficou idêntico antes e depois: só ` M .specs/features/BSV-14/validation.md`.

**Gate** (rodado pelo Verifier na árvore real, em `cbee68e` + este relatório): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (`CARGO_BUILD_JOBS=2`) → exit 0; **283 passed, 0 failed, 3 ignored** (os 3 ignorados são de antes do ticket).

**Gaps**: nenhum.

---

# Histórico: rodada 6 (texto original)

**Date (r6)**: 2026-10-02 (G2 + ajuste do dono LOG-05)
**Spec (r6)**: `.specs/features/BSV-14/spec.md` (CIC-08, LOG-05, T12)
**Diff range (r6)**: rodada 6 `123cd5f..374845c`; feature inteira `e24a757..374845c`
**Verifier (r6)**: sub-agente independente (autor ≠ verificador)

## Veredito da rodada 6: FAIL ❌

O G2 está fechado e o LOG-05 está certo no ciclo (arquivo e stderr). O timer dos **modos manuais**
do `besave-worker` não tem teste: o mutante R18 sobrevive. O LOG-05 cobre "console do `besave-worker`"
e o coordenador declara o timer nos modos manuais. A correção é só um teste.

## Rodada 6

### LOG-05 contra o pedido do dono

| Ponto | Evidência | Result |
| ----- | --------- | ------ |
| Formato `AAAA-MM-DDTHH:MM:SS.mmm-03:00`, Brasília com offset fixo | `apps/worker/src/logs.rs` `carimbo_brasilia(ms)`; `apps/worker/tests/logs.rs:100-108` `== "2026-10-02T11:45:00.000-03:00"` e `== "2026-10-01T22:30:00.123-03:00"` | ✅ PASS (R15, R16 mortos) |
| Reaproveita `OFFSET_BRASILIA_MIN` (pedido do dono) | `apps/worker/src/logs.rs` `FUSO_BRASILIA = OFFSET_BRASILIA_MIN * 60`; `carimbo_brasilia` usa `OFFSET_BRASILIA_MIN`; `apps/worker/src/pagina_html.rs:22` agora `pub`. Uma fonte só | ✅ PASS |
| Nunca o fuso do sistema; sem dependência nova | `HoraBrasilia::format_time` usa `SystemTime` + offset fixo; `Cargo.toml`/`Cargo.lock` fora do diff `123cd5f..374845c` | ✅ PASS |
| Arquivo e stderr do ciclo, nos dois binários; 01:30Z → arquivo do dia anterior | `apps/worker/tests/cli_ciclo.rs:453-503` `log_em_horario_de_brasilia`: `:494` arquivo `besave-worker.2026-10-01.log` para 01:30Z; `:498` toda linha do arquivo `starts_with("2026-10-01T22:30:00.000-03:00 ")`/`11:45`; `:503` toda linha do stderr idem | ✅ PASS (R14, R17 mortos) |
| Relógio fixo (`BESAVE_AGORA`, só com destino local) fixa o carimbo | `apps/worker/src/ciclo.rs` `relogio_fixo()` → `HoraBrasilia::fixa(s * 1000)`; mesmo teste `:498` | ✅ PASS |
| Modos manuais do `besave-worker` (`--dry-run`/`--gerar`/`--publicar`) | `apps/worker/src/main.rs:75` `.with_timer(HoraBrasilia::default())`; **sem teste** | ❌ GAP G3 (R18 sobreviveu) |

### G2 (rodada 5)

`apps/worker/tests/cli_ciclo.rs:409-443` `mapeamento_explicito_continua_valendo` agora roda os dois binários, com um `.env` sem `BESAVE_MAPEAMENTO` e o override vindo só do ambiente; `:440` `Some(2)` e `:442` log cita o arquivo. **R13 morto** → G2 fechado.

### Sensor (rodada 6)

Rodou numa worktree temporária a partir de `374845c`, com `CARGO_BUILD_JOBS=2`, só os testes relevantes, sem AWS, sem `TELEGRAM_*` e sem `BESAVE_MAPEAMENTO`.

| # | Mutação | Testes | Killed? |
| - | ------- | ------ | ------- |
| R13 | `Opcoes::do_env` ignora `BESAVE_MAPEAMENTO` | `cli_ciclo` | ✅ morto (`tests/cli_ciclo.rs:440`) |
| R14 | arquivo com o timer padrão (UTC) | `cli_ciclo` | ✅ morto (`tests/cli_ciclo.rs:498`) |
| R15 | sinal do offset trocado (`+03:00`) | `logs`, `cli_ciclo` | ✅ morto |
| R16 | sem milissegundos | `logs`, `cli_ciclo` | ✅ morto |
| R17 | stderr do ciclo sem o timer | `cli_ciclo` | ✅ morto (`tests/cli_ciclo.rs:503`) |
| R18 (extra, do Verifier) | modos manuais sem o timer (`main.rs:75`) | `cli_ciclo`, `dry_run` | ❌ sobreviveu |

**Resultado (rodada 6)**: 5/6 mortos.
**Isolamento**: a worktree foi removida e podada, e os binários de `debug/` foram restaurados. O `git status --porcelain` da árvore real ficou idêntico antes e depois: só ` M .specs/features/BSV-14/validation.md`.

**Gate**: o coordenador informou 282 passed, 0 failed, 3 ignored em `374845c`; o Verifier não rodou o gate completo nesta rodada.

### Gaps (rodada 6)

1. **G3, minor (LOG-05, modos manuais):** nenhum teste confere o carimbo no stderr de `besave-worker --dry-run`/`--gerar`.
   - **Correção (só teste):** em `tests/dry_run.rs` (ex.: `dry_run_fora_do_repo_usa_mapeamento_embutido`), exigir que toda linha do stderr com nível de log case `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}-03:00 `. O modo manual não tem relógio fixo, então o teste confere o padrão, não o valor.

---

# Histórico: rodada 5 (texto original)

**Date (r5)**: 2026-10-02 (bug da execução real do dono, CIC-08)
**Spec (r5)**: `.specs/features/BSV-14/spec.md` (CIC-08, T11)
**Diff range (r5)**: rodada 5 `7322698..123cd5f` (`70bc9d8`, `123cd5f`); feature inteira `e24a757..123cd5f`
**Verifier (r5)**: sub-agente independente (autor ≠ verificador)

## Veredito da rodada 5: FAIL ❌

A correção do bug está certa e o bug original (R11) é detectado pelos testes. Mas o override
`BESAVE_MAPEAMENTO` não tem teste no `besave-ciclo`, o binário que o Agendador usa: o mutante R13
sobrevive. O CIC-08 exige o override nos dois binários.

## Rodada 5

### CIC-08 contra o pedido do dono

| Ponto | Evidência | Result |
| ----- | --------- | ------ |
| Padrão = mapeamento embutido, com qualquer pasta de trabalho, em `--ciclo` e `besave-ciclo` | `apps/worker/src/mapeamento.rs` `MAPEAMENTO_CONTRATO = include_str!("../../../packages/contract/mapeamento.json")`, `embutido()`, `carregar_ou_embutido(None) → embutido`; `apps/worker/src/ciclo.rs` `publicar_ciclo` usa `carregar_ou_embutido(op.mapeamento.as_deref())`; `apps/worker/tests/cli_ciclo.rs:361-401` `ciclo_fora_do_repo_usa_mapeamento_embutido` (os dois binários, `current_dir` fora do repo, sem `BESAVE_MAPEAMENTO`) → `:394` `Some(0)`, `:396-399` `lidas=10 validas=3 rejeitadas=7`, `:400` `manifest.json` | ✅ PASS (R11 morto) |
| Padrão embutido nos modos manuais | `apps/worker/src/main.rs` `executar` usa `carregar_ou_embutido(args.mapeamento.as_deref())`; `apps/worker/tests/dry_run.rs:407` `dry_run_fora_do_repo_usa_mapeamento_embutido` → `:424-425` `validas: 3`, `rejeitadas: 7` | ✅ PASS |
| Embutido = arquivo do contrato | `apps/worker/tests/mapeamento.rs:53` `embutido_igual_ao_arquivo_do_contrato` (`:57` `assert_eq!(e.loja(t), f.loja(t))` …) | ✅ PASS |
| Override `BESAVE_MAPEAMENTO` vale (`--ciclo`/manual via `clap env`) | `apps/worker/tests/cli_ciclo.rs:406-425` `mapeamento_explicito_continua_valendo` (só `besave-worker --ciclo`) → `:422` `Some(2)`, `:424` log cita o arquivo, `:425` sem `manifest.json` | ✅ PASS (R12 morto) |
| Override vale no `besave-ciclo` (`Opcoes::do_env`) | sem teste: `apps/worker/src/ciclo.rs` `Opcoes::do_env` `mapeamento: var("BESAVE_MAPEAMENTO").map(PathBuf::from)` não é exercitado com um override que mude o resultado | ❌ GAP G2 (R13 sobreviveu) |
| README sem dependência do repo | `apps/worker/README.md:311` `BESAVE_MAPEAMENTO` = override, padrão embutido; `:386` "o executável não depende do repositório … recompile e copie o `.exe`"; a linha `BESAVE_MAPEAMENTO='C:\git\besave\…'` saiu do `.env` de exemplo | ✅ PASS |

### Sensor (rodada 5)

Rodou numa worktree temporária a partir de `123cd5f`, com `CARGO_BUILD_JOBS=2`, só os testes relevantes, sem AWS, sem `TELEGRAM_*` e sem `BESAVE_MAPEAMENTO` no ambiente.

| # | Mutação | Testes | Killed? |
| - | ------- | ------ | ------- |
| R11 | `carregar_ou_embutido(None)` → `carregar("../../packages/contract/mapeamento.json")` (bug original) | `cli_ciclo`, `dry_run`, `mapeamento` | ✅ morto (`ciclo_fora_do_repo_usa_mapeamento_embutido`, `tests/cli_ciclo.rs:394`) |
| R12 | `carregar_ou_embutido` ignora o `Some` | `cli_ciclo`, `dry_run`, `mapeamento` | ✅ morto (`mapeamento_explicito_continua_valendo`, `tests/cli_ciclo.rs:422`) |
| R13 | `Opcoes::do_env` ignora `BESAVE_MAPEAMENTO` (`mapeamento: None`) | `cli_ciclo` | ❌ sobreviveu |

**Resultado (rodada 5)**: 2/3 mortos.

**Isolamento**: a worktree foi removida e podada, e os binários de `debug/` foram restaurados do backup. O `git status --porcelain` da árvore real **não** ficou igual: durante o sensor apareceram ` M` em `src/ciclo.rs`, `src/logs.rs`, `src/main.rs`, `src/pagina_html.rs`, `tests/cli_ciclo.rs` e `tests/logs.rs`.
- Não vieram do sensor: nenhum padrão dos mutantes R11–R13 aparece no diff, e `logs.rs`/`pagina_html.rs` nem são alvo dos mutantes.
- Correção da rodada 6: eram edições em andamento do próprio coordenador (o ajuste LOG-05), depois commitadas em `374845c`; não eram de outra sessão.
- O Verifier não tocou nesses arquivos.

**Gate**: o coordenador informou 280 passed, 0 failed, 3 ignored em `123cd5f`. O Verifier não rodou o gate completo nesta rodada: a árvore real tinha edições não commitadas de outra sessão.

### Gaps (rodada 5)

1. **G2, major (CIC-08, override no `besave-ciclo`):** o mutante R13 sobrevive. Se o `besave-ciclo` (o binário do Agendador) ignorar o `BESAVE_MAPEAMENTO`, nenhum teste falha.
   - **Correção (só teste):** fazer `mapeamento_explicito_continua_valendo` rodar nos dois binários: `besave-worker --ciclo` e `besave-ciclo --env-file …`, com `BESAVE_MAPEAMENTO` apontando para um arquivo ausente → código 2, log citando o arquivo e nenhum `manifest.json`.
   - **Atenção:** o helper `env_file()` grava `BESAVE_MAPEAMENTO` no `.env`; para provar o override do ambiente, use um `.env` sem essa linha ou um valor diferente.

---

# Histórico: rodada 4 (texto original)

**Date (r4)**: 2026-10-01 (fix→re-verify 1 de 3)
**Spec (r4)**: `.specs/features/BSV-14/spec.md` (escopo do dono: `docs/specs/BSV-14.md` + ajuste de 01/10)
**Diff range (r4)**: rodada 4 `c7ef61c..7322698`; feature inteira `e24a757..7322698`
**Verifier (r4)**: sub-agente independente (autor ≠ verificador)

## Veredito da rodada 4: PASS ✅

O gap G1 da rodada 3 está fechado e a observação 2 foi acatada. Os 25 ACs têm evidência
`arquivo:linha`. A execução real do dono (Agendador + Telegram) continua bloqueando o merge.

## Rodada 4

| Item | Evidência | Result |
| ---- | --------- | ------ |
| G1 / CIC-06: argumento desconhecido → 2 também com `--env-file=` | `apps/worker/src/bin/besave-ciclo.rs:15-24` aceita só `[]`, `["--env-file", arq]` ou `[a]` com `--env-file=`; o resto → `Argumento`. `apps/worker/tests/cli_ciclo.rs` `besave_ciclo_argumento_invalido_sai_com_2`: o loop inclui `["--env-file=x.env", "--sim"]` e `["--sim", "--env-file=x.env"]` → `Some(2)` + `variante=Argumento` | ✅ PASS |
| Obs. 2: destino local avisa no log | `apps/worker/src/ciclo.rs:312` `warn!(… "BESAVE_DESTINO_LOCAL definida: publicando na pasta, não no S3")`; asserção em `apps/worker/tests/cli_ciclo.rs:285` | ✅ PASS |

**Gate**: 276 passed, 0 failed, 3 ignored no gate completo, informado pelo coordenador em `7322698`. O Verifier rodou `cargo test --test cli_ciclo` na árvore real depois do sensor: 10/10.

**Sensor (rodada 4)**: worktree temporária a partir de `7322698`, `CARGO_BUILD_JOBS=2`, só `--test cli_ciclo`, sem AWS nem `TELEGRAM_*`.

| # | Mutação | Killed? |
| - | ------- | ------- |
| R9 | `src/bin/besave-ciclo.rs` volta à versão de `c7ef61c` (parsing antigo) | ✅ morto (`besave_ciclo_argumento_invalido_sai_com_2`, `tests/cli_ciclo.rs:329`) |
| R10 | remove o `warn!` do destino local (`src/ciclo.rs:312`) | ✅ morto (`besave_ciclo_e_ciclo_dao_o_mesmo_relatorio`, `tests/cli_ciclo.rs:285`) |

**Resultado (rodada 4)**: 2/2 mortos. Acumulado do ticket: 19 (rodada 2) + 11 (rodada 3) + 2 = 32 mutantes, todos mortos.
**Isolamento**: worktree removida e podada; binários de `debug/` restaurados do backup; o `git status --porcelain` da árvore real ficou idêntico antes e depois (só ` M .specs/features/BSV-14/validation.md`, este relatório).

**Gaps**: nenhum.

---

# Histórico: rodada 3 (texto original)

**Date (r3)**: 2026-10-01
**Spec (r3)**: `.specs/features/BSV-14/spec.md` (escopo do dono: `docs/specs/BSV-14.md` + ajuste de 01/10: sem janela de console)
**Diff range (r3)**: rodada 3 `f5774fa..c7ef61c` (`5e2d1bb`, `a5eea29`, `c7ef61c`); feature inteira `e24a757..c7ef61c`
**Verifier (r3)**: sub-agente independente (autor ≠ verificador)

## Veredito da rodada 3: FAIL ❌

Um gap pequeno, com correção de uma linha: o **CIC-06** ("argumento desconhecido SHALL sair com
código 2") ainda falha na forma `--env-file=<arq> <extra>`. Todo o resto está verificado:
- os 25 ACs, menos esse caso, têm evidência `arquivo:linha`;
- gate verde: 276 passados, 0 falhos;
- sensor da rodada 3: 11/11 mortos, com R5–R7 mortos depois de `c7ef61c`;
- refatoração do `--ciclo` sem mudança de comportamento.

A execução real do dono continua bloqueando o merge.

---

## Rodada 3: ajuste do dono (`besave-ciclo` sem console)

### Tarefas

| Task | Status | Notes |
| ---- | ------ | ----- |
| T9 `besave-ciclo` sem console | ⚠️ Partial | `5e2d1bb` + `c7ef61c`; gap G1 (argumento extra com `--env-file=`) |
| T10 Agendador → `besave-ciclo.exe`; README | ✅ Done | `a5eea29` |

### Spec-Anchored Acceptance Criteria (alterados/novos)

Caminhos relativos a `apps/worker/`.

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| CIC-06a binário fino, mesmo caminho da lib, sem lógica duplicada | `besave-ciclo` só lê args/`.env` e chama `ciclo::executar` | `src/bin/besave-ciclo.rs:10-21` (26 linhas; chama `ciclo::executar(&Opcoes::do_env(), previa)`); `src/main.rs` (`--ciclo`) chama o mesmo `ciclo::executar` com `stderr: true` e `ao_publicar`; o `fake_demo` foi movido para `src/fonte.rs` sem mudança (diff do corpo vazio contra `f5774fa:src/main.rs`) | ✅ PASS |
| CIC-06b sem stdout/stderr | as duas saídas vazias | `tests/cli_ciclo.rs:275-276` `out_c.stdout.is_empty()`, `out_c.stderr.is_empty()` (sucesso); mesmas asserções no loop de `besave_ciclo_argumento_invalido_sai_com_2` (erro). Cabeçalho PE conferido pelo Verifier: `besave-ciclo.exe` subsistema 2 (GUI), `besave-worker.exe` 3 (console) | ✅ PASS |
| CIC-06c mesma linha `relatorio` para a mesma fonte fake | igualdade sem os campos de tempo | `tests/cli_ciclo.rs:279` `assert_eq!(relatorio_estavel(&local_c), rel_w)`; `:278` `rel_w.contains("lidas=10 validas=3 rejeitadas=7")` (ancora o valor, não só a igualdade) | ✅ PASS |
| CIC-06d argumento desconhecido → 2 | código 2, `variante=Argumento` | `tests/cli_ciclo.rs` `besave_ciclo_argumento_invalido_sai_com_2`: `--publicar` e `--env-file x.env --sim` → `Some(2)` + `variante=Argumento` | ❌ GAP G1: `besave-ciclo --env-file=<arq> --sim` (e `--sim --env-file=<arq>`) é aceito; reproduzido em `c7ef61c`: o log mostra `variante=EnvFile` (seguiu para o `.env`), não `Argumento`. Causa: `src/bin/besave-ciclo.rs:15` aceita `[_, _]` sempre que `env_file_dos_args` acha um `--env-file=` em qualquer posição |
| CIC-07a destino local publica em pasta + KVS em memória, sem `BESAVE_BUCKET`/`BESAVE_KVS_ARN` | código 0, `manifest.json` na pasta | `tests/cli_ciclo.rs:273-274` `Some(0)` para os dois binários; `:280` `saida/manifest.json` existe; código `src/ciclo.rs:285-288`, `:311-315` | ✅ PASS (R8 morto) |
| CIC-07b `BESAVE_AGORA` só com destino local | sem destino, relógio do sistema | `tests/cli_ciclo.rs:318-319` `nomes.len() == 1` e `!= "besave-worker.2026-09-21.log"`; código `src/ciclo.rs:196-205` | ✅ PASS (R3 morto) |
| AGD-01 tarefa aponta para `besave-ciclo.exe`, sem `--ciclo` | script rejeita outro exe; argumento só `--env-file` | `scripts/registrar-tarefa.ps1:33-36` `if ($nomeExe -ne 'besave-ciclo.exe') { throw … }`; `:44` `-Argument` só com `--env-file`; os outros gatilhos e limites não mudaram (rodada 2) | ✅ PASS |
| AGD-03 README atualizado | dois executáveis, cópia do `besave-ciclo.exe`, novas variáveis | `README.md:332` título; `:342` tabela `besave-ciclo.exe` (sem console); `:408-409` cópia e registro com `besave-ciclo.exe`; `:415` "o script só aceita o `besave-ciclo.exe`"; `BESAVE_DESTINO_LOCAL`/`BESAVE_AGORA` na tabela de variáveis | ✅ PASS |

**`--ciclo` sem mudança de comportamento:** os 10 testes antigos e novos de `tests/cli_ciclo.rs`
e os de `tests/execucao.rs` passam; M15b, M16b e M19b (os mutantes da rodada 2 que tocavam código
movido para `src/ciclo.rs`) morrem; e o `--ciclo` mantém o relatório no stdout (`c7ef61c`:
`lidas: 10`/`validas: 3`, R6 morto).

### Gate

- `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` (`CARGO_BUILD_JOBS=2`): exit 0.
- **Gate**: 276 passed, 0 failed, 3 ignored em `a5eea29`, rodado pelo Verifier.
- Em `c7ef61c`, `cargo test --test cli_ciclo` deu 10/10 depois do sensor; o coordenador informou 276/0/3 no gate completo nesse commit.

### Discrimination Sensor (rodada 3)

Rodou numa worktree temporária fora do repo, uma por execução, com `CARGO_BUILD_JOBS=2`, só `--test cli_ciclo`, alvo compartilhado, sem AWS nem `TELEGRAM_*`. Os binários do topo de `debug/` ganharam backup antes e foram restaurados depois.

| # | File:line | Mutação | `a5eea29` | `c7ef61c` |
| - | --------- | ------- | --------- | --------- |
| R1 | `src/ciclo.rs:115` | `Opcoes::do_env` com `stderr: true` | ✅ morto | - |
| R2 | `src/bin/besave-ciclo.rs:16` | `besave-ciclo` ignora o `.env` | ✅ morto | - |
| R3 | `src/ciclo.rs:197-198` | `BESAVE_AGORA` vale sem destino local | ✅ morto | - |
| R4 | `src/bin/besave-ciclo.rs:17` | aceita argumento desconhecido (1–2 args) | ✅ morto | - |
| R5 | `src/bin/besave-ciclo.rs:18` | aceita 3+ argumentos | ❌ sobreviveu | ✅ morto |
| R6 | `src/main.rs` (`ao_publicar: Some(&imprimir_publicacao)`) | `--ciclo` sem relatório no stdout | ❌ sobreviveu | ✅ morto |
| R7 | `src/ciclo.rs:262` | `ao_publicar` chamado também na falha | ❌ sobreviveu | ✅ morto |
| R8 | `src/ciclo.rs:285` | destino local ignorado (cai na AWS → 2) | ✅ morto | - |
| M15b | `src/ciclo.rs:81` | `dotenvy::from_path_override` | ✅ morto | - |
| M16b | `src/ciclo.rs:250` | ciclo pulado sai com 1 | ✅ morto | - |
| M19b | `src/ciclo.rs:85` | `erro_env_file` → `e.to_string()` | ✅ morto | - |

**Resultado (rodada 3)**: 11/11 mortos em `c7ef61c`. R5–R7 foram rodados de novo pelo Verifier, de forma independente, numa worktree nova a partir de `c7ef61c`.
**Isolamento**: o `git status --porcelain` da árvore real ficou idêntico antes e depois (vazio); a worktree foi removida e podada.

### Gaps (rodada 3)

1. **G1, minor (CIC-06):** `src/bin/besave-ciclo.rs:13-19` aceita um argumento extra quando o `.env` vem como `--env-file=<arq>`: `--env-file=a.env --sim` e `--sim --env-file=a.env` rodam o ciclo. O Agendador não passa isso, mas o AC diz "argumento desconhecido SHALL sair com código 2".
   - **Correção:** aceitar só `[]`, `["--env-file", arq]` ou `[a]` com `a` começando por `--env-file=`; o resto vira `Argumento`.
   - **Teste:** incluir `("ciclo-arg-igual", ["--env-file=x.env", "--sim"])` no loop de `besave_ciclo_argumento_invalido_sai_com_2`.
2. **Observação (não bloqueia):** um `BESAVE_DESTINO_LOCAL` esquecido no `.env` de produção faz todo ciclo "dar certo" (código 0) sem publicar no S3, e nem o log nem a linha `relatorio` dizem o destino.
   - **Sugestão:** um `WARN destino local: …` no início do ciclo, ou `destino=local` no relatório.

---

# Histórico: rodada 2 (texto original)

**Date (r2)**: 2026-10-01 (rodada 2)
**Spec (r2)**: `.specs/features/BSV-14/spec.md` (escopo do dono: `docs/specs/BSV-14.md`)
**Diff range (r2)**: `e24a757..6a5f3a8` (commits `cce0f85..6a5f3a8`, branch `rubenmarcus/rub-14-bsv-14-telegram`)
**Verifier (r2)**: sub-agente independente (autor ≠ verificador)

### Veredito da rodada 2: PASS ✅

- Todos os 23 ACs têm evidência `arquivo:linha`, e os valores testados batem com a spec.
- Gate verde: 273 passados, 0 falhos.
- Sensor: 19 de 19 mutantes mortos.
- Os gaps 1, 3, 4 e 5 da rodada 1 foram fechados em `6a5f3a8`.
- A execução real do dono (Agendador + Telegram) continua bloqueando o merge (spec → Success Criteria).

---

### Task Completion

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

### Spec-Anchored Acceptance Criteria

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

### Edge Cases

- [x] `alerta.json` corrompido → WARN + estado vazio: `tests/alerta.rs:247-248`.
- [x] Duas variantes na mesma janela → um envio cada: `tests/alerta.rs:119-120`.
- [x] Recuperado que falha mantém o estado: `tests/alerta.rs:230-235`.
- [x] Linha malformada do `.env` não vaza no log/stderr (CIC-05): `tests/cli_ciclo.rs:221`, `:224`.

---

### Owner scope (`docs/specs/BSV-14.md`) vs spec derivada

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

### Gate Check

- **Gate command** (em `apps/worker`, `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=2`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- **Gate**: exit 0. **273 passed, 0 failed, 3 ignored** (os 3 ignorados são de antes: `ciclo.rs`, `imagens.rs`, `paginas.rs`).
- **Test count**: 272 na rodada 1 → 273 (+1: `env_file_malformado_sai_com_2_sem_ecoar_a_linha`). São 36 testes novos do BSV-14 no total; nenhum teste foi apagado ou enfraquecido.

---

### Discrimination Sensor

**Sensor depth**: expandido. São 19 mutações manuais cobrindo os ramos de risco (estado persistido, concorrência, dados sensíveis, código de saída).
**Resultado (rodada 2)**: 19/19 killed

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

### Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / no scope creep | ✅ (`gerar()` intacto; sem loop interno) |
| Surgical changes | ✅ (`apps/worker/` + `.specs/features/BSV-14/`) |
| Matches patterns | ✅ |
| Spec-anchored outcome check | ✅ 23/23 |
| Every test maps to a requirement | ✅ |
| Guidelines (`CLAUDE.md`, `apps/worker/CLAUDE.md`) | ✅ (byte de controle de `main.rs` corrigido; nenhum outro byte de controle em `src/`/`tests/`) |

---

### Gaps

Nenhum gap bloqueante. Observações:
- **Merge bloqueado pela execução real do dono** (spec → Success Criteria): 6 execuções com resultado 0 em 30 min, 6 linhas `relatorio`, um alerta com `BESAVE_KVS_ARN` inválido e o "recuperado" depois. Sem isso, nada valida o gatilho do Agendador, o TLS do Telegram nem o caminho Oracle/AWS do `--ciclo`.
- `erro_env_file` (`src/main.rs:105-114`) mantém o texto de `Io`/`EnvVar`. O `io::Error` do Windows não traz conteúdo do arquivo, então não há vazamento conhecido.

---

### Histórico

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

### Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| CIC-01..05, TRV-01..04, LOG-01..04, ALR-01..07, AGD-01..03 | ✅ Verified |

---

### Summary

**Overall**: ✅ Ready (do lado do código; a execução real do dono continua bloqueando o merge)

**Spec-anchored check**: 23/23 ACs batem com a spec
**Sensor**: 19/19 mutações mortas
**Gate**: 273 passed, 0 failed, 3 ignored
