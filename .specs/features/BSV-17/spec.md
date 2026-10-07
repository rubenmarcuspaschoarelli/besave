# BSV-17 Specification — publicação do site pelo GitHub Actions (OIDC)

Fonte: `docs/specs/BSV-17.md`. Pasta: `infra/` + `.github/workflows/site-deploy.yml`.

## Problem Statement

O site SvelteKit (`apps/site`) não tem deploy. O bucket `besave-site` é compartilhado com o worker; um deploy
errado do site não pode apagar dados, ofertas, imagens, sitemap nem `_estado/`. Não pode haver chave de acesso
guardada no GitHub.

## Goals

- [ ] Merge em `main` que mexa em `apps/site/**` publica o site, com credencial temporária (OIDC)
- [ ] Papel restrito aos prefixos do site: nem um script errado apaga fora deles
- [ ] Deploy automático desligado até o dono ligar `SITE_DEPLOY_ATIVO`

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Preview por PR, homologação | spec |
| Deploy do worker; o worker deixar de publicar `assets/besave.css` (AD-078) | spec: nada muda no worker |
| Desligar o protótipo | spec |
| Rodar `actionlint` no `ci.yml` | spec pede validação local; `ci.yml` fora da pasta |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Fonte única dos prefixos | `infra/deploy-site/prefixos.json`, lido pelo Terraform (policy) e pelo script de publicação | lista igual nas duas travas; os testes têm a lista literal da spec, independente do arquivo | n |
| Lógica do deploy | script Node `infra/deploy-site/publicar.mjs` chamado pelo workflow, com `--ensaio` | testável sem AWS; o YAML fica só com a orquestração | n |
| ID da distribuição para a invalidação | variável do repositório `CF_DISTRIBUICAO_SITE` + output `id_distribuicao` | o papel não pode listar distribuições; spec não nomeia | n |
| `thumbprint_list` do provedor OIDC | omitido | opcional no provedor AWS 6.66 (schema conferido); a AWS valida o GitHub pela CA | n |
| `_app/version.json` (SvelteKit, nome fixo) | fora do sync imutável; `public, max-age=300`, `application/json` | nome sem hash com `immutable` congelaria a versão por 1 ano | n |
| Ordem do `--delete` em `_app/` | sync sem `--delete` primeiro, HTML, invalidação, e só no fim o sync com `--delete` | HTML novo nunca aponta para chunk ainda não enviado; o antigo some por último | n |
| `--size-only` no sync de `_app/` | sim | nomes com hash: mesmo nome = mesmo conteúdo; evita reenviar tudo a cada build | n |
| Cache de `favicon.*` e `assets/fontes/*` | `public, max-age=3600, stale-while-revalidate=86400` (igual ao CSS) | spec não define; nomes sem hash | n |
| Arquivo do build fora dos prefixos | o script falha antes de qualquer upload | a policy negaria no meio do deploy, deixando-o pela metade | n |
| `index.html` e `404.html` ausentes no build | falha | MANIFEST §5: o deploy sempre publica `/404.html` | n |
| Invalidação | `/index.html`, `/404.html`, `/{dir}/*` de cada diretório com HTML, `/assets/*`; nunca `/*` | wildcard conta como 1 caminho (1.000 grátis/mês); a chave de cache é a URI reescrita (`/x/index.html`) | n |
| Reverter | `workflow_dispatch` em `main` com input `commit`; só commit ancestral de `main`; script e workflow sempre do HEAD | a confiança é `ref:refs/heads/main`: rodar o workflow em outro ref falha no STS | n |
| Versões das ações | `@v4` (spec e `ci.yml`); há majors mais novas (checkout v7, setup-node v7, pnpm v6, configure-aws-credentials v6) | conferido via API do GitHub em 07/10/2026; atualização fica proposta no PR | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: OIDC e papel ⭐ MVP

1. OIDC-01: The Terraform SHALL criar `aws_iam_openid_connect_provider` com `url = https://token.actions.githubusercontent.com` e `client_id_list = ["sts.amazonaws.com"]`
2. OIDC-02: The Terraform SHALL criar o papel `besave-site-deploy` com `max_session_duration = 3600`, confiança `Federated` no provedor OIDC, ação `sts:AssumeRoleWithWebIdentity` e `StringEquals` em `aud = sts.amazonaws.com` e `sub = repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`
3. OIDC-03: The Terraform SHALL expor `arn_papel_site_deploy` e `id_distribuicao` como outputs

### P1: Policy mínima ⭐ MVP

1. POL-01: The policy SHALL permitir `s3:PutObject` e `s3:DeleteObject` só em `besave-site/` + `_app/*`, `index.html`, `404.html`, `favicon.*`, `desejos/*`, `assets/besave.css`, `assets/fontes/*` e `{slug}/*` dos 10 slugs (tech, players, meu-lar, elas, eles, cultura, familia, pets, esporte-vida, outros)
2. POL-02: The policy SHALL permitir `s3:ListBucket` no bucket só com `StringLike s3:prefix` nesses mesmos prefixos
3. POL-03: The policy SHALL permitir `cloudfront:CreateInvalidation` só na distribuição do site
4. POL-04: The policy SHALL não ter nenhum recurso ou prefixo em `data/`, `oferta/`, `img/`, `manifest*.json`, `sitemap*`, `robots.txt`, `_estado/`, nem `besave-site/*`

### P1: Publicação ⭐ MVP

1. PUB-01: IF algum arquivo do build está fora dos prefixos THEN o script SHALL falhar sem nenhum comando AWS
2. PUB-02: IF `index.html` ou `404.html` faltam no build THEN o script SHALL falhar sem nenhum comando AWS
3. PUB-03: The script SHALL usar `--delete` só em `aws s3 sync` com destino `s3://{bucket}/_app/`, depois dos uploads de HTML e da invalidação
4. PUB-04: The script SHALL enviar `_app/` com `public, max-age=31536000, immutable` (exceto `_app/version.json`: `public, max-age=300`)
5. PUB-05: The script SHALL enviar cada HTML com `public, max-age=300` e `text/html; charset=utf-8`, por arquivo
6. PUB-06: The script SHALL enviar `assets/besave.css` com `public, max-age=3600, stale-while-revalidate=86400` e `text/css; charset=utf-8`
7. PUB-07: The script SHALL criar uma invalidação só com caminhos de HTML e `/assets/*`, nunca `/*`
8. PUB-08: WHEN `--ensaio` the script SHALL imprimir os comandos sem executá-los

### P1: Workflow ⭐ MVP

1. WF-01: The workflow SHALL rodar em `workflow_dispatch` sempre e em `push` em `main` com `paths: apps/site/**` só WHILE `vars.SITE_DEPLOY_ATIVO == 'true'`
2. WF-02: The workflow SHALL rodar só em `refs/heads/main`, com `permissions` `id-token: write` e `contents: read`, sem nenhum segredo
3. WF-03: The workflow SHALL compilar com `pnpm install --frozen-lockfile && pnpm build` em `apps/site`
4. WF-04: The workflow SHALL assumir `vars.AWS_ROLE_SITE` em `us-east-1` com `aws-actions/configure-aws-credentials@v4`
5. WF-05: WHERE o input `commit` é dado the workflow SHALL publicar `apps/site` desse commit, só se ele for ancestral de `main`
6. WF-06: The workflow SHALL passar no `actionlint`

### P2: README

1. OPS-01: The README SHALL explicar: criar as variáveis, ligar o deploy, rodar à mão, reverter e simular o papel (`simulate-principal-policy`)

---

## Edge Cases

- IF o build traz `robots.txt` (ex.: `static/` do SvelteKit) THEN PUB-01 SHALL barrar
- IF o input `commit` não é SHA ancestral de `main` THEN o workflow SHALL falhar antes do build

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| OIDC-01 | P1: OIDC | Execute | Implemented |
| OIDC-02 | P1: OIDC | Execute | Implemented |
| OIDC-03 | P1: OIDC | Execute | Implemented |
| POL-01 | P1: Policy | Execute | Implemented |
| POL-02 | P1: Policy | Execute | Implemented |
| POL-03 | P1: Policy | Execute | Implemented |
| POL-04 | P1: Policy | Execute | Implemented |
| PUB-01 | P1: Publicação | Execute | Implemented |
| PUB-02 | P1: Publicação | Execute | Implemented |
| PUB-03 | P1: Publicação | Execute | Implemented |
| PUB-04 | P1: Publicação | Execute | Implemented |
| PUB-05 | P1: Publicação | Execute | Implemented |
| PUB-06 | P1: Publicação | Execute | Implemented |
| PUB-07 | P1: Publicação | Execute | Implemented |
| PUB-08 | P1: Publicação | Execute | Implemented |
| WF-01 | P1: Workflow | Execute | Implemented |
| WF-02 | P1: Workflow | Execute | Implemented |
| WF-03 | P1: Workflow | Execute | Implemented |
| WF-04 | P1: Workflow | Execute | Implemented |
| WF-05 | P1: Workflow | Execute | Implemented |
| WF-06 | P1: Workflow | Execute | Implemented |
| OPS-01 | P2: README | Execute | Implemented |

**Coverage:** 22 total, 22 mapped, 0 unmapped

---

## Success Criteria

- [ ] `terraform fmt/validate/test` limpos; `npm test` (infra/functions) verde; `actionlint` limpo
- [ ] Real (dono): `plan` só com adições; `apply`; simulação do papel; primeiro deploy manual depois da BSV-30
