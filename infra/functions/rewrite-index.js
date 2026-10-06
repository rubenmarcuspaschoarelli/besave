// viewer-request: www.besave.com.br → 301 para besave.com.br (BSV-16);
// /x/ → /x/index.html; /x sem extensão → /x/index.html.
function query(qs) {
  var pares = [];
  for (var chave in qs) {
    var valores = qs[chave].multiValue || [qs[chave]];
    for (var i = 0; i < valores.length; i++) pares.push(chave + '=' + valores[i].value);
  }
  return pares.length ? '?' + pares.join('&') : '';
}

function handler(event) {
  var request = event.request;
  var host = request.headers.host ? request.headers.host.value.toLowerCase() : '';
  if (host === 'www.besave.com.br') {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: { value: 'https://besave.com.br' + request.uri + query(request.querystring) },
        'cache-control': { value: 'public, max-age=86400' },
      },
    };
  }
  var uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (uri.slice(uri.lastIndexOf('/') + 1).indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }
  return request;
}
