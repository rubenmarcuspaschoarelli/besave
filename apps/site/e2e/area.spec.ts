// Páginas de área /{slug}/ (BSV-30b, CONTRATO §2.3).
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { catalogo, servir, todos } from './fixtura.ts';

const GRADE = '[data-grade] article';
const BUILD = new URL('../build/', import.meta.url);

const AREAS: [string, string, string][] = [
	['tech', 'TECH', 'Tech'],
	['players', 'PLAYERS', 'Players'],
	['meu-lar', 'MEU_LAR', 'Meu Lar'],
	['elas', 'ELAS', 'Elas'],
	['eles', 'ELES', 'Eles'],
	['cultura', 'CULTURA', 'Cultura'],
	['familia', 'FAMILIA', 'Família & filhos'],
	['pets', 'PETS', 'Pets'],
	['esporte-vida', 'ESPORTE_VIDA', 'Esporte & vida'],
	['outros', 'OUTROS', 'Outros']
];

const areasDe = (page: Page, sel: string) =>
	page.locator(sel).evaluateAll((els) => els.map((e) => e.getAttribute('data-area') ?? ''));

// ARE-01, ARE-02, ARE-03
for (const [slug, , rotulo] of AREAS) {
	test(`/${slug}/: 200, h1, title, description e canonical`, async ({ page }) => {
		await servir(page);
		const r = await page.goto(`/${slug}/`);
		expect(r?.status()).toBe(200);
		const h1 = page.getByRole('heading', { level: 1 });
		await expect(h1).toHaveText(`Ofertas de ${rotulo}`);
		await expect(h1).toBeVisible();
		expect(await h1.evaluate((e) => getComputedStyle(e).fontFamily)).toMatch(/^"?Lato"?,/);
		await expect(page).toHaveTitle(`Ofertas de ${rotulo} · Besave`);
		await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
			'href',
			`https://besave.com.br/${slug}/`
		);
		const descricao = await page.locator('meta[name="description"]').getAttribute('content');
		expect(descricao).toContain(rotulo);
		// No HTML do build, sem depender de JS.
		const html = readFileSync(new URL(`${slug}/index.html`, BUILD), 'utf8');
		expect(html).toContain(`<link rel="canonical" href="https://besave.com.br/${slug}/"`);
		expect(html).not.toMatch(/<meta name="robots"[^>]*noindex/);
	});
}

// ARE-04
test('/elas/: grade e faixa só com ELAS', async ({ page }) => {
	await servir(page);
	await page.goto('/elas/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	const grade = await areasDe(page, GRADE);
	expect(grade.length).toBeGreaterThan(0);
	expect(new Set(grade)).toEqual(new Set(['ELAS']));
	const faixa = page.locator('[data-faixa] a');
	await expect(faixa.first()).toBeVisible();
	const ids = await faixa.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))));
	const porId = new Map(todos(catalogo()).map((c) => [c.id, c.a]));
	expect(ids.length).toBeGreaterThan(0);
	expect(new Set(ids.map((id) => porId.get(id)))).toEqual(new Set(['ELAS']));
});

// ARE-05
test('busca em /elas/ não traz outra área; na home traz', async ({ page }) => {
	await servir(page);
	const esperados = todos(catalogo())
		.filter((c) => c.a === 'ELAS' && /\bprotetor/i.test(c.t) && !c.x)
		.map((c) => c.id)
		.sort((a, b) => a - b);
	expect(esperados.length).toBeGreaterThan(1);

	await page.goto('/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	await page.getByRole('searchbox', { name: 'Buscar ofertas' }).fill('protetor');
	await expect(page.locator('#titulo-recentes')).toContainText('Resultados para');
	expect(new Set(await areasDe(page, GRADE)).size).toBeGreaterThan(1);

	await page.goto('/elas/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	await page.getByRole('searchbox', { name: 'Buscar ofertas' }).fill('protetor');
	await expect(page.locator('#titulo-recentes')).toContainText('Resultados para “protetor”');
	await expect(page.locator(GRADE)).toHaveCount(esperados.length);
	expect(new Set(await areasDe(page, GRADE))).toEqual(new Set(['ELAS']));
	const ids = await page
		.locator(GRADE)
		.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))));
	expect(ids.sort((a, b) => a - b)).toEqual(esperados);
});

// ARE-06
test('/xyz/ responde 404', async ({ request }) => {
	for (const p of ['/xyz/', '/elas-x/']) {
		expect((await request.get(p)).status(), p).toBe(404);
	}
});

// ARE-07
test('/elas/ mantém barra, topo, ♡, "Ver mais" e rodapé', async ({ page }) => {
	// Tudo em ELAS: mais de 40 cards para o "Ver mais" aparecer.
	const soElas = new Map(
		[...catalogo()].map(([n, cs]) => [n, cs.map((c) => ({ ...c, a: 'ELAS' as const }))])
	);
	await servir(page, soElas);
	await page.goto('/elas/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	await expect(page.locator('[data-barra-canal]')).toBeVisible();
	await expect(page.locator('[data-topo]')).toBeVisible();
	await expect(page.locator('footer')).toContainText('links são de afiliado');
	const contador = page.locator('[data-topo] [data-contador]');
	await page.locator(GRADE).first().getByRole('button', { name: 'Lista de desejos' }).click();
	await expect(contador).toHaveText('1');
	await expect(page.locator(GRADE)).toHaveCount(40);
	await page.getByRole('button', { name: 'Ver mais ofertas' }).click();
	await expect(page.locator(GRADE)).toHaveCount(80);
});
