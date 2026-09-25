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
    return redirecionar(await kvs.get(id));
  } catch (e) {
    return redirecionar('/');
  }
}
