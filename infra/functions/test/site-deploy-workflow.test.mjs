import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// WF-*: leitura do .github/workflows/site-deploy.yml (BSV-17). Sintaxe e expressões: actionlint.
const yml = readFileSync(new URL('../../../.github/workflows/site-deploy.yml', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const semComentarios = yml.replace(/^\s*#.*$/gm, '');

test('WF-01: workflow_dispatch e push em main só com apps/site/**', () => {
  assert.match(yml, /^\s{2}workflow_dispatch:/m);
  assert.match(yml, /^\s{2}push:\n\s{4}branches: \[main\]\n\s{4}paths: \['apps\/site\/\*\*'\]/m);
  assert.doesNotMatch(semComentarios, /pull_request|schedule:/);
});

test('WF-01/02: o job só roda em main e, no push, só com SITE_DEPLOY_ATIVO == true', () => {
  const ifs = [...semComentarios.matchAll(/^\s{4}if: (.+)$/gm)].map((m) => m[1]);
  assert.deepEqual(ifs, [
    "github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch' || vars.SITE_DEPLOY_ATIVO == 'true')",
  ]);
});

test('WF-02: permissões mínimas, sem segredo e sem environment (mudaria o sub do token)', () => {
  assert.match(yml, /^permissions:\n\s{2}contents: read\n\s{2}id-token: write\n/m);
  assert.doesNotMatch(semComentarios, /secrets\.|aws-access-key-id|aws-secret-access-key|^\s+environment:/m);
});

test('WF-03: build com pnpm install --frozen-lockfile e pnpm build em apps/site', () => {
  assert.match(yml, /working-directory: apps\/site\n\s+run: \|\n\s+pnpm install --frozen-lockfile\n\s+pnpm build\n/);
});

test('WF-04: papel de vars.AWS_ROLE_SITE em us-east-1 com configure-aws-credentials@v6', () => {
  assert.match(yml, /uses: aws-actions\/configure-aws-credentials@v6\n\s+with:\n(\s+.+\n)*?\s+role-to-assume: \$\{\{ vars\.AWS_ROLE_SITE \}\}\n/);
  assert.match(yml, /aws-region: us-east-1\n/);
});

test('WF-04: ações fixadas na versão maior da spec', () => {
  const usos = [...semComentarios.matchAll(/uses: (\S+)/g)].map((m) => m[1]);
  assert.deepEqual(new Set(usos), new Set([
    'actions/checkout@v7', 'pnpm/action-setup@v6', 'actions/setup-node@v7', 'aws-actions/configure-aws-credentials@v6',
  ]));
});

test('WF-05: commit pedido precisa ser SHA ancestral de main e só troca apps/site', () => {
  assert.match(yml, /COMMIT: \$\{\{ inputs\.commit \}\}/);
  assert.match(yml, /git merge-base --is-ancestor "\$COMMIT" HEAD/);
  assert.match(yml, /git checkout "\$COMMIT" -- apps\/site\n/);
  // input nunca interpolado no shell (injeção): só aparece como valor de env
  assert.deepEqual([...semComentarios.matchAll(/^.*\$\{\{\s*inputs\..*$/gm)].map((m) => m[0].trim()), ['COMMIT: ${{ inputs.commit }}']);
});

// PUB-09: o ensaio lista _app/ no bucket (só leitura), então vem depois da credencial e antes de publicar.
test('PUB: credencial, ensaio e publicação, nessa ordem, pelo script do repositório', () => {
  const iCred = yml.indexOf('configure-aws-credentials@v6');
  const iEnsaio = yml.indexOf('publicar.mjs --build apps/site/build --bucket "$BUCKET" --distribuicao "$DISTRIBUICAO" --ensaio');
  const iPub = yml.lastIndexOf('node infra/deploy-site/publicar.mjs --build apps/site/build --bucket "$BUCKET" --distribuicao "$DISTRIBUICAO"\n');
  assert.ok(iCred > 0 && iCred < iEnsaio && iEnsaio < iPub, `${iCred} ${iEnsaio} ${iPub}`);
  assert.match(yml, /BUCKET: besave-site\n/);
  assert.doesNotMatch(semComentarios, /aws s3 |--delete|create-invalidation/);
});
