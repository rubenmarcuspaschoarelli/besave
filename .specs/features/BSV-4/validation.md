# BSV-4 Validation

**Verdict**: PASS ✅ (iteração 1 de 3, re-verificação: 30/30 ACs com evidência `file:line`, gate verde com 5 runs `terraform test` + 14 testes `node:test`; os 3 sobreviventes da iteração 0 (M24, M25, M26) agora morrem, e 9 mutantes já mortos foram re-testados sem regressão)

> Histórico: iteração 0 = FAIL (M24/M25/M26 sobreviveram: ausências exigidas por IAM-01 e S3-01 sem teste). Fechado em `805be99` e re-verificado.

**Date**: 2026-09-25
**Spec**: `.specs/features/BSV-4/spec.md` + `.specs/features/BSV-4/design.md` + `docs/specs/BSV-4.md` + critérios do dono no chat (AD-020: `/nao-existe` → 404 `text/html`; `/data/chunks/0-ffff.json.br` → 404, nunca 200)
**Diff range**: `1653949..HEAD` (HEAD `805be99`; spec em `d9fff45` + 7 commits de feature `f409c38`..`18c4458` + fix `805be99`; arquivos só em `infra/`, `docs/MANIFEST.md` e `.specs/features/BSV-4/`)
**Verifier**: sub-agente independente (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 rewrite-index | ✅ Done | `f409c38` |
| T2 redirect-afiliado | ✅ Done | `ac37b18` |
| T3 Provider + buckets | ✅ Done | `b69ee40` |
| T4 ACM + Route53 | ✅ Done | `86adc82` |
| T5 CloudFront + 404 | ✅ Done | `05ff4fe` |
| T6 IAM + outputs | ✅ Done | `8bcbd47` |
| T7 README + MANIFEST §5 | ✅ Done | `18c4458` |
| Fix 1 + Fix 2 (iteração 1) | ✅ Done | `805be99` (2 testes textuais + D-5 no design) |

---

## Spec-Anchored Acceptance Criteria

Terraform: `infra/tests/*.tftest.hcl` (`mock_provider "aws"`, `command = apply` com mock, nada é criado). Functions/404/OPS-02: `infra/functions/test/*.test.mjs` (`node:test`).

### P1: Functions de borda

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| FN-01 `uri` termina em `/` | `/` → `/index.html`; `/oferta/1/` → `/oferta/1/index.html` | `infra/functions/test/rewrite-index.test.mjs:9` - `assert.equal(await uriFinal('/'), '/index.html')`; `:10` - `'/oferta/1/index.html'` | ✅ PASS |
| FN-02 último segmento sem `.` | `/beleza` → `/beleza/index.html` | `infra/functions/test/rewrite-index.test.mjs:14` - `assert.equal(await uriFinal('/beleza'), '/beleza/index.html')`; `:15` - `/oferta/123/index.html` | ✅ PASS |
| FN-03 com extensão | `uri` intacto (`/manifest.json`, `/_app/x.js`) | `infra/functions/test/rewrite-index.test.mjs:23-27` - para `/manifest.json`, `/_app/x.js`, `/data/chunks/0-ffff.json.br`, `/404.html`: `r.uri == uri`, `r.method == 'GET'`, `r.statusCode == undefined` | ✅ PASS |
| FN-04 id na KVS | 302, `location` = valor da KVS, `cache-control: no-store` | `infra/functions/test/redirect-afiliado.test.mjs:36` - `assert302(r, URL_LOJA)` (`:29-31`: `statusCode == 302`, `location.value`, `cache-control == 'no-store'`); `:37` - `consultas == ['123']` | ✅ PASS |
| FN-05 id ausente (get lança) | 302 `location: /`, `no-store` | `infra/functions/test/redirect-afiliado.test.mjs:42` - `assert302(r, '/')`; `:43` - `consultas == ['999']` (KVS falsa lança em `:13`) | ✅ PASS |
| FN-06 id não decimal | 302 `/`, `no-store`, sem consultar a KVS | `infra/functions/test/redirect-afiliado.test.mjs:47-50` - para `/ir/`, `/ir/abc`, `/ir/12/x`, `/ir/12a`, `/ir/-1`: `assert302(r, '/')` e `consultas == []` | ✅ PASS |
| FN-07 runtime, KVS, código do repo | `cloudfront-js-2.0`; `redirect-afiliado` associada a `besave-redirects`; código de `infra/functions/*.js` | `infra/tests/cloudfront.tftest.hcl:10-11` - `runtime == "cloudfront-js-2.0" && publish`; `:15` - `code == file(".../functions/*.js")`; `:23` - `kvs.name == "besave-redirects" && key_value_store_associations == [kvs.arn]` | ✅ PASS |

### P1: Buckets

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| S3-01 `besave-site` | us-east-1, BPA 4 flags, **sem website hosting** | `infra/tests/buckets.tftest.hcl:10` - `bucket == "besave-site"`; `:14-15` - 4 flags `true` nos dois buckets; `:19` - BPA aponta para os buckets certos; `infra/functions/test/sem-recursos-existentes.test.mjs:33` - `doesNotMatch(src, /resource\s+"aws_s3_bucket_website_configuration"\|^\s*website\s*\{/m)` em todo `.tf` (M25 morto na iteração 1). Região: vem de `var.regiao` (`infra/variables.tf:4`, padrão `us-east-1`), não afirmada; é observação, não gap | ✅ PASS |
| S3-02 lifecycle | `data/chunks/` e `data/busca/` expiram em 7 dias | `infra/tests/buckets.tftest.hcl:25-27` - para cada prefixo exatamente 1 regra `Enabled` com `filter[0].prefix == p && expiration[0].days == 7`; `:31` - `length(rule) == 2` | ✅ PASS |
| S3-03 política OAC | só `s3:GetObject` para `cloudfront.amazonaws.com` com `AWS:SourceArn` = ARN da distribuição nova | `infra/tests/cloudfront.tftest.hcl:136-146` - `jsondecode(policy) == {…}` igualdade estrutural completa (1 statement, `Action = "s3:GetObject"`, `Resource = "${site.arn}/*"`, `Condition.StringEquals."AWS:SourceArn" == distribution.arn`); `:150` - policy no bucket do site | ✅ PASS |
| S3-04 `besave-logs` + logs `cf/` | BPA 4 flags, `BucketOwnerPreferred`, logs padrão com prefixo `cf/` | `infra/tests/buckets.tftest.hcl:14-15` (BPA), `:37` - `bucket == "besave-logs"`, `:41` - `object_ownership == "BucketOwnerPreferred"`; `infra/tests/cloudfront.tftest.hcl:156-157` - `logging_config[0].bucket == logs.bucket_domain_name && prefix == "cf/"` | ✅ PASS |

### P1: Distribuição CloudFront

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| CF-01 origem/OAC/protocolo | 1 origem S3 com OAC `sigv4`/`always`; `http2and3`; `redirect-to-https` e só GET/HEAD em todos os behaviors | `infra/tests/cloudfront.tftest.hcl:29` - OAC `s3`/`sigv4`/`always`; `:33-35` - `length(origin) == 1`, `domain_name == site.bucket_regional_domain_name`, `origin_access_control_id == oac.id`; `:39` - `http_version == "http2and3"`; `:43-46` - todos os behaviors (ordered + default): `redirect-to-https`, `allowed_methods`/`cached_methods == {GET, HEAD}` | ✅ PASS |
| CF-02 ordem | `/ir/*`, `/manifest.json`, `/data/*`, `/img/*`, `/oferta/*` + default | `infra/tests/cloudfront.tftest.hcl:52` - `[for b in ordered_cache_behavior : b.path_pattern] == ["/ir/*", "/manifest.json", "/data/*", "/img/*", "/oferta/*"]` (lista, ordem importa) | ✅ PASS |
| CF-03 `/ir/*` | `CachingDisabled`, `compress = false`, `redirect-afiliado` em `viewer-request` | `infra/tests/cloudfront.tftest.hcl:58-60` - `cache_policy_id == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"`, `!compress`, `function_association == [["viewer-request", redirect_afiliado.arn]]` (ARNs distintos por Function via `override_resource`, `infra/tests/mocks/aws.tfmock.hcl:24-31`) | ✅ PASS |
| CF-04 `/manifest.json` | TTL 0/300/300, gzip+br, `compress = true` | `infra/tests/cloudfront.tftest.hcl:66-71` - política `manifest`, `compress`, sem Function, `[min, default, max] == [0, 300, 300]`, gzip e br `true` | ✅ PASS |
| CF-05 `/data/*`, `/img/*` | TTL 0/31 536 000/31 536 000, sem gzip/br, `compress = false` | `infra/tests/cloudfront.tftest.hcl:77-78` - behaviors 2 e 3 (fixados como `/data/*`, `/img/*` por CF-02) com política `imutavel`, `!compress`, sem Function; `:82-84` - `[0, 31536000, 31536000]`, gzip e br `false` | ✅ PASS |
| CF-06 `/oferta/*` | TTL padrão 600, gzip+br, `compress = true`, `rewrite-index` em viewer-request | `infra/tests/cloudfront.tftest.hcl:90-95` - política `oferta`, `compress`, `function_association == [["viewer-request", rewrite_index.arn]]`, `default_ttl == 600`, gzip+br | ✅ PASS |
| CF-07 default | TTL padrão 300, gzip+br, `compress = true`, `rewrite-index` | `infra/tests/cloudfront.tftest.hcl:101-106` - política `padrao`, `compress`, `rewrite-index` em viewer-request, `default_ttl == 300`, gzip+br | ✅ PASS |
| CF-08 chave = path | sem cookie/header/query string nas 4 políticas próprias | `infra/tests/cloudfront.tftest.hcl:112-115` - nas 4 políticas `cookie_behavior`, `header_behavior`, `query_string_behavior == "none"` | ✅ PASS |
| CF-09 error responses (AD-020) | 403→404 e 404→404, `/404.html`, `error_caching_min_ttl = 60`, nenhuma com 200 | `infra/tests/cloudfront.tftest.hcl:121-122` - `toset([for e in custom_error_response : [error_code, response_code, response_page_path, error_caching_min_ttl]]) == toset([[403,404,"/404.html",60],[404,404,"/404.html",60]])` (igualdade de conjunto: exclui qualquer entrada extra, inclusive com 200) | ✅ PASS |
| CF-10 ACM | cobre `besave.com.br` + `www`; validação DNS em registros Route53 criados pelo Terraform | `infra/tests/acm.tftest.hcl:10` - `domain_name == "besave.com.br"`, SANs `== ["www.besave.com.br"]`; `:14` - `validation_method == "DNS"`; `:18-19` - registros na zona mockada, `CNAME`, `allow_overwrite`; `:23-26` - nome/valor de cada registro = o pedido pelo ACM (mock); `:30` - validação espera 2 FQDNs | ✅ PASS |
| CF-11 `ativar_dominios` | `false`: sem aliases, cert padrão; `true`: 2 aliases, ACM validado, `sni-only`, `TLSv1.2_2021` | `infra/tests/cloudfront.tftest.hcl:128-130` - `length(aliases) == 0`, `cloudfront_default_certificate`, `acm_certificate_arn == null`; `:171-175` (run `distribuicao_com_dominios`) - aliases `== {besave.com.br, www.besave.com.br}`, `acm_certificate_arn == aws_acm_certificate_validation.site.certificate_arn`, `!cloudfront_default_certificate`, `sni-only`, `TLSv1.2_2021` | ✅ PASS |
| CF-12 `404.html` | `noindex`, link para `/` e para as 9 áreas | `infra/functions/test/pagina-404.test.mjs:11` - `match(/<meta name="robots" content="noindex">/)`; `:15` - `href="/"`; `:16` - `href="/${area}/"` para as 9 áreas de `:8` | ✅ PASS |

### P1: IAM do worker

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| IAM-01 usuário | `besave-worker` existe, **sem login de console e sem access key criada pelo Terraform** | `infra/tests/iam.tftest.hcl:10` - `name == "besave-worker"`; `infra/functions/test/sem-recursos-existentes.test.mjs:28` - `doesNotMatch(src, /resource\s+"aws_iam_(access_key\|user_login_profile)"/)` em todo `.tf` (M24 e M26 mortos na iteração 1) | ✅ PASS |
| IAM-02 S3 | Put/Delete/GetObject só em `besave-site/*`; ListBucket só no bucket | `infra/tests/iam.tftest.hcl:16-50` - `jsondecode(policy) == {…}` igualdade estrutural completa (4 statements exatos) | ✅ PASS |
| IAM-03 KVS + invalidação | 4 ações KVS só no ARN da KVS; `CreateInvalidation` só no ARN da distribuição; nenhuma outra ação, nenhum `*` | mesma igualdade `infra/tests/iam.tftest.hcl:16-50` (statements `Redirects` e `Invalidar`); `:53` - policy no usuário do worker | ✅ PASS |

### P1: Operação

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| OPS-01 outputs | bucket, domínio CF, ARN KVS, ARN distribuição | `infra/tests/iam.tftest.hcl:59-62` - `output.bucket_site == "besave-site"`, `dominio_distribuicao == distribution.domain_name`, `arn_kvs == kvs.arn`, `arn_distribuicao == distribution.arn` | ✅ PASS |
| OPS-02 nada existente no plano | nenhum recurso do bucket `besave.com.br` nem de `E28G93A17WHHD` | `infra/tests/iam.tftest.hcl:68` - `!contains([site.bucket, logs.bucket], "besave.com.br")`; `infra/functions/test/sem-recursos-existentes.test.mjs:17-18` - nenhum `.tf` cita `E28G93A17WHHD` nem tem bloco `import`; `:23` - nenhum `bucket = "besave.com.br"` | ✅ PASS |
| OPS-03 README | pré-requisitos, init/plan/apply, state local, access key manual, curls, upload `/404.html`, virada | leitura: `infra/README.md:16-20` (pré-requisitos), `:22-30` (init/plan/apply), `:36-37` (state local), `:41-43` (access key), `:44-49` (upload 404), `:51-65` (4 curls + index de teste), `:79-86` (virada `ativar_dominios`) | ✅ PASS (leitura) |
| OPS-04 MANIFEST §5 | linha 6 sem fallback SPA; 403/404 → 404 `/404.html` | leitura: `docs/MANIFEST.md:116` (linha 6: "Sem fallback SPA (AD-020)") e `:118-121` (403/404 → 404 `/404.html`, TTL 60 s, nenhuma 200) | ✅ PASS (leitura) |

**Status**: 30/30 ACs com evidência `file:line` e valor alinhado ao spec (iteração 1: as ausências de IAM-01 e S3-01 agora são testadas).

### Critérios do dono (AD-020) e do ticket, pós-apply

| Item | Mapeamento estático | Result |
| ---- | ------------------- | ------ |
| `curl -I /nao-existe` → 404 `text/html` | `rewrite-index` → `/nao-existe/index.html` (FN-02) → S3 via OAC sem `ListBucket` responde 403 (S3-03 sem ListBucket, morto em M19) → CF-09 403→404 com `/404.html`; `content-type` depende do upload com `--content-type text/html` (`infra/README.md:47-48`) | ✅ estático / ⏭️ dono confere |
| `curl -I /data/chunks/0-ffff.json.br` → 404, nunca 200 | behavior `/data/*` sem Function (CF-05) → 403 do S3 → CF-09; nenhuma error response com 200 (morto em M01) | ✅ estático / ⏭️ dono confere |
| `/manifest.json` → 403/404 | mesma cadeia; na prática 404 (CF-09) | ✅ estático / ⏭️ dono |
| `/ir/999` → 302 `/` | FN-05 + CF-03 | ✅ estático / ⏭️ dono |
| `index.html` de teste em `/` | FN-01 + default behavior | ⏭️ dono |
| `plan` colado no PR; job CI | CI já tem job `infra` (`fmt` + `validate`, `.github/workflows/ci.yml:94-104`); `terraform test` no CI é proposta de PR (D-5) | ⏭️ dono |

### Conferência contra a semântica do provider AWS (v6.66.0, inspeção estática)

| Ponto | Código | Avaliação |
| ----- | ------ | --------- |
| `viewer_certificate` com certificado padrão | `infra/cloudfront.tf:240-245`: `cloudfront_default_certificate = true`, `acm_certificate_arn = null`, `ssl_support_method = null`, `minimum_protocol_version = "TLSv1"` | ✅ Com o certificado `*.cloudfront.net` a AWS só aceita/retorna `TLSv1`; qualquer outro valor gera diff perpétuo. Com `ativar_dominios`: ACM + `sni-only` + `TLSv1.2_2021`, válido. |
| `logging_config.bucket` | `infra/cloudfront.tf:229` = `aws_s3_bucket.logs.bucket_domain_name` | ✅ Formato exigido é `bucket.s3.amazonaws.com` (o `bucket_domain_name`, não o nome nem o regional). ACL habilitada (`BucketOwnerPreferred`) e `depends_on` na ownership (`:247`). |
| OAC + política | `infra/s3.tf:34-49`, `infra/cloudfront.tf:9-15` | ✅ Padrão AWS (`Service` principal + `AWS:SourceArn`). Sem `ListBucket` → objeto ausente = 403, convertido em 404 por CF-09 (coerente com AD-020). |
| KVS em Function | `infra/cloudfront.tf:31-38` | ✅ Associação exige `cloudfront-js-2.0`. ⚠️ Risco: `cf.kvs()` sem id (`infra/functions/redirect-afiliado.js:4`) segue a doc citada no design, mas não é verificável sem conta; se falhar, `/ir/999` dá 503 e o curl do dono pega. Recomendado `aws cloudfront test-function` (README `:76-77`). |
| ARN para `cloudfront-keyvaluestore:*` | `infra/iam.tf:33` = `aws_cloudfront_key_value_store.redirects.arn` | ✅ Recurso `key-value-store` usa o mesmo ARN `arn:aws:cloudfront::<conta>:key-value-store/<id>`. |
| Validação ACM | `infra/acm.tf:17-26` | ✅ `for_each` sobre chaves conhecidas (D-3); valores computados só nos atributos. |

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verif HEAD` + cópia de `infra/.terraform` (provider aws 6.66.0). Mutações aplicadas uma por vez por script (`scratchpad/sensor.py`, CRLF preservado, arquivo restaurado byte a byte depois de cada uma); cada mutante rodou **as duas suítes** (`terraform test` + `node --test test/*.test.mjs`); morto = qualquer uma falhou. M00 = baseline sem mutação: 5/5 runs e 12/12 testes verdes. Depois: `git worktree remove --force` (diretório final apagado após parar 2 processos órfãos do provider do scratch), `git worktree prune`. `git status --porcelain` do tree real: vazio antes e vazio depois (idêntico).

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M01 | `infra/cloudfront.tf:222` | `response_code` 404 → 200 (fallback SPA) | ✅ Killed (`distribuicao_padrao`, CF-09) |
| M02 | `infra/cloudfront.tf:223` | `/404.html` → `/index.html` | ✅ Killed (CF-09) |
| M03 | `infra/cloudfront.tf:219` | só 404 (sem error response do 403) | ✅ Killed (CF-09) |
| M04 | `infra/cloudfront.tf:224` | TTL de erro 60 → 300 | ✅ Killed (CF-09) |
| M05 | `infra/cloudfront.tf:142-165` | troca a ordem `/ir/*` ↔ `/manifest.json` | ✅ Killed (CF-02, CF-03) |
| M06 | `infra/cloudfront.tf:175` | `compress = true` em `/data/*` | ✅ Killed (CF-05) |
| M07 | `infra/cloudfront.tf:45` | manifest `max_ttl` 300 → 600 | ✅ Killed (CF-04) |
| M08 | `infra/cloudfront.tf:87` | oferta `default_ttl` 600 → 300 | ✅ Killed (CF-06) |
| M09 | `infra/cloudfront.tf:37` | remove associação com a KVS | ✅ Killed (FN-07) |
| M10 | `infra/cloudfront.tf:13` | OAC `always` → `no-override` | ✅ Killed (CF-01) |
| M11 | `infra/cloudfront.tf:153` | `/ir/*` com `rewrite-index` | ✅ Killed (CF-03) |
| M12 | `infra/cloudfront.tf:100` | query string `all` na chave de `/oferta/*` | ✅ Killed (CF-08) |
| M13 | `infra/cloudfront.tf:230` | prefixo de log `cf/` → `logs/` | ✅ Killed (S3-04) |
| M14 | `infra/cloudfront.tf:244` | `TLSv1.2_2021` → `TLSv1.2_2019` na virada | ✅ Killed (`distribuicao_com_dominios`, CF-11) |
| M15 | `infra/cloudfront.tf:134` | aliases sempre ligados | ✅ Killed (CF-11) |
| M16 | `infra/cloudfront.tf:70` | gzip na chave da política imutável | ✅ Killed (CF-05) |
| M17 | `infra/s3.tf:27` | lifecycle 7 → 30 dias | ✅ Killed (`buckets`, S3-02) |
| M18 | `infra/s3.tf:19` | lifecycle sem `data/busca/` | ✅ Killed (S3-02) |
| M19 | `infra/s3.tf:42` | policy OAC com `s3:ListBucket` extra | ✅ Killed (S3-03) |
| M20 | `infra/s3.tf:11` | BPA do site com `restrict_public_buckets = false` | ✅ Killed (S3-01) |
| M21 | `infra/s3.tf:59` | logs `BucketOwnerEnforced` (ACL desligada) | ✅ Killed (S3-04) |
| M22 | `infra/iam.tf:15` | ação extra `s3:PutObjectAcl` | ✅ Killed (`iam_e_outputs`, IAM-02) |
| M23 | `infra/iam.tf:39` | `CreateInvalidation` em `*` | ✅ Killed (IAM-03) |
| M24 | `infra/iam.tf` (novo recurso) | `aws_iam_access_key` para o worker | ❌ Survived → Fix 1 |
| M25 | `infra/s3.tf` (novo recurso) | `aws_s3_bucket_website_configuration` no `besave-site` | ❌ Survived → Fix 2 |
| M26 | `infra/iam.tf` (novo recurso) | `aws_iam_user_login_profile` (console) para o worker | ❌ Survived → Fix 1 |
| M27 | `infra/outputs.tf:13` | output `arn_kvs` devolve o id | ✅ Killed (OPS-01) |
| M28 | `infra/functions/rewrite-index.js:7` | extensão procurada no `uri` inteiro | ✅ Killed (FN-02 edge `/a.b/c`) |
| M29 | `infra/functions/rewrite-index.js:8` | `/beleza` → `/belezaindex.html` | ✅ Killed (FN-02) |
| M30 | `infra/functions/redirect-afiliado.js:19` | regex sem âncora final (`^[0-9]+`) | ✅ Killed (FN-06) |
| M31 | `infra/functions/redirect-afiliado.js:19` | regex aceita id vazio (`^[0-9]*$`) | ✅ Killed (FN-06) |
| M32 | `infra/functions/redirect-afiliado.js:12` | `no-store` → `max-age=60` | ✅ Killed (FN-04/05/06) |
| M33 | `infra/functions/redirect-afiliado.js:8` | 302 → 301 | ✅ Killed (FN-04/05/06) |
| M34 | `infra/functions/redirect-afiliado.js:25` | KVS lança → `location` errado | ✅ Killed (FN-05) |
| M35 | `infra/static/404.html:6` | sem `noindex` | ✅ Killed (CF-12) |
| M36 | `infra/static/404.html:22` | sem link `/pets/` | ✅ Killed (CF-12) |

**Sensor depth**: expandido (≥ 5; 36 mutantes em todas as camadas: CloudFront, S3, IAM, outputs, Functions, 404)
**Result (iteração 0)**: 33/36 killed - FAIL ❌ (M24, M25, M26 sobreviveram: cláusulas de ausência sem teste)

### Iteração 1 (re-verificação, HEAD `805be99`)

Scratch: novo `git worktree add --detach <scratchpad>/verif HEAD` + cópia de `infra/.terraform`; mesmo script, mesmas mutações, uma por vez, as duas suítes por mutante. M00 = baseline sem mutação: 5/5 runs e 14/14 testes verdes. Depois: processos órfãos do provider do scratch parados, `git worktree remove --force` + `rmdir` com caminho estendido + `git worktree prune`. `git status --porcelain` do tree real antes e depois: só `?? .specs/features/BSV-4/validation.md` (idêntico).

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M00 | — | baseline, sem mutação | (verde, 0 falhas) |
| M24 | `infra/iam.tf` (novo recurso) | `aws_iam_access_key` para o worker | ✅ Killed (`IAM-01: nenhum .tf cria access key nem login de console`) |
| M25 | `infra/s3.tf` (novo recurso) | `aws_s3_bucket_website_configuration` no `besave-site` | ✅ Killed (`S3-01: nenhum .tf configura website hosting`) |
| M26 | `infra/iam.tf` (novo recurso) | `aws_iam_user_login_profile` | ✅ Killed (`IAM-01: …`) |
| M01 | `infra/cloudfront.tf:222` | error response → 200 (regressão) | ✅ Killed (CF-09) |
| M05 | `infra/cloudfront.tf:142-165` | ordem `/ir/*` ↔ `/manifest.json` (regressão) | ✅ Killed (CF-02, CF-03) |
| M09 | `infra/cloudfront.tf:37` | sem associação KVS (regressão) | ✅ Killed (FN-07) |
| M17 | `infra/s3.tf:27` | lifecycle 7 → 30 (regressão) | ✅ Killed (S3-02) |
| M22 | `infra/iam.tf:15` | ação IAM extra (regressão) | ✅ Killed (IAM-02) |
| M23 | `infra/iam.tf:39` | `CreateInvalidation` em `*` (regressão) | ✅ Killed (IAM-03) |
| M30 | `infra/functions/redirect-afiliado.js:19` | regex sem âncora final (regressão) | ✅ Killed (FN-06) |
| M32 | `infra/functions/redirect-afiliado.js:12` | sem `no-store` (regressão) | ✅ Killed (FN-04/05/06) |
| M35 | `infra/static/404.html:6` | sem `noindex` (regressão) | ✅ Killed (CF-12) |

**Result**: 12/12 killed na iteração 1; acumulado: 36 mutantes distintos, todos mortos (M24/M25/M26 re-testados) - PASS ✅

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (um módulo raiz, recursos por serviço; `locals` mínimos) |
| Surgical changes | ✅ (só `infra/`, `docs/MANIFEST.md` §5 e `.specs/features/BSV-4/`; `ci.yml` não tocado, D-5) |
| No scope creep | ✅ (sem DNS da virada, sem backend remoto, sem popular KVS) |
| Matches patterns | ✅ (testes em `node:test` sem dependência nova; nomes em português como no resto) |
| Spec-anchored outcome check | ✅ (igualdades estruturais completas nas policies; TTLs, ordem e error responses literais) |
| Per-layer Coverage Expectation | ✅ Functions 1:1 com FN-01..06 + edge; Terraform cobre valores; ausências de IAM-01/S3-01 por inspeção textual dos `.tf` |
| Every test maps to a spec requirement | ✅ (todos os `assert` têm comentário FN/S3/CF/IAM/OPS) |
| Documented guidelines followed: `CLAUDE.md`, `docs/specs/BSV-4.md` | ✅ |

Observação (iteração 0): o design dizia `command = plan`, mas os testes usam `command = apply` com `mock_provider`. Alinhado em `805be99`: D-5 agora diz `command = apply`.

---

## Edge Cases

- [x] `rewrite-index` com `/a.b/c` → `/a.b/c/index.html` - `infra/functions/test/rewrite-index.test.mjs:19` (M28 morto)
- [x] `redirect-afiliado` com `/ir/` e `/ir/12/x` → 302 `/` - `infra/functions/test/redirect-afiliado.test.mjs:47-50`
- [ ] (sem teste, aceito) `/ir/12?utm=x` usa só o path: é garantido pelo runtime (`request.uri` não traz querystring; o evento de teste separa `querystring`, `infra/functions/test/carregar.mjs:17`). Não há lógica no código para testar.

---

## Gate Check

- **Gate command** (Build, `tasks.md`): em `infra/`: `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test`; em `infra/functions/`: `npm ci && npm test`
- **Terraform**: v1.16.4, provider `hashicorp/aws` v6.66.0. `fmt` limpo; `init` ok; `validate`: "Success! The configuration is valid."; `test`: **"Success! 5 passed, 0 failed."** (`acm`, `buckets`, `distribuicao_padrao`, `distribuicao_com_dominios`, `iam_e_outputs`)
- **Functions** (Node v24.21.0): `npm ci` "found 0 vulnerabilities"; `npm test`: **tests 14, pass 14, fail 0, skipped 0** (re-verificação, HEAD `805be99`; iteração 0: 12/12)
- **Terraform na iteração 1**: `fmt` limpo, `init` ok, `validate` ok, `test` "Success! 5 passed, 0 failed."
- **Test count before feature** (`1653949`): 0 (não havia `infra/`)
- **Test count after feature**: 5 runs Terraform (39 `assert`) + 14 testes `node:test` (iteração 1: +2, IAM-01 e S3-01)
- **Skipped tests**: nenhum
- **Failures**: nenhuma

---

## Fix Plans

> Status: Fix 1 e Fix 2 foram aplicados em `805be99` e verificados na iteração 1 (M24, M25, M26 mortos). Ficam abaixo como histórico.

### Fix 1: IAM-01 "sem console e sem access key" não é discriminado (M24, M26)

- **Root cause**: `infra/tests/iam.tftest.hcl:10` só afirma o nome do usuário. Uma ausência de recurso não aparece em nenhum atributo que `terraform test` inspecione.
- **Fix task**: em `infra/functions/test/sem-recursos-existentes.test.mjs` (já faz inspeção textual dos `.tf` para OPS-02), acrescentar um teste "IAM-01: nenhum .tf declara `aws_iam_access_key` nem `aws_iam_user_login_profile`" com `assert.doesNotMatch(src, /resource\s+"aws_iam_(access_key|user_login_profile)"/, f)`.
- **Verify**: re-rodar M24 e M26; os dois devem morrer.
- **Priority**: Major (credencial criada pelo Terraform iria parar no state local; é exatamente o que o ticket proíbe).

### Fix 2: S3-01 "sem website hosting" não é discriminado (M25)

- **Root cause**: nenhum teste prova a ausência de `aws_s3_bucket_website_configuration`.
- **Fix task**: no mesmo teste textual, `assert.doesNotMatch(src, /resource\s+"aws_s3_bucket_website_configuration"/, f)`. Opcional: afirmar a região em `infra/tests/buckets.tftest.hcl` (p.ex. `var.regiao == "us-east-1"`, ou `aws_s3_bucket.site.region == "us-east-1"` se o mock do provider v6 expõe o atributo).
- **Verify**: re-rodar M25; deve morrer.
- **Priority**: Minor.

---

## Spec-precision gaps

- Nenhum AC com resultado indefinido. Observações: CF-06/CF-07 só fixam o TTL **padrão** (min/máx vêm da tabela de Assumptions, `n`) e os testes afirmam só o padrão, o que está alinhado ao spec. Os 5 curls pós-apply (incluindo os dois do dono para AD-020) só podem ser confirmados pelo dono; o mapeamento estático para CF-09 + S3-03 + CF-05 está acima.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| FN-01..07 | Implemented | ✅ Verified |
| S3-01..04 | Implemented | ✅ Verified (S3-01: ausência de website hosting testada na iteração 1) |
| CF-01..12 | Implemented | ✅ Verified |
| IAM-01..03 | Implemented | ✅ Verified (IAM-01: ausência de console/access key testada na iteração 1) |
| OPS-01..04 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ PASS

**Spec-anchored check**: 30/30 ACs com evidência; 0 spec-precision gaps
**Sensor**: iteração 0 33/36; iteração 1 12/12 (M24/M25/M26 + 9 de regressão) → 0 sobreviventes
**Gate**: Terraform 5/5 runs; Functions 14/14

**What works**: Functions (rewrite e redirect com regex ancorada, `no-store`, KVS só para id decimal), behaviors na ordem e TTLs de MANIFEST §5, error responses AD-020 (403/404 → 404 `/404.html`, sem 200), OAC e policy do bucket exatas, IAM mínimo com igualdade estrutural, certificado/validação ACM, `ativar_dominios` nos dois estados, logs `cf/` com o formato certo de `bucket_domain_name`.

**Issues found**: nenhuma em aberto (as ausências de IAM-01 e S3-01 foram fechadas em `805be99`).

**Next steps**: o dono faz `apply`, roda os curls do README (incluindo `/nao-existe` e `/data/chunks/0-ffff.json.br`) e `test-function` da `redirect-afiliado`, e cola o `plan` no PR.
