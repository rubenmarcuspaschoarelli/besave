# BSV-16 Validation

## Validation: BSV-16 - PASS

**Date**: 2026-10-03
**Spec**: `.specs/features/BSV-16/spec.md` (fonte: `docs/specs/BSV-16.md`)
**Diff range**: `c8de133..c8830c5` (f6aaabd..c8830c5, 7 commits; 22 arquivos, +1059/-41)
**Ciclo**: 2 de 3 (ciclo 1: FAIL por mutante T16; correção em c8830c5, tarefa T7)
**Verifier**: sub-agente independente (autor ≠ verificador)
**Result**: PASS — ciclo 2. 25/25 ACs com evidência, gate verde, mutante T16 do ciclo 1 agora morto. Critérios **Real (dono)** pendentes: são do dono, fora do alcance do Verifier.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 link-curto | ✅ Done | f6aaabd |
| T2 www → apex | ✅ Done | 2ae2b54 |
| T3 páginas provisórias | ✅ Done | 6fe41ef |
| T4 registros + vigia | ✅ Done | 6e188d9 |
| T5 domínios curtos | ✅ Done | a1248c1 |
| T6 README | ✅ Done | 2b85cec |
| T7 fix G1 (ciclo 1) | ✅ Done | c8830c5: output `certificado_validado` (`infra/tests/inspecao/main.tf:42`) + asserção (`infra/tests/curto.tftest.hcl:141`) |

---

## Spec-Anchored Acceptance Criteria

### P1: Virada (`terraform test`, `infra/tests/dominios.tftest.hcl`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| VIR-01 | A+AAAA de `besave.com.br` e `www`, zona do domínio, alias para a distribuição nova, `allow_overwrite = true` | `infra/tests/dominios.tftest.hcl:31` - conjunto `"name type"` == {besave.com.br A/AAAA, www.besave.com.br A/AAAA}; `:37` - `r.zone_id == "Z0000000000000EXEMPLO" && r.allow_overwrite && r.alias[0].name == aws_cloudfront_distribution.site.domain_name && r.alias[0].zone_id == ...site.hosted_zone_id` (código: `infra/dominios.tf:15`) | ✅ PASS |
| VIR-02 | `ativar_dominios = false` → nenhum A/AAAA | `infra/tests/dominios.tftest.hcl:11` - `length(aws_route53_record.site) == 0` | ✅ PASS |
| VIR-03 | `URL_MANIFEST = https://besave.com.br/manifest.json` | `infra/tests/dominios.tftest.hcl:47` - `== "https://besave.com.br/manifest.json"` (código: `infra/vigia.tf:112`) | ✅ PASS |
| VIR-04 | `URL_MANIFEST = https://<*.cloudfront.net>/manifest.json` | `infra/tests/dominios.tftest.hcl:17` - `== "https://${aws_cloudfront_distribution.site.domain_name}/manifest.json"` (mock `d111111abcdef8.cloudfront.net`, `infra/tests/mocks/aws.tfmock.hcl:20`) | ✅ PASS |

### P1: `www` → domínio sem www (`infra/functions/test/rewrite-index.test.mjs`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| WWW-01 | 301, `location = https://besave.com.br/oferta/1/?a=1` (uri original) | `infra/functions/test/rewrite-index.test.mjs:41` - `r.statusCode === 301`; `:42` - `location === 'https://besave.com.br/oferta/1/?a=1'` | ✅ PASS |
| WWW-01 edge | Host `WWW.Besave.com.br` redireciona igual | `infra/functions/test/rewrite-index.test.mjs:50` - `'https://besave.com.br/elas?t=1&t=2'` | ✅ PASS |
| WWW-02 | sem query, `location` sem `?` | `infra/functions/test/rewrite-index.test.mjs:56` - `=== 'https://besave.com.br/'` | ✅ PASS |
| WWW-03 | domínio sem www mantém FN-01..03 | `infra/functions/test/rewrite-index.test.mjs:61-62` - `statusCode === undefined`, `uri === '/oferta/1/index.html'`; FN-01..03 intactos em `:8-27` | ✅ PASS |

### P1: Domínios curtos (`infra/tests/curto.tftest.hcl`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| CUR-01 | zonas `besave.io`, `besave.me` sempre | `infra/tests/curto.tftest.hcl:11` - `toset(names) == toset(["besave.io","besave.me"])` (run com `ativar_curto` padrão `false`) | ✅ PASS |
| CUR-02 | output com os 4 NS de cada zona | `infra/tests/curto.tftest.hcl:17-18` - chaves == as 2 zonas, `length(ns) == 4 && tolist(ns) == zona.name_servers` | ✅ PASS |
| CUR-03 | `false` → sem certificado, validação, Function, distribuição, A/AAAA | `infra/tests/curto.tftest.hcl:24-26` - `length(...) == 0` para os 6 recursos | ✅ PASS |
| CUR-04 | cert `besave.io` + SANs `www.besave.io`, `besave.me`, `www.besave.me`, DNS, `prevent_destroy` | `infra/tests/curto.tftest.hcl:40-42` - domain_name/SANs/`validation_method == "DNS"`; `:135` - `output.prevent_destroy["aws_acm_certificate.curto"]` (código: `infra/curto.tf:30`) | ✅ PASS |
| CUR-05 | 1 registro de validação por nome, na zona do domínio | `infra/tests/curto.tftest.hcl:48-53` - 4 chaves + `zone_id` por nome + zonas distintas; `:57-60` name/type/records do ACM | ✅ PASS |
| CUR-06 | 4 aliases, cert validado, `sni-only`, `TLSv1.2_2021`, origem custom `besave.com.br`, `link-curto` viewer-request, logs `besave-logs` prefixo `curto/` | `infra/tests/curto.tftest.hcl:78` aliases; `:82-85` viewer_certificate; `:89-91` origem; `:95-97` function_association `[["viewer-request", arn]]`; `:101-102` bucket logs + `prefix == "curto/"`; "validado": `infra/tests/curto.tftest.hcl:141` - `output.certificado_validado["aws_cloudfront_distribution.curto"]` (regex na fonte: `acm_certificate_arn = ...aws_acm_certificate_validation.`) | ✅ PASS (ciclo 2) |
| CUR-07 | A+AAAA dos 4 nomes, na zona do domínio, alias para a distribuição curta | `infra/tests/curto.tftest.hcl:108-113` - conjunto `"zone_id name type"` exato; `:116-118` alias = distribuição curta; `:122` distribuições distinguíveis | ✅ PASS |
| CUR-08 | `cloudfront-js-2.0`, `publish = true`, código de `functions/link-curto.js` | `infra/tests/curto.tftest.hcl:70-72` - name, runtime, publish, `code == file(...)` | ✅ PASS |

### P1: Function `link-curto` (`infra/functions/test/link-curto.test.mjs`; helper `assert301` em `:16-20` confere status, `location` exato e `Cache-Control`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| LNK-01 | `/5412`, `/5412/`, `/05412` → `https://besave.com.br/oferta/5412/` | `infra/functions/test/link-curto.test.mjs:23-27` (inclui limites `/1` e 12 dígitos) | ✅ PASS |
| LNK-02 | `/5412/ir` → `https://besave.com.br/ir/5412` | `infra/functions/test/link-curto.test.mjs:31-32` | ✅ PASS |
| LNK-03 | query anexada (`?utm_source=telegram`) | `infra/functions/test/link-curto.test.mjs:36` - `.../oferta/5412/?utm_source=telegram`; `:38-41` múltiplas chaves e home; edge repetida `:46` - `?t=1&t=2` | ✅ PASS |
| LNK-04 | `/`, `/abc`, `/1234567890123`, id zero, outros → `https://besave.com.br/` | `infra/functions/test/link-curto.test.mjs:50-51` (11 entradas, inclui `/0`, `/000`, `/5412/ir/`, `//5412`) | ✅ PASS |
| LNK-05 | sempre 301 + `Cache-Control: public, max-age=86400` | `infra/functions/test/link-curto.test.mjs:17,19` em todas as chamadas | ✅ PASS |

### P2: Páginas (`infra/functions/test/pagina-404.test.mjs`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| PAG-01 | nome besave, "site em construção", `href="{CANAL_TELEGRAM}"` | `infra/functions/test/pagina-404.test.mjs:17-19` | ✅ PASS |
| PAG-02 | `noindex`, "Oferta encerrada ou não encontrada", links `/` e canal | `infra/functions/test/pagina-404.test.mjs:13` noindex; `:23-25` | ✅ PASS |
| PAG-03 | sem link de área | `infra/functions/test/pagina-404.test.mjs:29` (10 slugs, incl. `outros`); `:31` - `links == ['/', '{CANAL_TELEGRAM}']` | ✅ PASS |
| PAG-04 | sem `t.me/` real nem telefone | `infra/functions/test/pagina-404.test.mjs:36-37` | ✅ PASS |

### P2: README

| AC | Spec-defined outcome | Evidência | Result |
| -- | -------------------- | --------- | ------ |
| OPS-01 | roteiro de 6 passos, upload manual, custos, reversão | `infra/README.md:193-207` roteiro (6 passos, iguais à spec); `infra/README.md:227-238` upload com `sed` do marcador; `infra/README.md:242` custos (valores iguais à spec); `infra/README.md:250` reverter. Sem teste automatizado (camada "none" na matriz) | ✅ PASS (leitura) |

**Status**: ✅ 25/25 ACs com evidência `file:line` e asserção no valor da spec.

---

## Discrimination Sensor

Escopo: worktree temporária `git worktree add --detach <scratchpad>/wt HEAD` (com cópia de `infra/.terraform`); cada mutação revertida com `git checkout -- <arquivo>` antes da próxima. Sensor expandido (≥ 5) por ser link permanente/DNS.

### Node (`cd functions && npm test`)

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| M1 | `infra/functions/link-curto.js:17` | não remove zeros à esquerda | ✅ (LNK-01/02/04) |
| M2 | `infra/functions/link-curto.js:24` | perde a query | ✅ (LNK-03) |
| M3 | `infra/functions/link-curto.js:21` | 301 → 302 | ✅ (5 testes) |
| M4 | `infra/functions/link-curto.js:16` | `{1,12}` → `{1,13}` | ✅ (LNK-04) |
| M5 | `infra/functions/link-curto.js:19` | `/ir` invertido | ✅ |
| M6 | `infra/functions/link-curto.js:25` | `max-age=86400` → `3600` | ✅ |
| M7 | `infra/functions/link-curto.js:8` | ignora `multiValue` | ✅ (LNK-03 edge) |
| M8 | `infra/functions/rewrite-index.js:15` | regra do www nunca casa | ✅ (WWW-01/02) |
| M9 | `infra/functions/rewrite-index.js:14` | sem `toLowerCase` | ✅ (WWW-01 edge) |
| M10 | `infra/functions/rewrite-index.js:20` | www perde a query | ✅ |
| M11 | `infra/functions/rewrite-index.js:17` | www 301 → 302 | ✅ |
| M12 | `infra/functions/rewrite-index.js:9` | `?` sempre presente | ✅ (WWW-02) |
| M13 | `infra/static/404.html:13` | 404 com link `/elas/` | ✅ (PAG-03) |
| M14 | `infra/static/404.html:11` | texto "Página não encontrada" | ✅ (PAG-02) |
| M15 | `infra/static/404.html:6` | sem `noindex` | ✅ (CF-12) |
| M16 | `infra/static/index.html:9` | `t.me/` real | ✅ (PAG-04) |
| M17 | `infra/static/index.html:11` | sem "site em construção" | ✅ (PAG-01) |
| M18 | `infra/static/404.html:14` | telefone na 404 | ✅ (PAG-04) |

### Terraform (`terraform test -filter=...`)

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| T1 | `infra/dominios.tf:15` | remove `allow_overwrite` | ✅ (`dominios_ativos`) |
| T2 | `infra/curto.tf:102` | prefixo de log `curto/` → `site/` | ✅ (`curto_fase_2`) |
| T3 | `infra/curto.tf:30` | remove `prevent_destroy` | ✅ (`curto_protecao`) |
| T4 | `infra/vigia.tf:112` | `URL_MANIFEST` sempre `*.cloudfront.net` | ✅ (`dominios_ativos`) |
| T5 | `infra/curto.tf:125` | A/AAAA de `www.besave.me` na zona `besave.io` | ✅ (`curto_fase_2`) |
| T6 | `infra/curto.tf:37` | validação de `www.besave.me` na zona `besave.io` | ✅ (`curto_fase_2`) |
| T7 | `infra/curto.tf:70` | aliases sem `www.*` | ✅ |
| T8 | `infra/curto.tf:52` | Function `link-curto` criada na fase 1 | ✅ (`curto_fase_1`) |
| T9 | `infra/curto.tf:130` | registros curtos apontando para a distribuição do site | ✅ |
| T10 | `infra/dominios.tf:4` | registros do site sem o gate `ativar_dominios` | ✅ (`dominios_desligados`) |
| T11 | `infra/curto.tf:55` | runtime `cloudfront-js-1.0` | ✅ |
| T12 | `infra/curto.tf:116` | TLS mínimo `TLSv1` | ✅ |
| T13 | `infra/curto.tf:95` | `viewer-response` em vez de `viewer-request` | ✅ |
| T14 | `infra/curto.tf:14` | zonas curtas só com `ativar_curto` | ✅ (`curto_fase_1`) |
| T15 | `infra/dominios.tf:18` | alias do site para outro alvo | ✅ |
| T16 | `infra/curto.tf:114` | `acm_certificate_arn = aws_acm_certificate.curto[0].arn` (pula `aws_acm_certificate_validation`) | ciclo 1: ❌ Survived → ciclo 2: ✅ Killed (`curto_protecao`) |
| T17 | `infra/curto.tf:5` | `nomes_curtos` sem `www.*` (cert, aliases, registros) | ✅ |
| T18 | `infra/curto.tf:74` | origem `besave-site.s3.amazonaws.com` | ✅ |

**Sensor depth**: expandido (ciclo 1: 36 mutações, 18 Node + 18 Terraform).
**Ciclo 1**: 35/36 killed (T16 sobreviveu → fix task T7).

Ciclo 1 — por que T16 sobrevivia: os ARNs do certificado e da validação são iguais no mock (`infra/tests/mocks/aws.tfmock.hcl:70`, `:81`) e na AWS; a asserção por valor (`infra/tests/curto.tftest.hcl:82`) não provava a dependência.

### Ciclo 2 (c8830c5) — re-execução em worktree temporária nova

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| T16 | `infra/curto.tf:114` | ARN direto do certificado | ✅ (`curto_protecao`, `infra/tests/curto.tftest.hcl:141`) |
| T16b | `infra/curto.tf:114` | ARN da validação **do site** | ✅ (`curto_fase_2`, valor em `:82`) |
| T16d | `infra/curto.tf:114` | ARN direto + linha comentada com a referência correta | ✅ (`curto_protecao`: comentários de linha inteira são removidos antes do regex) |
| T3 | `infra/curto.tf:30` | sem `prevent_destroy` (mesmo run alterado) | ✅ (`curto_protecao`) |
| T16c | `infra/curto.tf:114` | ARN direto + **comentário no fim da linha** citando `aws_acm_certificate_validation.` | ⚠️ Survived — limite conhecido da inspeção textual |
| T19 | `infra/cloudfront.tf:242` | distribuição do **site** com ARN direto (código anterior ao ticket) | ⚠️ Survived — fora do diff (o output `certificado_validado` cobre o site, mas só a chave `curto` é afirmada) |

**Result ciclo 2**: mutantes de comportamento plausíveis no diff: 4/4 killed — PASS. T16c é um mutante adversarial construído para enganar a inspeção por texto; não é uma regressão plausível. O check de `prevent_destroy` já existente tem o mesmo limite. Por isso fica registrado como lacuna menor (G6), não como bloqueio. T19 está fora da superfície do diff (lacuna G7, informativa).

**Isolamento**: ciclo 1 — porcelain vazio antes e depois. Ciclo 2 — baseline `?? .specs/features/BSV-16/validation.md` (este relatório), idêntico depois (`diff` sem diferenças). Nos dois ciclos: worktree desregistrada com `git worktree remove --force` + `prune`; o diretório (com `.terraform` acima de MAX_PATH) foi apagado com `rd /s /q \?\<caminho>`.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (`link-curto.js` 28 linhas, sem estado) |
| Surgical changes | ✅ só `infra/` e `.specs/features/BSV-16/` |
| No scope creep | ✅ protótipo, Search Console, HSTS fora |
| Matches patterns | ✅ `for_each` + `setproduct` como `acm.tf`; mocks no padrão existente |
| Spec-anchored outcome check | ✅ |
| Per-layer Coverage Expectation met | ✅ |
| Every test maps to a spec requirement | ✅ (CF-12 noindex mantido; teste antigo "9 áreas" substituído por PAG-03 — a spec inverte a regra) |
| Documented guidelines followed | ✅ `CLAUDE.md`, `docs/specs/BSV-16.md` |

Observação: `query()` duplicada em `link-curto.js:5` e `rewrite-index.js:3` — inevitável, CloudFront Functions não compartilham módulo.

---

## Edge Cases

- [x] `Host: WWW.Besave.com.br` → mesmo 301 (`infra/functions/test/rewrite-index.test.mjs:46-50`)
- [x] Query com chave repetida preservada em `link-curto` (`infra/functions/test/link-curto.test.mjs:44-46`) e em `rewrite-index` (`:47-50`)

---

## Gate Check

- **Gate command** (em `infra/`): `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test && python -m unittest discover -s lambdas/vigia && cd functions && npm test`
- **Result (ciclo 2, HEAD c8830c5)**: fmt OK; validate "Success! The configuration is valid."; `terraform test` **14 passed, 0 failed** (asserção nova dentro do run `curto_protecao`); vigia **35 OK**; Node **26 pass, 0 fail, 0 skipped**.
- **Contagem antes (c8de133)**: Node 14, Terraform runs 9.
- **Contagem depois**: Node 26, Terraform runs 14.
- **Delta**: +12 Node (13 novos, 1 removido: "CF-12 links das 9 áreas", contrariado por PAG-03 — remoção justificada pela spec), +5 runs Terraform.
- **Skipped**: nenhum. **Failures**: nenhuma.

---

## Lacunas

Falhas de código: nenhuma. As lacunas G2–G5 são premissas ou pendências **do dono**, não falhas do código.

1. **G1 — RESOLVIDA no ciclo 2** (c8830c5): CUR-06 "certificado validado" agora afirmado pela fonte (`infra/tests/curto.tftest.hcl:141`, `infra/tests/inspecao/main.tf:42`); T16 morto.
2. **G2 (premissa do dono) — "`plan` da fase 1 só com adições".** A implementação gera 2 adições + 1 alteração in-place (`rewrite-index`, regra do `www`), registrada como premissa não confirmada em `.specs/features/BSV-16/spec.md:33` e no README (`infra/README.md:195`). Não é verificável por mocks; o dono precisa aceitar ao colar o `plan`.
3. **G3 (pendência do dono) — critério Real (dono).** `test-function` das duas Functions (eventos em `infra/functions/eventos/`), `curl` do roteiro, `lambda invoke` do vigia e prévia no Telegram. A codificação da query (valores repassados como vieram em `querystring`, padrão do exemplo oficial da AWS) só se confirma no `test-function` real.
4. **G4 (premissa do dono / observação) — `www` só redireciona nos behaviors que têm `rewrite-index`** (`/oferta/*` e default). `www.besave.com.br/manifest.json`, `/data/*`, `/img/*` respondem 200 e `/ir/*` vai para `redirect-afiliado`. Atende a spec ("rewrite-index responde 301"), mas há conteúdo duplicado fora do HTML. Sem impacto de SEO relevante (não são páginas).
5. **G5 (proposta para o dono) — zonas curtas sem `prevent_destroy`** (`.specs/features/BSV-16/spec.md:43`). Zona recriada troca os NS e quebra links permanentes. Sugestão para o PR.
6. **G6 (menor, teste) — inspeção textual aceita comentário no fim da linha** (mutante T16c). `infra/tests/inspecao/main.tf` remove só comentários de linha inteira. Sugestão opcional: remover também `#...` no fim da linha antes do regex. Isso endurece `certificado_validado` e `prevent_destroy` ao mesmo tempo.
7. **G7 (informativa, fora do diff) — distribuição do site** (`infra/cloudfront.tf:242`): o padrão anterior ao ticket não é afirmado por `certificado_validado["aws_cloudfront_distribution.site"]`. Basta uma linha em `infra/tests/cloudfront.tftest.hcl`, num ticket futuro.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| VIR-01..04, WWW-01..03, CUR-01..05, CUR-07, CUR-08, LNK-01..05, PAG-01..04, OPS-01 | Implemented | ✅ Verified (mocks/Node); Real (dono) pendente |
| CUR-06 | Implemented | ✅ Verified (ciclo 2) |

---

## Summary

**Overall**: ✅ Ready para PR (ciclo 2). O merge segue dependendo do critério **Real (dono)**: `test-function`, `curl`, `lambda invoke`, prévia no Telegram e `plan` das duas fases colado com `REDACTED`.

**Spec-anchored check**: 25/25 ACs com evidência e valor da spec
**Sensor**: ciclo 1 35/36; ciclo 2, 4/4 mutantes plausíveis mortos (T16 incluído); T16c (adversarial) e T19 (fora do diff) registrados como G6/G7
**Gate**: Terraform 14/14, vigia 35/35, Node 26/26

**Lições propostas (para o dono mover a `docs/DECISOES.md`; não gravadas em LESSONS)**: (1) quando mock e AWS devolvem o mesmo valor para dois recursos (ARN do certificado e da validação), uma asserção por valor não prova a dependência: prove a referência pela fonte (`tests/inspecao`). (2) Num ambiente Windows, `.terraform` copiado para a worktree temporária excede `MAX_PATH` no `git worktree remove`: apague com `rd /s /q \?\<caminho>`.
