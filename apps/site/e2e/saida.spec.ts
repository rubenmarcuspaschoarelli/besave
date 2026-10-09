// Saída do `pnpm build`: 404, ausência de fallback, besave.css e fontes (MANIFEST §1, §5).
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { servir } from './fixtura.ts';

const BUILD = new URL('../build/', import.meta.url);
const ler = (rel: string) => readFileSync(new URL(rel, BUILD), 'utf8');

// ERR-01
test('404.html: noindex, texto, início e canal', async ({ page }) => {
	const html = ler('404.html');
	expect(html).toContain('<meta name="robots" content="noindex"');
	await page.goto('/404.html');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText(
		'Oferta encerrada ou não encontrada'
	);
	const main = page.locator('main');
	await expect(main.getByRole('link', { name: 'Ir para o início' })).toHaveAttribute('href', '/');
	await expect(main.getByRole('link', { name: 'Canal do Telegram' })).toHaveAttribute(
		'href',
		'https://t.me/besaveofertas'
	);
	// Servida em qualquer path: assets sempre absolutos.
	expect(html).not.toMatch(/(href|src)="\.\.?\//);
});

// ERR-02: só páginas prerenderizadas, sem fallback SPA.
test('build sem fallback', () => {
	const htmls = (readdirSync(BUILD, { recursive: true }) as string[])
		.map((f) => f.replaceAll('\\', '/'))
		.filter((f) => f.endsWith('.html'))
		.sort();
	expect(htmls).toEqual(
		[
			'404.html',
			'desejos/index.html',
			'index.html',
			// ARE-01: as 10 áreas do CONTRATO §2.3.
			...[
				'tech',
				'players',
				'meu-lar',
				'elas',
				'eles',
				'cultura',
				'familia',
				'pets',
				'esporte-vida',
				'outros'
			].map((s) => `${s}/index.html`)
		].sort()
	);
});

// CSS-01
test('/assets/besave.css sai do build como text/css', async ({ request }) => {
	expect(ler('assets/besave.css')).toContain('--cor-marca:#0b6e4f');
	const r = await request.get('/assets/besave.css');
	expect(r.status()).toBe(200);
	expect(r.headers()['content-type']).toContain('text/css');
});

// TOK-02, TOK-03: Lato carregada do próprio site; logo em Lato 900 na cor da marca; corpo no sistema.
test('Lato no logo e nos títulos, fonte do sistema no corpo', async ({ page }) => {
	const fontes: string[] = [];
	page.on('request', (r) => {
		if (r.resourceType() === 'font') fontes.push(new URL(r.url()).pathname);
	});
	await servir(page);
	await page.goto('/');
	await page.evaluate(() => document.fonts.ready);
	const logo = page.getByRole('link', { name: 'Besave', exact: true });
	await expect(logo).toHaveCSS('font-weight', '900');
	await expect(logo).toHaveCSS('color', 'rgb(11, 110, 79)');
	expect(await logo.evaluate((e) => getComputedStyle(e).fontFamily)).toMatch(/^"?Lato"?,/);
	expect(
		await page.locator('#titulo-recentes').evaluate((e) => getComputedStyle(e).fontFamily)
	).toMatch(/^"?Lato"?,/);
	expect(await page.locator('body').evaluate((e) => getComputedStyle(e).fontFamily)).toMatch(
		/^system-ui/
	);
	expect(await page.evaluate(() => document.fonts.check('900 16px Lato'))).toBe(true);
	// FNT-03: a Lato vem do arquivo com hash do build.
	expect(
		fontes.some((f) => /^\/_app\/immutable\/assets\/lato-latin-900-normal\.[\w-]+\.woff2$/.test(f))
	).toBe(true);
	expect(fontes.filter((f) => f.startsWith('/assets/fontes/'))).toEqual([]);
});

// FNT-01, FNT-02: Lato com hash em _app/immutable/assets, citada pelo CSS do site e pelo besave.css.
test('Lato sai do build com hash e sem cópia em assets/fontes', () => {
	const imutaveis = readdirSync(new URL('_app/immutable/assets/', BUILD));
	const cssSite = imutaveis
		.filter((f) => f.endsWith('.css'))
		.map((f) => ler(`_app/immutable/assets/${f}`));
	const besave = ler('assets/besave.css');
	for (const peso of [700, 900]) {
		const arquivo = imutaveis.find((f) =>
			new RegExp(`^lato-latin-${peso}-normal\\.[\\w-]{6,}\\.woff2$`).test(f)
		);
		expect(arquivo, String(peso)).toBeDefined();
		const url = `/_app/immutable/assets/${arquivo}`;
		expect(besave, `besave.css ${peso}`).toContain(`url(${url})`);
		// O CSS do site pode estar só embutido no HTML (CSS-04): procura nos dois.
		const html = ler('index.html');
		expect(
			[...cssSite, html].some((c) => c.includes(`url(${url})`)),
			`site ${peso}`
		).toBe(true);
	}
	expect(readdirSync(new URL('assets/fontes/', BUILD))).toEqual(['OFL.txt']);
});

// CSS-04: CSS da página num <style>. O SvelteKit mantém um <link> `disabled` com media que nunca casa
// (kit/src/runtime/server/page/render.js) só para o roteador saber que o CSS já está na página.
const PAGINAS = [
	'index.html',
	'elas/index.html',
	'outros/index.html',
	'desejos/index.html',
	'404.html'
];
test('CSS embutido: <style> com o CSS e nenhum <link> de CSS ativo', () => {
	for (const p of PAGINAS) {
		const html = ler(p);
		const estilo = html.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '';
		expect(estilo.length, p).toBeGreaterThan(10_000);
		expect(estilo, p).toContain('--cor-marca:#0b6e4f');
		const links = html.match(/<link\b[^>]*rel="stylesheet"[^>]*>/g) ?? [];
		for (const l of links) {
			expect(l, p).toMatch(/\sdisabled[\s>]/);
			expect(l, p).toContain('media="(max-width: 0)"');
		}
	}
});

test('home e área abrem sem pedir arquivo de CSS', async ({ page }) => {
	await servir(page);
	for (const url of ['/', '/elas/']) {
		const css: string[] = [];
		const ouvir = (r: { resourceType(): string; url(): string }) => {
			if (r.resourceType() === 'stylesheet' || r.url().endsWith('.css')) css.push(r.url());
		};
		page.on('request', ouvir);
		await page.goto(url);
		await expect(page.locator('[data-grade] article').first()).toBeVisible();
		page.off('request', ouvir);
		expect(css, url).toEqual([]);
		// O desenho continua: logo em Lato 900 na cor da marca.
		const logo = page.getByRole('link', { name: 'Besave', exact: true });
		await expect(logo).toHaveCSS('font-weight', '900');
		await expect(logo).toHaveCSS('color', 'rgb(11, 110, 79)');
	}
});

// BUD-01: JS inicial da home (modulepreload + imports estáticos, bruto) + CSS embutido ≤ 150 KiB.
const ORCAMENTO_KIB = 150;

/** Arquivos `/_app/...js` que a home pede ao abrir, seguindo os imports estáticos. */
function jsInicial(html: string): Map<string, number> {
	const vistos = new Map<string, number>();
	const fila = [...html.matchAll(/(?:href="|import\(")(\/_app\/[^"]+\.js)"/g)].map((m) => m[1]);
	while (fila.length) {
		const f = fila.shift() as string;
		if (vistos.has(f)) continue;
		const arquivo = new URL(f.slice(1), BUILD);
		expect(existsSync(arquivo), f).toBe(true);
		const codigo = readFileSync(arquivo);
		vistos.set(f, codigo.length);
		for (const m of codigo.toString().matchAll(/(?:from|import)\s*"(\.{1,2}\/[^"]+\.js)"/g))
			fila.push(new URL(m[1], `http://x${f}`).pathname);
	}
	return vistos;
}

test(`bundle inicial da home ≤ ${ORCAMENTO_KIB} KiB`, () => {
	const html = ler('index.html');
	const js = jsInicial(html);
	const css = (html.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '').length;
	const jsBytes = [...js.values()].reduce((a, b) => a + b, 0);
	const total = jsBytes + css;
	test.info().annotations.push({
		type: 'bundle',
		description: `JS ${jsBytes} B (${js.size} arquivos) + CSS ${css} B = ${total} B (${(total / 1024).toFixed(1)} KiB)`
	});
	// Sanidade da medida: entrada do kit e CSS da página entram na conta.
	expect([...js.keys()].some((f) => f.includes('/entry/start.'))).toBe(true);
	expect(js.size).toBeGreaterThan(5);
	expect(css).toBeGreaterThan(10_000);
	expect(total).toBeLessThanOrEqual(ORCAMENTO_KIB * 1024);
});
