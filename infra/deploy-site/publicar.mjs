// Publica o build do SvelteKit no bucket compartilhado com o worker (BSV-17).
// Uso: node publicar.mjs --build <dir> --bucket <nome> --distribuicao <id> [--ensaio]
// Só toca os prefixos de prefixos.json (a mesma lista da policy do papel besave-site-deploy).
import { readFileSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { relative, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const PREFIXOS = JSON.parse(readFileSync(new URL('./prefixos.json', import.meta.url), 'utf8'));
const IMUTAVEL = 'public, max-age=31536000, immutable';
const CURTO = 'public, max-age=300';
const ASSET = 'public, max-age=3600, stale-while-revalidate=86400';
const TIPOS = {
  html: 'text/html; charset=utf-8',
  css: 'text/css; charset=utf-8',
  js: 'text/javascript; charset=utf-8',
  json: 'application/json',
  woff2: 'font/woff2',
  woff: 'font/woff',
  ttf: 'font/ttf',
  svg: 'image/svg+xml',
  ico: 'image/x-icon',
  png: 'image/png',
  webp: 'image/webp',
};
const OBRIGATORIOS = ['index.html', '404.html'];

// `*` casa qualquer sequência, inclusive `/` (mesma semântica do Resource do IAM).
const casa = (padrao, chave) =>
  new RegExp('^' + padrao.split('*').map((p) => p.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$').test(chave);
const tipo = (chave) => TIPOS[chave.slice(chave.lastIndexOf('.') + 1).toLowerCase()];

function copia(build, bucket, chave, cache) {
  const ct = tipo(chave);
  return ['s3', 'cp', `${build}/${chave}`, `s3://${bucket}/${chave}`, '--cache-control', cache, ...(ct ? ['--content-type', ct] : [])];
}

/** Arquivos do build (relativos) → { erros, comandos }; com erro, nenhum comando. */
export function planejar(arquivos, { build, bucket, distribuicao, prefixos = PREFIXOS }) {
  const chaves = arquivos.map((f) => f.replaceAll('\\', '/')).sort();
  const erros = [
    ...chaves.filter((c) => !prefixos.some((p) => casa(p, c))).map((c) => `fora dos prefixos do site: ${c}`),
    ...OBRIGATORIOS.filter((o) => !chaves.includes(o)).map((o) => `faltando no build: ${o}`),
  ];
  if (erros.length) return { erros, comandos: [] };

  const app = chaves.filter((c) => c.startsWith('_app/'));
  const html = chaves.filter((c) => c.endsWith('.html'));
  const outros = chaves.filter((c) => !c.startsWith('_app/') && !c.endsWith('.html'));
  const sync = ['s3', 'sync', `${build}/_app`, `s3://${bucket}/_app/`, '--exclude', 'version.json', '--size-only', '--cache-control', IMUTAVEL];

  // Na raiz só cabem os OBRIGATORIOS (prefixos.json); vão por último, depois das páginas que linkam.
  const internos = html.filter((c) => c.includes('/'));
  const htmlOrdenado = [...internos, '404.html', 'index.html'];
  const dirs = [...new Set(internos.map((c) => `/${c.split('/')[0]}/*`))];
  const caminhos = ['/index.html', '/404.html', ...dirs, '/assets/*'];

  const temApp = app.some((c) => c !== '_app/version.json');
  const comandos = [
    ...(temApp ? [sync] : []),
    ...(app.includes('_app/version.json') ? [copia(build, bucket, '_app/version.json', CURTO)] : []),
    ...outros.map((c) => copia(build, bucket, c, c.startsWith('assets/') || c.startsWith('favicon.') ? ASSET : CURTO)),
    ...htmlOrdenado.map((c) => copia(build, bucket, c, CURTO)),
    ['cloudfront', 'create-invalidation', '--distribution-id', distribuicao, '--paths', ...caminhos],
    // Só no fim: HTML novo já no ar; o que sobrou em _app/ é do build anterior.
    ...(temApp ? [[...sync, '--delete']] : []),
  ];
  return { erros: [], comandos };
}

function listar(dir) {
  return readdirSync(dir, { recursive: true, withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => relative(dir, join(e.parentPath, e.name)));
}

function argumentos(argv) {
  const a = { ensaio: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--ensaio') a.ensaio = true;
    else if (argv[i].startsWith('--')) a[argv[i].slice(2)] = argv[++i];
  }
  return a;
}

const exibir = (args) => 'aws ' + args.map((x) => (/[\s;,]/.test(x) ? `"${x}"` : x)).join(' ');

function principal() {
  const a = argumentos(process.argv.slice(2));
  if (!a.build || !a.bucket || !a.distribuicao) {
    console.error('uso: node publicar.mjs --build <dir> --bucket <nome> --distribuicao <id> [--ensaio]');
    return 1;
  }
  const { erros, comandos } = planejar(listar(a.build), { build: a.build.replaceAll('\\', '/'), bucket: a.bucket, distribuicao: a.distribuicao });
  if (erros.length) {
    for (const e of erros) console.error(e);
    return 1;
  }
  for (const c of comandos) {
    console.log(exibir(c));
    if (a.ensaio) continue;
    const r = spawnSync('aws', c, { stdio: 'inherit' });
    if (r.status !== 0) {
      console.error(`falhou (${r.status ?? r.error}): ${exibir(c)}`);
      return 1;
    }
  }
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exitCode = principal();
