# BSV-17 · Infra: publicação do site pelo GitHub Actions (OIDC, sem chave guardada)

**Papel:** DevOps · **Pasta:** `infra/` + `.github/workflows/site-deploy.yml` · **Depende de:** BSV-4, BSV-16.
MANIFEST.md §1, §4, §5; AD-046, AD-060, AD-072

## Contexto
O site SvelteKit (`apps/site`) vai substituir a home e a 404 provisórias. Hoje não há deploy. `main` é
produção (AD-060). O bucket `besave-site` é compartilhado com o worker, que publica dados, ofertas,
imagens, sitemap e `_estado/`; um deploy errado do site não pode apagar nada disso.

## Objetivo
A cada merge em `main` que mexa em `apps/site/**`, o GitHub Actions compila o site e publica só os
arquivos do site, com credencial temporária (OIDC) e permissão restrita aos prefixos do site.

## Entregáveis
1. **Terraform:** provedor OIDC `token.actions.githubusercontent.com` (não existe na conta); papel
   `besave-site-deploy` com confiança só em `repo:rubenmarcuspaschoarelli/besave:ref:refs/heads/main`
   (`aud = sts.amazonaws.com`); sessão de no máximo 1 h.
2. **Policy mínima** do papel:
   - `s3:PutObject`, `s3:DeleteObject` só em: `_app/*`, `index.html`, `404.html`, `favicon.*`,
     `desejos/*`, `assets/besave.css`, `assets/fontes/*`, e `{slug}/*` dos 10 slugs de área (CONTRATO §2.3).
   - `s3:ListBucket` com condição `s3:prefix` nesses mesmos prefixos.
   - `cloudfront:CreateInvalidation` só na distribuição do site.
   - Nada em `data/`, `oferta/`, `img/`, `manifest*.json`, `sitemap*`, `robots.txt`, `_estado/`.
3. **Workflow `site-deploy.yml`:** `pnpm install --frozen-lockfile && pnpm build` em `apps/site`; depois:
   - `_app/` → `aws s3 sync --delete`, `public, max-age=31536000, immutable`;
   - HTML (`index.html`, `404.html`, `desejos/`, páginas de área) → `public, max-age=300`,
     `text/html; charset=utf-8`;
   - `assets/besave.css` → `public, max-age=3600, stale-while-revalidate=86400`, `text/css; charset=utf-8`;
   - invalidação só dos caminhos HTML e de `/assets/*` (nunca `/*`).
   - **Gatilho:** `workflow_dispatch` sempre; `push` em `main` com `paths: apps/site/**` **só quando a
     variável do repositório `SITE_DEPLOY_ATIVO == 'true'`** (o dono liga quando a BSV-30 estiver
     aprovada; antes disso, um deploy publicaria o placeholder da BSV-35 por cima da home provisória).
   - ARN do papel em variável do repositório (`AWS_ROLE_SITE`), não em segredo; região `us-east-1`.
4. README da infra: criar a variável, ligar o deploy, rodar à mão, reverter (rodar o workflow num commit
   anterior).

## Regras
- Nenhuma chave de acesso criada ou guardada no GitHub.
- `--delete` só dentro de `_app/`; o resto é cópia por arquivo. A policy é a segunda trava: mesmo um
  script errado não consegue apagar fora dos prefixos do site.
- Ações do GitHub fixadas por versão maior conhecida (`actions/checkout@v4`,
  `aws-actions/configure-aws-credentials@v4`, `pnpm/action-setup@v4`, `actions/setup-node@v4`); conferir
  na documentação oficial antes de usar.
- Nada muda na distribuição, no bucket, no worker ou no vigia.

## Fora de escopo
Preview por PR, ambiente de homologação, deploy do worker, desligar o protótipo.

## Critério de aceite
- `terraform test` (mocks): provedor OIDC com o `client_id_list` certo; confiança restrita a `main` deste
  repositório; policy exatamente com os prefixos acima (teste por leitura do código, lição 11); nenhuma
  ação em prefixos do worker.
- Workflow: `actionlint` (ou validação equivalente) limpo; gatilho `push` condicionado à variável.
- `terraform fmt/validate/test` limpos; `plan` real só com adições (provedor, papel, policy).
- **Real (dono):** `apply`; criar `AWS_ROLE_SITE`; simular o papel com o IAM Policy Simulator (ou
  `aws iam simulate-principal-policy`): `PutObject` em `_app/x.js` → permitido; `DeleteObject` em
  `manifest.json`, `oferta/1/index.html` e `data/chunks/x` → negado. O primeiro deploy de verdade é feito
  pelo dono à mão (`workflow_dispatch`) quando a BSV-30 estiver aprovada; até lá
  `curl -s https://besave.com.br/` continua mostrando a home provisória.

## Definition of done
PR com README, `plan` colado (ARNs `REDACTED`), log do workflow manual, testes verdes.
