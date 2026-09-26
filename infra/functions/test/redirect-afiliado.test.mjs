import { test } from 'node:test';
import assert from 'node:assert/strict';
import { carregar, evento } from './carregar.mjs';

// KVS falsa: get lança para chave ausente, como a documentada.
function cfFalso(chaves) {
  const consultas = [];
  return {
    consultas,
    kvs: () => ({
      get: async (chave) => {
        consultas.push(chave);
        if (!(chave in chaves)) throw new Error(`KeyNotFound: ${chave}`);
        return chaves[chave];
      },
    }),
  };
}

const URL_LOJA = 'https://loja.example/p/123?aff=besave';

async function chamar(uri) {
  const cf = cfFalso({ 123: URL_LOJA });
  const r = await carregar('redirect-afiliado.js', cf)(evento(uri));
  return { r, consultas: cf.consultas };
}

function assert302(r, location) {
  assert.equal(r.statusCode, 302);
  assert.equal(r.headers.location.value, location);
  assert.equal(r.headers['cache-control'].value, 'no-store');
}

test('FN-04: id presente na KVS → 302 para a URL com no-store', async () => {
  const { r, consultas } = await chamar('/ir/123');
  assert302(r, URL_LOJA);
  assert.deepEqual(consultas, ['123']);
});

test('FN-05: id ausente na KVS → 302 para / com no-store', async () => {
  const { r, consultas } = await chamar('/ir/999');
  assert302(r, '/');
  assert.deepEqual(consultas, ['999']);
});

test('FN-06: id não decimal → 302 para / sem consultar a KVS', async () => {
  for (const uri of ['/ir/', '/ir/abc', '/ir/12/x', '/ir/12a', '/ir/-1']) {
    const { r, consultas } = await chamar(uri);
    assert302(r, '/');
    assert.deepEqual(consultas, [], uri);
  }
});
