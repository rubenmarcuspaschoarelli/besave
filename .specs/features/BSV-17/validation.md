# Validation: BSV-17 - PASS ✅

## Veredito: PASS ✅ (ciclo 2 de 3)

Todos os critérios de aceite da spec do dono (`docs/specs/BSV-17.md`) que dá para verificar offline estão
atendidos no código e afirmados por teste com o valor da spec. Gates verdes. Sensor: 47/47 mutantes mortos;
o sobrevivente do ciclo 1 (W7) agora morre, assim como 2 variantes dele. O que falta é a execução real do dono
(abaixo), que bloqueia o merge por regra do repositório, não por este relatório.

- **Data**: 2026-10-07
- **Verifier**: Verifier sub-agente independente, Claude Opus 5.5 (autor ≠ verificador; não escreveu código nem testes)
- **Spec do dono**: `docs/specs/BSV-17.md` · **EARS**: `.specs/features/BSV-17/spec.md`
- **Diff range**: `31a86f4..2fd9fd7` (5 commits: 5359044, d2549ca, 4180d48, 6c2d4a3, 2fd9fd7)

---

## Histórico de ciclos

| ciclo | HEAD | veredito | sensor | gaps |
|---|---|---|---|---|
| 1 | `6c2d4a3` | FAIL ❌ | 39/40 (W7 sobreviveu) | 1 teste anti-injeção não discriminava; 2 cache de fonte/favicon não afirmado; 3 `--delete` logo após a invalidação (risco); 4 stack trace com build ausente; 5 frase errada no README |
| 2 | `2fd9fd7` | PASS ✅ | 47/47 | 1, 2, 4, 5 fechados (ver abaixo); 3 vai ao PR como proposta para o dono |

Correções do ciclo 2 (commit `2fd9fd7`, só 4 arquivos: README, `publicar.mjs`, 2 testes; `site_deploy.tf`,
`tests/`, mocks e workflow sem mudança):

- **Gap 1** — `infra/functions/test/site-deploy-workflow.test.mjs:48`: `deepEqual` das linhas com `${{ inputs.` fora de comentário = `['COMMIT: ${{ inputs.commit }}']`. Mata W7, W7b, W7c.
- **Gap 2** — `infra/functions/test/deploy-site.test.mjs:129-137`: `--cache-control` de fonte e favicon = `public, max-age=3600, stale-while-revalidate=86400`. Mata F1, F2, F3.
- **Gap 4** — `infra/deploy-site/publicar.mjs:94-97` (`existsSync`) + teste `deploy-site.test.mjs:192-197` (exit 1, `build não encontrado`, sem `at …publicar.mjs` no stderr). Mata B1, B2.
- **Gap 5** — `infra/README.md:311`: "O job só roda em `main` (o `if` pula outros branches)". Correto (`site-deploy.yml:27`).

---

## Gate Check (em `2fd9fd7`)

| gate | comando | resultado |
|---|---|---|
| fmt | `cd infra && terraform fmt -check -recursive` | limpo |
| validate | `terraform init -backend=false && terraform validate` | `Success! The configuration is valid.` (Terraform 1.16.2, aws 6.66.0) |
| test | `terraform test` | **17 passed, 0 failed** (`site_deploy`: 1 run, 7 asserts) |
| node | `cd infra/functions && npm test` | **52 passed, 0 failed, 0 skipped** (ciclo 1: 51; antes da feature: 28 → +24) |
| workflow | `actionlint -shellcheck shellcheck.exe .github/workflows/site-deploy.yml` | exit 0, sem achados |

Nenhum teste removido ou enfraquecido: o único assert trocado (`site-deploy-workflow.test.mjs:48`) ficou mais
forte (de "não casa nesta linha" para "conjunto exato de ocorrências").

---

## Spec-Anchored Acceptance Criteria

### Critérios da spec do dono

| critério | valor da spec | código (`file:line`) | teste (`file:line` + asserção) | resultado |
|---|---|---|---|---|
| provedor OIDC com `client_id_list` certo | url `https://token.actions.githubusercontent.com`, `["sts.amazonaws.com"]` | `infra/site_deploy.tf:9-12` | `infra/tests/site_deploy.tftest.hcl:19-20` — `client_id_list == toset(["sts.amazonaws.com"])` | ✅ |
| confiança só em `main` deste repo, `aud = sts.amazonaws.com` | `repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`, `StringEquals` | `infra/site_deploy.tf:17-30` | `infra/tests/site_deploy.tftest.hcl:30-44` — `jsondecode(assume_role_policy) == {…}` literal | ✅ |
| sessão ≤ 1 h | `max_session_duration = 3600` | `infra/site_deploy.tf:16` | `infra/tests/site_deploy.tftest.hcl:26` | ✅ |
| Put/Delete exatamente nos 17 prefixos | `_app/*`, `index.html`, `404.html`, `favicon.*`, `desejos/*`, `assets/besave.css`, `assets/fontes/*` + 10 slugs do CONTRATO §2.3 | `infra/site_deploy.tf:39-44`, `infra/deploy-site/prefixos.json:1-19` | `infra/tests/site_deploy.tftest.hcl:7-11` (lista literal da spec, independente do JSON) e `:55-80` — igualdade da policy inteira; `infra/functions/test/deploy-site.test.mjs:35-42` | ✅ |
| `ListBucket` com `s3:prefix` nos mesmos | `StringLike s3:prefix` = os 17 | `infra/site_deploy.tf:45-51` | `infra/tests/site_deploy.tftest.hcl:64-70` | ✅ |
| `CreateInvalidation` só na distribuição do site | ARN de `aws_cloudfront_distribution.site` | `infra/site_deploy.tf:52-57` | `infra/tests/site_deploy.tftest.hcl:71-76` — ARN literal `…distribution/EEXEMPLO000000`; `curto` tem ARN distinto no mock (`ECURTO00000000`, `infra/tests/mocks/aws.tfmock.hcl:85-87`) → lição 11 respeitada (T7b) | ✅ |
| nada em prefixos do worker | sem `data/`, `oferta/`, `img/`, `manifest*`, `sitemap*`, `robots.txt`, `_estado/`, nem `*` | `infra/deploy-site/prefixos.json` | `infra/tests/site_deploy.tftest.hcl:87-95` | ✅ |
| `pnpm install --frozen-lockfile && pnpm build` em `apps/site` | literal | `.github/workflows/site-deploy.yml:70-74` | `site-deploy-workflow.test.mjs:27-29` | ✅ |
| `_app/` → `sync --delete`, `public, max-age=31536000, immutable` | literal | `publicar.mjs:10,50,66` | `deploy-site.test.mjs:75-105` | ✅ (desvio D1) |
| HTML → `public, max-age=300`, `text/html; charset=utf-8` | literal | `publicar.mjs:11,14,63` | `deploy-site.test.mjs:107-118` | ✅ |
| `assets/besave.css` → `public, max-age=3600, stale-while-revalidate=86400`, `text/css; charset=utf-8` | literal | `publicar.mjs:12,15,62` | `deploy-site.test.mjs:120-126` | ✅ |
| invalidação só HTML e `/assets/*`, nunca `/*` | literal | `publicar.mjs:55-56,64` | `deploy-site.test.mjs:139-156` — conjunto exato; `!includes('/*')` | ✅ |
| `--delete` só dentro de `_app/` | regra | `publicar.mjs:66` | `deploy-site.test.mjs:75-90` | ✅ |
| gatilho `workflow_dispatch` sempre; `push` em `main` + `paths: apps/site/**` só com `SITE_DEPLOY_ATIVO == 'true'` | literal | `site-deploy.yml:5-14,27` | `site-deploy-workflow.test.mjs:9-20` | ✅ |
| `AWS_ROLE_SITE` em variável; `us-east-1` | literal | `site-deploy.yml:36,82,85` | `site-deploy-workflow.test.mjs:22-25,31-34` | ✅ |
| ações `@v4` | 4 ações | `site-deploy.yml:43,65,67,80` | `site-deploy-workflow.test.mjs:36-41` | ✅ |
| nenhuma chave no GitHub; `id-token: write` | — | `site-deploy.yml:16-18` | `site-deploy-workflow.test.mjs:22-25` | ✅ |
| `actionlint` limpo | — | — | execução acima | ✅ |
| README: variável, ligar, rodar à mão, reverter | — | `infra/README.md` (seção "Deploy do site (BSV-17)") | leitura | ✅ |
| `plan` só com adições; `apply`; simulação; 1º deploy manual | — | — | **só a execução real do dono prova** | ⏳ |

### IDs EARS (`.specs/features/BSV-17/spec.md`)

| ID | evidência de teste | resultado |
|---|---|---|
| OIDC-01..03 | `site_deploy.tftest.hcl:18-51` | ✅ |
| POL-01..04 | `site_deploy.tftest.hcl:54-95` | ✅ |
| PUB-01 | `deploy-site.test.mjs:44-54` (12 intrusos), `:185-190` (CLI) | ✅ |
| PUB-02 | `deploy-site.test.mjs:56-62` | ✅ |
| PUB-03 | `deploy-site.test.mjs:75-90` | ✅ |
| PUB-04 | `deploy-site.test.mjs:92-105` | ✅ |
| PUB-05 | `deploy-site.test.mjs:107-118` | ✅ |
| PUB-06 | `deploy-site.test.mjs:120-126` | ✅ |
| PUB-07 | `deploy-site.test.mjs:139-156` | ✅ |
| PUB-08 | `deploy-site.test.mjs:177-183` | ✅ |
| WF-01..04, WF-06 | `site-deploy-workflow.test.mjs:9-41` + actionlint | ✅ |
| WF-05 | `site-deploy-workflow.test.mjs:43-49` (SHA, ancestral, só `apps/site`, input só via `env`) | ✅ |
| OPS-01 | `infra/README.md` | ✅ (leitura) |

### Fidelidade EARS × spec do dono (desvios registrados pelo autor como suposição; dono confirma no PR)

- **D1** `_app/version.json` com `public, max-age=300` em vez de imutável (nome fixo do SvelteKit).
- **D2** `--size-only` no sync de `_app/`; só seria problema com arquivo de nome fixo em `_app/` além de `version.json` (o build atual não tem).
- **D3** Ordem sync sem `--delete` → HTML → invalidação → sync com `--delete`.
- **D4** Variável `CF_DISTRIBUICAO_SITE` e output `id_distribuicao`.
- **D5** Reverter por input `commit` (só ancestral de `main`), porque a confiança é só `ref:refs/heads/main`.
- **D6** Cache de `favicon.*`/`assets/fontes/*` = o do CSS: a spec não define; agora fixado pela suposição do spec.md e afirmado (`deploy-site.test.mjs:129-137`). Fica como ⚠️ spec-precision para o dono confirmar o valor.

---

## Discrimination Sensor

Worktree temporário (`git worktree add --detach <scratchpad>/m2 2fd9fd7`), mutação textual, `git checkout -- .`
entre mutantes, worktree removido no fim. `git status --porcelain` da árvore real igual antes e depois (só o
próprio `validation.md`, não rastreado). Profundidade P0 (credencial e permissão em bucket compartilhado).
No ciclo 2 rodou o conjunto inteiro do ciclo 1 mais 7 mutantes novos.

| # | arquivo | mutação | testes | ciclo 1 | ciclo 2 |
|---|---|---|---|---|---|
| T1 | `prefixos.json` | + `"data/*"` | tf, npm | ✅ | ✅ |
| T2 | `prefixos.json` | + `"*"` | tf, npm | ✅ | ✅ |
| T3 | `prefixos.json` | − `"pets/*"` | tf, npm | ✅ | ✅ |
| T4 | `site_deploy.tf:26` | `refs/heads/main` → `refs/heads/*` | tf | ✅ | ✅ |
| T5 | `site_deploy.tf:26` | sub → `repo:…:*` | tf | ✅ | ✅ |
| T6 | `site_deploy.tf:16` | `max_session_duration = 7200` | tf | ✅ | ✅ |
| T7 | `site_deploy.tf:56` | Invalidar → `one(aws_cloudfront_distribution.curto[*].arn)` | tf | ✅ | ✅ |
| T7b | `site_deploy.tf:56` | Invalidar → `curto[0].arn` com `-var=ativar_curto=true` (ARNs distintos; lição 11) | tf | ✅ | — (arquivo sem mudança) |
| T8 | `site_deploy.tf:56` | Invalidar em `"*"` | tf | ✅ | ✅ |
| T9 | `site_deploy.tf:11` | `client_id_list = ["sigstore"]` | tf | ✅ | ✅ |
| T10 | `site_deploy.tf:50` | sem condição `s3:prefix` | tf | ✅ | ✅ |
| T11 | `site_deploy.tf:25` | sem condição `aud` | tf | ✅ | ✅ |
| T12 | `site_deploy.tf:43` | Put/Delete no bucket `logs` | tf | ✅ | ✅ |
| T13 | `site_deploy.tf:42` | + `s3:GetObject` | tf | ✅ | ✅ |
| J1 | `publicar.mjs:60` | `--delete` no primeiro sync | npm | ✅ | ✅ |
| J2 | `publicar.mjs:42` | sem checagem de prefixos | npm | ✅ | ✅ |
| J3 | `publicar.mjs:26` | `404.html` não obrigatório | npm | ✅ | ✅ |
| J4 | `publicar.mjs:63` | HTML com cache de 1 h | npm | ✅ | ✅ |
| J5 | `publicar.mjs:62` | CSS com cache de 300 s | npm | ✅ | ✅ |
| J6 | `publicar.mjs:10` | `_app` sem `immutable` | npm | ✅ | ✅ |
| J7 | `publicar.mjs:56` | invalidação inclui `/*` | npm | ✅ | ✅ |
| J8 | `publicar.mjs:60,66` | sync `--delete` antes do HTML | npm | ✅ | ✅ |
| J9 | `publicar.mjs:14` | HTML sem `charset=utf-8` | npm | ✅ | ✅ |
| J10 | `publicar.mjs:50` | sync com destino na raiz do bucket | npm | ✅ | ✅ |
| J11 | `publicar.mjs:30` | `*` não cruza `/` | npm | ✅ | ✅ |
| J12 | `publicar.mjs:56` | invalida também `/_app/*` | npm | ✅ | ✅ |
| J13 | `publicar.mjs:105` | `--ensaio` executa comandos | npm | ✅ | ✅ |
| W1 | `site-deploy.yml:27` | sem `vars.SITE_DEPLOY_ATIVO` | npm | ✅ | ✅ |
| W2 | `site-deploy.yml:82` | `vars.AWS_ROLE_SITE` → `secrets.` | npm | ✅ | ✅ |
| W3 | `site-deploy.yml:18` | sem `id-token: write` | npm | ✅ | ✅ |
| W4 | `site-deploy.yml:85` | `sa-east-1` | npm | ✅ | ✅ |
| W5 | `site-deploy.yml:27` | sem guarda `refs/heads/main` | npm | ✅ | ✅ |
| W6 | `site-deploy.yml:14` | push sem `paths` | npm | ✅ | ✅ |
| W7 | `site-deploy.yml:63` | `${{ inputs.commit }}` numa linha interna de `run: \|` | npm, actionlint | ❌ sobreviveu | ✅ morto |
| W7b | `site-deploy.yml:61` | `${{inputs.commit}}` (sem espaços) dentro do bloco `run` | npm, actionlint | — | ✅ morto |
| W7c | `site-deploy.yml:43` | `run: echo "${{ inputs.commit }}"` em linha única | npm, actionlint | — | ✅ morto |
| W8 | `site-deploy.yml:57-60` | sem checagem de ancestral | npm | ✅ | ✅ |
| W9 | `site-deploy.yml:43` | `checkout@v5` | npm | ✅ | ✅ |
| W10 | `site-deploy.yml:13` | push também em `develop` | npm | ✅ | ✅ |
| W11 | `site-deploy.yml:78` | ensaio sem `--ensaio` | npm | ✅ | ✅ |
| W12 | `site-deploy.yml:73` | `pnpm install` sem `--frozen-lockfile` | npm | ✅ | ✅ |
| F1 | `publicar.mjs:62` | fontes com cache de 300 s | npm | — | ✅ morto |
| F2 | `publicar.mjs:62` | favicon com cache de 300 s | npm | — | ✅ morto |
| F3 | `publicar.mjs:62` | fontes/favicon imutáveis por 1 ano | npm | — | ✅ morto |
| B1 | `publicar.mjs:94-97` | sem checagem do build (volta o stack trace) | npm | — | ✅ morto |
| B2 | `publicar.mjs:94` | checagem do build desligada (`if (false)`) | npm | — | ✅ morto |

**Resultado ciclo 2**: 47/47 mortos (T7b não reexecutado: `site_deploy.tf` e mocks iguais aos do ciclo 1) — PASS ✅.
O actionlint não mata nenhum mutante W (não trata `inputs.*` como não confiável); quem pega são os testes de leitura.

### Ensaio contra o build real (ciclo 1, `vite build` de `apps/site`)

O build atual traz `index.html`, `_app/version.json` e `_app/immutable/**`, sem `404.html`. O `publicar.mjs --ensaio`
responde `faltando no build: 404.html`, exit 1, sem comando — correto (MANIFEST §5) e documentado no README.
Com um `404.html` sintético a ordem sai como esperada (sync → `version.json` → `404.html` → `index.html` →
invalidação `/index.html /404.html /assets/*` → sync `--delete`).

---

## Code Quality

| princípio | status |
|---|---|
| Mínimo de código / sem escopo extra | ✅ (D2/D4/D5 justificados) |
| Mudanças cirúrgicas, só nas pastas da spec | ✅ |
| Nada muda na distribuição, bucket, worker, vigia | ✅ |
| Testes afirmam valor da spec (lista literal independente do JSON) | ✅ |
| Lição 11 (mocks distintos) | ✅ (`curto` ≠ `site`; `logs` ≠ `site`) |
| Line endings | ✅ índice em LF (`git ls-files --eol`) |
| Regra 7 (dependência nova) | ✅ nenhuma |
| Diretrizes: `CLAUDE.md`, `docs/WORKFLOW-AGENTES.md` §6 | ✅ |

---

## Gaps restantes (não bloqueiam este veredito)

1. **[Risco, decisão do dono — ex-gap 3]** `publicar.mjs:64-66`: `sync --delete` de `_app/` logo após uma invalidação
   assíncrona. Página antiga (até 300 s no navegador) pode pedir chunk já apagado numa falta de cache na borda → 404.
   Probabilidade baixa (borda guarda `_app/` por 1 ano, `immutable`). Proposta: apagar só o `_app/` de dois builds atrás,
   como os manifests do worker. Vai ao PR como proposta.
2. **[Spec-precision, D6]** valor de cache de fonte/favicon não está na spec; dono confirma.

---

## O que só a execução real do dono prova (bloqueia o merge)

- `terraform plan` real: só 3 adições (provedor OIDC, papel, policy), 0 change/destroy; `apply`.
- Que a conta não tem `token.actions.githubusercontent.com` (senão `EntityAlreadyExists` → `import`).
- `aws iam simulate-principal-policy`: `PutObject _app/x.js` → allowed; `DeleteObject manifest.json`,
  `oferta/1/index.html`, `data/chunks/x` → implicitDeny; `ListBucket` com `s3:prefix=data/` → implicitDeny.
- Que o `sub` do token num `workflow_dispatch` em `main` é `repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`
  (muda com template de `sub` customizado ou com `environment:`).
- Criar `AWS_ROLE_SITE` e `CF_DISTRIBUICAO_SITE`; primeiro deploy manual (`workflow_dispatch`) só depois da BSV-30
  (o build precisa trazer `404.html`); até lá `curl -s https://besave.com.br/` mostra a home provisória.
- `plan` e log do workflow manual colados no PR com ARNs `REDACTED` (regra 11).
- CI do GitHub rodou de fato no PR (lição 12).

---

## Requirement Traceability Update

| Requirement | Ciclo 1 | Ciclo 2 |
|---|---|---|
| OIDC-01..03, POL-01..04, PUB-01..08, WF-01..04, WF-06, OPS-01 | ✅ Verified | ✅ Verified |
| WF-05 | ❌ Needs Fix | ✅ Verified |

## Summary

**Overall**: ✅ Ready para o PR (merge bloqueado só pela execução real do dono)
**Spec-anchored check**: 21/21 ACs verificáveis offline com valor da spec; 1 spec-precision (D6, agora afirmado); plan/apply/simulação/deploy só na execução real
**Sensor**: 47/47 mortos (ciclo 1: 39/40)
**Gate**: terraform test 17/17, npm test 52/52, actionlint limpo, fmt/validate limpos
