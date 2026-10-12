// pnpm inventario — do que é feito o carregamento inicial de uma página (BSV-39, BUD-01).
// Sobre o build: JS seguido como no e2e/saida.spec.ts (modulepreload + imports estáticos, bruto) e
// o CSS embutido. Com `BESAVE_MAPAS=1 pnpm build` antes, divide cada arquivo por módulo-fonte
// (sourcemaps só nesse build; não vão para o deploy). Página: `pnpm inventario elas/index.html`.
import { existsSync, readFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';

const RAIZ = new URL('../', import.meta.url);
const BUILD = new URL('build/', RAIZ);
const ORCAMENTO = 150 * 1024;
const pagina = process.argv[2] ?? 'index.html';

interface Mapa {
	sources: string[];
	mappings: string;
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/** Segmento VLQ de sourcemap → campos (deltas). */
function vlq(s: string): number[] {
	const out: number[] = [];
	let v = 0;
	let desloc = 0;
	for (const ch of s) {
		let d = B64.indexOf(ch);
		const continua = d & 32;
		d &= 31;
		v += d << desloc;
		if (continua) desloc += 5;
		else {
			out.push(v & 1 ? -(v >> 1) : v >> 1);
			v = 0;
			desloc = 0;
		}
	}
	return out;
}

/** Bytes do arquivo gerado por fonte (o trecho até o próximo segmento conta para a fonte dele). */
function porFonte(codigo: string, mapa: Mapa): Map<string, number> {
	const linhas = codigo.split('\n');
	const total = new Map<string, number>();
	let fonte = 0;
	mapa.mappings.split(';').forEach((linha, i) => {
		const texto = linhas[i] ?? '';
		const segs: [number, number][] = [];
		let col = 0;
		for (const s of linha ? linha.split(',') : []) {
			const c = vlq(s);
			col += c[0];
			if (c.length > 1) fonte += c[1];
			segs.push([col, c.length > 1 ? fonte : -1]);
		}
		segs.forEach(([ini, f], k) => {
			const fim = k + 1 < segs.length ? segs[k + 1][0] : texto.length;
			const nome = f < 0 ? '(sem fonte)' : mapa.sources[f];
			total.set(nome, (total.get(nome) ?? 0) + fim - ini);
		});
	});
	return total;
}

/** Grupo legível de um caminho de fonte do sourcemap. */
function grupo(fonte: string): string {
	const f = fonte.replaceAll('\\', '/');
	if (f.includes('node_modules/svelte/')) return 'runtime Svelte';
	if (f.includes('node_modules/devalue/')) return 'SvelteKit (devalue)';
	if (f.includes('node_modules/@sveltejs/kit/') || f.includes('.svelte-kit/generated/'))
		return 'SvelteKit';
	if (f.includes('node_modules/')) return f.replace(/.*node_modules\/([^/]+).*/, '$1');
	return f.replace(/^(\.\.\/)+/, '').replace(/^.*?src\//, 'src/');
}

function jsInicial(html: string): Map<string, Buffer> {
	const vistos = new Map<string, Buffer>();
	const fila = [...html.matchAll(/(?:href="|import\(")(\/_app\/[^"]+\.js)"/g)].map((m) => m[1]);
	while (fila.length) {
		const f = fila.shift() as string;
		if (vistos.has(f)) continue;
		// Sem o comentário do sourcemap: os bytes batem com os do build de produção.
		const codigo = Buffer.from(
			readFileSync(new URL(f.slice(1), BUILD), 'utf8').replace(
				/\n\/\/# sourceMappingURL=\S+\s*$/,
				''
			)
		);
		vistos.set(f, codigo);
		for (const m of codigo.toString().matchAll(/(?:from|import)\s*"(\.{1,2}\/[^"]+\.js)"/g))
			fila.push(new URL(m[1], `http://x${f}`).pathname);
	}
	return vistos;
}

const html = readFileSync(new URL(pagina, BUILD), 'utf8');
const js = [...jsInicial(html)].sort((a, b) => b[1].length - a[1].length);
const css = html.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '';
const comMapas = js.some(([f]) => existsSync(new URL(f.slice(1) + '.map', BUILD)));

const kb = (n: number) => n.toLocaleString('pt-BR');
const linhas: string[] = [
	`Página: \`${pagina}\``,
	'',
	'| arquivo | bruto (B) | gzip (B) | conteúdo |',
	'|---|---:|---:|---|'
];
let bruto = 0;
let gzip = 0;
const grupos = new Map<string, number>();
for (const [f, codigo] of js) {
	const g = gzipSync(codigo).length;
	bruto += codigo.length;
	gzip += g;
	const mapa = new URL(f.slice(1) + '.map', BUILD);
	let conteudo = '';
	if (existsSync(mapa)) {
		const fontes = [...porFonte(codigo.toString(), JSON.parse(readFileSync(mapa, 'utf8')))];
		const doArquivo = new Map<string, number>();
		for (const [fonte, n] of fontes) {
			const nome = grupo(fonte);
			doArquivo.set(nome, (doArquivo.get(nome) ?? 0) + n);
			grupos.set(nome, (grupos.get(nome) ?? 0) + n);
		}
		conteudo = [...doArquivo]
			.sort((a, b) => b[1] - a[1])
			.slice(0, 6)
			.map(([nome, n]) => `${nome} ${kb(n)}`)
			.join(', ');
	}
	linhas.push(
		`| \`${f.replace('/_app/immutable/', '')}\` | ${kb(codigo.length)} | ${kb(g)} | ${conteudo} |`
	);
}
linhas.push(
	`| CSS embutido (\`<style>\`) | ${kb(css.length)} | ${kb(gzipSync(css).length)} | Tailwind (tema, preflight, utilitários), tokens, @font-face |`,
	`| **total** (${js.length} JS + CSS) | **${kb(bruto + css.length)}** | ${kb(gzip + gzipSync(css).length)} | folga ${kb(ORCAMENTO - bruto - css.length)} B do limite de ${kb(ORCAMENTO)} B |`
);
// CSS por bloco de topo: camadas do Tailwind, depois tokens/@font-face e os @property.
const marcos = [
	['fallback de variáveis (@layer properties)', css.indexOf('@layer properties{')],
	['tema do Tailwind (@layer theme)', css.indexOf('@layer theme{')],
	['preflight + base do app.css (@layer base)', css.indexOf('@layer base{')],
	['utilitários (@layer utilities)', css.indexOf('@layer utilities{')],
	['tokens, @font-face (fora de camada)', css.indexOf(':root{--cor-')],
	['@property (variáveis --tw-*)', css.indexOf('@property')]
] as const;
const presentes = marcos.filter(([, i]) => i >= 0).sort((a, b) => a[1] - b[1]);
linhas.push('', '| bloco do CSS embutido | bytes |', '|---|---:|');
presentes.forEach(([nome, i], k) => {
	const fim = k + 1 < presentes.length ? presentes[k + 1][1] : css.length;
	linhas.push(`| ${nome} | ${kb(fim - i)} |`);
});
if (comMapas) {
	linhas.push('', '| módulo / grupo | bytes (mapeados) |', '|---|---:|');
	for (const [nome, n] of [...grupos].sort((a, b) => b[1] - a[1]))
		linhas.push(`| ${nome} | ${kb(n)} |`);
} else linhas.push('', 'Sem sourcemaps: `BESAVE_MAPAS=1 pnpm build` para dividir por módulo.');
console.log(linhas.join('\n'));
