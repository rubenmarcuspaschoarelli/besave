# BSV-4 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `CLAUDE.md`, `docs/specs/BSV-4.md` (Functions testadas com fixtures de evento; `terraform validate`/`plan` sem credenciais reais).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| CloudFront Functions | unit | FN-01..06 1:1 + edge cases, fixtures de evento `cloudfront-js-2.0` | `infra/functions/test/*.test.mjs` | `npm test` |
| Página 404 | unit | CF-12 | `infra/functions/test/pagina-404.test.mjs` | `npm test` |
| Terraform (plan) | integration | S3-*, CF-*, IAM-*, FN-07, OPS-01..02 via `mock_provider` | `infra/tests/*.tftest.hcl` | `terraform test` |
| README / MANIFEST | none | leitura | - | build gate only |

## Gate Check Commands

> Rodar em `infra/` (Terraform local: binário no PATH ou no scratchpad).

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cd functions && npm test` |
| Full | After tasks with e2e/integration tests | `terraform init -backend=false && terraform validate && terraform test` |
| Build | After phase completion or config/entity-only tasks | `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test && cd functions && npm ci && npm test` |

---

## Execution Plan

### Phase 1: Functions

```
T1 → T2
```

### Phase 2: Terraform e operação (depois da Phase 1)

```
T3 → T4 → T5 → T6 → T7
```

---

## Task Breakdown

### T1: Function rewrite-index

**What**: `rewrite-index.js` (`cloudfront-js-2.0`), `package.json` sem dependências (`node --test`), loader de teste que troca o `import cf`, fixtures de evento.
**Where**: `infra/functions/`
**Depends on**: None
**Reuses**: nada (pasta nova)
**Requirement**: FN-01, FN-02, FN-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `/` → `/index.html`; `/oferta/1/` → `/oferta/1/index.html`; `/beleza` → `/beleza/index.html`; `/a.b/c` → `/a.b/c/index.html`
- [ ] `/manifest.json`, `/_app/x.js` intactos
- [ ] Gate check passes: `npm ci && npm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): add rewrite-index CloudFront Function`

---

### T2: Function redirect-afiliado

**What**: `redirect-afiliado.js`: id decimal → `kvs.get` → 302 `location` + `no-store`; ausente/inválido → 302 `/`.
**Where**: `infra/functions/redirect-afiliado.js`, `infra/functions/test/redirect-afiliado.test.mjs`
**Depends on**: T1
**Reuses**: loader de teste de T1
**Requirement**: FN-04, FN-05, FN-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] id presente → 302, `location` = valor, `cache-control: no-store`
- [ ] id ausente (get lança) → 302 `/` + `no-store`
- [ ] `/ir/`, `/ir/abc`, `/ir/12/x` → 302 `/` sem chamar a KVS
- [ ] Gate check passes: `npm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): add redirect-afiliado CloudFront Function`

---

### T3: Provider, variáveis e buckets

**What**: `main.tf` (provider, locals), `variables.tf`, `s3.tf` com `besave-site` (BPA, lifecycle 7 dias) e `besave-logs` (BPA, `BucketOwnerPreferred`), `.terraform.lock.hcl`, teste `buckets.tftest.hcl`.
**Where**: `infra/main.tf`, `infra/variables.tf`, `infra/s3.tf`, `infra/tests/buckets.tftest.hcl`
**Depends on**: None
**Reuses**: `.gitignore` já ignora `.terraform/` e `*.tfstate`
**Requirement**: S3-01, S3-02, S3-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Plano (mock) tem os 4 flags de BPA `true` nos dois buckets, lifecycle `data/chunks/` e `data/busca/` = 7 dias, ownership `BucketOwnerPreferred` no de logs, nenhum `aws_s3_bucket_website_configuration`
- [ ] Gate check passes: `terraform init -backend=false && terraform validate && terraform test`

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): add terraform provider and site/log buckets`

---

### T4: Certificado ACM com validação Route53

**What**: `acm.tf`: certificado para `dominio` + `www.dominio`, registros de validação por domínio (`allow_overwrite`), `aws_acm_certificate_validation`.
**Where**: `infra/acm.tf`, `infra/tests/acm.tftest.hcl`
**Depends on**: T3
**Reuses**: `var.dominio`, `local.dominios`
**Requirement**: CF-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Certificado com `domain_name = besave.com.br`, SAN `www.besave.com.br`, `validation_method = DNS`; 2 registros de validação na zona
- [ ] Gate check passes: `terraform validate && terraform test`

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): add ACM certificate with Route53 DNS validation`

---

### T5: CloudFront (OAC, KVS, Functions, políticas, distribuição) e 404

**What**: `cloudfront.tf` com OAC, KVS `besave-redirects`, 2 Functions, 4 políticas próprias + `CachingDisabled`, distribuição (6 behaviors, logs `cf/`, error responses 403/404 → 404 `/404.html`, `ativar_dominios`), política do bucket para OAC; `infra/static/404.html`.
**Where**: `infra/cloudfront.tf`, `infra/s3.tf` (policy), `infra/static/404.html`, `infra/tests/cloudfront.tftest.hcl`, `infra/functions/test/pagina-404.test.mjs`
**Depends on**: T4 (e Phase 1)
**Reuses**: `infra/functions/*.js`, certificado de T4
**Requirement**: FN-07, S3-03, CF-01, CF-02, CF-03, CF-04, CF-05, CF-06, CF-07, CF-08, CF-09, CF-11, CF-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Behaviors na ordem e com políticas/TTL/compress/Functions de MANIFEST §5 (atualizado por AD-020)
- [ ] Error responses 403→404 e 404→404 `/404.html` TTL 60; nenhuma com 200
- [ ] `ativar_dominios` false → sem aliases, certificado padrão; true → 2 aliases + ACM `sni-only`
- [ ] Policy do bucket: só `s3:GetObject` para `cloudfront.amazonaws.com` com `AWS:SourceArn` da distribuição
- [ ] `404.html` com `noindex`, link `/` e as 9 áreas
- [ ] Gate check passes: build

**Tests**: integration, unit
**Gate**: build

**Commit**: `feat(infra): add CloudFront distribution with OAC, KVS and edge functions`

---

### T6: IAM do worker e outputs

**What**: `iam.tf` (usuário sem console/sem key, policy inline mínima), `outputs.tf`, teste de IAM/outputs e de ausência de recursos existentes.
**Where**: `infra/iam.tf`, `infra/outputs.tf`, `infra/tests/iam.tftest.hcl`
**Depends on**: T5
**Reuses**: ARNs de bucket, KVS e distribuição
**Requirement**: IAM-01, IAM-02, IAM-03, OPS-01, OPS-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Policy com exatamente as ações/recursos de IAM-02/03; sem `aws_iam_access_key` nem `aws_iam_user_login_profile`
- [ ] 4 outputs; nenhum recurso do plano referencia `besave.com.br` como bucket nem `E28G93A17WHHD`
- [ ] Gate check passes: build

**Tests**: integration
**Gate**: build

**Commit**: `feat(infra): add least-privilege IAM user for the worker and outputs`

---

### T7: README de operação e MANIFEST §5

**What**: `infra/README.md` (pré-requisitos, apply, access key manual, curls de aceite, 404.html, virada); MANIFEST §5 linha 6 sem fallback SPA.
**Where**: `infra/README.md`, `docs/MANIFEST.md`
**Depends on**: T6
**Reuses**: outputs de T6
**Requirement**: OPS-03, OPS-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] README cobre todos os itens de OPS-03
- [ ] MANIFEST §5 linha 6 = 403/404 → 404 `/404.html`, sem fallback SPA
- [ ] Gate check passes: build

**Tests**: none
**Gate**: build

**Commit**: `docs(infra): add operations README and drop SPA fallback from MANIFEST`
