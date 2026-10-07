import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { planejar } from '../../deploy-site/publicar.mjs';

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

test('PUB-03: --delete só no sync de _app/, e só depois do HTML e da invalidação', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const comDelete = comandos.filter((c) => c.includes('--delete'));
  assert.equal(comDelete.length, 1);
  const [del] = comDelete;
  assert.deepEqual(del.slice(0, 2), ['s3', 'sync']);
  assert.equal(del[3], 's3://besave-site/_app/');
  const iDel = comandos.indexOf(del);
  const iUltimoHtml = comandos.findLastIndex((c) => c[1] === 'cp' && c[3].endsWith('.html'));
  const iInval = comandos.findIndex((c) => c[0] === 'cloudfront');
  assert.ok(iUltimoHtml >= 0 && iInval >= 0);
  assert.ok(iDel > iUltimoHtml && iDel > iInval, `delete em ${iDel}, html até ${iUltimoHtml}, invalidação ${iInval}`);
  // o primeiro sync (antes do HTML) existe e não apaga
  const iSync = comandos.findIndex((c) => c[1] === 'sync');
  assert.ok(iSync < iUltimoHtml && !comandos[iSync].includes('--delete'));
});

test('PUB-04: _app/ é imutável por 1 ano; version.json (nome fixo) tem 300 s', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const syncs = comandos.filter((c) => c[1] === 'sync');
  assert.ok(syncs.length >= 1);
  for (const s of syncs) {
    assert.equal(s[2], 'build/_app');
    assert.equal(valor(s, '--cache-control'), IMUTAVEL);
    assert.equal(valor(s, '--exclude'), 'version.json');
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

test('PUB: fontes e favicon vão por arquivo com tipo explícito', () => {
  const { comandos } = planejar(buildBom, opcoes);
  const fonte = comandos.find((x) => x[3] === 's3://besave-site/assets/fontes/lato-900.woff2');
  assert.equal(valor(fonte, '--content-type'), 'font/woff2');
  const fav = comandos.find((x) => x[3] === 's3://besave-site/favicon.svg');
  assert.equal(valor(fav, '--content-type'), 'image/svg+xml');
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

test('PUB-08: --ensaio imprime os comandos aws e sai 0', () => {
  const r = rodar(buildBom, ['--ensaio']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /aws s3 sync .*_app s3:\/\/besave-site\/_app\/ .*--delete/);
  assert.match(r.stdout, /aws cloudfront create-invalidation --distribution-id EDIST0000/);
  assert.match(r.stdout, /s3:\/\/besave-site\/elas\/feminino\/index\.html/);
});

test('PUB-01 (CLI): arquivo proibido no build sai 1, mesmo em ensaio, sem imprimir comando', () => {
  const r = rodar([...buildBom, 'robots.txt'], ['--ensaio']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /robots\.txt/);
  assert.doesNotMatch(r.stdout, /aws /);
});

test('PUB (CLI): sem --bucket ou --distribuicao sai 1', () => {
  const r = spawnSync(process.execPath, [script, '--build', '.', '--ensaio'], { encoding: 'utf8' });
  assert.equal(r.status, 1);
});
