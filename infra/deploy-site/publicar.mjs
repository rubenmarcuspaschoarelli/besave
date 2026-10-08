// Publica o build do SvelteKit no bucket compartilhado com o worker (BSV-17).
// Uso: node publicar.mjs --build <dir> --bucket <nome> --distribuicao <id> [--ensaio [--remotos <listagem.json>]]
// Só toca os prefixos de prefixos.json (a mesma lista da policy do papel besave-site-deploy).
import { existsSync, readFileSync, readdirSync } from 'node:fs';
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
const CARENCIA_DIAS = 7;

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
  const sync = ['s3', 'sync', `${build}/_app`, `s3://${bucket}/_app/`, '--exclude', 'version.json', '--cache-control', IMUTAVEL];

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
  ];
  return { erros: [], comandos };
}

/**
 * Limpeza de _app/ com carência: só sai o que (a) não está no build atual e (b) subiu há mais de
 * `dias`. Arquivo do build nunca sai. Sem --size-only, todo deploy reenvia o _app/ do build, então o
 * LastModified é o do último deploy que tinha o arquivo: a carência conta de quando ele saiu do build.
 * Página antiga em cache ainda acha seus chunks durante a carência.
 */
export function expurgar(remotos, arquivosBuild, agora, dias = CARENCIA_DIAS) {
  const build = new Set(arquivosBuild.map((f) => f.replaceAll('\\', '/')));
  const limite = agora - dias * 86_400_000;
  return (remotos ?? [])
    .filter((o) => o.Key.startsWith('_app/') && !build.has(o.Key) && Date.parse(o.LastModified) < limite)
    .map((o) => o.Key)
    .sort();
}

/** Saída de `list-objects-v2 --query Contents[]...` → [{ Key, LastModified }]; prefixo vazio dá `null`. */
export const lerListagem = (saida) => JSON.parse(saida) ?? [];

export const listagem = (bucket) => [
  's3api', 'list-objects-v2', '--bucket', bucket, '--prefix', '_app/',
  '--query', 'Contents[].{Key: Key, LastModified: LastModified}', '--output', 'json',
];

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

// Executor do aws CLI; os testes passam um falso que grava os argumentos.
const awsReal = (args, { capturar = false } = {}) =>
  spawnSync('aws', args, capturar ? { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] } : { stdio: 'inherit' });

export function principal(argv, aws = awsReal, agora = Date.now()) {
  const a = argumentos(argv);
  if (!a.build || !a.bucket || !a.distribuicao) {
    console.error('uso: node publicar.mjs --build <dir> --bucket <nome> --distribuicao <id> [--ensaio [--remotos <listagem.json>]]');
    return 1;
  }
  if (a.remotos && !a.ensaio) {
    console.error('--remotos só com --ensaio: a limpeza real usa a listagem do bucket');
    return 1;
  }
  if (!existsSync(a.build)) {
    console.error(`build não encontrado: ${a.build}`);
    return 1;
  }
  const arquivos = listar(a.build);
  const { erros, comandos } = planejar(arquivos, { build: a.build.replaceAll('\\', '/'), bucket: a.bucket, distribuicao: a.distribuicao });
  if (erros.length) {
    for (const e of erros) console.error(e);
    return 1;
  }
  const executar = (c) => {
    console.log(exibir(c));
    if (a.ensaio) return true;
    const r = aws(c);
    if (r.status !== 0) console.error(`falhou (${r.status ?? r.error}): ${exibir(c)}`);
    return r.status === 0;
  };
  for (const c of comandos) if (!executar(c)) return 1;

  // Limpeza por último: HTML novo já no ar. A listagem é só leitura e roda também no ensaio.
  let remotos;
  if (a.remotos) {
    remotos = lerListagem(readFileSync(a.remotos, 'utf8'));
  } else {
    console.log(exibir(listagem(a.bucket)));
    const r = aws(listagem(a.bucket), { capturar: true });
    if (r.status !== 0) {
      console.error(`falhou (${r.status ?? r.error}): listagem de _app/`);
      return 1;
    }
    try {
      remotos = lerListagem(r.stdout);
    } catch {
      console.error('listagem de _app/ ilegível');
      return 1;
    }
  }
  const velhos = expurgar(remotos, arquivos, agora);
  console.log(`${a.ensaio ? 'apagaria' : 'apagando'} ${velhos.length} arquivo(s) de _app/ fora do build e com mais de ${CARENCIA_DIAS} dias`);
  for (const k of velhos) if (!executar(['s3', 'rm', `s3://${a.bucket}/${k}`])) return 1;
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exitCode = principal(process.argv.slice(2));
