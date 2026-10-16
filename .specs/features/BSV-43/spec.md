# BSV-43 Worker: binário Linux ARM64 e execução na VPS Specification

Fonte: `docs/specs/BSV-43.md`. Roteiro da máquina: `docs/infra/VPS-INSTANCIA-1.md` (Fases 2, 4 e 6).

## Problem Statement

`besave-ciclo` e `besave-envio` rodam no Agendador do Windows. Vão para a instância 1 da OCI (Ubuntu
24.04 ARM64), onde nada se compila. Falta quem gere o binário ARM64 rastreável ao commit, quem o
instale com conferência de integridade e quem o rode a cada 5 min no lugar do Agendador.

## Goals

- [ ] Todo push em `main` (e toda PR para `develop`) que toca o worker gera, no runner ARM, os 3
      binários testados e um `SHA256SUMS`, num artefato com o sha curto no nome.
- [ ] A VPS instala um artefato com um comando, sem compilar, e roda ciclo e envio de 5 em 5 min
      pelo `systemd`, sobrevivendo a reinício.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Robôs de captura | BSV-42 |
| Backup do banco, instância 2 | spec |
| Mudança de lógica do ciclo/envio, Windows ARM | spec |
| Instalar a VPS (Instant Client, wallet, usuário, `gh auth login`) | roteiro do dono, `docs/infra/VPS-INSTANCIA-1.md` |
| Ligar os timers e a virada | execução real do dono (bloqueia o merge) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Sha curto do artefato | 7 primeiros hex de `github.sha` | Padrão do GitHub; o `instalar.sh` deriva o nome do `headSha` da execução | n |
| Commit compilado na PR | A ponta da PR (`pull_request.head.sha`), não o merge sintético | O nome do artefato e o `VERSAO` apontam para um commit que existe; é o `headSha` que o `gh` devolve | n |
| `instalar.sh` sem argumento | Última execução `success` de `worker-arm64.yml` em `main`, evento `push` | Produção roda binário de `main` (AD-060) | n |
| `instalar.sh <id>` de execução que não é push em `main` | Instala e avisa (stderr) que é só para o teste real antes do merge | Regra 2 da spec (lição 9) | n |
| Exigir `conclusion=success` com id explícito | Não: o artefato só é enviado depois de fmt/clippy/test no mesmo job; a conferência é o `SHA256SUMS` | Permite testar o script no próprio workflow, que ainda está em andamento | n |
| Troca "atômica" | Cada binário é `rename(2)` de um arquivo completo na mesma pasta (`/srv/besave/bin/.instalar.*`); processo em execução segue com o inode antigo | Nenhum timer executa arquivo pela metade; os 3 binários são independentes | n |
| `SHA256SUMS` que omite um binário | Recusa | `sha256sum -c` só confere o que está listado | n |
| Agenda dos timers | `OnCalendar=*:0/5` (ciclo) e `*:2/5` (envio), `AccuracySec=1s`, `Persistent=false` | 5 min como no PC; defasagem de 2 min espalha a CPU de 1 OCPU; o envio já tolera atraso | n |
| Ciclo que passa de 5 min | Timer não dispara outro enquanto o `oneshot` está ativo; trava do binário continua | Mesmo efeito do "não abrir nova instância" do Agendador | n |
| Tempo máximo | `TimeoutStartSec=20min` | Igual ao limite da tarefa do Windows | n |
| Variáveis | `EnvironmentFile=/srv/besave/worker.env`, sem `--env-file` | Spec; evita ler o mesmo arquivo com dois parsers | n |
| Trava, alerta e estado do envio | `BESAVE_LOCK=/srv/besave/estado/worker.lock`, `BESAVE_ENVIO_LOCK=/srv/besave/estado/envio.lock`; sem `LOCALAPPDATA`, `alerta.json`, `alerta-envio.json` e `envio-estado.json` ficam ao lado da trava | Código atual (`ciclo.rs` `pastas`, `envio/binario.rs` `pastas`); persistente, não `/run` | n |
| Onde rodam as conferências de Linux | Job `vps` no próprio `worker-arm64.yml` (ARM, Ubuntu 24.04), com `infra/vps/**` nos `paths` | `systemd-analyze` e `shellcheck` precisam de Linux; o mesmo job testa o `instalar.sh` contra o artefato real | n |
| Ajustes de portabilidade no Rust | Nenhum previsto: `cargo test` já roda em Linux x86 no `ci.yml` e não há `cfg(windows)` no worker | Só entram se o runner ARM reprovar algo (spec saída 3) | n |

Open questions: none

---

## User Stories

### P1: Binários ARM64 do CI ⭐ MVP

**User Story**: Como dono, quero que cada merge em `main` gere os binários Linux ARM64 testados, para
instalar na VPS o mesmo commit que está em `main`.

**Acceptance Criteria**:

1. WF-01: WHEN há push em `main` ou PR para `develop` com mudança em `apps/worker/**`,
   `packages/contract/**`, `infra/vps/**` ou `.github/workflows/worker-arm64.yml`, ou disparo manual,
   THEN o workflow `worker-arm64.yml` SHALL rodar em `ubuntu-24.04-arm`.
2. WF-02: WHEN o workflow roda THEN SHALL executar `cargo fmt --check`, `cargo clippy --all-targets
   -- -D warnings`, `cargo test` e `cargo build --release` dos bins `besave-ciclo`, `besave-envio`
   e `besave-worker`, nessa ordem, falhando no primeiro erro.
3. WF-03: WHEN o build termina THEN SHALL enviar o artefato `worker-linux-arm64-<sha7>` com
   exatamente os 3 binários e `SHA256SUMS`, retenção de 90 dias.
4. WF-04: WHEN o artefato é baixado THEN `sha256sum -c SHA256SUMS` SHALL passar e cada binário SHALL
   ser ELF aarch64.
5. WF-05: O workflow SHALL ter só `contents: read` e `actions: read`, sem segredo, AWS ou Oracle.

**Independent Test**: execução do workflow na PR (job `vps` baixa o artefato pelo `instalar.sh`).

---

### P1: Instalação na VPS ⭐ MVP

**User Story**: Como dono, quero trocar os binários da VPS com um comando que confere a integridade.

**Acceptance Criteria**:

1. INS-01: WHEN `instalar.sh` roda sem argumento THEN SHALL escolher a última execução `success`,
   evento `push`, ramo `main`, de `worker-arm64.yml`.
2. INS-02: WHEN recebe um ID de execução THEN SHALL instalar o artefato `worker-linux-arm64-<sha7>`
   dessa execução; se ela não for push em `main`, SHALL avisar no stderr que é só para teste.
3. INS-03: WHEN o `SHA256SUMS` confere e lista os 3 binários THEN SHALL deixar em `BESAVE_BIN`
   (padrão `/srv/besave/bin`) os 3 binários executáveis com o conteúdo do artefato e um `VERSAO` com
   o ID e o sha, sem sobras temporárias, e sair com 0.
4. INS-04: WHEN um hash não confere, um binário falta no artefato ou o `SHA256SUMS` não lista um dos 3
   THEN SHALL sair com código ≠ 0, sem alterar nenhum arquivo de `BESAVE_BIN` e sem sobras.
5. INS-05: WHEN o argumento não é um número ou há mais de um THEN SHALL sair com 2 sem chamar o `gh`.
6. INS-06: `shellcheck` SHALL ficar limpo em `instalar.sh` e no seu teste.

**Independent Test**: `infra/vps/teste_instalar.sh` com um `gh` falso; job `vps` com o `gh` real.

---

### P1: Execução agendada ⭐ MVP

**User Story**: Como dono, quero ciclo e envio rodando a cada 5 min na VPS com o mesmo comportamento
do PC.

**Acceptance Criteria**:

1. SYS-01: `besave-ciclo.service`/`.timer` e `besave-envio.service`/`.timer` SHALL rodar
   `/srv/besave/bin/besave-ciclo` e `/srv/besave/bin/besave-envio` como `besave`, `Type=oneshot`,
   `EnvironmentFile=/srv/besave/worker.env`, timers de 5 min, `Persistent=false`, habilitáveis em
   `timers.target`.
2. SYS-02: `systemd-analyze verify` SHALL passar sem erros nas 4 unidades, com os binários instalados.
3. SYS-03: `worker.env.example` SHALL trazer `TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_LOCK`,
   `BESAVE_ENVIO_LOCK`, `BESAVE_IMAGENS_DIR`, sem `BESAVE_ORACLE_CLIENT_DIR` e sem segredo preenchido.
4. SYS-04: WHEN o `besave-ciclo` instalado roda no ARM com `BESAVE_FONTE=fake`, `BESAVE_DESTINO_LOCAL`
   e as pastas de `worker.env.example` (sem `LOCALAPPDATA`) THEN SHALL sair com 0 e escrever
   `relatorio` no log de `BESAVE_LOG_DIR` e o `manifest.json` no destino.

---

### P2: Documentação

1. DOC-01: `apps/worker/README.md` SHALL ter a seção "Rodar no Linux (VPS)": pré-requisitos,
   `instalar.sh`, unidades, virada **desligando as tarefas do PC antes** de ligar os timers, logs,
   reversão.

---

## Edge Cases

- `gh` sem execução `success` em `main` → `instalar.sh` sai com ≠ 0 e mensagem clara (INS-01).
- Artefato expirado/inexistente → `gh run download` falha → ≠ 0, nada alterado (INS-04).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| INS-01 | Instalação | Execute | Done |
| INS-02 | Instalação | Execute | Done |
| INS-03 | Instalação | Execute | Done |
| INS-04 | Instalação | Execute | Done |
| INS-05 | Instalação | Execute | Done |
| INS-06 | Instalação | Execute | Done |
| SYS-01 | Execução agendada | Execute | Done |
| SYS-02 | Execução agendada | Execute | Done |
| SYS-03 | Execução agendada | Execute | Done |
| SYS-04 | Execução agendada | Execute | Done |
| WF-01 | Binários ARM64 | Execute | Done |
| WF-02 | Binários ARM64 | Execute | Done |
| WF-03 | Binários ARM64 | Execute | Done |
| WF-04 | Binários ARM64 | Execute | Done |
| WF-05 | Binários ARM64 | Execute | Done |
| DOC-01 | Documentação | Execute | Done |

---

## Success Criteria

- [ ] Workflow verde na PR, no ARM, com o artefato conferido por `sha256sum -c`.
- [ ] Real (dono): dry-run no Oracle, virada, primeiro ciclo com zero escritas, lote do envio, reboot,
      alerta de falha.
