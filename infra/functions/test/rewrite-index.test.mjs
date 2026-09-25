import { test } from 'node:test';
import assert from 'node:assert/strict';
import { carregar, evento } from './carregar.mjs';

const handler = carregar('rewrite-index.js');
const uriFinal = async (uri) => (await handler(evento(uri))).uri;

test('FN-01: uri terminado em / ganha index.html', async () => {
  assert.equal(await uriFinal('/'), '/index.html');
  assert.equal(await uriFinal('/oferta/1/'), '/oferta/1/index.html');
});

test('FN-02: último segmento sem extensão ganha /index.html', async () => {
  assert.equal(await uriFinal('/beleza'), '/beleza/index.html');
  assert.equal(await uriFinal('/oferta/123'), '/oferta/123/index.html');
});

test('FN-02 edge: ponto num segmento anterior não conta como extensão', async () => {
  assert.equal(await uriFinal('/a.b/c'), '/a.b/c/index.html');
});

test('FN-03: path com extensão passa intacto e a requisição segue para a origem', async () => {
  for (const uri of ['/manifest.json', '/_app/x.js', '/data/chunks/0-ffff.json.br', '/404.html']) {
    const r = await handler(evento(uri));
    assert.equal(r.uri, uri);
    assert.equal(r.method, 'GET');
    assert.equal(r.statusCode, undefined);
  }
});
