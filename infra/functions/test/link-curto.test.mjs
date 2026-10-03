import { test } from 'node:test';
import assert from 'node:assert/strict';
import { carregar, evento } from './carregar.mjs';

// BSV-16: besave.io/{id} e besave.me/{id} → besave.com.br (CONTRATO §5).
const handler = carregar('link-curto.js');
const SITE = 'https://besave.com.br';

function chamar(uri, querystring = {}) {
  const ev = evento(uri);
  ev.request.querystring = querystring;
  ev.request.headers.host.value = 'besave.io';
  return handler(ev);
}

function assert301(r, location) {
  assert.equal(r.statusCode, 301);
  assert.equal(r.headers.location.value, location);
  assert.equal(r.headers['cache-control'].value, 'public, max-age=86400');
}

test('LNK-01: /{id} e /{id}/ → /oferta/{id}/, sem zeros à esquerda', () => {
  assert301(chamar('/5412'), `${SITE}/oferta/5412/`);
  assert301(chamar('/5412/'), `${SITE}/oferta/5412/`);
  assert301(chamar('/05412'), `${SITE}/oferta/5412/`);
  assert301(chamar('/1'), `${SITE}/oferta/1/`);
  assert301(chamar('/123456789012'), `${SITE}/oferta/123456789012/`);
});

test('LNK-02: /{id}/ir → /ir/{id}', () => {
  assert301(chamar('/5412/ir'), `${SITE}/ir/5412`);
  assert301(chamar('/005412/ir'), `${SITE}/ir/5412`);
});

test('LNK-03: query string de entrada preservada', () => {
  assert301(chamar('/5412', { utm_source: { value: 'telegram' } }), `${SITE}/oferta/5412/?utm_source=telegram`);
  assert301(
    chamar('/5412/ir', { utm_source: { value: 'telegram' }, utm_medium: { value: 'canal' } }),
    `${SITE}/ir/5412?utm_source=telegram&utm_medium=canal`,
  );
  assert301(chamar('/', { a: { value: '1' } }), `${SITE}/?a=1`);
});

test('LNK-03 edge: chave repetida preserva todas as ocorrências', () => {
  const qs = { t: { value: '1', multiValue: [{ value: '1' }, { value: '2' }] } };
  assert301(chamar('/5412', qs), `${SITE}/oferta/5412/?t=1&t=2`);
});

test('LNK-04: / e qualquer outro caminho → home', () => {
  for (const uri of ['/', '/abc', '/1234567890123', '/0', '/000', '/12a', '/5412/ir/', '/5412/x', '/oferta/5412/', '/-1', '//5412']) {
    assert301(chamar(uri), `${SITE}/`);
  }
});
