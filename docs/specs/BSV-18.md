# BSV-18 · Infra e CI: manutenção (versões das actions, testes sem tfvars, actionlint)

**Papel:** DevOps · **Pasta:** `.github/workflows/` + `infra/tests/` + `.gitignore` da raiz ·
**Depende de:** BSV-17 (mergeado). Roda em paralelo com a BSV-33 (que não toca nessas pastas).
AD-060, AD-071, AD-078, AD-084, AD-085; WORKFLOW-AGENTES lições 12 e 14

## Contexto
Três pendências pequenas, anotadas ao longo da BSV-17, da BSV-30 e da virada:
1. Os workflows usam versões maiores antigas das actions (`actions/checkout@v4`, `actions/setup-node@v4`,
   `pnpm/action-setup@v4`, `aws-actions/configure-aws-credentials@v4`, `dorny/paths-filter@v3`,
   `hashicorp/setup-terraform@v3`, `actions/setup-python@v5`); o agente da BSV-17 apontou que já há versões
   maiores. Não há verificação automática de sintaxe dos workflows: o `ci.yml` ficou inválido de 25/09 a 03/10
   sem ninguém ver (lição 12).
2. `terraform test` lê o `infra/terraform.tfvars` local do dono (`ativar_dominios`, `ativar_curto` = true) e
   4 testes falham na máquina dele, embora passem no CI e numa cópia limpa.
3. Um `package.json` e um `pnpm-lock.yaml` vazios aparecem na raiz dos worktrees (ferramenta externa); nunca
   devem entrar em commit.

## Objetivo
CI com actions atualizadas e verificação de sintaxe dos workflows; testes do Terraform com o mesmo resultado
na máquina do dono e no CI; arquivos soltos da raiz ignorados pelo git.

## Entregáveis
1. **Versões das actions:** em `ci.yml` e `site-deploy.yml`, cada action na maior versão estável atual,
   **conferida na página oficial de releases de cada uma** (não presumir números). Para cada salto de versão
   maior, ler as notas de mudança e ajustar entradas renomeadas ou removidas. `dtolnay/rust-toolchain@stable`
   fica como está.
2. **actionlint no CI:** job `workflows` que roda o `actionlint` (com `shellcheck`) quando `.github/**` muda
   (novo filtro em `changes`). Instalação fixada por versão.
3. **Testes do Terraform independentes do tfvars local:** cada `infra/tests/*.tftest.hcl` declara no topo um
   bloco `variables` com os valores padrão que ele assume (`ativar_dominios = false`, `ativar_curto = false`,
   etc.), e os `run` que testam a virada continuam sobrescrevendo. Conferir na documentação do Terraform a
   precedência entre `variables` do arquivo de teste e `terraform.tfvars`.
4. **`.gitignore` da raiz:** `/package.json` e `/pnpm-lock.yaml` (só na raiz; `apps/site` e `packages/contract`
   continuam versionados), com comentário do motivo.

## Regras
- Nenhuma mudança de comportamento no deploy: mesmos passos, mesmo papel, mesmos prefixos, mesmos gatilhos.
- Nenhuma mudança em `infra/*.tf` (recursos); só testes.
- O deploy do site não é executado neste ticket; a prova é o CI e o `actionlint`.

## Fora de escopo
Cache curto do `besave.css` (AD-087), desligar o protótipo (roteiro manual do dono), preview por PR.

## Critério de aceite
- `actionlint` limpo nos dois workflows, local e no novo job do CI.
- PR mostra a tabela "action · versão antiga · versão nova · link das notas · ajuste feito".
- Na pasta `infra/` **com** um `terraform.tfvars` contendo `ativar_dominios = true` e `ativar_curto = true`:
  `terraform test` → todos passam (hoje 4 falham). Sem o arquivo → todos passam.
- `git check-ignore package.json pnpm-lock.yaml` na raiz → ignorados; `git check-ignore apps/site/package.json`
  → não ignorado.
- CI da PR: jobs `changes`, `workflows` e `infra` rodaram de fato (lição 12).
- **Real (dono):** depois do merge em `main`, rodar `gh workflow run site-deploy.yml --ref main` uma vez e
  conferir `completed success` (ensaio + publicação com as actions novas).

## Definition of done
PR com a tabela de versões, saída do `actionlint` e do `terraform test` com tfvars, `validation.md` do Verifier
independente, CI verde.
