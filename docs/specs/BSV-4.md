# BSV-4 · Infra base em IaC (Terraform) — bucket privado + CloudFront + KVS + IAM do worker

**Papel:** DevOps · **Pasta:** `infra/` · **Depende de:** BSV-2 (MANIFEST.md §1, §4, §5)

## Contexto
- Hoje: bucket público `besave.com.br` (website hosting, us-east-1) servindo o protótipo via
  distribuição `E28G93A17WHHD`, tudo criado no console. Route53 gerencia `besave.com.br`.
- Decisão AD-016: **não tocar no que está no ar.** Criar a stack nova ao lado, validar no domínio
  do CloudFront, virar o DNS depois (fora deste ticket).

## Objetivo
Terraform em `infra/` que cria, do zero e de forma reproduzível, tudo que o site novo precisa,
sem credenciais no código.

## Entregáveis
1. `infra/main.tf`, `variables.tf`, `outputs.tf`, `README.md` (como aplicar; state local por ora,
   `*.tfstate` no `.gitignore`; migrar para S3 backend é ticket futuro).
2. Bucket `besave-site` (us-east-1): privado, Block Public Access total, sem website hosting,
   versionamento desligado, lifecycle: `data/chunks/` e `data/busca/` expiram em 7 dias
   (só órfãos sobrevivem tanto; o manifest atual sempre aponta para arquivos recentes).
3. Bucket `besave-logs` (ou reutilizar `logs.besave.com.br`): logs padrão do CloudFront, prefixo `cf/`.
4. Distribuição CloudFront nova: origem S3 com **OAC**, certificado ACM (us-east-1) para
   `besave.com.br` e `www.besave.com.br` (validação DNS via Route53, criada pelo Terraform),
   HTTP→HTTPS, HTTP/2+3, compressão ligada, behaviors **exatamente** como MANIFEST.md §5
   (6 behaviors, políticas de cache por path, `/ir/*` sem cache).
5. CloudFront KeyValueStore `besave-redirects` + CloudFront Functions:
   - `rewrite-index` (viewer-request): `/x/` → `/x/index.html`; `/x` sem extensão → `/x/index.html`.
   - `redirect-afiliado` (viewer-request em `/ir/*`): lê `id` do path, `kvs.get(id)`, 302 com
     `Location` e `Cache-Control: no-store`; ausente → 302 `/`. **Sem chave real ainda**: o
     worker (BSV-12) popula.
   - Funções versionadas no repo em `infra/functions/*.js` com teste unitário do runtime
     (`cloudfront-js-2.0`) usando fixtures de evento.
6. IAM: usuário `besave-worker` (sem console) com policy mínima:
   `s3:PutObject, s3:DeleteObject, s3:ListBucket, s3:GetObject` no bucket `besave-site`;
   `cloudfront-keyvaluestore:DescribeKeyValueStore, PutKey, DeleteKey, ListKeys` na KVS;
   `cloudfront:CreateInvalidation` restrito à distribuição nova. **Sem** access key criada pelo
   Terraform — o dono gera no console e guarda fora do git.
7. `outputs.tf`: nome do bucket, domínio da distribuição, ARN da KVS, ARN da distribuição.

## Fora de escopo
Registro DNS de `besave.com.br` apontando para a distribuição nova (virada), migração do
conteúdo do bucket antigo, backend remoto do state, alertas de custo.

## Critério de aceite
- `terraform validate` e `terraform plan` limpos no CI (job `infra`, adicionar ao `ci.yml` com
  filtro `infra/**`; `plan` só em PR, sem credenciais reais → usar `-refresh=false` com
  provider mock, ou apenas `fmt`+`validate` se `plan` exigir conta).
- Após `apply` pelo dono: `curl -I https://<dominio-cf>/manifest.json` retorna 403 ou 404 do S3
  via OAC (não erro de DNS/TLS); `curl -I https://<dominio-cf>/ir/999` retorna 302 para `/`;
  upload manual de um `index.html` de teste aparece em `https://<dominio-cf>/`.
- Nenhum recurso existente (`besave.com.br`, `E28G93A17WHHD`) aparece no `plan`.
- Testes das duas Functions passam com fixtures de evento.

## Definition of done
PR com `README.md` de operação, `plan` colado no PR, testes verdes, sem segredo no diff.
