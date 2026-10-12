// BSV-39: a dieta do carregamento inicial não muda a ordem dos pedidos nem o rodapé.
import { readFileSync, readdirSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { catalogo, servir } from './fixtura.ts';

const BUILD = new URL('../build/', import.meta.url);
const ler = (rel: string) => readFileSync(new URL(rel, BUILD), 'utf8');

// DIE-05: manifest primeiro; os 3 chunks de `n` mais alto antes dos demais, em `n` decrescente.
test('primeira carga: manifest, depois os 3 chunks mais recentes, depois o resto', async ({
	page
}) => {
	const cards = [...catalogo().values()].flat();
	// Cinco chunks (n = 0..4): o mesmo catálogo espalhado pelas faixas de id de cada `n`.
	const c = new Map(
		[0, 1, 2, 3, 4].map((n) => [
			n,
			cards.filter((_, i) => i % 5 === n).map((card, j) => ({ ...card, id: n * 1000 + j + 1 }))
		])
	);
	const pedidos: string[] = [];
	page.on('request', (r) => {
		const p = new URL(r.url()).pathname;
		if (p === '/manifest.json') pedidos.push('manifest');
		else if (p.startsWith('/data/chunks/'))
			pedidos.push(`chunk ${p.split('/').pop()?.split('-')[0]}`);
	});
	await servir(page, c);
	await page.goto('/');
	await expect(page.locator('[data-grade] article').first()).toBeVisible();
	await expect.poll(() => pedidos.length).toBe(6);
	expect(pedidos.slice(0, 4)).toEqual(['manifest', 'chunk 4', 'chunk 3', 'chunk 2']);
	expect([...pedidos.slice(4)].sort()).toEqual(['chunk 0', 'chunk 1']);
});

/** Páginas do build (todas prerenderizadas). */
const htmls = (readdirSync(BUILD, { recursive: true }) as string[])
	.map((f) => f.replaceAll('\\', '/'))
	.filter((f) => f.endsWith('.html'));

// DIE-07
test('um rodapé por página, igual em todas, dentro do contêiner do app', () => {
	const rodapes = new Set<string>();
	for (const p of htmls) {
		const html = ler(p);
		const achados = html.match(/<footer[\s\S]*?<\/footer>/g) ?? [];
		expect(achados, p).toHaveLength(1);
		const [rodape = ''] = achados;
		rodapes.add(rodape);
		// Depois da raiz do Svelte e antes de fechar o `<div style="display: contents">`.
		const conteiner =
			html.match(/<div style="display: contents">([\s\S]*)<\/div>\s*<\/body>/)?.[1] ?? '';
		expect(conteiner, p).toContain(rodape);
		expect(conteiner.indexOf(rodape), p).toBeGreaterThan(conteiner.indexOf('<script'));
	}
	expect(rodapes.size).toBe(1);
	const [rodape] = rodapes;
	expect(rodape).toContain('Os links são de afiliado');
	expect(rodape).toContain('href="/desejos/"');
	expect(rodape).toContain('href="https://t.me/besaveofertas"');
});

// DIE-08
test('"Lista de desejos" no rodapé navega sem recarregar e o rodapé continua único', async ({
	page
}) => {
	await servir(page);
	await page.goto('/');
	await expect(page.locator('[data-grade] article').first()).toBeVisible();
	await page.evaluate(() => ((window as unknown as { marca: number }).marca = 39));
	await page.locator('footer').getByRole('link', { name: 'Lista de desejos' }).click();
	await expect(page).toHaveURL(/\/desejos\/$/);
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lista de desejos');
	expect(await page.evaluate(() => (window as unknown as { marca?: number }).marca)).toBe(39);
	await expect(page.locator('footer')).toHaveCount(1);
	await page.goBack();
	await expect(page.locator('[data-grade] article').first()).toBeVisible();
	await expect(page.locator('footer')).toHaveCount(1);
});

// DIE-09: o rodapé vem no HTML; o JS inicial da home não tem o texto dele.
test('JS inicial da home sem o rodapé', () => {
	const vistos = new Set<string>();
	const fila = [...ler('index.html').matchAll(/(?:href="|import\(")(\/_app\/[^"]+\.js)"/g)].map(
		(m) => m[1]
	);
	while (fila.length) {
		const f = fila.shift() as string;
		if (vistos.has(f)) continue;
		vistos.add(f);
		const codigo = ler(f.slice(1));
		expect(codigo, f).not.toContain('Sobre a Besave');
		for (const m of codigo.matchAll(/(?:from|import)\s*"(\.{1,2}\/[^"]+\.js)"/g))
			fila.push(new URL(m[1], `http://x${f}`).pathname);
	}
	expect(vistos.size).toBeGreaterThan(5);
});

// DIE-06: os utilitários próprios (app.css) desenham o mesmo que os do Tailwind que substituíram.
test('expirada em cinza, foco do card na cor de foco, sombra do menu "Mais"', async ({ page }) => {
	await servir(page);
	await page.goto('/busca/?q=produto+7');
	const expirada = page.locator('[data-grade] article', { hasText: 'Encerrada' }).first();
	await expect(expirada.locator('img')).toHaveCSS('filter', 'grayscale(1)');
	await expect(page.locator('[data-grade] article strong').first()).toHaveCSS(
		'font-variant-numeric',
		'tabular-nums'
	);
	const card = page.locator('[data-grade] article').first();
	await card.locator('a').first().focus();
	await page.keyboard.press('Shift+Tab');
	await page.keyboard.press('Tab');
	await expect(card).toHaveCSS('box-shadow', 'rgb(29, 78, 216) 0px 0px 0px 2px');
	await page.goto('/');
	await page.getByText('Mais ▾').click();
	await expect(page.locator('nav details div.absolute')).toHaveCSS(
		'box-shadow',
		'rgba(0, 0, 0, 0.1) 0px 10px 15px -3px, rgba(0, 0, 0, 0.1) 0px 4px 6px -4px'
	);
});
