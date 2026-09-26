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

Não gerencia o bucket `besave.com.br` nem a distribuição atual do protótipo: o `plan` não mostra nenhum dos dois.

## Pré-requisitos

- Terraform ≥ 1.7 e Node 22 (testes das Functions).
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
`ativar_dominios` (`false`), `classe_preco` (`PriceClass_All`: 100/200 não cobrem a América do Sul).
Nome de bucket é global: se `besave-site` ou `besave-logs` estiver tomado, passe `-var bucket_site=...`.

**State local.** `terraform.tfstate` fica em `infra/` e está no `.gitignore`. Faça backup fora do
git: sem ele o Terraform perde o controle dos recursos. Backend S3 é ticket futuro.

## Depois do apply

1. **Access key do worker**: IAM → Users → `besave-worker` → Security credentials → Create access key.
   Guarde fora do git (gerenciador de senhas / `.env` local). O Terraform nunca cria essa chave.
   O worker (BSV-12) recebe `BESAVE_BUCKET` = output `bucket_site` e `BESAVE_KVS_ARN` = output `arn_kvs`.
2. **Página 404** (o deploy do site deve **sempre** publicar `/404.html`; até lá, o placeholder):

   ```sh
   aws s3 cp static/404.html s3://besave-site/404.html \
     --content-type "text/html; charset=utf-8" --cache-control "public, max-age=300"
   ```

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
cd functions && npm ci && npm test   # Functions com fixtures de evento + 404.html + sem recursos do protótipo
```

**Obrigatório** após qualquer mudança em `functions/*.js`: rodar `test-function` no runtime real. O
cloudfront-js-2.0 é um subconjunto do JS (ex.: `await` como argumento de função é erro de sintaxe) e
os testes Node acima não o emulam — passam com código que o CloudFront recusa.

Para testar uma Function no runtime real depois do apply:
`aws cloudfront test-function --name redirect-afiliado --if-match <ETag> --stage LIVE --event-object fileb://evento.json`.

## Virada de DNS (fora deste ticket)

CloudFront recusa o mesmo CNAME em duas distribuições (`CNAMEAlreadyExists`), por isso a distribuição
nova nasce sem aliases e com o certificado `*.cloudfront.net`. Na virada:

1. Tirar `besave.com.br` e `www.besave.com.br` dos aliases da distribuição do protótipo (console).
2. `terraform apply -var ativar_dominios=true` (aliases + certificado ACM, `sni-only`, `TLSv1.2_2021`).
3. Apontar os registros A/AAAA alias do Route53 para o output `dominio_distribuicao`.

## Cuidados

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
