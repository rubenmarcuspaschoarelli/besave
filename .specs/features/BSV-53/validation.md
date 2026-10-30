# BSV-53 — validation

**Veredito: PASS** (com ressalvas; a migração real é do dono e bloqueia o merge)
**Verificador:** sub-agente independente (autor ≠ verificador), Terraform 1.16.2 local (o CI fixa 1.16.4), commit 4a2cf3c.

## Critérios e saídas

| # | Critério / saída | Evidência | Resultado |
|---|---|---|---|
| S1 | Bucket de bootstrap em `infra/estado/` com BPA | `infra/estado/bucket.tf:11-16`; teste `infra/estado/tests/estado.tftest.hcl:28-34` | PASS |
| S1 | SSE-S3 | `bucket.tf:22`; teste `estado.tftest.hcl:23-26` | PASS |
| S1 | Versionamento | `bucket.tf:30`; teste `estado.tftest.hcl:17` | PASS |
| S1 | `prevent_destroy` (conferido lendo o código) | `bucket.tf:6` | PASS |
| S1 | Policy nega sem TLS | `bucket.tf:58-67`; teste `estado.tftest.hcl:36-49` | PASS |
| S1 | Lifecycle 90 dias / 30 versões / multipart 7 dias | `bucket.tf:45,46,50`; teste `estado.tftest.hcl:51-69` | PASS |
| S2 | Backend S3 com `use_lockfile`, sem DynamoDB | `infra/main.tf:5-11` | PASS |
| S2 | `required_version` sobe para a primeira versão com `use_lockfile` estável (1.11) | `infra/main.tf:2`; `infra/estado/main.tf` (`>= 1.11`) | PASS |
| S3 | CI sem credencial; `init -backend=false`, `validate`, `test`, `fmt -check` também em `infra/estado/` | `.github/workflows/ci.yml` (job `infra`, passo "infra/estado"); gates rodados abaixo | PASS |
| S4 | Teste lê o documento das 5 policies (worker, backup, site_deploy, vigia, vigia_agenda): sem ARN do state e sem `s3:*`/`*` em Resource `*` | `infra/tests/estado_acesso.tftest.hcl:22-47`; 15 mutantes mortos | PASS |
| S5 | `.gitignore`: `infra/**/*.plan` e state local de `estado/` | `.gitignore:33,35`; `git check-ignore` confirma `infra/backup.plan`, `infra/x/y.plan`, `infra/estado/terraform.tfstate(.backup)` | PASS |
| S6 | README: roteiro 1–6, recuperar versão, `force-unlock`, state local de `estado/` e reimport | `infra/README.md:42-78` | PASS |
| Regra 1 | Nenhum recurso existente muda | O diff toca só `main.tf` (backend e `required_version`), testes, `ci.yml`, `.gitignore`, README e `infra/estado/` | PASS (por leitura do diff) |
| Aceite | CI verde nas duas raízes (lição 12) | Gates locais verdes. **Não conferi `gh run` da PR**: a PR ainda não existia. Confira a aba Checks. | PENDENTE (CI) |
| Aceite | Migração real, "No changes" e erro de lock | Depende do dono | PENDENTE (dono) |

## Gates rodados (lição 21)

| Gate | Resultado |
|---|---|
| `infra/`: `terraform fmt -check -recursive` | ok |
| `infra/`: `init -backend=false`, `validate` | ok |
| `infra/`: `terraform test` | 20 passed, 0 failed |
| `infra/estado/`: `fmt -check -recursive`, `init -backend=false`, `validate` | ok |
| `infra/estado/`: `terraform test` | 1 passed, 0 failed |
| `shellcheck` | **não rodou** (não instalado no Windows) |
| `bash backup/teste_backup.sh` | **não rodou** |
| `python -m unittest discover -s lambdas/vigia` | **não rodou** |
| `npm test` das Functions | **não rodou** |

Esses quatro gates não têm relação com a mudança do BSV-53. Dependem do CI.

## Sensor de discriminação (mutantes)

Todos aplicados e revertidos (`git status` limpo ao fim).

`infra/estado/`:

| Mutante | Resultado |
|---|---|
| versionamento `Suspended` | morto |
| versionamento removido | morto (erro de referência) |
| SSE `aws:kms` | morto |
| SSE removido | morto (erro de referência) |
| `block_public_acls=false` | morto |
| `block_public_policy=false` | morto |
| `ignore_public_acls=false` | morto |
| `restrict_public_buckets=false` | morto |
| `Deny` → `Allow` | morto |
| `aws:SecureTransport` = `"true"` | morto |
| `noncurrent_days` 91 | morto |
| `newer_noncurrent_versions` 29 | morto |
| multipart 8 dias | morto |
| regra de lifecycle `Disabled` | morto |
| default de `bucket_estado` ≠ `besave-tfstate` | **SOBREVIVEU** |
| `prevent_destroy=false` | sobreviveu, por desenho (a spec manda conferir lendo o código) |

`infra/` (as 5 policies × 3 mutantes: ARN `arn:aws:s3:::besave-tfstate/*`, `s3:*` em Resource `"*"`, `["*"]` em `["*"]`): **15/15 mortos pelo `estado_acesso.tftest.hcl`**. Medi o `estado_acesso` separado do `iam.tftest.hcl`, que também falha com statement extra.

## Sobreviventes e observações

1. **Sobrevivente:** o default de `variables.tf` (`bucket_estado`) não é testado, porque o teste da raiz `estado/` define a variável explicitamente. O nome literal do backend (`infra/main.tf:6`) poderia divergir do default sem nenhum teste falhar. Risco baixo. Sugestão: apagar `bucket_estado` do bloco `variables` do teste, ou afirmar o default.
2. O `terraform test` local (1.16.2) dá `panic: value has marks` ao renderizar uma asserção que falhou. O exit code continua não-zero, então a falha é detectada. É o mesmo tipo de bug citado no `ci.yml` para a 1.16.4.
3. O `terraform fmt -check` em `estado/` no CI não usa `-recursive`. Não há subpastas com `.tf`, então tanto faz.
4. O `prevent_destroy` não tem teste automatizado, como a spec determina.

## Pendente do dono (bloqueia o merge)

Roteiro do README, passos 1–6, com conta e ARNs trocados por `REDACTED` na PR (regra 11):
- `apply` em `infra/estado/`;
- `init -migrate-state` em `infra/`;
- `plan` com **"No changes"**;
- teste do lock com `Error acquiring the state lock`.

Também falta conferir o CI da PR (aba Checks, lição 12).
