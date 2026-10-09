# BSV-18 validation

Verificador: sub-agente independente (autor != verificador). Commit verificado: 9510f2a.

Veredito geral: **PASS**

| # | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 1 | actionlint limpo nos dois workflows | PASS | `actionlint .github/workflows/*.yml` -> rc=0, sem saida. shellcheck NAO instalado localmente: checagem dos blocos `run` nao coberta aqui (roda no CI, ubuntu-latest). |
| 2 | Actions na maior release estavel | PASS | `gh api .../releases/latest`: checkout v7.0.1 (usa @v7), setup-node v7.1.0 (@v7), setup-python v7.0.0 (@v7), pnpm/action-setup v6.1.0 (@v6), configure-aws-credentials v6.3.0 (@v6), paths-filter v4.0.3 (@v4), setup-terraform v4.0.1 (@v4). `dtolnay/rust-toolchain@stable` mantido; `Swatinem/rust-cache@v2` intocado (latest v2.9.2, mesma major). |
| 3 | Sem mudanca de comportamento no deploy | PASS | `git diff HEAD~1 -- .github`: site-deploy.yml so troca 4 versoes (checkout, pnpm, setup-node, configure-aws); role (`vars.AWS_ROLE_SITE`), session-name, passos e gatilhos inalterados. ci.yml: so versoes, filtro e job novos. |
| 4 | Job `workflows` + filtro | PASS | ci.yml:22 output `workflows`; ci.yml:34 `workflows: ['.github/**']`; job ci.yml:36-46 (`needs: changes`, `if outputs.workflows == 'true'`); actionlint fixado v1.7.12 (script e versao, ci.yml:45). |
| 5 | terraform test sem tfvars | PASS | `Success! 17 passed, 0 failed.` |
| 6 | terraform test com tfvars (`ativar_dominios = true`, `ativar_curto = true`) | PASS | `Success! 17 passed, 0 failed.` Arquivo removido ao fim. |
| 7 | Nenhum infra/*.tf alterado | PASS | `git diff HEAD~1 --stat -- '*.tf'` vazio; so infra/tests/*.tftest.hcl. |
| 8 | Sensor: mutante 1 (remove `variables` de curto e dominios, com tfvars) | PASS (detectado) | `curto_fase_1... fail`, Test assertion failed. |
| 9 | Sensor: mutante 2 (`ativar_dominios = true` no topo de cloudfront.tftest.hcl, sem tfvars) | PASS (detectado) | `distribuicao_padrao... fail`; `Failure! 16 passed, 1 failed.` Testes restaurados com `git checkout -- infra/tests`. |
| 10 | .gitignore | PASS | `git check-ignore package.json pnpm-lock.yaml` -> ambos ignorados (rc=0); `apps/site/package.json packages/contract/package.json` -> nao ignorados (rc=1). Regras `/package.json` e `/pnpm-lock.yaml` com comentario. |
| 11 | Regra 11 | PASS | grep no diff do commit por `C:\Users`, token, secret, AKIA, 12 digitos: nada. |

## Pendente (nao verificavel aqui)
- CI da PR: jobs `changes`, `workflows`, `infra` devem rodar de fato (licao 12).
- Real (dono): `gh workflow run site-deploy.yml --ref main` apos merge.
- Tabela "versao antiga/nova/link das notas/ajuste" e responsabilidade do corpo da PR; as notas de cada salto major nao foram relidas por este Verifier.
