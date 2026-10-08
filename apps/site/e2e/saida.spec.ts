// Saída do `pnpm build`: 404, ausência de fallback, besave.css e fontes (MANIFEST §1, §5).
import { readFileSync, readdirSync } from 'node:fs';
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
