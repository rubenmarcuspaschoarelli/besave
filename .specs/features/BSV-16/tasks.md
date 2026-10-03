# BSV-16 Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `spec.md`
**Status**: Done

---

## Test Coverage Matrix

> Guidelines: `CLAUDE.md`, `docs/specs/BSV-16.md` (critério de aceite: `terraform test` com mocks + testes Node das Functions).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| CloudFront Functions | unit | LNK-*, WWW-* 1:1 + edge cases | `infra/functions/test/*.test.mjs` | `cd infra/functions && npm test` |
| Páginas estáticas | unit | PAG-* | `infra/functions/test/pagina-*.test.mjs` | `cd infra/functions && npm test` |
| Terraform | integration | VIR-*, CUR-* via `mock_provider` | `infra/tests/*.tftest.hcl` | `terraform test` |
| README | none | leitura | - | build gate only |

## Gate Check Commands

> Rodar em `infra/`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cd functions && npm test` |
| Full | After tasks with e2e/integration tests | `terraform init -backend=false && terraform validate && terraform test` |
| Build | After phase completion or config/entity-only tasks | `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test && python -m unittest discover -s lambdas/vigia && cd functions && npm test` |

---

## Execution Plan

### Phase 1: Functions e páginas

```
T1 → T2 → T3
```

### Phase 2: Terraform e README

```
T4 → T5 → T6 → T7 → T8 → T9
```

---

## Task Breakdown

### T1: Function link-curto

**What**: `link-curto.js` (viewer-request, 301 para oferta, `/ir`, home; query preservada; `Cache-Control`) e seus testes Node.
**Where**: `infra/functions/link-curto.js`
**Depends on**: None
**Reuses**: `functions/test/carregar.mjs`
**Requirement**: LNK-01, LNK-02, LNK-03, LNK-04, LNK-05

**Done when**:

- [x] `/5412`, `/5412/`, `/05412` → `/oferta/5412/`; `/5412/ir` → `/ir/5412`; `/`, `/abc`, `/1234567890123` → home
- [x] Query preservada; status 301 e `Cache-Control: public, max-age=86400` em todas
- [x] Gate check passes: `cd functions && npm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): add link-curto function for short domains`

---

### T2: www → domínio sem www em rewrite-index

**What**: `rewrite-index.js` responde 301 para `https://besave.com.br{uri}{query}` quando `Host` é `www.besave.com.br`.
**Where**: `infra/functions/rewrite-index.js`
**Depends on**: T1
**Reuses**: `functions/test/rewrite-index.test.mjs`
**Requirement**: WWW-01, WWW-02, WWW-03

**Done when**:

- [x] `Host: www.besave.com.br` + `/oferta/1/?a=1` → 301 `https://besave.com.br/oferta/1/?a=1`
- [x] Testes FN-01..03 existentes verdes
- [x] Gate check passes: `cd functions && npm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): redirect www.besave.com.br to the apex domain`

---

### T3: Páginas provisórias

**What**: `static/index.html` nova; `static/404.html` sem links de área, com "Oferta encerrada ou não encontrada" e canal.
**Where**: `infra/static/`
**Depends on**: T2
**Reuses**: `functions/test/pagina-404.test.mjs`
**Requirement**: PAG-01, PAG-02, PAG-03, PAG-04

**Done when**:

- [x] Teste CF-12 antigo (links das 9 áreas) substituído por PAG-03 (spec BSV-16 inverte a regra)
- [x] Gate check passes: `cd functions && npm test`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(infra): add provisional home and fix 404 page`

---

### T4: Registros de besave.com.br e URL do vigia

**What**: `dominios.tf` com A/AAAA alias de `besave.com.br` e `www` (gated por `ativar_dominios`, `allow_overwrite`); `URL_MANIFEST` do vigia no domínio quando ativo.
**Where**: `infra/dominios.tf`, `infra/vigia.tf`
**Depends on**: None
**Reuses**: `data.aws_route53_zone.site`, `tests/mocks`
**Requirement**: VIR-01, VIR-02, VIR-03, VIR-04

**Done when**:

- [x] `terraform test`: com `true` 4 registros com `allow_overwrite` e `URL_MANIFEST` no domínio; com `false` nenhum e URL cloudfront.net
- [x] Gate check passes: full gate

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): point besave.com.br records to the new distribution`

---

### T5: Domínios curtos

**What**: `curto.tf`: zonas `besave.io`/`besave.me` e output dos NS; com `ativar_curto`, certificado ACM (4 nomes, `prevent_destroy`), validação DNS, Function `link-curto`, distribuição `besave-curto` e A/AAAA.
**Where**: `infra/curto.tf`, `infra/variables.tf`, `infra/outputs.tf`
**Depends on**: T4
**Reuses**: `cloudfront.tf`, `acm.tf` (padrões), `tests/inspecao`
**Requirement**: CUR-01, CUR-02, CUR-03, CUR-04, CUR-05, CUR-06, CUR-07, CUR-08

**Done when**:

- [x] `terraform test`: com `false` só as 2 zonas; com `true` certificado, validação, distribuição e registros conforme a spec
- [x] Gate check passes: full gate

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): add besave.io and besave.me short-link domains`

---

### T6: README do roteiro

**What**: roteiro da virada, upload das páginas, `test-function`, custos e reversão.
**Where**: `infra/README.md`, `infra/functions/eventos/`
**Depends on**: T5
**Reuses**: README atual
**Requirement**: OPS-01

**Done when**:

- [x] Roteiro de 6 passos, custos e reversão no README
- [x] Gate check passes: build gate

**Tests**: none
**Gate**: build

**Commit**: `docs(infra): document DNS cutover and short domains`

---

### T7: Fix — CUR-06 prova o certificado validado

**What**: inspeção do código garante que `besave-curto` usa o ARN de `aws_acm_certificate_validation` (mutante T16 do Verifier sobreviveu: ARNs iguais no mock e na AWS).
**Where**: `infra/tests/inspecao/main.tf`, `infra/tests/curto.tftest.hcl`
**Depends on**: T6
**Reuses**: `tests/inspecao` (padrão do `prevent_destroy`)
**Requirement**: CUR-06

**Done when**:

- [x] Mutante T16 (`aws_acm_certificate.curto[0].arn`) falha em `curto_protecao`
- [x] Gate check passes: full gate

**Tests**: integration
**Gate**: full

**Commit**: `test(infra): assert short distribution waits for certificate validation`

---

### T8: Revisão do dono — passo 0 com Functions temporárias

**What**: README: passo 0 com `testar_function` (create/test/delete) antes de qualquer apply; upload das páginas no passo 1.
**Where**: `infra/README.md`
**Depends on**: T7
**Reuses**: README e testes existentes
**Requirement**: OPS-02

**Done when**:

- [x] Roteiro com passo 0 e upload das páginas no passo 1
- [x] Gate check passes: build gate

**Tests**: none
**Gate**: build

**Commit**: `docs(infra): test functions on temporary copies before any apply`

---

### T9: Revisão do dono — prevent_destroy nos registros e nas zonas

**What**: `prevent_destroy` em `aws_route53_record.site` e `aws_route53_zone.curto`, coberto por leitura do código (`tests/inspecao`); reversão no README conferida.
**Where**: `infra/dominios.tf`, `infra/curto.tf`, `infra/tests/`, `infra/README.md`
**Depends on**: T8
**Reuses**: README e testes existentes
**Requirement**: VIR-05, CUR-09

**Done when**:

- [x] `dominios_protecao` e `curto_protecao` falham sem o `prevent_destroy` e passam com ele
- [x] Gate check passes: full gate

**Tests**: integration
**Gate**: full

**Commit**: `feat(infra): protect domain records and short zones from destroy`
