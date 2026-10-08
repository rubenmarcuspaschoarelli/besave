import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { planejar, expurgar, lerListagem, listagem, principal } from '../../deploy-site/publicar.mjs';

// Deploy do site (BSV-17): script chamado pelo .github/workflows/site-deploy.yml.
const script = fileURLToPath(new URL('../../deploy-site/publicar.mjs', import.meta.url));
const opcoes = { build: 'build', bucket: 'besave-site', distribuicao: 'EDIST0000' };
const IMUTAVEL = 'public, max-age=31536000, immutable';
const HTML_CC = 'public, max-age=300';
const HTML_CT = 'text/html; charset=utf-8';
const CSS_CC = 'public, max-age=3600, stale-while-revalidate=86400';

const buildBom = [
  '_app/immutable/entry/start.abc123.js',
  '_app/immutable/assets/0.def456.css',
  '_app/version.json',
  'index.html',
  '404.html',
  'desejos/index.html',
  'elas/index.html',
  'elas/feminino/index.html',
  'esporte-vida/index.html',
  'assets/besave.css',
  'assets/fontes/lato-900.woff2',
  'favicon.svg',
];

const valor = (cmd, flag) => (cmd.includes(flag) ? cmd[cmd.indexOf(flag) + 1] : undefined);
const destinos = (cmds) => cmds.flatMap((c) => c.filter((a) => a.startsWith('s3://')));
test('PUB: prefixos.json é exatamente a lista da spec', () => {
  const lista = JSON.parse(readFileSync(new URL('../../deploy-site/prefixos.json', import.meta.url), 'utf8'));
  assert.deepEqual(lista, [
    '_app/*', 'index.html', '404.html', 'favicon.*', 'desejos/*', 'assets/besave.css', 'assets/fontes/*',
    'tech/*', 'players/*', 'meu-lar/*', 'elas/*', 'eles/*', 'cultura/*', 'familia/*', 'pets/*',
    'esporte-vida/*', 'outros/*',
  ]);
});

test('PUB-01: arquivo fora dos prefixos do site barra o deploy inteiro, sem comando AWS', () => {
  for (const intruso of [
    'robots.txt', 'manifest.json', 'manifest.prev.json', 'sitemap.xml', 'sitemap-0.xml',
    'data/chunks/0-ab.json.br', 'oferta/1/index.html', 'img/ofertas/1.webp', '_estado/paginas.json',
    'assets/outro.css', 'sobre/index.html', 'favicon',
  ]) {
    const { erros, comandos } = planejar([...buildBom, intruso], opcoes);
    assert.equal(comandos.length, 0, intruso);
    assert.ok(erros.some((e) => e.includes(intruso)), `${intruso}: ${erros}`);
  }
});

test('PUB-02: sem index.html ou sem 404.html não há deploy', () => {
  for (const falta of ['index.html', '404.html']) {
    const { erros, comandos } = planejar(buildBom.filter((f) => f !== falta), opcoes);
    assert.equal(comandos.length, 0, falta);
    assert.ok(erros.some((e) => e.includes(falta)), `${falta}: ${erros}`);
  }
});

test('PUB-01/02: build válido não tem erro e só escreve dentro de s3://besave-site/ nos prefixos', () => {
  const { erros, comandos } = planejar(buildBom, opcoes);
  assert.deepEqual(erros, []);
  assert.ok(comandos.length > 0);
  for (const d of destinos(comandos)) {
    assert.ok(d.startsWith('s3://besave-site/'), d);
    assert.doesNotMatch(d, /s3:\/\/besave-site\/(data|oferta|img|_estado)\/|manifest|sitemap|robots/, d);
    assert.notEqual(d, 's3://besave-site/');
  }
});

// PUB-03 (revisão do dono): sem sync --delete; a limpeza de _app/ é por carência (PUB-09).
test('PUB-03: o plano não apaga nada (nenhum --delete, nenhum rm)', () => {
  const { comandos } = planejar(buildBom, opcoes);
  assert.ok(!comandos.some((c) => c.includes('--delete')));
  assert.ok(!comandos.some((c) => c[1] === 'rm' || c.includes('delete-object') || c.includes('delete-objects')));
  const syncs = comandos.filter((c) => c[1] === 'sync');
  assert.equal(syncs.length, 1);
  const iSync = comandos.indexOf(syncs[0]);
  const iPrimeiroHtml = comandos.findIndex((c) => c[1] === 'cp' && c[3].endsWith('.html'));
  assert.ok(iSync < iPrimeiroHtml, '_app/ novo sobe antes do HTML que o referencia');
});

// PUB-09: apaga de _app/ só o que (a) não está no build atual e (b) tem LastModified há mais de 7 dias.
const DIA = 86_400_000;
const AGORA = Date.parse('2026-10-07T12:00:00Z');
const ha = (dias) => new Date(AGORA - dias * DIA).toISOString();

test('PUB-09: fora do build com 8 dias → apagado; com 1 dia → mantido; do build com 30 dias → mantido', () => {
  const remotos = [
    { Key: '_app/immutable/chunks/velho.js', LastModified: ha(8) },
    { Key: '_app/immutable/chunks/recente.js', LastModified: ha(1) },
    { Key: '_app/immutable/entry/start.abc123.js', LastModified: ha(30) },
  ];
  assert.deepEqual(expurgar(remotos, buildBom, AGORA), ['_app/immutable/chunks/velho.js']);
});

test('PUB-09: fronteira de 7 dias — exatamente 7 dias fica, 7 dias e 1 s sai', () => {
  const remotos = [
    { Key: '_app/a.js', LastModified: ha(7) },
    { Key: '_app/b.js', LastModified: new Date(AGORA - 7 * DIA - 1000).toISOString() },
  ];
  assert.deepEqual(expurgar(remotos, buildBom, AGORA), ['_app/b.js']);
});

test('PUB-09: version.json do build nunca sai; nada fora de _app/ sai; lista vazia/nula não apaga', () => {
  const remotos = [
    { Key: '_app/version.json', LastModified: ha(90) },
    { Key: 'index.html', LastModified: ha(90) },
    { Key: 'data/chunks/0-ab.json.br', LastModified: ha(90) },
    { Key: '_appx/x.js', LastModified: ha(90) },
  ];
  assert.deepEqual(expurgar(remotos, buildBom, AGORA), []);
  assert.deepEqual(expurgar([], buildBom, AGORA), []);
  assert.deepEqual(expurgar(null, buildBom, AGORA), []);
});

test('PUB-09: caminhos do build no formato do Windows também protegem', () => {
  const remotos = [{ Key: '_app/immutable/entry/start.abc123.js', LastModified: ha(30) }];
  assert.deepEqual(expurgar(remotos, buildBom.map((f) => f.replaceAll('/', '\\')), AGORA), []);
});

test('PUB-04: _app/ é imutável por 1 ano, reenviado a cada deploy (sem --size-only); version.json tem 300 s', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const syncs = comandos.filter((c) => c[1] === 'sync');
  assert.ok(syncs.length >= 1);
  for (const s of syncs) {
    assert.equal(s[2], 'build/_app');
    assert.equal(valor(s, '--cache-control'), IMUTAVEL);
    assert.equal(valor(s, '--exclude'), 'version.json');
    // decisão do dono (08/10): LastModified = último deploy que tinha o arquivo; a carência conta daí
    assert.ok(!s.includes('--size-only'));
  }
  const v = comandos.find((c) => c[1] === 'cp' && c[3] === 's3://besave-site/_app/version.json');
  assert.ok(v, 'version.json enviado à parte');
  assert.equal(valor(v, '--cache-control'), HTML_CC);
  assert.equal(valor(v, '--content-type'), 'application/json');
});

test('PUB-05: cada HTML vai por arquivo com 300 s e text/html; charset=utf-8', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const htmls = buildBom.filter((f) => f.endsWith('.html'));
  for (const h of htmls) {
    const c = comandos.find((x) => x[1] === 'cp' && x[3] === `s3://besave-site/${h}`);
    assert.ok(c, h);
    assert.equal(c[2], `build/${h}`);
    assert.equal(valor(c, '--cache-control'), HTML_CC, h);
    assert.equal(valor(c, '--content-type'), HTML_CT, h);
    assert.ok(!c.includes('--recursive') && !c.includes('--delete'), h);
  }
});

test('PUB-06: assets/besave.css com 1 h + swr de 1 dia e text/css; charset=utf-8', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const c = comandos.find((x) => x[1] === 'cp' && x[3] === 's3://besave-site/assets/besave.css');
  assert.ok(c);
  assert.equal(valor(c, '--cache-control'), CSS_CC);
  assert.equal(valor(c, '--content-type'), 'text/css; charset=utf-8');
});

// Cache de fontes e favicon: a spec não define; spec.md (suposições) fixa o mesmo do CSS.
test('PUB: fontes e favicon vão por arquivo com tipo explícito e cache do CSS', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const fonte = comandos.find((x) => x[3] === 's3://besave-site/assets/fontes/lato-900.woff2');
  assert.equal(valor(fonte, '--content-type'), 'font/woff2');
  assert.equal(valor(fonte, '--cache-control'), CSS_CC);
  const fav = comandos.find((x) => x[3] === 's3://besave-site/favicon.svg');
  assert.equal(valor(fav, '--content-type'), 'image/svg+xml');
  assert.equal(valor(fav, '--cache-control'), CSS_CC);
});

test('PUB-07: invalidação só de HTML e /assets/*, nunca /*', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const inval = comandos.filter((c) => c[0] === 'cloudfront');
  assert.equal(inval.length, 1);
  const [c] = inval;
  assert.equal(c[1], 'create-invalidation');
  assert.equal(valor(c, '--distribution-id'), 'EDIST0000');
  const caminhos = c.slice(c.indexOf('--paths') + 1);
  assert.deepEqual(new Set(caminhos), new Set(['/index.html', '/404.html', '/desejos/*', '/elas/*', '/esporte-vida/*', '/assets/*']));
  assert.ok(!caminhos.includes('/*'));
  for (const p of caminhos) assert.doesNotMatch(p, /^\/(_app|data|oferta|img)\b/, p);
});

test('PUB-07: build sem HTML de área invalida só a raiz, 404 e /assets/*', () => {
  const { comandos } = planejar(['_app/x.js', 'index.html', '404.html'], opcoes);
  const c = comandos.find((x) => x[0] === 'cloudfront');
  assert.deepEqual(new Set(c.slice(c.indexOf('--paths') + 1)), new Set(['/index.html', '/404.html', '/assets/*']));
});

test('PUB: caminhos do Windows são normalizados para /', () => {
  const { erros } = planejar(buildBom.map((f) => f.replaceAll('/', '\\')), opcoes);
  assert.deepEqual(erros, []);
});

// CLI de ponta a ponta, com --ensaio (nada é executado).
function rodar(arquivos, extra = []) {
  const dir = mkdtempSync(join(tmpdir(), 'deploy-site-'));
  try {
    for (const f of arquivos) {
      mkdirSync(dirname(join(dir, f)), { recursive: true });
      writeFileSync(join(dir, f), 'x');
    }
    return spawnSync(process.execPath, [script, '--build', dir, '--bucket', 'besave-site', '--distribuicao', 'EDIST0000', ...extra], { encoding: 'utf8' });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// --remotos: listagem de _app/ lida de arquivo (o que list-objects-v2 devolveria), para testar sem AWS.
function comRemotos(remotos, fn) {
  const dir = mkdtempSync(join(tmpdir(), 'deploy-site-remotos-'));
  try {
    const arq = join(dir, 'remotos.json');
    writeFileSync(arq, JSON.stringify(remotos));
    return fn(arq);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
const haReal = (dias) => new Date(Date.now() - dias * DIA).toISOString();

test('PUB-08: --ensaio imprime os comandos aws e sai 0', () => {
  const r = comRemotos([], (arq) => rodar(buildBom, ['--ensaio', '--remotos', arq]));
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /aws s3 sync .*_app s3:\/\/besave-site\/_app\/ /);
  assert.doesNotMatch(r.stdout, /--delete/);
  assert.match(r.stdout, /aws cloudfront create-invalidation --distribution-id EDIST0000/);
  assert.match(r.stdout, /s3:\/\/besave-site\/elas\/feminino\/index\.html/);
});

test('PUB-09 (CLI): --ensaio mostra a lista que seria apagada, depois da invalidação', () => {
  const remotos = [
    { Key: '_app/immutable/chunks/velho.js', LastModified: haReal(8) },
    { Key: '_app/immutable/chunks/recente.js', LastModified: haReal(1) },
    { Key: '_app/immutable/entry/start.abc123.js', LastModified: haReal(30) },
  ];
  const r = comRemotos(remotos, (arq) => rodar(buildBom, ['--ensaio', '--remotos', arq]));
  assert.equal(r.status, 0, r.stderr);
  const rms = r.stdout.split('\n').filter((l) => l.startsWith('aws s3 rm '));
  assert.deepEqual(rms, ['aws s3 rm s3://besave-site/_app/immutable/chunks/velho.js']);
  assert.ok(r.stdout.indexOf('create-invalidation') < r.stdout.indexOf('aws s3 rm '));
  assert.match(r.stdout, /apagaria 1 arquivo/);
});

test('PUB-09 (CLI): nada a apagar é dito no ensaio', () => {
  const r = comRemotos([{ Key: '_app/x.js', LastModified: haReal(1) }], (arq) => rodar(buildBom, ['--ensaio', '--remotos', arq]));
  assert.equal(r.status, 0, r.stderr);
  assert.doesNotMatch(r.stdout, /aws s3 rm /);
  assert.match(r.stdout, /apagaria 0 arquivo/);
});

test('PUB-09: listagem do list-objects-v2 (JSON ou "null" de prefixo vazio) é lida', () => {
  assert.deepEqual(lerListagem('null\n'), []);
  assert.deepEqual(lerListagem('[{"Key":"_app/a.js","LastModified":"2026-10-01T00:00:00+00:00"}]'), [
    { Key: '_app/a.js', LastModified: '2026-10-01T00:00:00+00:00' },
  ]);
  assert.throws(() => lerListagem('não é json'));
});

test('PUB-01 (CLI): arquivo proibido no build sai 1, mesmo em ensaio, sem imprimir comando', () => {
  const r = rodar([...buildBom, 'robots.txt'], ['--ensaio']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /robots\.txt/);
  assert.doesNotMatch(r.stdout, /aws /);
});

test('PUB (CLI): diretório de build inexistente sai 1 com mensagem, sem stack trace', () => {
  const r = spawnSync(process.execPath, [script, '--build', join(tmpdir(), 'nao-existe-besave'), '--bucket', 'b', '--distribuicao', 'D', '--ensaio'], { encoding: 'utf8' });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /build não encontrado/);
  assert.doesNotMatch(r.stderr, /at .*publicar\.mjs/);
});

test('PUB (CLI): sem --bucket ou --distribuicao sai 1', () => {
  const r = spawnSync(process.execPath, [script, '--build', '.', '--ensaio'], { encoding: 'utf8' });
  assert.equal(r.status, 1);
});

// PUB-09, modo real: aws falso grava as chamadas; nada sai para a rede.
test('PUB-09: listagem pede só _app/ do bucket, com Key e LastModified, em JSON', () => {
  assert.deepEqual(listagem('besave-site'), [
    's3api', 'list-objects-v2', '--bucket', 'besave-site', '--prefix', '_app/',
    '--query', 'Contents[].{Key: Key, LastModified: LastModified}', '--output', 'json',
  ]);
});

function comBuild(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'deploy-site-real-'));
  try {
    for (const f of buildBom) {
      mkdirSync(dirname(join(dir, f)), { recursive: true });
      writeFileSync(join(dir, f), 'x');
    }
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function awsFalso({ listagemStatus = 0, saida } = {}) {
  const chamadas = [];
  const aws = (args) => {
    chamadas.push(args);
    if (args[1] === 'list-objects-v2') return { status: listagemStatus, stdout: saida };
    return { status: 0 };
  };
  return { aws, chamadas };
}

const remotosReais = JSON.stringify([
  { Key: '_app/immutable/chunks/velho.js', LastModified: ha(8).replace('Z', '+00:00') },
  { Key: '_app/immutable/chunks/recente.js', LastModified: ha(1).replace('Z', '+00:00') },
  { Key: '_app/immutable/entry/start.abc123.js', LastModified: ha(30).replace('Z', '+00:00') },
]);
const argsReais = (dir) => ['--build', dir, '--bucket', 'besave-site', '--distribuicao', 'EDIST0000'];

test('PUB-09 (real): publica, lista _app/ depois da invalidação e apaga só o arquivo fora do build com 8 dias', () => {
  const { aws, chamadas } = awsFalso({ saida: remotosReais });
  const status = comBuild((dir) => principal(argsReais(dir), aws, AGORA));
  assert.equal(status, 0);
  const iInval = chamadas.findIndex((c) => c[0] === 'cloudfront');
  const iLista = chamadas.findIndex((c) => c[1] === 'list-objects-v2');
  assert.ok(iInval >= 0 && iLista > iInval);
  assert.deepEqual(chamadas[iLista], listagem('besave-site'));
  const rms = chamadas.filter((c) => c[1] === 'rm');
  assert.deepEqual(rms, [['s3', 'rm', 's3://besave-site/_app/immutable/chunks/velho.js']]);
  assert.ok(chamadas.indexOf(rms[0]) > iLista);
  assert.ok(chamadas.some((c) => c[1] === 'cp' && c[3] === 's3://besave-site/index.html'));
});

test('PUB-09 (real): prefixo vazio ("null") não apaga nada e sai 0', () => {
  const { aws, chamadas } = awsFalso({ saida: 'null\n' });
  assert.equal(comBuild((dir) => principal(argsReais(dir), aws, AGORA)), 0);
  assert.ok(!chamadas.some((c) => c[1] === 'rm'));
});

test('PUB-09 (real): listagem que falha ou vem ilegível sai 1 sem apagar', () => {
  for (const falso of [awsFalso({ listagemStatus: 255, saida: remotosReais }), awsFalso({ saida: 'xml?' })]) {
    assert.equal(comBuild((dir) => principal(argsReais(dir), falso.aws, AGORA)), 1);
    assert.ok(!falso.chamadas.some((c) => c[1] === 'rm'));
  }
});

test('PUB-08/09 (ensaio): só a listagem chega ao aws; nada é escrito nem apagado', () => {
  const { aws, chamadas } = awsFalso({ saida: remotosReais });
  assert.equal(comBuild((dir) => principal([...argsReais(dir), '--ensaio'], aws, AGORA)), 0);
  assert.deepEqual(chamadas, [listagem('besave-site')]);
});

test('PUB-09: --remotos sem --ensaio é recusado (a limpeza real usa a listagem do bucket)', () => {
  const { aws, chamadas } = awsFalso({ saida: remotosReais });
  const status = comRemotos([], (arq) => comBuild((dir) => principal([...argsReais(dir), '--remotos', arq], aws, AGORA)));
  assert.equal(status, 1);
  assert.deepEqual(chamadas, []);
});

// PUB-04/09 entre deploys: S3 simulado guarda LastModified por chave e imita o aws s3 sync
// (com --size-only, chave existente de mesmo nome não é reenviada; sem ele, todo arquivo do build é).
function s3Simulado() {
  const objetos = new Map();
  let relogio = 0;
  const aws = (args) => {
    if (args[1] === 'sync') {
      const origem = args[2];
      for (const rel of readdirSync(origem, { recursive: true, withFileTypes: true })
        .filter((e) => e.isFile())
        .map((e) => relative(origem, join(e.parentPath, e.name)).replaceAll('\\', '/'))) {
        if (rel === valor(args, '--exclude')) continue;
        const chave = `_app/${rel}`;
        if (!(args.includes('--size-only') && objetos.has(chave))) objetos.set(chave, relogio);
      }
    } else if (args[1] === 'cp') {
      objetos.set(args[3].replace('s3://besave-site/', ''), relogio);
    } else if (args[1] === 'rm') {
      objetos.delete(args[2].replace('s3://besave-site/', ''));
    } else if (args[1] === 'list-objects-v2') {
      const lista = [...objetos].filter(([k]) => k.startsWith('_app/'))
        .map(([Key, t]) => ({ Key, LastModified: new Date(t).toISOString().replace('Z', '+00:00') }));
      return { status: 0, stdout: JSON.stringify(lista.length ? lista : null) };
    }
    return { status: 0 };
  };
  const deploy = (arquivos, quando) => {
    relogio = quando;
    const dir = mkdtempSync(join(tmpdir(), 'deploy-site-sim-'));
    try {
      for (const f of arquivos) {
        mkdirSync(dirname(join(dir, f)), { recursive: true });
        writeFileSync(join(dir, f), 'x');
      }
      return principal(['--build', dir, '--bucket', 'besave-site', '--distribuicao', 'EDIST0000'], aws, quando);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  };
  return { objetos, deploy };
}

const SAIU = '_app/immutable/chunks/saiu.js';

test('PUB-09: arquivo do build anterior que saiu agora, com 1º upload há 30 dias, NÃO é apagado (LastModified = deploy anterior)', () => {
  const s3 = s3Simulado();
  assert.equal(s3.deploy([...buildBom, SAIU], AGORA - 30 * DIA), 0); // 1º upload
  assert.equal(s3.deploy([...buildBom, SAIU], AGORA - 1 * DIA), 0);  // deploy anterior, ainda com o arquivo
  assert.equal(s3.deploy(buildBom, AGORA), 0);                       // saiu do build agora
  assert.ok(s3.objetos.has(SAIU), 'a carência conta do último deploy que tinha o arquivo');
  assert.equal(s3.objetos.get(SAIU), AGORA - 1 * DIA);
});

test('PUB-09: arquivo que saiu do build há mais de 7 dias é apagado no deploy seguinte', () => {
  const s3 = s3Simulado();
  assert.equal(s3.deploy([...buildBom, SAIU], AGORA - 30 * DIA), 0);
  assert.equal(s3.deploy([...buildBom, SAIU], AGORA - 8 * DIA), 0);
  assert.equal(s3.deploy(buildBom, AGORA), 0);
  assert.ok(!s3.objetos.has(SAIU));
  for (const f of buildBom.filter((x) => x.startsWith('_app/'))) assert.ok(s3.objetos.has(f), f);
});
