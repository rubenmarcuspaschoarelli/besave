import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';

// OPS-02: o Terraform não referencia nem importa o que está no ar (AD-016).
const dir = new URL('../../', import.meta.url);
const tf = readdirSync(dir)
  .filter((f) => f.endsWith('.tf'))
  .map((f) => [f, readFileSync(new URL(f, dir), 'utf8')]);

test('OPS-02: há arquivos .tf para inspecionar', () => {
  assert.ok(tf.length >= 6, tf.map(([f]) => f).join(','));
});

test('OPS-02: nenhum .tf cita a distribuição E28G93A17WHHD nem tem bloco import', () => {
  for (const [f, src] of tf) {
    assert.doesNotMatch(src, /E28G93A17WHHD/, f);
    assert.doesNotMatch(src, /^\s*import\s*\{/m, f);
  }
});

test('OPS-02: nenhum .tf declara bucket com o nome do protótipo', () => {
  for (const [f, src] of tf) assert.doesNotMatch(src, /bucket\s*=\s*"besave\.com\.br"/, f);
});

// IAM-01: o Terraform nunca cria credencial do worker (ficaria no state local).
test('IAM-01: nenhum .tf cria access key nem login de console', () => {
  for (const [f, src] of tf) assert.doesNotMatch(src, /resource\s+"aws_iam_(access_key|user_login_profile)"/, f);
});

// S3-01: bucket privado, sem website hosting.
test('S3-01: nenhum .tf configura website hosting', () => {
  for (const [f, src] of tf) assert.doesNotMatch(src, /resource\s+"aws_s3_bucket_website_configuration"|^\s*website\s*\{/m, f);
});
