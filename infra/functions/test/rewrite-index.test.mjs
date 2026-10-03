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

// BSV-16: www.besave.com.br → domínio sem www, com caminho original e query.
function comHost(uri, host, querystring = {}) {
  const ev = evento(uri);
  ev.request.headers.host.value = host;
  ev.request.querystring = querystring;
  return handler(ev);
}

test('WWW-01: Host www → 301 para o domínio sem www com caminho e query', async () => {
  const r = await comHost('/oferta/1/', 'www.besave.com.br', { a: { value: '1' } });
  assert.equal(r.statusCode, 301);
  assert.equal(r.headers.location.value, 'https://besave.com.br/oferta/1/?a=1');
  assert.equal(r.headers['cache-control'].value, 'public, max-age=86400');
});

test('WWW-01 edge: Host em maiúsculas e chave repetida', async () => {
  const qs = { t: { value: '1', multiValue: [{ value: '1' }, { value: '2' }] } };
  const r = await comHost('/elas', 'WWW.Besave.com.br', qs);
  assert.equal(r.statusCode, 301);
  assert.equal(r.headers.location.value, 'https://besave.com.br/elas?t=1&t=2');
});

test('WWW-02: sem query, location sem ?', async () => {
  const r = await comHost('/', 'www.besave.com.br');
  assert.equal(r.statusCode, 301);
  assert.equal(r.headers.location.value, 'https://besave.com.br/');
});

test('WWW-03: domínio sem www segue com o rewrite', async () => {
  const r = await comHost('/oferta/1/', 'besave.com.br', { a: { value: '1' } });
  assert.equal(r.statusCode, undefined);
  assert.equal(r.uri, '/oferta/1/index.html');
});

test('WWW-01 edge: valor codificado repassado sem recodificar', async () => {
  const r = await comHost('/oferta/1/', 'www.besave.com.br', { utm_campaign: { value: 'a%20b%26c' } });
  assert.equal(r.headers.location.value, 'https://besave.com.br/oferta/1/?utm_campaign=a%20b%26c');
});
