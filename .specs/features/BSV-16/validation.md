# BSV-16 Validation

## Validation: BSV-16 - PASS

**Date**: 2026-10-03
**Spec**: `.specs/features/BSV-16/spec.md` (fonte: `docs/specs/BSV-16.md`), 30 ACs
**Diff range**: `3941d63..fb1c2cd` (base `origin/develop`; 13 commits, 59cf316..fb1c2cd; 24 arquivos, +1488/-44)
**Ciclo**: 3 de 3. Ciclo 1: FAIL por mutante T16. Ciclo 2: PASS depois da correção T7. Ciclo 3: revisão do dono, T8–T12 (acd3b04..fb1c2cd).
**Verifier**: sub-agente independente (autor ≠ verificador)
**Result**: PASS — 30/30 ACs com evidência, gate verde, 26/26 mutantes do ciclo 3 mortos. O critério **Real (dono)** continua pendente: é do dono, fora do alcance do Verifier.

---

## Task Completion

| Task | Commit | Status |
| ---- | ------ | ------ |
| T1 link-curto | 59cf316 | ✅ Done |
| T2 www → apex | 2d2ec86 | ✅ Done |
| T3 páginas provisórias | e7a435a | ✅ Done |
| T4 registros + vigia | afe42be | ✅ Done |
| T5 domínios curtos | 880f928 | ✅ Done |
| T6 README | 9a60413 | ✅ Done |
| T7 fix CUR-06 (ciclo 1) | 708a6b8 | ✅ Done |
| T8 passo 0 com Functions temporárias | acd3b04 | ✅ Done |
| T9 `prevent_destroy` em registros e zonas | 4883b86 | ✅ Done |
| T10 canal da marca nas páginas | f7833d3 | ✅ Done |
| T11 query codificada no Conferir | 16f4ab1 | ✅ Done |
| T12 certificado validado no site | fb1c2cd | ✅ Done |

`tasks.md` sem caixas abertas. 350ddb0 só registra o relatório do ciclo 2.

---

## Spec-Anchored Acceptance Criteria

Legenda: 🆕 = AC novo no ciclo 3; ✏️ = AC reescrito no ciclo 3; demais = inalterados, reconferidos em fb1c2cd.

### P1: Virada

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| VIR-01 | A+AAAA de `besave.com.br` e `www`, zona do domínio, alias para a distribuição nova, `allow_overwrite` | `infra/tests/dominios.tftest.hcl:31` conjunto `"name type"` exato; `infra/tests/dominios.tftest.hcl:37` zona, `allow_overwrite`, alias name/zone_id da distribuição do site | ✅ |
| VIR-02 | `false` → nenhum A/AAAA | `infra/tests/dominios.tftest.hcl:11` `length(aws_route53_record.site) == 0` | ✅ |
| VIR-03 | `URL_MANIFEST = https://besave.com.br/manifest.json` | `infra/tests/dominios.tftest.hcl:47` igualdade literal | ✅ |
| VIR-04 | `URL_MANIFEST` no `*.cloudfront.net` | `infra/tests/dominios.tftest.hcl:17` `== "https://${...site.domain_name}/manifest.json"` | ✅ |
| 🆕 VIR-05 | `aws_route53_record.site` com `prevent_destroy = true` | `infra/tests/dominios.tftest.hcl:60` `output.prevent_destroy["aws_route53_record.site"]` (inspeção da fonte, `infra/tests/inspecao/main.tf:26`); código `infra/dominios.tf:25` | ✅ |
| 🆕 VIR-06 | distribuição principal usa o ARN de `aws_acm_certificate_validation.site` (leitura do código) | `infra/tests/cloudfront.tftest.hcl:188` `output.certificado_validado["aws_cloudfront_distribution.site"]` (`infra/tests/inspecao/main.tf:42`); valor em `infra/tests/cloudfront.tftest.hcl:171` | ✅ |

### P1: `www` → domínio sem www

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| WWW-01 | 301, `location = https://besave.com.br/oferta/1/?a=1` | `infra/functions/test/rewrite-index.test.mjs:41-43` status, location, cache-control; edges: maiúsculas e chave repetida `:50`; valor codificado `a%20b%26c` sem recodificar `:67` | ✅ |
| WWW-02 | sem query, sem `?` | `infra/functions/test/rewrite-index.test.mjs:56` `=== 'https://besave.com.br/'` | ✅ |
| WWW-03 | sem www: FN-01..03 intactos | `infra/functions/test/rewrite-index.test.mjs:61-62`; FN-01..03 `:8-27` | ✅ |

### P1: Domínios curtos

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| CUR-01 | zonas `besave.io`, `besave.me` sempre | `infra/tests/curto.tftest.hcl:11` | ✅ |
| CUR-02 | output com 4 NS de cada zona | `infra/tests/curto.tftest.hcl:17` | ✅ |
| CUR-03 | `false` → sem cert, validação, Function, distribuição, A/AAAA | `infra/tests/curto.tftest.hcl:24` (6 × `length == 0`) | ✅ |
| CUR-04 | cert `besave.io` + 3 SANs, DNS, `prevent_destroy` | `infra/tests/curto.tftest.hcl:40`; `infra/tests/curto.tftest.hcl:135` | ✅ |
| CUR-05 | 1 registro de validação por nome, na zona do domínio | `infra/tests/curto.tftest.hcl:48`, `:57`, `:64` | ✅ |
| CUR-06 | 4 aliases, cert validado, `sni-only`, `TLSv1.2_2021`, origem `besave.com.br`, `link-curto` viewer-request, logs `curto/` | `infra/tests/curto.tftest.hcl:78`, `:82`, `:89`, `:95`, `:101`; "validado" pela fonte em `infra/tests/curto.tftest.hcl:147` | ✅ |
| CUR-07 | A+AAAA dos 4 nomes, zona certa, alias para a distribuição curta | `infra/tests/curto.tftest.hcl:108`, `:116`, `:122` | ✅ |
| CUR-08 | `cloudfront-js-2.0`, `publish`, código do arquivo | `infra/tests/curto.tftest.hcl:70` | ✅ |
| 🆕 CUR-09 | `aws_route53_zone.curto` com `prevent_destroy = true` | `infra/tests/curto.tftest.hcl:141` `output.prevent_destroy["aws_route53_zone.curto"]`; código `infra/curto.tf:21` | ✅ |

### P1: Function `link-curto` (helper `infra/functions/test/link-curto.test.mjs:16-20`: status 301, `location` exato, `Cache-Control`)

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| LNK-01 | `/5412`, `/5412/`, `/05412` → `/oferta/5412/` | `infra/functions/test/link-curto.test.mjs:23-27` | ✅ |
| LNK-02 | `/5412/ir` → `/ir/5412` | `infra/functions/test/link-curto.test.mjs:31-32` | ✅ |
| LNK-03 | query anexada | `infra/functions/test/link-curto.test.mjs:36-41`; chave repetida `:46`; valor codificado repassado sem recodificar `:58` | ✅ |
| LNK-04 | `/`, não dígitos, > 12 dígitos, id zero → home | `infra/functions/test/link-curto.test.mjs:50-51` | ✅ |
| LNK-05 | sempre 301 + `public, max-age=86400` | `infra/functions/test/link-curto.test.mjs:17`, `:19` | ✅ |

### P2: Páginas

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| ✏️ PAG-01 | index: nome, "site em construção", `href="https://t.me/besaveofertas"` | `infra/functions/test/pagina-404.test.mjs:19-21` | ✅ |
| ✏️ PAG-02 | 404: `noindex`, texto, links `/` e `https://t.me/besaveofertas` | `infra/functions/test/pagina-404.test.mjs:15`, `:25-27` | ✅ |
| PAG-03 | 404 sem link de área | `infra/functions/test/pagina-404.test.mjs:31`; conjunto exato de links `:33` (`['/', CANAL]`) | ✅ |
| ✏️ PAG-04 | único link Telegram = `t.me/besaveofertas`; sem telefone nem `{CANAL_TELEGRAM}` | `infra/functions/test/pagina-404.test.mjs:38` (lista de ocorrências `t.me/…` == `['t.me/besaveofertas']`, inclusive em texto/comentário), `:39`, `:40` | ✅ |

### P2: README (leitura; sem teste automatizado, camada "none" na matriz)

| AC | Spec-defined outcome | Evidência | Result |
| -- | -------------------- | --------- | ------ |
| OPS-01 | roteiro, upload, custos, reverter | `infra/README.md:213-228` (passos 0–5 = 6 passos), `infra/README.md:257-266` upload, `infra/README.md:270` custos, `infra/README.md:278` reverter | ✅ |
| 🆕 OPS-02 | passo 0 antes de qualquer `apply`: `create-function` (`cloudfront-js-2.0`), `test-function` DEVELOPMENT com `functions/eventos/`, `delete-function`; upload no passo 1 | `infra/README.md:213` passo 0; função `testar_function` em `infra/README.md:86-96` (create → test DEVELOPMENT → delete); upload no passo 1 `infra/README.md:216` | ✅ |
| 🆕 OPS-03 | Conferir com `curl -I` `%20`/`%26` em `besave.io` e `www`, `location` mantendo `%20`/`%26`; não afirmar que o `test-function` prova a query | `infra/README.md:239-242`; ressalva sobre o evento sintético no fim da seção Testes e logo após o bloco Conferir | ✅ |

**Status**: ✅ 30/30 ACs com evidência `file:line`; cada asserção mira o valor definido na spec.

---

## Edge Cases

- [x] `Host: WWW.Besave.com.br` → mesmo 301 (`infra/functions/test/rewrite-index.test.mjs:46-50`)
- [x] Chave repetida preservada (`infra/functions/test/link-curto.test.mjs:44-46`, `infra/functions/test/rewrite-index.test.mjs:46-50`)
- [x] Valor já codificado repassado sem recodificar nem decodificar (`infra/functions/test/link-curto.test.mjs:57-58`, `infra/functions/test/rewrite-index.test.mjs:65-67`). O teste fixa a premissa; só o `curl` real (OPS-03) prova como o CloudFront entrega o valor.

---

## Discrimination Sensor (ciclo 3)

Cópia isolada: `git worktree add --detach` em diretório temporário do scratchpad, em fb1c2cd, com cópia de `infra/.terraform`. Cada mutação foi revertida com `git checkout -- <arquivo>` antes da próxima.

### Node (`cd functions && npm test`)

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| N1 | `infra/functions/link-curto.js:9` | `encodeURIComponent` no valor | ✅ LNK-03 edge (codificado) |
| N2 | `infra/functions/rewrite-index.js:7` | `encodeURIComponent` no valor | ✅ WWW-01 edge (codificado) |
| N3 | `infra/functions/link-curto.js:9` | `decodeURIComponent` no valor | ✅ LNK-03 edge |
| N4 | `infra/functions/link-curto.js:9` | perde o valor (`chave=`) | ✅ LNK-03 (3 testes) |
| N5 | `infra/functions/link-curto.js:8` | só a primeira ocorrência (ignora `multiValue`) | ✅ LNK-03 edge (repetida) |
| N6 | `infra/functions/rewrite-index.js:7` | perde o valor | ✅ WWW-01 (3 testes) |
| N7 | `infra/functions/rewrite-index.js:6` | só a primeira ocorrência | ✅ WWW-01 edge |
| N8 | `infra/static/index.html:12` | segundo link `t.me/joinchat/...` | ✅ PAG-04 |
| N9 | `infra/static/404.html:14` | segundo `t.me/outrocanal` só em texto | ✅ PAG-04 |
| N10 | `infra/static/404.html:12` | marcador `{CANAL_TELEGRAM}` de volta no link | ✅ PAG-02, PAG-03, PAG-04 |
| N11 | `infra/static/index.html:9` | marcador de volta só no comentário | ✅ PAG-04 |
| N12 | `infra/static/404.html:12` | 404 sem o parágrafo/link do canal | ✅ PAG-02, PAG-03, PAG-04 |
| N13 | `infra/static/index.html:12` | canal errado (`besave_ofertas`) | ✅ PAG-01, PAG-04 |
| N14 | `infra/static/404.html:12` | link do canal sem `https://` | ✅ PAG-02, PAG-03 |

### Terraform (`terraform test -filter=...`)

| # | File:line | Mutação | Killed? |
| - | --------- | ------- | ------- |
| T20 | `infra/dominios.tf:25` | remove o bloco `lifecycle { prevent_destroy }` dos registros | ✅ `dominios_protecao` |
| T20b | `infra/dominios.tf:25` | `prevent_destroy = false` | ✅ `dominios_protecao` |
| T21 | `infra/curto.tf:21` | zonas curtas sem `prevent_destroy` | ✅ `curto_protecao` |
| T22 | `infra/cloudfront.tf:242` | site com ARN direto de `aws_acm_certificate.site` (T19 dos ciclos anteriores) | ✅ `certificado_validado` |
| T16 | `infra/curto.tf:119` | curto com ARN direto do certificado (regressão) | ✅ `curto_protecao` |
| T3 | `infra/curto.tf:35` | certificado curto sem `prevent_destroy` (regressão, mesmo run) | ✅ `curto_protecao` |

**Sensor depth**: expandido (DNS e links permanentes). **Result**: 20/20 mortos no ciclo 3. Nos ciclos 1–2: 36 + 6 mutações. O único sobrevivente que resta é T16c, adversarial (lacuna G6).

**Isolamento**: `git status --porcelain` da árvore real vazio antes e depois do sensor. A worktree foi desregistrada (`git worktree remove --force` + `prune`) e o diretório temporário (o `.terraform` passa de MAX_PATH) foi apagado com `rd /s /q` usando o prefixo de caminho longo.

---

## Gate Check

- **Gate command** (em `infra/`): `terraform fmt -check -recursive && terraform init -backend=false && terraform validate && terraform test && python -m unittest discover -s lambdas/vigia && cd functions && npm test`
- **Result (fb1c2cd)**: fmt OK; validate "Success! The configuration is valid."; `terraform test` **16 passed, 0 failed**; vigia **35 OK**; Node **28 pass, 0 fail, 0 skipped**.
- **Contagem antes (3941d63, develop)**: Node 14, runs Terraform 9.
- **Contagem depois**: Node 28, runs Terraform 16.
- **Delta**: +14 Node (15 novos; 1 removido, "CF-12 links das 9 áreas", contrariado por PAG-03 por decisão da spec) e +7 runs Terraform.
- **Skipped / failures**: nenhum.

---

## Revisão do README (roteiro 0–5 e reversão)

| Ponto | Verificação contra o código | Resultado |
| ----- | --------------------------- | --------- |
| Passo 0 `testar_function` | `create-function` com `Runtime: cloudfront-js-2.0` → ETag → `test-function --stage DEVELOPMENT --if-match` → `delete-function --if-match` (`infra/README.md:86-96`). Não publica nada e roda antes do `apply` que põe `rewrite-index` (`publish = true`) no ar. Eventos `infra/functions/eventos/*.json` com host/query coerentes com os testes Node | ✅ coerente |
| Passo 1 plano "2 adições + 1 in-place, 0 destroy" | zonas (`infra/curto.tf:13`) + `rewrite-index` alterado; registros e Function curta gated (`infra/dominios.tf:4`, `infra/curto.tf`) | ✅ coerente (premissa G2) |
| Passo 2 virada | `ativar_dominios = true`: aliases + cert na distribuição, 4 registros com `allow_overwrite`, `URL_MANIFEST` no domínio | ✅ |
| Passo 4 fase 2 curta | cert + validação + Function + distribuição + 8 registros, todos gated por `ativar_curto` | ✅ |
| Reverter domínio | `terraform state rm 'aws_route53_record.site'` vem **antes** de `ativar_dominios = false`. Sem ele, o plano tentaria destruir os registros e o `prevent_destroy` (`infra/dominios.tf:25`) o recusaria. Com o `state rm`, os registros saem do state sem ser apagados, e o `apply` só mexe na distribuição e no vigia. `aws_acm_certificate.site` não depende de `ativar_dominios` e não entra no plano | ✅ funciona |
| Reverter curtos | `ativar_curto = false` falha no plano pelo `prevent_destroy` do certificado (`infra/curto.tf:35`); o README manda remover o `prevent_destroy` num commit explícito. As zonas (`infra/curto.tf:21`) não dependem de `ativar_curto` e continuam | ✅ funciona |

Pontos menores de redação (G8, não bloqueiam):
- `infra/README.md:189` ainda diz que "um `apply` sem elas volta para `false` e desfaz a virada". Com os `prevent_destroy` de T9, esse `apply` **falha no plano**, tanto pelos registros quanto pelo certificado curto. O conselho de gravar em `terraform.tfvars` continua válido; só a consequência descrita ficou desatualizada.
- `infra/README.md:286`: "Para refazer a virada depois, basta `ativar_dominios = true`". Antes disso é preciso tirar de novo os aliases da distribuição do protótipo, como no passo 2: CloudFront recusa o mesmo CNAME em duas distribuições (AD-021).

---

## Lacunas

Falhas de código: **nenhuma**. G2–G5 são premissas ou pendências **do dono**, não falhas do código.

1. **G1 — resolvida no ciclo 2** (708a6b8, antigo c8830c5): CUR-06 "validado" afirmado pela fonte.
2. **G2 (premissa do dono)**: "`plan` da fase 1 só com adições" fica, na prática, em 2 adições + 1 in-place (`rewrite-index`). Registrado em `.specs/features/BSV-16/spec.md:33` e no README (passo 1). O dono aceita ao colar o `plan`.
3. **G3 (pendência do dono)**: critério Real — `testar_function` (passo 0), `curl` do Conferir (incluindo `%20`/`%26`, única prova da codificação da query), `lambda invoke` do vigia, prévia no Telegram e `plan` das duas fases colado com IDs e ARNs como `REDACTED`.
4. **G4 (premissa do dono / observação)**: o 301 do `www` só existe nos behaviors com `rewrite-index` (`/oferta/*` e default). Em `www`, `/manifest.json`, `/data/*` e `/img/*` respondem 200, conforme a spec.
5. **G5 — resolvida no ciclo 3** (4883b86): zonas curtas com `prevent_destroy` (CUR-09).
6. **G6 (menor, teste)**: a inspeção textual remove só comentários de linha inteira, então um comentário no fim da linha citando `aws_acm_certificate_validation.` engana `certificado_validado` (mutante adversarial T16c, ciclo 2). Sugestão opcional: remover também `#…` no fim da linha em `infra/tests/inspecao/main.tf`.
7. **G7 — resolvida no ciclo 3** (fb1c2cd): VIR-06 cobre a distribuição principal (antigo T19, agora T22, morto).
8. **G8 (menor, README)**: as duas frases desatualizadas da seção acima.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ só `infra/` e `.specs/features/BSV-16/` |
| No scope creep | ✅ |
| Matches patterns | ✅ `prevent_destroy` + `tests/inspecao`, como em `acm.tf` |
| Spec-anchored outcome check | ✅ |
| Every test maps to a spec requirement | ✅ |
| Regra 11 (evidência sem segredo) | ✅ este relatório não traz caminho de usuário, ARN nem token; o canal `t.me/besaveofertas` é público por decisão do dono (PAG-01) |

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| VIR-01..06, WWW-01..03, CUR-01..09, LNK-01..05, PAG-01..04, OPS-01..03 | Implemented | ✅ Verified (mocks/Node/leitura); Real (dono) pendente |

---

## Summary

**Overall**: ✅ Ready para PR. O merge depende do critério **Real (dono)** (G3).

**Spec-anchored check**: 30/30 ACs
**Sensor**: ciclo 3 com 20/20 mortos
**Gate**: Terraform 16/16, vigia 35/35, Node 28/28

**Lições propostas** (o dono move para `docs/DECISOES.md`; não gravadas em LESSONS):
1. Quando mock e AWS devolvem o mesmo valor para dois recursos (ARN do certificado e da validação), uma asserção por valor não prova a dependência. Prove a referência pela fonte (`tests/inspecao`).
2. Ao adicionar `prevent_destroy`, revise no mesmo commit todo texto do README que descreve o efeito de desligar a variável (G8).
3. No Windows, a cópia de `.terraform` numa worktree temporária passa de MAX_PATH no `git worktree remove`. Apague o diretório com o prefixo de caminho longo.
