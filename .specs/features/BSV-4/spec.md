# BSV-4 — Infra base em IaC (Terraform): bucket privado + CloudFront + KVS + IAM do worker

Fonte: `docs/specs/BSV-4.md`. Contrato: `docs/MANIFEST.md` §1, §4, §5; `docs/DECISOES.md` AD-006, AD-016.
Decisão do dono nesta sessão (2026-09-25): sem fallback SPA; 403/404 do S3 viram 404 com `/404.html`
(proposta AD-020, ver `design.md`).

## Problem Statement

O protótipo roda num bucket público com website hosting e numa distribuição criada no console.
O site novo precisa de bucket privado com OAC, behaviors por path, redirect de afiliado na borda
(KVS) e um usuário IAM mínimo para o worker (BSV-12). Tudo em Terraform, ao lado do que está no
ar, sem tocar em `besave.com.br` (bucket) nem em `E28G93A17WHHD`.

## Goals

- [ ] `terraform fmt -check`, `validate` e `test` (provider mock, sem conta AWS) limpos em `infra/`.
- [ ] `npm test` em `infra/functions` passa com fixtures de evento das duas Functions.
- [ ] Após `apply` pelo dono: `/manifest.json` → 403/404, `/ir/999` → 302 `/`, `index.html` de teste
      aparece em `/`, `/nao-existe` → 404 `text/html`, `/data/chunks/0-ffff.json.br` → 404.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Registro DNS de `besave.com.br` apontando para a distribuição nova (virada) | spec BSV-4 |
| Migração do conteúdo do bucket antigo | spec BSV-4 |
| Backend remoto do state | spec BSV-4 (ticket futuro) |
| Alertas de custo | spec BSV-4 |
| Link curto `besave.io/{id}` (AD-018) | CONTRATO.md: ticket separado |
| Design final da `/404.html` | BSV-30 (site) |
| Popular a KVS | BSV-12 (worker) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| SPA fallback (MANIFEST §5 linha 6) | Removido. `custom_error_response` 403→404 e 404→404 com `/404.html`, TTL 60 s | Error responses do CloudFront valem para a distribuição inteira; fallback global devolveria HTML 200 para chunk ausente. Site não tem rota client-side | y (dono) |
| Aliases `besave.com.br`/`www` na distribuição nova | Variável `ativar_dominios` (padrão `false`): sem aliases e com certificado padrão do CloudFront até a virada | CloudFront recusa um CNAME já usado por outra distribuição (`CNAMEAlreadyExists`); `E28G93A17WHHD` usa esses nomes hoje. O certificado ACM é criado e validado já | n |
| Registros de validação ACM | `allow_overwrite = true` | Mesma conta + mesmo domínio geram o mesmo CNAME de validação; se o certificado atual foi validado por DNS, o registro já existe | n |
| Zona Route53 | `data "aws_route53_zone"` por nome (`var.dominio`) | Zona já existe; só leitura | n |
| Bucket de logs | Novo, `besave-logs` (variável), ACL habilitada (`BucketOwnerPreferred`) com grant explícito a `awslogsdelivery`, sem acesso público; logging legacy para S3 (não v2) | Log padrão do CloudFront exige ACL; reutilizar `logs.besave.com.br` faria o Terraform mexer em recurso existente | n |
| Versionamento do `besave-site` | Nenhum recurso de versionamento (bucket novo já nasce sem) | `Disabled` explícito só vale para import | n |
| Políticas de cache | `/ir/*` usa a gerenciada `CachingDisabled` (`4135ea2d-6df8-44a3-9df3-4b5a84be39ad`); demais são políticas próprias, sem query string/cookie/header na chave | TTLs exatos de MANIFEST §5; chave = path | n |
| TTL máximo de `/oferta/*` e default | `/oferta/*` máx 86 400; default máx 31 536 000 | MANIFEST §5 só fixa o padrão; o máximo deixa valer o `Cache-Control` da origem (`_app/**` immutable) | n |
| Classe de preço | `PriceClass_All` (variável) | Público no Brasil; 100/200 não incluem América do Sul | n |
| `id` inválido em `/ir/*` (vazio, não numérico, com `/` extra) | 302 para `/` sem consultar a KVS | Chave da KVS é o id decimal (BSV-12) | n |
| Política do bucket para OAC | Só `s3:GetObject` para `cloudfront.amazonaws.com` com `AWS:SourceArn` = distribuição nova | Mínimo privilégio; o 403 de objeto ausente vira 404 pela error response | n |
| Testes da infra | `terraform test` com `mock_provider "aws"` (plan, sem credenciais) | Prova behaviors/TTLs/IAM sem conta; CI atual roda só `fmt`+`validate` (proposta de passo no PR) | n |
| Dependências das Functions | Nenhuma: `node:test` nativo (Node 22 do CI) | Regra 7: sem dependência nova | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Functions de borda ⭐ MVP

**User Story**: Como visitante, quero que `/x/` sirva `/x/index.html` e que `/ir/{id}` me leve à loja, sem URL de afiliado no HTML.

**Why P1**: Sem `rewrite-index` nenhuma página abre; sem `redirect-afiliado` nenhum CTA funciona (AD-006).

**Acceptance Criteria**:

1. WHEN o `uri` termina em `/` THEN `rewrite-index` SHALL devolver a requisição com `uri` + `index.html` (`/` → `/index.html`, `/oferta/1/` → `/oferta/1/index.html`).  <!-- FN-01 -->
2. WHEN o último segmento do `uri` não tem `.` THEN `rewrite-index` SHALL devolver `uri` + `/index.html` (`/beleza` → `/beleza/index.html`).  <!-- FN-02 -->
3. WHEN o último segmento tem extensão THEN `rewrite-index` SHALL devolver a requisição com o `uri` intacto (`/manifest.json`, `/_app/x.js`).  <!-- FN-03 -->
4. WHEN `/ir/{id}` tem `id` presente na KVS THEN `redirect-afiliado` SHALL responder 302 com `location` = valor da KVS e `cache-control: no-store`.  <!-- FN-04 -->
5. IF o `id` não existe na KVS (get lança erro) THEN `redirect-afiliado` SHALL responder 302 com `location: /` e `cache-control: no-store`.  <!-- FN-05 -->
6. IF o `id` não é um inteiro decimal (vazio, letras, segmento extra) THEN `redirect-afiliado` SHALL responder 302 para `/` com `no-store` sem consultar a KVS.  <!-- FN-06 -->
7. The funções SHALL rodar em `cloudfront-js-2.0`, `redirect-afiliado` associada à KVS `besave-redirects`, código lido de `infra/functions/*.js`.  <!-- FN-07 -->

**Independent Test**: `cd infra/functions && npm test`; FN-07 em `terraform test`.

---

### P1: Buckets ⭐ MVP

**User Story**: Como dono, quero um bucket privado para o site e um de logs, sem acesso público.

**Why P1**: É a origem da distribuição.

**Acceptance Criteria**:

1. The bucket `besave-site` SHALL existir em us-east-1 com Block Public Access nos 4 flags e sem website hosting.  <!-- S3-01 -->
2. The bucket `besave-site` SHALL não ter regra de lifecycle com expiração (revisão do dono 2026-09-25: chunk é por faixa de id e fica referenciado por semanas; a única remoção é a limpeza de órfãos do worker, BSV-11).  <!-- S3-02 -->
3. The política do `besave-site` SHALL permitir só `s3:GetObject` ao principal `cloudfront.amazonaws.com` com `AWS:SourceArn` igual ao ARN da distribuição nova.  <!-- S3-03 -->
4. The bucket `besave-logs` SHALL ter Block Public Access nos 4 flags, ownership `BucketOwnerPreferred` e ACL com `FULL_CONTROL` para o dono da conta e para `awslogsdelivery` (canonical ID `c4c1ede66af53448b93c283ce9448c4ba468c9432aa01d700d3878632f77d2d0`), e a distribuição SHALL gravar logs padrão (legacy, S3) nele com prefixo `cf/`.  <!-- S3-04 -->

**Independent Test**: `terraform test`.

---

### P1: Distribuição CloudFront ⭐ MVP

**User Story**: Como visitante, quero o site via HTTPS com cache por path exatamente como MANIFEST §5.

**Why P1**: É a stack nova.

**Acceptance Criteria**:

1. The distribuição SHALL ter uma origem S3 (`besave-site`) com OAC (`sigv4`, `always`), `http_version = http2and3`, `viewer_protocol_policy = redirect-to-https` em todos os behaviors e só `GET`/`HEAD`.  <!-- CF-01 -->
2. The distribuição SHALL ter os behaviors ordenados `/ir/*`, `/manifest.json`, `/data/*`, `/img/*`, `/oferta/*` + default.  <!-- CF-02 -->
3. The `/ir/*` SHALL usar `CachingDisabled`, `compress = false` e a Function `redirect-afiliado` em `viewer-request`.  <!-- CF-03 -->
4. The `/manifest.json` SHALL usar política TTL min 0 / padrão 300 / máx 300 com gzip+br e `compress = true`.  <!-- CF-04 -->
5. The `/data/*` e `/img/*` SHALL usar política TTL min 0 / padrão 31 536 000 / máx 31 536 000, sem gzip/br na chave e `compress = false`.  <!-- CF-05 -->
6. The `/oferta/*` SHALL usar TTL padrão 600 com gzip+br, `compress = true` e `rewrite-index` em `viewer-request`.  <!-- CF-06 -->
7. The default SHALL usar TTL padrão 300 com gzip+br, `compress = true` e `rewrite-index` em `viewer-request`.  <!-- CF-07 -->
8. The políticas próprias SHALL não ter cookie, header nem query string na chave de cache.  <!-- CF-08 -->
9. The distribuição SHALL ter `custom_error_response` 403 → 404 e 404 → 404, ambos com `/404.html` e `error_caching_min_ttl = 60`, e nenhuma error response com `response_code` 200.  <!-- CF-09 -->
10. The certificado ACM SHALL cobrir `besave.com.br` e `www.besave.com.br` com validação DNS em registros Route53 criados pelo Terraform.  <!-- CF-10 -->
13. The certificado ACM e os registros de validação Route53 SHALL ter `lifecycle { prevent_destroy = true }`.  <!-- CF-13 -->
11. WHEN `ativar_dominios = false` (padrão) THEN a distribuição SHALL não ter aliases e usar o certificado padrão do CloudFront; WHEN `true` THEN SHALL ter os dois aliases com o certificado ACM validado (`sni-only`, `TLSv1.2_2021`).  <!-- CF-11 -->
12. The `infra/static/404.html` SHALL ter `<meta name="robots" content="noindex">`, link para `/` e para as 9 áreas.  <!-- CF-12 -->

**Independent Test**: `terraform test`; CF-12 por `npm test`.

---

### P1: IAM do worker ⭐ MVP

**User Story**: Como worker (BSV-12), quero credenciais com o mínimo para publicar no bucket, na KVS e invalidar a distribuição.

**Why P1**: BSV-12 depende disso para o teste real.

**Acceptance Criteria**:

1. The usuário `besave-worker` SHALL existir sem login de console e sem access key criada pelo Terraform.  <!-- IAM-01 -->
2. The policy do usuário SHALL permitir `s3:PutObject`, `s3:DeleteObject`, `s3:GetObject` só em `besave-site/*` e `s3:ListBucket` só no bucket.  <!-- IAM-02 -->
3. The policy SHALL permitir `cloudfront-keyvaluestore:DescribeKeyValueStore`, `PutKey`, `DeleteKey`, `ListKeys` só no ARN da KVS e `cloudfront:CreateInvalidation` só no ARN da distribuição nova, sem outra ação nem `*` em recurso.  <!-- IAM-03 -->

**Independent Test**: `terraform test`.

---

### P1: Operação ⭐ MVP

**User Story**: Como dono, quero aplicar e conferir a infra seguindo o README, sem tocar no que está no ar.

**Why P1**: Definition of done do ticket.

**Acceptance Criteria**:

1. The `outputs.tf` SHALL expor nome do bucket, domínio da distribuição, ARN da KVS e ARN da distribuição.  <!-- OPS-01 -->
2. The plano SHALL não conter recurso cujo nome/id seja o bucket `besave.com.br` ou a distribuição `E28G93A17WHHD`.  <!-- OPS-02 -->
3. The `infra/README.md` SHALL explicar pré-requisitos, `init/plan/apply`, state local, geração manual da access key, os `curl` do critério de aceite, upload do `/404.html` e o passo da virada (`ativar_dominios`).  <!-- OPS-03 -->
4. The `docs/MANIFEST.md` §5 linha 6 SHALL descrever o default sem fallback SPA (403/404 → 404 `/404.html`).  <!-- OPS-04 -->
5. The job `infra` do `.github/workflows/ci.yml` SHALL rodar `terraform test` depois de `terraform validate`.  <!-- OPS-05 -->

**Independent Test**: `terraform test` (OPS-01, OPS-02); leitura (OPS-03, OPS-04).

---

## Edge Cases

- WHEN `rewrite-index` recebe `/a.b/c` (ponto num segmento anterior) THEN SHALL tratar só o último segmento: `/a.b/c/index.html`.
- WHEN `redirect-afiliado` recebe `/ir/` (id vazio) ou `/ir/12/x` THEN SHALL responder 302 `/`.
- WHEN a querystring existe (`/ir/12?utm=x`) THEN `redirect-afiliado` SHALL usar só o path (o `uri` do evento não inclui querystring).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| FN-01 | P1: Functions | T1 | Implemented |
| FN-02 | P1: Functions | T1 | Implemented |
| FN-03 | P1: Functions | T1 | Implemented |
| FN-04 | P1: Functions | T2 | Implemented |
| FN-05 | P1: Functions | T2 | Implemented |
| FN-06 | P1: Functions | T2 | Implemented |
| FN-07 | P1: Functions | T5 | Implemented |
| S3-01 | P1: Buckets | T3 | Implemented |
| S3-02 | P1: Buckets | T8 | Implemented |
| S3-03 | P1: Buckets | T5 | Implemented |
| S3-04 | P1: Buckets | T10 | Pending |
| CF-01 | P1: Distribuição | T5 | Implemented |
| CF-02 | P1: Distribuição | T5 | Implemented |
| CF-03 | P1: Distribuição | T5 | Implemented |
| CF-04 | P1: Distribuição | T5 | Implemented |
| CF-05 | P1: Distribuição | T5 | Implemented |
| CF-06 | P1: Distribuição | T5 | Implemented |
| CF-07 | P1: Distribuição | T5 | Implemented |
| CF-08 | P1: Distribuição | T5 | Implemented |
| CF-09 | P1: Distribuição | T5 | Implemented |
| CF-10 | P1: Distribuição | T4 | Implemented |
| CF-11 | P1: Distribuição | T5 | Implemented |
| CF-12 | P1: Distribuição | T5 | Implemented |
| CF-13 | P1: Distribuição | T9 | Implemented |
| IAM-01 | P1: IAM | T6 | Implemented |
| IAM-02 | P1: IAM | T6 | Implemented |
| IAM-03 | P1: IAM | T6 | Implemented |
| OPS-01 | P1: Operação | T6 | Implemented |
| OPS-02 | P1: Operação | T6 | Implemented |
| OPS-03 | P1: Operação | T7 | Implemented |
| OPS-04 | P1: Operação | T7 | Implemented |
| OPS-05 | P1: Operação | T11 | Pending |

**Coverage:** 32 total, 32 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test` verde em `infra/` sem credenciais.
- [ ] `npm ci && npm test` verde em `infra/functions`.
- [ ] Dono roda `apply` e os 5 `curl` do README batem.
