# BSV-43 · Worker: binário Linux ARM64 e execução na VPS

**Papel:** Backend Rust + CI · **Pastas:** `apps/worker/`, `.github/workflows/` (+ `infra/vps/`, novo) ·
**Depende de:** BSV-42 em paralelo (não bloqueia). AD-060, AD-080, AD-100, AD-104; MANIFEST §6;
`docs/infra/VPS-INSTANCIA-1.md` (Fase 6)

## Contexto
`besave-ciclo` e `besave-envio` rodam no Agendador do Windows do PC a cada 5 min. Vão para a instância 1
da OCI (Ubuntu 24.04 **ARM64**), perto do banco: a leitura do Oracle cai de ~10 s (pela internet) para
poucos segundos. Decisão do dono: nada se compila nas VPS. O código já é portável (trava com
`File::try_lock`, pastas por `BESAVE_LOG_DIR`/`BESAVE_LOCK`/`BESAVE_ENVIO_LOCK`), mas nunca rodou em
produção fora do Windows, e o CI testa só em x86.

## Objetivo
Cada merge em `main` que toca o worker gera os binários Linux ARM64 rastreáveis ao commit, e a VPS os roda
de 5 em 5 minutos com o mesmo comportamento do PC.

## Saídas
1. **Workflow** `worker-arm64.yml`: em `push` para `main` com mudança em `apps/worker/**` ou
   `packages/contract/**`, e manual (`workflow_dispatch`); `runs-on: ubuntu-24.04-arm` (grátis em
   repositório público); `cargo fmt --check`, `clippy -D warnings`, `cargo test` e
   `cargo build --release` de `besave-ciclo`, `besave-envio` e `besave-worker`; artefato
   `worker-linux-arm64-<sha curto>` com os 3 binários e um `SHA256SUMS`; retenção de 90 dias.
2. **Execução na VPS** (`infra/vps/`): unidades `systemd` `besave-ciclo.service` + `.timer` e
   `besave-envio.service` + `.timer` (5 min, `Persistent=false`, usuário `besave`, `EnvironmentFile`
   apontando para o `.env` fora do repo); modelo `worker.env.example` para Linux sem segredos
   (`TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_LOCK`, `BESAVE_ENVIO_LOCK`, `BESAVE_IMAGENS_DIR`, sem
   `BESAVE_ORACLE_CLIENT_DIR`); script `instalar.sh` que baixa um artefato pelo `gh`, confere o
   `SHA256SUMS` e troca os binários em `/srv/besave/bin` de forma atômica.
3. Ajustes de portabilidade que os testes no ARM revelarem (só os necessários; listar no PR).
4. `apps/worker/README.md`: seção "Rodar no Linux (VPS)".

## Regras
1. O comportamento no Windows não muda; o `windows_subsystem` continua.
2. Produção roda binário de `main` (AD-060); o teste real antes do merge usa o artefato do
   `workflow_dispatch` da branch da PR (lição 9), e o `instalar.sh` aceita o ID da execução. Nada de
   compilar na VPS.
3. O workflow não guarda segredo nenhum e não fala com AWS nem Oracle.
4. **Virada sem sobreposição:** o roteiro do PR manda desabilitar `Besave Worker` e `Besave Envio` no PC
   **antes** de ligar os timers na VPS. Dois envios ao mesmo tempo postam em dobro no canal.
5. Lições 12 e 21: conferir que o workflow rodou de verdade (falha em 0 s = YAML inválido).

## Fora de escopo
Robôs (BSV-42), backup do banco (plano da instância 2), mudança de lógica do ciclo ou do envio,
Windows ARM.

## Critério de aceite
- Workflow verde num PR de teste (`workflow_dispatch` na branch) com `cargo test` passando no ARM e o
  artefato com 3 binários e `SHA256SUMS` corretos (conferido com `sha256sum -c`).
- `systemd-analyze verify` sem erros nas unidades; `shellcheck` limpo no `instalar.sh`.
- **Real (dono):** na instância 1, `besave-worker --dry-run` lendo o Oracle; virada (PC desligado → timers
  ligados); primeiro ciclo com **zero escritas** além dos manifests e `t_leitura_fonte` menor que no PC;
  um lote do envio postado normalmente; `sudo reboot` e os timers voltam sozinhos; alerta de falha no
  Telegram ao derrubar a conexão do banco de propósito por um ciclo.

## Definition of done
PR com o workflow verde no ARM, unidades e script revisados, `validation.md` do Verifier independente e
a execução real do dono antes do merge.
