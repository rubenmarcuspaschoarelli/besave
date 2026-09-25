// Carrega uma CloudFront Function (cloudfront-js-2.0) como no runtime:
// o `import cf from 'cloudfront'` vira um parâmetro `cf` injetado pelo teste.
import { readFileSync } from 'node:fs';

export function carregar(arquivo, cf = {}) {
  const url = new URL(`../${arquivo}`, import.meta.url);
  const fonte = readFileSync(url, 'utf8').replace(/^import cf from 'cloudfront';?$/m, '');
  return new Function('cf', `${fonte}\nreturn handler;`)(cf);
}

// Evento viewer-request conforme a estrutura documentada do CloudFront Functions.
export function evento(uri) {
  return {
    version: '1.0',
    context: { eventType: 'viewer-request', distributionId: 'EDFDVBD6EXAMPLE', requestId: 'r1' },
    viewer: { ip: '198.51.100.1' },
    request: { method: 'GET', uri, querystring: {}, headers: { host: { value: 'd111111abcdef8.cloudfront.net' } }, cookies: {} },
  };
}
