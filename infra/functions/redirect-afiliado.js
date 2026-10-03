// Runtime cloudfront-js-2.0 é um subconjunto do JS: `await` não pode ser argumento de função
// ("await in arguments not supported"). Atribua a uma variável antes. Rode `aws cloudfront
// test-function` após qualquer mudança; os testes Node não emulam o runtime.
import cf from 'cloudfront';

// viewer-request em /ir/*: /ir/{id} → 302 para a URL da KVS; ausente ou inválido → 302 /.
const kvs = cf.kvs();

function redirecionar(location) {
  return {
    statusCode: 302,
    statusDescription: 'Found',
    headers: {
      location: { value: location },
      'cache-control': { value: 'no-store' },
    },
  };
}

async function handler(event) {
  const id = event.request.uri.slice('/ir/'.length);
  if (!/^[0-9]+$/.test(id)) {
    return redirecionar('/');
  }
  try {
    const url = await kvs.get(id);
    return redirecionar(url);
  } catch (e) {
    return redirecionar('/');
  }
}
