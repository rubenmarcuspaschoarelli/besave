import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// CF-12: placeholder servido pelas error responses 403/404.
const html = readFileSync(new URL('../../static/404.html', import.meta.url), 'utf8');
// CONTRATO.md §2.3 em minúsculas, `_` → `-` (MANIFEST.md §1: /{area}/).
const AREAS = ['tech', 'players', 'meu-lar', 'elas', 'eles', 'cultura', 'familia', 'pets', 'esporte-vida'];

test('CF-12: 404.html é noindex', () => {
  assert.match(html, /<meta name="robots" content="noindex">/);
});

test('CF-12: 404.html tem link para a home e para as 9 áreas', () => {
  assert.match(html, /href="\/"/);
  for (const area of AREAS) assert.match(html, new RegExp(`href="/${area}/"`), area);
});
