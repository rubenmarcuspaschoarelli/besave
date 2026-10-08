import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { EXPIRADAS, catalogo, servir, todos } from './fixtura.ts';

const GRADE = '[data-grade] article';

const atributos = (page: Page, nome: string) =>
	page.locator(GRADE).evaluateAll((els, n) => els.map((e) => e.getAttribute(n) ?? ''), nome);

test.beforeEach(async ({ page }) => {
	await servir(page);
	await page.goto('/');
	await expect(page.locator(GRADE).first()).toBeVisible();
});

// HOM-01
test('ordem: barra, topo, descontos, recentes, rodapé', async ({ page }) => {
	const ys: number[] = [];
	for (const s of [
		'[data-barra-canal]',
		'[data-topo]',
		'#titulo-descontos',
		'#titulo-recentes',
		'footer'
	]) {
		ys.push((await page.locator(s).boundingBox())?.y ?? -1);
	}
	expect(ys.every((y) => y >= 0)).toBe(true);
	expect([...ys].sort((a, b) => a - b)).toEqual(ys);
	await expect(page.locator('[data-faixa] a')).toHaveCount(8);
});

// HOM-02
test('topo fica fixo ao rolar', async ({ page }) => {
	await page.mouse.wheel(0, 2500);
	await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(1000);
	const caixa = await page.locator('[data-topo]').boundingBox();
	expect(Math.abs(caixa?.y ?? 99)).toBeLessThan(1);
	await expect(page.getByRole('link', { name: 'Besave', exact: true })).toBeInViewport();
});

// HOM-03
test('barra do canal fecha e não volta ao recarregar', async ({ page }) => {
	const barra = page.locator('[data-barra-canal]');
	await expect(barra).toBeVisible();
	await page.getByRole('button', { name: 'Fechar aviso do canal' }).click();
	await expect(barra).toBeHidden();
	await page.reload();
	await expect(page.locator(GRADE).first()).toBeVisible();
	await expect(barra).toBeHidden();
});

// HOM-04
test('área filtra a grade; Outros só no menu Mais', async ({ page }) => {
	const nav = page.getByRole('navigation', { name: 'Áreas' });
	await expect(nav.getByRole('button', { name: 'Outros' })).toBeHidden();

	await nav.getByRole('button', { name: 'Tech', exact: true }).click();
	await expect(page.locator('#titulo-recentes')).toContainText('Tech');
	const tech = await atributos(page, 'data-area');
	expect(tech.length).toBeGreaterThan(0);
	expect(new Set(tech)).toEqual(new Set(['TECH']));

	await nav.getByText('Mais ▾').click();
	await nav.getByRole('button', { name: 'Outros' }).click();
	await expect(page.locator('#titulo-recentes')).toContainText('Outros');
	const outros = await atributos(page, 'data-area');
	expect(outros.length).toBeGreaterThan(0);
	expect(new Set(outros)).toEqual(new Set(['OUTROS']));
});

// HOM-05
test('busca "protetor" mostra só cards com a palavra', async ({ page }) => {
	const esperados = todos(catalogo())
		.filter((c) => /\bprotetor/i.test(c.t))
		.map((c) => c.id)
		.sort((a, b) => a - b);
	expect(esperados.length).toBeGreaterThan(1);
	await page.getByRole('searchbox', { name: 'Buscar ofertas' }).fill('protetor');
	await expect(page.locator('#titulo-recentes')).toContainText('Resultados para “protetor”');
	await expect(page.locator(GRADE)).toHaveCount(esperados.length);
	const ids = (await atributos(page, 'data-id')).map(Number).sort((a, b) => a - b);
	expect(ids).toEqual(esperados);
	for (const t of await page.locator(`${GRADE} h3`).allTextContents()) {
		expect(t).toMatch(/protetor/i);
	}
});

// HOM-06
test('"Ver mais ofertas" acrescenta 40', async ({ page }) => {
	await expect(page.locator(GRADE)).toHaveCount(40);
	const primeiros = await atributos(page, 'data-id');
	await page.getByRole('button', { name: 'Ver mais ofertas' }).click();
	await expect(page.locator(GRADE)).toHaveCount(80);
	const depois = await atributos(page, 'data-id');
	expect(depois.slice(0, 40)).toEqual(primeiros);
	expect(depois.map(Number)).not.toContain(EXPIRADAS[1]);
});

// HOM-07
test('♡ atualiza o contador do topo', async ({ page }) => {
	const contador = page.locator('[data-topo] [data-contador]');
	const coracao = (i: number) =>
		page.locator(GRADE).nth(i).getByRole('button', { name: 'Lista de desejos' });
	await expect(contador).toHaveCount(0);
	await coracao(0).click();
	await expect(contador).toHaveText('1');
	await expect(coracao(0)).toHaveAttribute('aria-pressed', 'true');
	await coracao(1).click();
	await expect(contador).toHaveText('2');
	await coracao(0).click();
	await expect(contador).toHaveText('1');
});

// HOM-08
test('card abre /oferta/{id}/', async ({ page }) => {
	const card = page.locator(GRADE).nth(2);
	const id = await card.getAttribute('data-id');
	expect(Number(id)).toBeGreaterThan(0);
	await card.locator('h3').click();
	await expect(page).toHaveURL(new RegExp(`/oferta/${id}/$`));
});

// HOM-09
test('2 colunas no celular, 5 no desktop', async ({ page }, info) => {
	const colunas = await page
		.locator('[data-grade]')
		.evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length);
	expect(colunas).toBe(info.project.name === 'celular' ? 2 : 5);
	// As colunas cabem na tela: nada de rolagem horizontal da página.
	const largura = info.project.use.viewport?.width ?? 0;
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
		largura
	);
	const ultimo = await page
		.locator(GRADE)
		.nth(colunas - 1)
		.boundingBox();
	expect((ultimo?.x ?? 0) + (ultimo?.width ?? Infinity)).toBeLessThanOrEqual(largura);
});

// HOM-10
test('rede: só manifest.json e chunks; nenhum link /ir/', async ({ page }) => {
	const pedidos: string[] = [];
	page.on('request', (r) => {
		if (['fetch', 'xhr'].includes(r.resourceType())) pedidos.push(new URL(r.url()).pathname);
	});
	await page.reload();
	await expect(page.locator(GRADE).first()).toBeVisible();
	expect(pedidos.length).toBeGreaterThan(1);
	for (const p of pedidos) expect(p).toMatch(/^\/(manifest\.json|data\/chunks\/[^/]+\.json\.br)$/);
	expect(await page.locator('a[href*="/ir/"]').count()).toBe(0);
});

// HOM-11
test('rodapé com aviso de afiliado e canal; sem redes sem link', async ({ page }) => {
	const rodape = page.locator('footer');
	await expect(rodape).toContainText('links são de afiliado');
	await expect(rodape.getByRole('link', { name: 'Canal do Telegram' })).toHaveAttribute(
		'href',
		'https://t.me/besaveofertas'
	);
	for (const r of ['X', 'Instagram', 'Facebook', 'YouTube', 'Discord', 'Android', 'iOS']) {
		await expect(rodape.getByRole('link', { name: r, exact: true })).toHaveCount(0);
	}
});
