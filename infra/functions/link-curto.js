// viewer-request dos domínios curtos (besave.io, besave.me), CONTRATO §5. Sempre responde; a origem nunca
// é alcançada. /{id} e /{id}/ → oferta; /{id}/ir → /ir/{id}; resto → home. Query preservada.
var SITE = 'https://besave.com.br';

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
  var m = /^\/([0-9]{1,12})(\/|\/ir)?$/.exec(request.uri);
  var id = m ? m[1].replace(/^0+/, '') : '';
  var destino = '/';
  if (id) destino = m[2] === '/ir' ? '/ir/' + id : '/oferta/' + id + '/';
  return {
    statusCode: 301,
    statusDescription: 'Moved Permanently',
    headers: {
      location: { value: SITE + destino + query(request.querystring) },
      'cache-control': { value: 'public, max-age=86400' },
    },
  };
}
