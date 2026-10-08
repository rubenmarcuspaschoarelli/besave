# infra — stack nova do site (BSV-4)

Terraform que cria, ao lado do protótipo (AD-016), a infra do site novo:

| recurso | nome | arquivo |
|---|---|---|
| bucket de origem, privado, Block Public Access total, **sem** lifecycle de expiração (só o worker remove órfãos, BSV-11) | `besave-site` | `s3.tf` |
| bucket de logs padrão do CloudFront (prefixo `cf/`) | `besave-logs` | `s3.tf` |
| certificado ACM `besave.com.br` + `www` com validação DNS no Route53 | — | `acm.tf` |
| distribuição CloudFront com OAC, 6 behaviors de `docs/MANIFEST.md` §5, 403/404 → 404 `/404.html` | — | `cloudfront.tf` |
| KeyValueStore de redirects + Functions `rewrite-index` e `redirect-afiliado` | `besave-redirects` | `cloudfront.tf`, `functions/*.js` |
| usuário IAM do worker, sem console e sem access key | `besave-worker` | `iam.tf` |
| vigia externo: Lambda Python a cada 10 min (Scheduler), avisa no Telegram (BSV-15) | `besave-vigia` | `vigia.tf`, `lambdas/vigia/` |
| A/AAAA de `besave.com.br` e `www` na distribuição nova (com `ativar_dominios`, BSV-16) | — | `dominios.tf` |
| zonas `besave.io`/`besave.me`; com `ativar_curto`: certificado, Function `link-curto`, distribuição e A/AAAA (BSV-16) | `besave-curto` | `curto.tf`, `functions/link-curto.js` |
| provedor OIDC do GitHub e papel do deploy do site, restrito aos prefixos do site (BSV-17) | `besave-site-deploy` | `site_deploy.tf`, `deploy-site/` |

Não gerencia o bucket `besave.com.br` nem a distribuição atual do protótipo: o `plan` não mostra nenhum dos dois.

## Pré-requisitos

- Terraform ≥ 1.7, Node 22 (testes das Functions) e Python ≥ 3.12 (testes do vigia).
- Credenciais AWS de administrador no shell (`AWS_PROFILE` ou variáveis de ambiente), nunca em arquivo do repo.
- Zona Route53 `besave.com.br` existente na mesma conta.

## Aplicar

```sh
cd infra
terraform init
terraform plan -out plano.tfplan   # conferir: só recursos novos, 0 to change, 0 to destroy
terraform apply plano.tfplan
terraform output
```

Variáveis (`variables.tf`), todas com padrão: `regiao`, `dominio`, `bucket_site`, `bucket_logs`,
`ativar_dominios` (`false`), `classe_preco` (`PriceClass_All`: 100/200 não cobrem a América do Sul),
`dominios_curtos` (`["besave.io", "besave.me"]`), `ativar_curto` (`false`).
Nome de bucket é global: se `besave-site` ou `besave-logs` estiver tomado, passe `-var bucket_site=...`.

**State local.** `terraform.tfstate` fica em `infra/` e está no `.gitignore`. Faça backup fora do
git: sem ele o Terraform perde o controle dos recursos. Backend S3 é ticket futuro.

## Depois do apply

1. **Access key do worker**: IAM → Users → `besave-worker` → Security credentials → Create access key.
   Guarde fora do git (gerenciador de senhas / `.env` local). O Terraform nunca cria essa chave.
   O worker (BSV-12) recebe `BESAVE_BUCKET` = output `bucket_site` e `BESAVE_KVS_ARN` = output `arn_kvs`.
2. **Páginas provisórias** `index.html` e `404.html`: ver [Páginas provisórias](#páginas-provisórias)
   (o deploy do site deve **sempre** publicar `/404.html`; até lá, as provisórias).

3. **Conferir** (`CF=$(terraform output -raw dominio_distribuicao)`):

   ```sh
   curl -I https://$CF/manifest.json                # 404 (ou 403) vindo do S3 via OAC, não erro de DNS/TLS
   curl -I https://$CF/ir/999                       # 302, location: /, cache-control: no-store
   curl -I https://$CF/nao-existe                   # 404, content-type: text/html (/404.html)
   curl -I https://$CF/data/chunks/0-ffff.json.br   # 404, nunca 200

   echo '<h1>teste besave</h1>' > /tmp/index.html
   aws s3 cp /tmp/index.html s3://besave-site/index.html --content-type "text/html; charset=utf-8"
   curl -s https://$CF/                             # <h1>teste besave</h1>
   aws s3 rm s3://besave-site/index.html
   ```

   Respostas de erro ficam 60 s em cache: depois de publicar `/404.html`, espere 1 minuto antes de repetir.

## Testes (sem conta AWS)

```sh
terraform fmt -check -recursive
terraform init -backend=false && terraform validate
terraform test                       # tests/*.tftest.hcl com mock_provider: nada é criado
python -m unittest discover -s lambdas/vigia   # vigia: dublês de S3/HTTP/SSM/Telegram, sem rede
cd functions && npm ci && npm test   # Functions, 404.html, sem recursos do protótipo, deploy do site (BSV-17)
```

**Obrigatório** após qualquer mudança em `functions/*.js`, **antes do `apply`**: rodar `test-function` no
runtime real (AD-030). O cloudfront-js-2.0 é um subconjunto do JS (ex.: `await` como argumento de função é
erro de sintaxe) e os testes Node acima não o emulam — passam com código que o CloudFront recusa. Como as
Functions têm `publish = true`, o `apply` põe o código no ar na hora, em todas as rotas que o usam
(`rewrite-index` está em todo HTML). Por isso o teste roda numa Function temporária, criada pela CLI com o
código novo, e apagada em seguida:

```sh
# testar_function <arquivo .js> <evento .json>...   (rodar em infra/)
testar_function() {
  nome="tmp-$(basename "$1" .js)-$(date +%s)"; arq=$1; shift
  etag=$(aws cloudfront create-function --name "$nome" \
    --function-config '{"Comment":"teste temporario","Runtime":"cloudfront-js-2.0"}' \
    --function-code "fileb://$arq" --query ETag --output text) || return 1
  for ev in "$@"; do
    echo "== $ev"
    aws cloudfront test-function --name "$nome" --if-match "$etag" --stage DEVELOPMENT \
      --event-object "fileb://$ev" --query 'TestResult.[FunctionErrorMessage,FunctionOutput]' --output text
  done
  aws cloudfront delete-function --name "$nome" --if-match "$etag"
}

testar_function functions/rewrite-index.js functions/eventos/rewrite-index-www.json functions/eventos/rewrite-index.json
#   www  → 301, location https://besave.com.br/oferta/1/?a=1
#   apex → request com uri /oferta/1/index.html
testar_function functions/link-curto.js functions/eventos/link-curto.json
#   → 301, location https://besave.com.br/oferta/5412/?utm_source=telegram, cache-control public, max-age=86400
```

A primeira coluna da saída (`FunctionErrorMessage`) tem de vir vazia. `redirect-afiliado` usa KVS e não
cabe nesse atalho: para ela, `test-function --stage DEVELOPMENT` na própria Function antes de publicar.
O evento do `test-function` é sintético: ele prova sintaxe e lógica no runtime, não como o CloudFront
monta o objeto `querystring` de uma requisição real (isso só o `curl` do roteiro prova).

## Vigia externo (BSV-15)

A Lambda `besave-vigia` roda a cada 10 min (EventBridge Scheduler) e faz duas checagens:
- **frescor**: `LastModified` de `s3://besave-site/manifest.json` com mais de 30 min (`LIMIAR_MIN`) é problema;
- **disponibilidade**: `GET https://<dominio_distribuicao>/manifest.json`, com timeout de 10 s, precisa devolver 200 e um JSON com `versao`.

Os avisos vão para o Telegram:
- ⚠️ na passagem de ok para problema;
- ⏰ a cada 3 h enquanto o problema durar;
- ✅ na volta ("site atualizado de novo (parado por 1h40)").

O estado do vigia fica em `s3://besave-site/_estado/vigia.json` e só é gravado quando algum aviso sai.
Se a leitura do estado falhar, o vigia segue "sem estado", ou seja, como `ok`. Quando o arquivo ainda não existe (`NoSuchKey`) isso vai para o log como INFO; qualquer outro código, inclusive `AccessDenied`, vai como ERROR. Para o S3 responder `NoSuchKey` em vez de `AccessDenied` quando o arquivo não existe, a policy tem `s3:ListBucket` restrito a `s3:prefix = "_estado/vigia.json"`.
Se o Telegram falhar, o estado não avança e a próxima execução tenta de novo. Por isso o Scheduler e a
invocação assíncrona têm 0 retentativas: repetir um aviso já enviado duplicaria a mensagem.

O código é um arquivo só (`lambdas/vigia/handler.py`). Usa a stdlib e o `boto3` que já vem no runtime
`python3.12`, e o `archive_file` zipa esse arquivo em `.build/` (ignorado pelo git).

### 1. Parâmetros do Telegram (antes do `plan`)

O dono cria os parâmetros. O Terraform só monta o ARN a partir do nome e nunca lê o valor, então o
segredo não entra no state. Use o mesmo bot e chat da BSV-14.

```sh
read -rs TOKEN && aws ssm put-parameter --name /besave/telegram/token   --type SecureString --value "$TOKEN"
read -rs CHAT  && aws ssm put-parameter --name /besave/telegram/chat_id --type SecureString --value "$CHAT"
unset TOKEN CHAT
```

O `read -s` não deixa o valor no histórico do shell. O primeiro SecureString cria a chave KMS gerenciada
`alias/aws/ssm`, que o `plan` lê (`data.aws_kms_alias`). Sem os parâmetros, o `plan` falha nesse data source.

### 2. Aplicar

O `plan` mostra 8 recursos a adicionar (`0 to change, 0 to destroy`):
- Lambda e grupo de log com retenção de 14 dias;
- 2 roles e 2 policies;
- invoke config;
- agenda.

### 3. Testar

```sh
aws lambda invoke --function-name besave-vigia --cli-binary-format raw-in-base64-out --payload '{}' saida.json
cat saida.json                                    # {"resultado": "sem_aviso"} com o worker rodando
aws logs tail /aws/lambda/besave-vigia --since 1h
```

Valores possíveis de `resultado`:
- `sem_aviso`: nada a avisar;
- `avisado`: mensagem enviada e estado gravado;
- `falha_envio`: o Telegram ou o SSM falhou, o estado ficou como estava e a próxima execução tenta de novo.
- `falha_estado`: a mensagem saiu, mas a gravação do estado falhou, e o próximo ciclo repete o aviso.

Teste real: desative a tarefa do worker (BSV-14) por 40 min e um ⚠️ chega em até 10 min depois dos 30 min
sem atualização. Reative e o ✅ chega no ciclo seguinte à próxima publicação.

### Custo

Cerca de US$ 0,01/mês, dentro do free tier:
- 4.320 invocações/mês de ~1 s com 128 MB (≈ 540 GB-s), contra 1 M de requisições e 400 mil GB-s grátis
  na Lambda;
- Scheduler e SSM standard sem custo nesse volume;
- 8.640 GET/HEAD no S3 (≈ US$ 0,004);
- 4.320 requisições no CloudFront;
- poucos KB de log.

## Virada de DNS e domínios curtos (BSV-16)

CloudFront recusa o mesmo CNAME em duas distribuições (`CNAMEAlreadyExists`, AD-021), por isso a
distribuição nova nasceu sem aliases. Duas variáveis controlam a virada:

- `ativar_dominios`: aliases `besave.com.br`/`www` + certificado na distribuição nova, registros A/AAAA
  alias para ela (`allow_overwrite`: os atuais foram criados no console e apontam para o protótipo) e
  vigia lendo `https://besave.com.br/manifest.json` (testa também DNS e certificado).
- `ativar_curto`: fase 2 dos domínios curtos. As zonas `besave.io` e `besave.me` existem sempre (fase 1).

**As variáveis precisam valer em todo `apply` seguinte.** Sem elas, voltam para `false` e o `plan` tenta
desfazer a virada; o `prevent_destroy` dos registros e do certificado curto o faz falhar, mas qualquer
`apply` fica bloqueado até elas voltarem. Grave-as em `infra/terraform.tfvars` (ignorado pelo git), não só
em `-var`:

```hcl
ativar_dominios = true
ativar_curto    = true
```

`www.besave.com.br` responde 301 para `https://besave.com.br{caminho}{?query}` (Function `rewrite-index`).
`besave.io` e `besave.me` (com e sem `www`) respondem sempre pela Function `link-curto`, sem estado:

| entrada | 301 para |
|---|---|
| `/5412`, `/5412/`, `/05412` | `https://besave.com.br/oferta/5412/` |
| `/5412/ir` | `https://besave.com.br/ir/5412` |
| `/`, `/abc`, `/0`, 13+ dígitos, qualquer outro | `https://besave.com.br/` |

A query de entrada é preservada (`/5412?utm_source=telegram` → `/oferta/5412/?utm_source=telegram`) e
toda resposta leva `Cache-Control: public, max-age=86400`. A origem da `besave-curto` (`besave.com.br`)
nunca é alcançada. Logs em `besave-logs/curto/`. O behavior aceita HTTP (`allow-all`): link colado sem
esquema vira `http://` e a Function já manda para `https://`, sem um salto extra.

### Roteiro (dono)

0. **Functions no runtime real, antes de qualquer `apply`.** `testar_function` (seção
   [Testes](#testes-sem-conta-aws)) com `rewrite-index.js` e `link-curto.js` e os eventos de
   `functions/eventos/`. O `apply` do passo 1 já publica o `rewrite-index` novo em todas as rotas HTML.
1. **Zonas curtas e páginas provisórias.** `terraform plan -out plano.tfplan` com as duas variáveis em
   `false`. O plano esperado tem 2 adições (as zonas) e 1 alteração in-place (`rewrite-index`, com a regra
   do `www`, inofensiva antes da virada); `0 to destroy`. `apply`, depois `terraform output ns_curtos` e
   configurar os 4 NS de cada zona no registrador de `.io` e `.me`. Upload de `index.html` e `404.html`
   (seção [Páginas provisórias](#páginas-provisórias)), para a virada já encontrá-las.
2. **Virada.** No console, remover `besave.com.br` e `www.besave.com.br` dos aliases da distribuição do
   protótipo e salvar. **Logo em seguida**, `ativar_dominios = true` no `terraform.tfvars` e `apply`. O site
   fica fora do ar nos minutos entre os dois passos (protótipo; aceito).
3. **Indexação.** No `.env` do worker, `BESAVE_INDEXAVEL=true`. O próximo ciclo grava o `robots.txt` com
   `Allow` + `Sitemap`.
4. **Domínios curtos.** Quando o NS propagar (`nslookup -type=NS besave.io` e `besave.me` devolvem os NS da
   AWS), `ativar_curto = true` e `apply`. A validação do certificado espera o DNS; leva alguns minutos.
5. PR `develop → main` (AD-060).

### Conferir

```sh
ID=<id de uma oferta ativa>
curl -I https://besave.com.br/oferta/$ID/          # 200
curl -I https://www.besave.com.br/oferta/$ID/      # 301, location: https://besave.com.br/oferta/$ID/
curl -I https://besave.io/$ID                      # 301, location: https://besave.com.br/oferta/$ID/
curl -I https://besave.me/$ID                      # 301, idem
curl -I "https://besave.io/$ID?utm_source=telegram" # 301, query preservada
curl -I "https://besave.io/$ID?utm_campaign=a%20b%26c"
#   location: https://besave.com.br/oferta/$ID/?utm_campaign=a%20b%26c   (%20 e %26 intactos)
curl -I "https://www.besave.com.br/oferta/$ID/?utm_campaign=a%20b%26c"
#   location: https://besave.com.br/oferta/$ID/?utm_campaign=a%20b%26c   (%20 e %26 intactos)
curl -s https://besave.com.br/robots.txt           # Allow + Sitemap
curl -s https://besave.com.br/                     # página provisória
curl -I https://besave.com.br/nao-existe           # 404 com a 404 provisória
aws lambda invoke --function-name besave-vigia --cli-binary-format raw-in-base64-out --payload '{}' saida.json && cat saida.json
```

Os dois `curl` com `%20`/`%26` são a única prova de como o CloudFront entrega a query às Functions: a
documentação não diz se o valor chega codificado, e o evento do `test-function` é sintético. As Functions
repassam o valor como recebido. Se o `location` vier com espaço ou `&` cru (ex.: `utm_campaign=a b&c`), o
valor chega decodificado e as duas Functions precisam de `encodeURIComponent` antes do merge.

Por último, colar `besave.io/<id>` num chat do Telegram: a prévia precisa mostrar a oferta (confirma
que o robô do Telegram segue os 301).

### Páginas provisórias

`static/index.html` (nome, "site em construção", link do canal) e `static/404.html` ("Oferta encerrada ou
não encontrada", link para o início e para o canal, `noindex`). O canal é o público da marca,
`https://t.me/besaveofertas`; o repositório é público e não leva conta, telefone ou contato pessoal.
O Terraform não gerencia esses objetos; o deploy do site (BSV-30) os substitui.

```sh
for f in index.html 404.html; do
  aws s3 cp static/$f s3://besave-site/$f --content-type "text/html; charset=utf-8" --cache-control "public, max-age=300"
done
```

### Custos

- Zonas `besave.io` e `besave.me`: US$ 0,50/mês cada (+US$ 1,00/mês). Consultas a registros alias para
  CloudFront não são cobradas.
- Functions: 2 milhões de execuções/mês gratuitas, depois US$ 0,10 por milhão (AWS Pricing API, 02/10/2026).
- Certificado ACM público e distribuição `besave-curto`: sem custo fixo; a distribuição só cobra
  requisições (respostas da Function não vão à origem).

### Reverter

- **Domínio principal (volta ao protótipo):** primeiro `terraform state rm 'aws_route53_record.site'`.
  Os registros têm `prevent_destroy`: sem o `state rm`, o `plan` com `ativar_dominios = false` falha de
  propósito, e o `state rm` tira o Terraform da gestão deles sem apagá-los no Route53. Depois,
  `ativar_dominios = false` e `apply` (tira os aliases da distribuição nova e o vigia volta ao
  `*.cloudfront.net`). Em seguida, no console: aliases de volta na distribuição do protótipo e os registros
  A/AAAA de `besave.com.br`/`www` apontando para ela. No worker, `BESAVE_INDEXAVEL=false`. Fora do ar entre
  o `apply` e a edição dos registros. Para refazer a virada depois, repita o passo 2 do roteiro: tirar
  de novo os aliases da distribuição do protótipo (AD-021) e `ativar_dominios = true`; o `allow_overwrite`
  assume os registros de novo.
- **Domínios curtos:** `ativar_curto = false` falha de propósito no `plan` (certificado com
  `prevent_destroy`, AD-022). Para desligar, remova o `prevent_destroy` num commit explícito. As zonas
  também têm `prevent_destroy` e não dependem de `ativar_curto`: zona recriada ganha outros NS e os links
  já postados param até o registrador ser atualizado.

## Deploy do site (BSV-17)

O GitHub Actions (`.github/workflows/site-deploy.yml`) compila `apps/site` e publica no `besave-site` com
credencial temporária (OIDC): nenhuma chave de acesso no GitHub. O bucket é compartilhado com o worker, então
há duas travas com a mesma lista de prefixos (`deploy-site/prefixos.json`):

1. **Policy do papel** `besave-site-deploy`: `PutObject`/`DeleteObject` e `ListBucket` (`s3:prefix`) só em
   `_app/*`, `index.html`, `404.html`, `favicon.*`, `desejos/*`, `assets/besave.css`, `assets/fontes/*` e
   `{slug}/*` das 10 áreas; `CreateInvalidation` só na distribuição do site. Nada em `data/`, `oferta/`,
   `img/`, `manifest*.json`, `sitemap*`, `robots.txt`, `_estado/`.
2. **Script** `deploy-site/publicar.mjs`: recusa o build inteiro, antes de qualquer upload, se houver
   arquivo fora desses prefixos ou se faltar `index.html` ou `404.html` (MANIFEST §5).

O papel só é assumido por `repo:rubenmarcuspaschoarelli@51489817/besave@1371919473:ref:refs/heads/main`, com sessão de 1 h. O repositório usa o formato imutável do `sub` (`gh api repos/{dono}/{repo}/actions/oidc/customization/sub` → `use_immutable_subject: true`), com os IDs numéricos do dono e do repositório; o formato antigo (`repo:dono/repo:…`) é recusado pela AWS com `Not authorized to perform sts:AssumeRoleWithWebIdentity`.
O job só roda em `main` (o `if` pula outros branches); fora dele o STS recusaria o token.

O que o script faz, em ordem:

| passo | comando | headers |
|---|---|---|
| 1 | `aws s3 sync _app/` (sem `--delete` e sem `--size-only`: reenvia o `_app/` do build, e o `LastModified` fica o do último deploy que tinha o arquivo) | `public, max-age=31536000, immutable` |
| 2 | `_app/version.json` (nome fixo do SvelteKit) | `public, max-age=300`, `application/json` |
| 3 | `assets/besave.css`, `assets/fontes/*`, `favicon.*`, um `cp` por arquivo | `public, max-age=3600, stale-while-revalidate=86400` |
| 4 | cada HTML, um `cp` por arquivo; `404.html` e `index.html` por último | `public, max-age=300`, `text/html; charset=utf-8` |
| 5 | invalidação: `/index.html`, `/404.html`, `/{dir}/*` de cada diretório com HTML, `/assets/*` (nunca `/*`) | — |
| 6 | limpeza de `_app/` com carência: lista `_app/` (`s3api list-objects-v2`) e apaga (`s3 rm`, um por arquivo) só o que **não está no build atual e subiu há mais de 7 dias**; arquivo do build nunca sai, mesmo antigo | — |

A carência conta de quando o arquivo saiu do build e deixa uma página antiga ainda em cache (navegador ou borda) achar
os chunks dela por uma semana. Reenviar o `_app/` a cada deploy custa pouco (hoje 12 arquivos, ~100 KB).
Nunca há `--delete`. O `--ensaio` também lista `_app/` (só leitura) e mostra o que seria apagado
(`apagaria N arquivo(s)` e as linhas `aws s3 rm`), por isso no workflow ele roda depois da credencial.

Uma rota nova fora desses prefixos (ex.: `/sobre/`) exige, na mesma PR, o prefixo em
`deploy-site/prefixos.json`, os testes (`tests/site_deploy.tftest.hcl`, `functions/test/deploy-site.test.mjs`)
e um `apply`. Antes disso, o deploy falha no passo de ensaio.

### 1. Aplicar (dono)

```sh
cd infra
terraform plan -out plano.tfplan   # 3 to add (provedor OIDC, papel, policy), 0 to change, 0 to destroy
terraform apply plano.tfplan
terraform output arn_papel_site_deploy id_distribuicao
```

O provedor `token.actions.githubusercontent.com` não existe na conta. Se o `apply` acusar
`EntityAlreadyExists`, alguém o criou no console: `terraform import aws_iam_openid_connect_provider.github <arn>`.

### 2. Variáveis do repositório

São variáveis (não segredos): o ARN não dá acesso sem o token OIDC do GitHub.

```sh
gh variable set AWS_ROLE_SITE        --body "$(terraform output -raw arn_papel_site_deploy)"
gh variable set CF_DISTRIBUICAO_SITE --body "$(terraform output -raw id_distribuicao)"
```

### 3. Simular o papel

```sh
ROLE=$(terraform output -raw arn_papel_site_deploy)
sim() { aws iam simulate-principal-policy --policy-source-arn "$ROLE" --action-names "$1" \
  --resource-arns "arn:aws:s3:::besave-site/$2" --query 'EvaluationResults[0].EvalDecision' --output text; }
sim s3:PutObject    _app/x.js              # allowed
sim s3:PutObject    elas/index.html        # allowed
sim s3:DeleteObject manifest.json          # implicitDeny
sim s3:DeleteObject oferta/1/index.html    # implicitDeny
sim s3:DeleteObject data/chunks/x          # implicitDeny
sim s3:PutObject    robots.txt             # implicitDeny
aws iam simulate-principal-policy --policy-source-arn "$ROLE" --action-names s3:ListBucket \
  --resource-arns arn:aws:s3:::besave-site \
  --context-entries ContextKeyName=s3:prefix,ContextKeyValues=data/,ContextKeyType=string \
  --query 'EvaluationResults[0].EvalDecision' --output text   # implicitDeny (com _app/ → allowed)
```

### 4. Primeiro deploy (à mão) e ligar o automático

O build tem de trazer `index.html` **e** `404.html`; o placeholder da BSV-35 ainda não traz o `404.html`, e o
deploy falha no ensaio sem tocar o bucket. Primeiro deploy, quando a BSV-30 estiver aprovada:

```sh
gh workflow run site-deploy.yml --ref main
gh run watch "$(gh run list --workflow site-deploy.yml --limit 1 --json databaseId -q '.[0].databaseId')"
curl -s https://besave.com.br/ | head        # home nova
curl -I https://besave.com.br/nao-existe     # 404 com o /404.html do site
```

Até aqui `curl -s https://besave.com.br/` continua mostrando a home provisória. Depois do primeiro deploy
conferido, ligar o automático (todo merge em `main` que mexa em `apps/site/**`):

```sh
gh variable set SITE_DEPLOY_ATIVO --body true
```

Para desligar: `gh variable set SITE_DEPLOY_ATIVO --body false` (qualquer valor diferente de `true`).

Ensaio local, sem AWS (imprime os comandos):

```sh
cd apps/site && pnpm build && cd ../..
node infra/deploy-site/publicar.mjs --build apps/site/build --bucket besave-site --distribuicao EXEMPLO --ensaio
```

O ensaio lista `_app/` no bucket; sem credencial, passe uma listagem salva com `--remotos arquivo.json`
(`[{"Key": "_app/...", "LastModified": "..."}]`, `[]` para nenhuma).

### 5. Reverter

Rodar o workflow com o SHA de um commit anterior de `main` (só ancestral de `main` é aceito; o workflow e o
script continuam os do HEAD, só `apps/site` vem do commit):

```sh
git log --oneline main -- apps/site            # escolher o último commit bom
gh workflow run site-deploy.yml --ref main -f commit=<sha>
```

### Cuidados

- `assets/besave.css` passa a ser do deploy do site (AD-078), mas o worker ainda o publica até a BSV-30
  tirá-lo do worker. Enquanto os dois publicam, vale o último que escreveu.
- Invalidação: cada deploy usa até 14 caminhos (wildcard conta como 1); 1.000 por mês são grátis, depois
  US$ 0,005 por caminho.
- O papel não lê nem lista nada fora dos prefixos; `aws s3 ls s3://besave-site/` com ele dá `AccessDenied`.

## Cuidados

- **Registro TXT do Google Search Console** em `besave.com.br`: criado no console do Route53 (06/10/2026), fora do Terraform. Não apagar: é a verificação da propriedade de domínio.

- **Registros de validação ACM** usam `allow_overwrite`: o CNAME de validação é o mesmo para o mesmo
  domínio na mesma conta, e o certificado atual pode já tê-lo criado. O Terraform passa a gerenciar
  esse registro. Por isso ele e o certificado ACM têm `prevent_destroy = true`: `terraform destroy`
  (ou um plan que os recrie) falha em vez de apagar e quebrar a renovação do certificado antigo.
  Para destruir de propósito, remova o `prevent_destroy` num commit explícito.
- **Bucket de logs** usa logging padrão *legacy* para S3 (não o v2 via CloudWatch/Firehose: v2 cobra
  por GB entregue e o dado só precisa estar no S3). Legacy exige ACL: ownership `BucketOwnerPreferred`
  e `aws_s3_bucket_acl.logs` com `FULL_CONTROL` para o dono e para `awslogsdelivery`
  (`c4c1ede6…d2d0`, ID documentado pela AWS). O grant é o mesmo que o CloudFront colocaria sozinho.
- **KVS** limita 5 MB (~45k ofertas ativas, MANIFEST §5). O Terraform cria a store vazia; o worker popula.
