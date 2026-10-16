# BSV-43 Validation

## Validation: BSV-43 - PASS condicionado à execução do workflow

**Date**: 2026-10-16
**Spec**: `.specs/features/BSV-43/spec.md` (ACs) + `docs/specs/BSV-43.md` (spec do dono)
**Diff range**: `b1412fc..d9cacff` (0d455a0, e8f4c2c, b7e2b19, 9ebcaf2, d9cacff)
**Verifier**: Verifier sub-agente, independente do autor (autor ≠ verificador). Só leitura; mutantes em cópia temporária fora do repositório.
**Iteração**: 2 de 3. A 1ª deu FAIL com G1 (README), G3 (teste INS-02) e G4 (`sort` dependente de locale). O commit `d9cacff` fecha os três, e a re-verificação está abaixo.

**O que o condicionamento quer dizer:** o PASS vale para tudo o que dá para provar sem o GitHub. O workflow `worker-arm64.yml` ainda **não rodou** (o autor não tem autorização de push). WF-04, SYS-02 e SYS-04 só têm cobertura de passo de CI não executado e **não contam como provados**; WF-01/02/03 estão provados só na parte estática. O PASS cai se a execução da PR não ficar verde nos jobs `build` e `vps` (lições 12 e 21). A execução real do dono (critério "Real" da spec) continua bloqueando o merge.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `instalar.sh` + teste | ✅ Done | caso novo de INS-02 em `d9cacff`; M14 morto |
| T2 unidades + `worker.env.example` | ✅ Done | revisão estática; `systemd-analyze verify` só no job `vps` |
| T3 workflow | ⏳ Done, não executado | `actionlint` limpo; `LC_ALL=C sort` em `d9cacff` |
| T4 README | ✅ Done | virada desliga as duas tarefas (`d9cacff`) |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + asserção | Result |
| -- | -------------------- | ---------------------- | ------ |
| INS-01 | sem argumento: última execução `success`, `push`, `main`, `worker-arm64.yml` | `infra/vps/teste_instalar.sh:78-79`: a linha inteira do `gh run list` é comparada com `esperado="run list -R $REPO --workflow worker-arm64.yml --branch main --event push --status success --limit 1 ..."` (lição 14); `:80` download do id 4242; borda sem execução em `:85-90` (`codigo != 0`, sem download, mensagem "nenhuma execução", `intacto`). Código: `infra/vps/instalar.sh:25-27` | ✅ PASS (M2, M3, M4 mortos) |
| INS-02 | ID → artefato `worker-linux-arm64-<sha7>` dessa execução; se não for push em `main`, aviso no stderr | `teste_instalar.sh:96-97`: `run list` não chamado e `run download 123 ... -n worker-linux-arm64-abcdef1`. Aviso: `:103-106` (pull_request), `:110-112` (push em develop), `:115-119` (`workflow_dispatch` em main, novo). Sem aviso em push/main: `:99`. Código: `instalar.sh:30-35` | ✅ PASS (M9, M14, M14b mortos) |
| INS-03 | 3 binários executáveis com o conteúdo do artefato em `BESAVE_BIN`, `VERSAO` com ID e sha, sem sobras, saída 0 | `teste_instalar.sh:61-72` `instalado()`: `cmp -s bin/$b art/$b`, `[ -x bin/$b ]`, `grep -qx "execucao=$id"`, `grep -qx "commit=$SHA"` (sha completo), `find -name '.*'` vazio; `codigo = 0` em `:77,:95,:104` | ✅ PASS; o `-x` só discrimina no Linux (M7, G5 aceito) |
| INS-04 | hash errado / binário ausente / lista incompleta / artefato inexistente → ≠ 0, `BESAVE_BIN` intacto, sem sobras | `teste_instalar.sh:122-146`: `codigo != 0` + `intacto()` (`:57-59`, foto com nome e hash de tudo, inclusive ocultos) | ✅ PASS (M5, M6, M11 mortos) |
| INS-05 | argumento não numérico ou mais de um → saída 2, sem chamar o `gh` | `teste_instalar.sh:149-156`: `"abc" "12a" "-1" "1 2"` → `codigo = 2`, `gh.log` vazio, `intacto` | ✅ PASS (M1, M10 mortos) |
| INS-06 | `shellcheck` limpo em `instalar.sh` e no teste | local: `shellcheck 0.11.0 infra/vps/*.sh` → exit 0; no CI em `.github/workflows/worker-arm64.yml:89` | ✅ PASS |
| SYS-01 | `/srv/besave/bin/besave-{ciclo,envio}`, `User=besave`, `Type=oneshot`, `EnvironmentFile=/srv/besave/worker.env`, timers de 5 min, `Persistent=false`, `WantedBy=timers.target` | revisão: `infra/vps/besave-ciclo.service:9-13`, `infra/vps/besave-envio.service:9-13`; `infra/vps/besave-ciclo.timer:7,9,12` (`OnCalendar=*:0/5`, `Persistent=false`, `WantedBy=timers.target`); `infra/vps/besave-envio.timer:6,8,11` (`*:2/5`) | ✅ PASS (revisão estática) |
| SYS-02 | `systemd-analyze verify` sem erros nas 4 unidades, com os binários instalados | `.github/workflows/worker-arm64.yml:119-120`, depois do `instalar.sh` real (`:107-117`) | ⏳ coberto por passo de CI **não executado** (`systemd-analyze` não existe no Windows; Docker parado) |
| SYS-03 | modelo com `TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_LOCK`, `BESAVE_ENVIO_LOCK`, `BESAVE_IMAGENS_DIR`; sem `BESAVE_ORACLE_CLIENT_DIR`; sem segredo | `infra/vps/worker.env.example:10,15,16,17,18`; `BESAVE_ORACLE_CLIENT_DIR` só no comentário `:4`; credenciais com `...`. Nomes conferidos no código: `apps/worker/src/ciclo.rs:136-141`, `apps/worker/src/envio/binario.rs:79-84,326` | ✅ PASS (revisão) |
| SYS-04 | `besave-ciclo` no ARM, fonte fake, destino local, pastas do modelo, sem `LOCALAPPDATA` → 0, `relatorio` no log, `manifest.json` no destino | `worker-arm64.yml:137` (`ExecMainStatus = 0`), `:138` (`grep -q ' relatorio '`; formato vem de `apps/worker/src/execucao.rs:243` e `apps/worker/src/logs.rs:17`), `:139` (`test -f /srv/besave/site/manifest.json`) | ⏳ coberto por passo de CI **não executado** |
| WF-01 | gatilhos push `main` / PR `develop` com os 4 caminhos + manual; `ubuntu-24.04-arm` | `worker-arm64.yml:6-21`, `:38,:75` | ✅ estático (`actionlint`); ⏳ disparo real |
| WF-02 | fmt → clippy `-D warnings` → test → build release dos 3 bins, falhando no primeiro erro | `worker-arm64.yml:52-55` (passos sequenciais, shell `-eo pipefail`) | ✅ estático; ⏳ resultado no ARM |
| WF-03 | artefato `worker-linux-arm64-<sha7>` com exatamente 3 binários + `SHA256SUMS`, 90 dias | `worker-arm64.yml:58-69` (`${COMMIT::7}`, pasta só com os 4 arquivos, `retention-days: 90`, `if-no-files-found: error`) | ✅ estático; ⏳ upload real |
| WF-04 | `sha256sum -c` passa; cada binário é ELF aarch64 | `worker-arm64.yml:101` (lista exata, agora com `LC_ALL=C sort`), `:102` (`sha256sum -c`), `:103-105` (`file` + `grep -q 'ELF 64-bit LSB .*ARM aarch64'`) | ⏳ coberto por passo de CI **não executado** |
| WF-05 | só `contents: read` + `actions: read`; sem segredo, AWS ou Oracle | `worker-arm64.yml:23-25`; único token é `github.token` (`:94,:109`); nenhum `secrets.*`, nenhum `aws-actions`, fonte `fake` (`:127`) | ✅ PASS (revisão) |
| DOC-01 | seção com pré-requisitos, `instalar.sh`, unidades, virada **desligando o PC antes**, logs, reversão | `apps/worker/README.md:686` (seção), `:694` pré-requisitos, `:709-721` instalar/reverter, `:729` unidades, `:745-758` virada (`:749-751`: "desabilitar **as duas** tarefas", com `.\scripts\remover-tarefa.ps1` e `... -NomeTarefa 'Besave Envio'`, conforme o parâmetro de `apps/worker/scripts/remover-tarefa.ps1:11`), `:760` logs | ✅ PASS (G1 fechado) |

**Status**: 16 ACs. 10 provados localmente ou por revisão (INS-01..06, SYS-01, SYS-03, WF-05, DOC-01). 3 provados só na parte estática (WF-01/02/03). 3 só em passo de CI não executado (WF-04, SYS-02, SYS-04).

### Spec do dono (`docs/specs/BSV-43.md`)

| item | situação |
| ---- | -------- |
| Saída 1 (workflow) | atendida no texto; `paths` inclui também `infra/vps/**` (superconjunto, coerente com o job `vps`) |
| Saída 2 (systemd, modelo, `instalar.sh`) | atendida; a troca atômica é por arquivo (`rename` de cada binário, `instalar.sh:56`), decisão registrada nas Assumptions |
| Saída 3 (portabilidade) | nenhum ajuste; só se confirma quando o `cargo test` rodar no ARM |
| Saída 4 (README) | atendida |
| Regra 1 (Windows não muda) | ✅ o diff não toca `apps/worker/src` nem `Cargo.*`; `#![windows_subsystem]` intacto (`apps/worker/src/bin/besave-ciclo.rs:4`) |
| Regra 2 (binário de `main`; ID aceito; nada compila na VPS) | ✅ `instalar.sh:22-28` |
| Regra 3 (sem segredo, AWS ou Oracle) | ✅ |
| Regra 4 (virada sem sobreposição) | ✅ `README.md:749-753` |
| Regra 5 (workflow rodou de verdade) | ⏳ pendente: push + `gh run list --workflow worker-arm64.yml` (lição 12) |
| Critério "Real (dono)" | pendente; bloqueia o merge |

---

## Gate Check (local, re-rodado em `d9cacff`)

| gate | comando | resultado |
| ---- | ------- | --------- |
| teste do `instalar.sh` | `bash infra/vps/teste_instalar.sh` | `ok: teste_instalar`, exit 0 (14 casos; eram 13) |
| shellcheck | `shellcheck infra/vps/*.sh` (0.11.0) | exit 0 |
| actionlint | `actionlint -shellcheck <shellcheck.exe> .github/workflows/*.yml` (1.7.12) | exit 0, com a regra `shellcheck` ativa |
| ordenação de G4 | `LANG=en_US.UTF-8 LC_ALL=C sort` sobre os 4 nomes | `./SHA256SUMS ./besave-ciclo ./besave-envio ./besave-worker`, igual à string esperada em `worker-arm64.yml:101` |
| `systemd-analyze verify` | — | não disponível (Windows); fica para o job `vps` |
| `cargo` | não rodado | o diff não toca Rust |
| segredos (regra 11) | busca por `C:\Users`, token de bot, ARN com conta, `chat_id`, hostname interno | nada encontrado |

Contagem de testes: 0 → 14 casos. Nenhum teste removido ou enfraquecido.

---

## Discrimination Sensor

Cópia de `infra/vps/instalar.sh` + `teste_instalar.sh` em `mktemp -d` fora do repositório, um mutante por vez. Pasta apagada no fim; `git status --porcelain` do worktree igual ao de antes (só `?? .specs/features/BSV-43/validation.md`). O `instalar.sh` não mudou em `d9cacff`, então os mortos da iteração 1 continuam valendo; M14, M14b e M7 foram re-rodados.

| # | `file:line` | mutação | resultado |
| - | ----------- | ------- | --------- |
| M1 | `instalar.sh:16` | aceita argumento não numérico | ✅ morto (it. 1) |
| M2 | `instalar.sh:25` | `--branch main` → `develop` | ✅ morto (it. 1) |
| M3 | `instalar.sh:25` | sem `--status success` | ✅ morto (it. 1) |
| M4 | `instalar.sh:25` | sem `--event push` | ✅ morto (it. 1) |
| M5 | `instalar.sh:45` | não confere que o `SHA256SUMS` lista os 3 | ✅ morto (it. 1) |
| M6 | `instalar.sh:48` | sem `sha256sum -c` | ✅ morto (it. 1) |
| M7 | `instalar.sh:51` | sem `chmod 755` | sobrevive no Windows: o Git Bash trata como executável todo arquivo que começa com `#!`. No Linux (job `vps`) os arquivos falsos têm modo 644 e `teste_instalar.sh:65` mata o mutante; `worker-arm64.yml:117` também executa o binário. Morte só por análise; G5 aceito pelo coordenador |
| M8 | `instalar.sh:52-53` | `VERSAO` com sha curto | ✅ morto (it. 1) |
| M9 | `instalar.sh:34` | sem aviso | ✅ morto (it. 1) |
| M10 | `instalar.sh:16` | aceita 2 argumentos | ✅ morto (it. 1) |
| M11 | antes de `instalar.sh:43` | copia para `BIN` antes de conferir | ✅ morto (it. 1) |
| M12 | `instalar.sh:56` | `mv -f` → `cp -f` | sobrevive; não equivalente, mas a atomicidade não é observável num teste sequencial. Aceito pela leitura de `instalar.sh:56` |
| M13 | `instalar.sh:32` | sem validar o sha de 40 hex | sobrevive; quase equivalente: com sha vazio o download falha com ≠ 0 e `BIN` fica intacto |
| M14 | `instalar.sh:33` | aviso só quando o ramo ≠ `main` | ✅ **morto** (it. 2: `INS-02 main fora de push`, `teste_instalar.sh:115-119`) |
| M14b | `instalar.sh:33` | aviso só quando o evento ≠ `push` | ✅ morto (it. 2: `INS-02 push fora de main`) |

**Profundidade**: estendida (15 mutantes). **Placar do sensor**: 12 mortos, 3 sobreviventes aceitos (M7 depende da plataforma, M12 não observável, M13 quase equivalente). Nenhum sobrevivente aponta lacuna de AC.

---

## Riscos do workflow (primeira execução)

| # | risco | onde | o que fazer se acontecer |
| - | ----- | ---- | ------------------------ |
| R1 | ~~ordenação dependente de locale~~ | `worker-arm64.yml:101` | fechado (`LC_ALL=C sort`) |
| R2 | `gh run download` sobre a própria execução em andamento. Os artefatos v4+ ficam na API logo após o upload e o `gh` não exige execução concluída, mas não foi verificado aqui | `:98`, `:114` | se falhar, WF-04 com `actions/download-artifact`; o `instalar.sh` fica para o teste real |
| R3 | `systemd-analyze verify` também carrega dependências (`network-online.target`, `timers.target`); erro em unidade alheia da imagem pode reprovar o passo | `:120` | ler a saída; não afrouxar o passo sem registrar |
| R4 | o AVISO do `instalar.sh` no stderr em execução de PR é esperado | `instalar.sh:34` | — |
| R5 | `enable --now` dos timers no fim do job pode disparar o envio sem Oracle nem Telegram: sem efeito externo | `:141` | — |

Conferidos sem risco: rótulo `ubuntu-24.04-arm`; permissões mínimas; nome do artefato pelo `pull_request.head.sha` (`:34`), igual ao `headSha` lido pelo `instalar.sh`; `retention-days: 90`; `upload-artifact@v7` existe (v7.0.2); `target/` em `apps/worker/target`; `ProtectSystem=full` não bloqueia `/srv`; a trava persiste (`test -f worker.lock`, `:140`).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical (nada em `src/`) | ✅ |
| No scope creep | ✅ |
| Matches patterns (versões do `ci.yml`) | ✅ |
| Spec-anchored outcome check | ✅ |
| Every test maps to a spec requirement (ID do AC no rótulo de cada caso) | ✅ |
| Documented guidelines: `CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` §6 | ✅ lição 14 (`teste_instalar.sh:78`); lição 12 pendente (G2) |

## Edge Cases

- [x] Sem execução `success` em `main` → ≠ 0, mensagem clara (`teste_instalar.sh:85-90`)
- [x] Artefato inexistente → ≠ 0, nada alterado (`teste_instalar.sh:143-146`)

---

## Lacunas ranqueadas

1. **G2 (bloqueia o PASS pleno)**: o workflow nunca executou. Falta push da branch e PR para `develop`, com `build` e `vps` verdes e sem falha em 0 s. Prova WF-01..04, SYS-02 e SYS-04.
2. **Execução real do dono**: dry-run no Oracle, virada, zero escritas, lote do envio, reboot, alerta. Bloqueia o merge.
3. **G5 (aceito)**: o `-x` de `teste_instalar.sh:65` só discrimina no Linux.

Fechadas na iteração 2: G1 (`apps/worker/README.md:749-751`), G3 (`infra/vps/teste_instalar.sh:115-119`), G4 (`.github/workflows/worker-arm64.yml:101`).

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| INS-01..06, SYS-01, SYS-03, WF-05, DOC-01 | ✅ Verified |
| WF-01, WF-02, WF-03 | ✅ estático; ⏳ execução (G2) |
| WF-04, SYS-02, SYS-04 | ⏳ só passo de CI não executado (G2) |

## Summary

**Overall**: ⚠️ PASS condicionado à execução do workflow: tudo o que dá para verificar localmente está provado, mas o PASS não vale até o `worker-arm64` ficar verde na PR. O merge depende ainda da execução real do dono.
**Spec-anchored check**: 10/16 provados, 3/16 só estáticos, 3/16 só em CI não executado; nenhum gap aberto
**Sensor**: 15 injetados, 12 mortos, 3 sobreviventes aceitos
**Gate**: `teste_instalar.sh` ok (14 casos), `shellcheck` limpo, `actionlint` limpo
