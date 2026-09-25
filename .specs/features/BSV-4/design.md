# BSV-4 — Design

Spec: `spec.md`. Terraform em `infra/`, um módulo raiz, state local.

## Arquivos

| arquivo | conteúdo |
|---|---|
| `infra/main.tf` | `required_version`, provider `aws` (us-east-1, `default_tags`), `locals` |
| `infra/variables.tf` | `regiao`, `dominio`, `bucket_site`, `bucket_logs`, `ativar_dominios`, `classe_preco` |
| `infra/s3.tf` | `besave-site` (BPA, lifecycle, policy OAC) e `besave-logs` (BPA, ownership) |
| `infra/acm.tf` | certificado + registros Route53 + `aws_acm_certificate_validation` |
| `infra/cloudfront.tf` | OAC, KVS, 2 Functions, 4 políticas de cache, distribuição |
| `infra/iam.tf` | usuário `besave-worker` + policy inline |
| `infra/outputs.tf` | bucket, domínio CF, ARN KVS, ARN distribuição |
| `infra/functions/*.js` | código das Functions, lido com `file()` |
| `infra/functions/test/*.test.mjs` | `node:test`; carrega o `.js` trocando `import cf from 'cloudfront'` por um `cf` falso |
| `infra/tests/*.tftest.hcl` | `terraform test` com `mock_provider "aws"` e `command = plan` |
| `infra/static/404.html` | placeholder da página 404 |

A spec pede `main.tf`: ele guarda provider e `locals`; os recursos ficam em arquivos por serviço.

## Decisões

**AD-020 (proposta, decisão do dono em 2026-09-25)** · Sem fallback SPA; 403/404 do S3 viram 404 com
`/404.html` (TTL de erro 60 s); adapter-static com fallback desabilitado · o site não tem rota
client-side (home, áreas, busca são prerender; oferta é HTML do worker) e um fallback global
devolveria HTML 200 para chunk ausente em `/data/*` · error response 403/404 → `/index.html` 200.

**D-1 · Aliases atrás de `ativar_dominios` (padrão `false`).** CloudFront não aceita o mesmo CNAME em
duas distribuições; `E28G93A17WHHD` tem `besave.com.br`. Até a virada a distribuição nova usa
`*.cloudfront.net`; o certificado ACM já nasce validado. Na virada: tirar os aliases da antiga,
`ativar_dominios = true`, apontar o DNS.

**D-2 · `allow_overwrite` nos registros de validação ACM.** O CNAME de validação é o mesmo para o mesmo
domínio na mesma conta; se já existe (certificado atual), o Terraform assume o registro com o mesmo
valor. Consequência: `terraform destroy` apagaria esse registro. Documentado no README.

**D-3 · Registros de validação indexados por domínio conhecido** (`for_each = toset(local.dominios)`),
não por `domain_validation_options`, para o plano não depender de valor computado.

**D-4 · Chave de cache = path** em todas as políticas próprias; gzip/br só onde o CloudFront comprime.

**D-5 · Testes de Terraform com `mock_provider`**, sem conta AWS. O CI atual roda `fmt` + `validate`;
propor no PR o passo `terraform test` no job `infra` (editar `ci.yml` não foi autorizado neste ticket).

## Function `redirect-afiliado`

```
uri = /ir/{id}; id deve casar ^[0-9]+$ → kvs.get(id) → 302 location=valor
qualquer outra coisa ou get lança → 302 location=/
sempre cache-control: no-store
```

`cf.kvs()` sem argumento usa a store associada (docs AWS, "Helper methods for key value stores").
