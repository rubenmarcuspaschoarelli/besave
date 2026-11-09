# BSV-53 · Infra: state do Terraform no S3, com versionamento e lock

**Papel:** IaC (Terraform) · **Pasta:** `infra/` (+ `.gitignore`) ·
**Depende de:** nada. AD-030, AD-055; lições 11, 16 e 21

## Contexto
O state do Terraform é **local**. Ele vive em `infra/terraform.tfstate`, no PC do dono (fora do git, serial 88).
Ele controla tudo o que está no ar:
- as duas distribuições CloudFront, as Functions e a KVS dos redirects;
- os buckets `besave-site`, `besave-logs` e `besave-backup`;
- os usuários IAM do worker e do backup, o papel do deploy do site (OIDC) e o vigia;
- os certificados e o Route53.

O `infra/README.md` já chama isso de risco ("sem ele o Terraform perde o controle dos recursos. Backend
S3 é ticket futuro"). Os problemas concretos:
- **Perda:** se o disco do PC falhar ou o arquivo for apagado, perde-se o mapa dos ~50 recursos. A volta
  seria `terraform import` recurso por recurso, com risco de o `plan` querer recriar CDN ou bucket.
- **Sem histórico:** o `.backup` guarda só a versão anterior. Um `apply` errado não tem como voltar.
- **Sem lock:** duas execuções ao mesmo tempo corrompem o state. Hoje só o dono aplica, mas agentes
  rodam `plan` e `test` no mesmo checkout.
- **Planos soltos:** `infra/backup.plan` e `infra/backup2.plan` (de 23/10) estão fora do `.gitignore`, que
  só cobre `*.tfplan`. Um arquivo de plano pode conter valores sensíveis, e o repositório é público.

## Objetivo
O state passa a ficar num bucket S3 privado, versionado e criptografado, com lock nativo do S3. O PC
deixa de ser ponto único de falha.

## Saídas
1. **Raiz de bootstrap `infra/estado/`** (state local próprio, mudança rara). Ela cria só o bucket do
   state (ex.: `besave-tfstate`, nome por variável) com:
   - bloqueio de acesso público;
   - SSE-S3;
   - versionamento;
   - `prevent_destroy`;
   - policy negando acesso sem TLS (`aws:SecureTransport = false`);
   - lifecycle: versões não correntes expiram em 90 dias, mantendo sempre as 30 mais novas; multipart
     incompleto é abortado em 7 dias.

   Uma raiz separada evita o problema do ovo e da galinha: o backend não pode apontar para um bucket que
   o próprio state ainda vai criar.
2. **Backend S3 na raiz `infra/`:**
   ```hcl
   backend "s3" {
     bucket       = "besave-tfstate"
     key          = "infra/terraform.tfstate"
     region       = "us-east-1"
     encrypt      = true
     use_lockfile = true
   }
   ```
   - O lock é o nativo do S3 (`use_lockfile`), **sem DynamoDB**.
   - `required_version` sobe para a primeira versão em que `use_lockfile` é estável. O agente verifica
     qual é, pela regra 8.
   - O bloco não aceita variáveis: o nome fica literal, igual ao da raiz `estado/`.
3. **CI continua sem credencial AWS.** O job `infra` roda `init -backend=false`, `validate`, `test` e
   `fmt -check -recursive` também em `infra/estado/`. Teste novo (`tests/` da raiz `estado/`, com mocks)
   cobre a configuração do bucket.
4. **Nenhum usuário ou papel de serviço acessa o bucket do state.** Isso vale para o worker, o backup,
   `site_deploy` e o vigia: só a identidade de administrador do dono (nunca a conta root) aplica. Um
   teste prova que as policies desses quatro não citam o ARN do bucket nem usam `s3:*` com recurso `*`.
   A verificação lê o documento da policy, não depende de mock com o mesmo valor (lição 11).
5. **`.gitignore`:** acrescentar `infra/**/*.plan` e o state local de `infra/estado/`.
6. **`infra/README.md`:** a seção "State local" vira o roteiro da migração (abaixo) e explica:
   - como recuperar uma versão anterior do state (versão do objeto no S3);
   - como liberar um lock preso (`terraform force-unlock`, só com certeza de que ninguém está aplicando);
   - que o state de `infra/estado/` fica local, com backup, e como reimportar o bucket se ele se perder.

## Roteiro da migração (dono, documentado no README)
1. Copiar `infra/terraform.tfstate*` para uma pasta fora do repositório.
2. Em `infra/estado/`: `terraform init`, `terraform plan -out p` (só o bucket e as configurações dele) e
   `terraform apply p`.
3. Em `infra/`: `terraform init -migrate-state` e responder `yes`.
4. `terraform plan` em `infra/` → **"No changes"**. Esse é o gate: qualquer diferença para tudo, e o
   state local copiado no passo 1 continua valendo.
5. **Teste do lock:**
   - no terminal A, `terraform apply` sem arquivo de plano, parado na confirmação;
   - no terminal B, `terraform plan` → deve falhar com `Error acquiring the state lock`;
   - responder `no` no terminal A.
6. Tirar `terraform.tfstate*` de `infra/`, movendo para a pasta do passo 1 (sem apagar), e guardar por 30
   dias. Apagar os `infra/*.plan` antigos depois de conferir que são planos de 23/10.

## Regras
1. **Nenhum recurso existente muda** (`plan` da raiz `infra/` igual antes e depois). A PR não mistura
   mudança de recurso com a migração.
2. O state nunca vai para o git, e nenhum segredo entra nele: os parâmetros do Telegram continuam no SSM.
3. Sem DynamoDB e sem serviço novo pago. O custo esperado é de centavos por mês.
4. `infra/estado/` não tem `destroy` no roteiro. O `prevent_destroy` barra de propósito.

## Fora de escopo
- Mover os recursos para módulos.
- Workspaces.
- Executar o `apply` pelo CI (OIDC com permissão de escrita).
- Migrar o state de `infra/estado/` para dentro do próprio bucket.

## Critério de aceite
- `terraform test` da raiz `estado/` prova:
  - versionamento ligado;
  - SSE;
  - os quatro bloqueios de acesso público;
  - negação sem TLS;
  - as duas regras de lifecycle (90 dias / 30 versões; multipart em 7 dias).

  O `prevent_destroy` é conferido lendo o código.
- O teste das policies (Saída 4) falha se alguma das quatro ganhar acesso ao bucket do state. O Verifier
  injeta esse mutante.
- O job `infra` do CI está verde e roda nas duas raízes. Conferir que ele rodou de fato (lição 12) e
  rodar todos os gates do job (lição 21).
- **Real (dono):** os passos 1 a 6 do roteiro, com `plan` "No changes" depois da migração e o erro de
  lock no teste do passo 5. A PR registra as duas saídas, com conta e ARNs trocados por `REDACTED`
  (regra 11).

## Definition of done
PR com:
- as duas raízes validadas no CI;
- o README com o roteiro;
- `validation.md` do Verifier independente, com sensor de discriminação;
- a migração real feita pelo dono antes do merge.
