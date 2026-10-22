# BSV-49 — validation.md

**Verificador:** sub-agente independente (autor != verificador), commit `7e88c3d`. Não alterou código nem testes.
**Veredito: PASS com ressalvas** (5 lacunas menores nos testes, nenhuma no código; execução real pendente do dono).

## 1. Gates (executados pelo verificador)

| gate | resultado |
|---|---|
| `terraform fmt -check -recursive` | ok |
| `terraform validate` | Success |
| `terraform test` | 19 passed, 0 failed |
| `bash infra/backup/teste_backup.sh` | 178 de 178 verificações ok (~3 min no Git Bash/Windows) |
| shellcheck 5 scripts de `infra/backup/*.sh` | limpo (só SC1091 "not following lib.sh", artefato de rodar por stdin sem `-x`; o CI usa `shellcheck -x`) |
| CI job `infra` (`.github/workflows/ci.yml:128-134`) | inclui shellcheck e `teste_backup.sh` |

## 2. Critérios de aceite x evidência

| critério (spec original) | resultado | evidência |
|---|---|---|
| Export 03:30 via Data Pump, nome com data, direto no bucket OCI | PASS (API real pendente) | `systemd/besave-backup-diario.timer:6`; `backup-diario.sh:63-74` (parfile, `dumpfile=$URI/besave-AAAAMMDD-%L.dmp`); teste BKP-01 compara parfile e comando inteiros |
| Bucket `besave-backup` privado, SSE, versionamento, ciclo de vida | PASS | `backup.tf:2-47`; `backup.tftest.hcl` BKP-01..06 |
| IAM só grava/lê/lista `db/`; apagar negado | PASS | `backup.tf:83-107` (Allow Put/Get/Abort em `db/*`, List com `s3:prefix=db/*`, Deny Delete{Object,ObjectVersion,Bucket}); `backup.tftest.hcl:77-114` (BKP-08/09, Deny explícito). Mutantes T2, T3, T4, T7 mortos |
| Retenção OCI 7 d (mantém D-6..D) | PASS | `backup-diario.sh:112-122`; teste BKP-04 (fronteira exata e arquivo fora do padrão) |
| Retenção AWS 30 d | PASS | `backup.tf:54-56`; BKP-05 (mutante `days=31` morto) |
| Rodar 2x não duplica nem apaga o anterior | PASS | marcador OCI `backup-diario.sh:48-52`, marcador S3 `:92-96`; BKP-02 compara hash de todos os objetos, zero expdp/apagar/upload e histórico intacto (`:131`) |
| Sobra de tentativa sem marcador não quebra o dia seguinte | PASS | `backup-diario.sh:54`; BKP-03 |
| Falha em cada etapa -> alerta + código != 0 | PASS | `falhar` `lib.sh:38-48`; `backup-diario.sh:126-128`; BKP-05 (12 pontos de falha), BKP-06/07/08; restauração RST-05 (5 pontos); resumo RES-03; alerta que não sai não esconde a falha (BKP-08); rede de segurança do `OnFailure=` em `alerta.sh:17-20` (ALR-01..04) |
| Segredos fora de argumentos de processo | PASS | token Telegram por stdin do `curl -K -` (`lib.sh:30-34`, BKP-09 compara comando inteiro); senha só em parfile `umask 077` apagado pelo trap (`lib.sh:52-57`, `backup-diario.sh:29`); `sqlplus` lê SQL do stdin (`teste-restauracao.sh:28-34`); `backup.env` lido sem `source` (BKP-12) |
| Backup nunca escreve em BESAVE | PASS | só `expdp schemas=BESAVE` (leitura); `sql/backup-dono.sql` não dá DML a BESAVE_BACKUP; contagem só `SELECT` (RST-01 `nao_contem INSERT/DELETE`) |
| Restauração só em BESAVE_RESTORE e limpa mesmo na falha | PASS | `remap_schema` `teste-restauracao.sh:86`; trap `:43` + `LIMPEZA` `:36-42`; RST-02 (7 divergências), RST-05 e M11/M13 mortos provam limpeza em toda falha |
| Comparação de linhas e inválidos com tolerância | PASS com lacuna | `teste-restauracao.sh:97-111`; RST-02/03/04 fronteira de 5% e mín. 20 (mutante M14 sobrevive, ver abaixo) |
| Teste mensal dia 1 05:00; unidades com `OnFailure=` | PASS | `besave-backup-teste.timer:5`; `.service` `OnFailure=besave-backup-alerta@teste.service` |
| Resumo semanal Telegram | PASS | `resumo-semanal.sh`; RES-01..03 |
| README com restauração de tabela/schema/banco, usuário de backup e IP | PASS (leitura) | `README.md` seções 4, 6a/6b/6c; `sql/backup-dono.sql` |
| Testes comparam comando inteiro (regra 5) | PASS | BKP-01, BKP-09, RST-01 comparam parfile, `expdp`, `impdp`, `oci`, `aws`, `curl`, `sqlplus` inteiros |

## 3. Sensor de discriminação (mutantes)

Bash: cópias em pasta temporária fora do repo a partir de `HEAD` (worktree intocado), cada uma rodando a suíte inteira.
Terraform: mutação em `infra/backup.tf`, restaurada com `git checkout`.

| id | mutação | resultado |
|---|---|---|
| M1 | retenção `-lt` -> `-le` | morto (BKP-04) |
| M7 | corte `RETENCAO_DIAS-1` -> `RETENCAO_DIAS` | morto |
| M3 | marcador sobe junto com o dump na cópia S3 (`--exclude` removido) | morto (BKP-01, comando inteiro) |
| M4 | removido `\|\| return 1` da contagem pós-download | morto (6 falhas) |
| M8 | `\|\| true` no upload do marcador S3 | morto (6 falhas) |
| M9 | removido trap de limpeza do diário | morto |
| M10 | sentido da comparação de inválidos invertido | morto |
| M11 | removido trap de limpeza do teste de restauração | morto (12 falhas) |
| M12 | piso de tolerância invertido | morto |
| M13 | `&&` -> `;` em `etapa_apagar` (desarma limpeza mesmo falhando) | morto |
| M15 | removida marca `alertado-` em `falhar` | morto (12 falhas) |
| M16 | removido apagar de sobra pré-export | morto (12 falhas) |
| T1 | `days=30` -> 31 | morto (terraform test) |
| T2 | Deny sem `DeleteObject` | morto |
| T3 | Allow com `DeleteObject` | morto |
| T4 | Allow `db/*` -> `*` | morto |
| T5 | versionamento/status -> Suspended | morto |
| T6 | `block_public_policy=false` | morto |
| T7 | `s3:prefix` `db/*` -> `*` | morto |
| **M2** | removido `rm -f alertado-$MODO` no início | **SOBREVIVEU** |
| **M5** | `esperados -le 1` -> `-lt 1` | **SOBREVIVEU** |
| **M6** | `n -gt 0` -> `-gt 1` (dump no bucket) | **SOBREVIVEU** |
| **M14** | removido `$4 < 0` (tabela ausente no restore) | **SOBREVIVEU** |
| **M17** | janela do resumo `-6 days` -> `-7 days` | **SOBREVIVEU** |
| M18 | `umask 077` -> 022 | não avaliável no Windows (teste de modo 600 é pulado em MINGW, `teste_backup.sh` caso BKP-01); roda no CI Linux |

Sobreviventes (todos lacunas de teste, nenhum equivalente):
- **M2:** execução morta (kill/timeout) até 10 min depois de uma que já alertou teria o `OnFailure=` suprimido. Faltou caso "marca antiga + nova execução".
- **M5:** export com só o log (1 objeto) passaria na cópia; o guard `esperados <= 1` não tem caso de fronteira.
- **M6:** a fake gera sempre 2 peças; sem caso de dump de peça única o `-gt 1` produziria falso alarme em banco pequeno.
- **M14 (mais relevante):** tabela ausente no restore com origem < 20 linhas passa, pois `d <= tolerância mínima`. Falta caso `LINHAS|PEQUENA|5|-1` esperando falha. Corrigir no teste (o código está certo).
- **M17:** nenhum registro em D-7 na fixture do RES-01.

Recomendação (não bloqueia): adicionar os 4 casos acima antes do merge ou aceitar como pendência registrada.

## 4. Pendências que só a execução real do dono cobre

1. Sintaxe real do Instant Client: `expdp`/`impdp` com `credential=`, `dumpfile=<URI>/…%L.dmp` e `filesize` no Autonomous (parfile e flags são suposição documental; fake não valida). Nome das peças reais (`_aaaaaa`, `%L`) e que `os object list --prefix besave-AAAAMMDD-` as enxerga.
2. `oci --auth instance_principal` na inst2: política IAM/dynamic group do bucket; formato real de `--query 'length(data)' --raw-output` e de `data[].name --output json` com **lista vazia** (o código trata como 0 / vazio, mas isso nunca foi visto na saída real).
3. `ORA-01031` nas rotinas `ADMIN.BACKUP_PREPARA_RESTORE`/`BACKUP_LIMPA_RESTORE` (CREATE/DROP USER por direitos do definidor; ADMIN pode precisar de grant direto, já avisado no `sql/backup-dono.sql`). Conferir `NO AUTHENTICATION` e `DROP USER ... CASCADE` no Autonomous, e cada GRANT (`DATAPUMP_CLOUD_EXP/IMP`, `SELECT ANY TABLE`, `SELECT ANY DICTIONARY`).
4. Credencial padrão do AWS CLI (`AWS_PROFILE=besave-backup` via `EnvironmentFile`), `aws s3 cp --recursive` sob a policy (sem List fora de `db/`) e `Deny` real de apagar.
5. `bulk-download` real: estrutura de pastas gerada em `--download-dir` (o código assume arquivos planos e compara contagem com `find -type f`).
6. Fuso `America/Sao_Paulo` para os `OnCalendar` locais; 03:30 sem conflito de carga no banco; `TimeoutStartSec` 2 h/3 h.
7. Do critério "Real (dono)": export manual + agendado, dump nos dois buckets, teste de restauração manual com contagens batendo, falha forçada gerando alerta, tamanho e tempo registrados no PR, `terraform apply` e chave IAM geradas fora do git.
8. O arquivo de testes leva ~3 min no Git Bash; no Linux deve ser bem menor.
