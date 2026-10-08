import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { EXPIRADAS, servir } from './fixtura.ts';

const CARD = '[data-grade] article';

async function comFavoritos(page: Page, ids: number[]) {
	await page.goto('/');
	await page.evaluate((v) => localStorage.setItem('besave:favoritos', JSON.stringify(v)), ids);
	await page.goto('/desejos/');
}

test.beforeEach(async ({ page }) => {
	await servir(page);
});

// HOM-07 + DES-01: ♡ na home, depois /desejos/ pelo ícone do topo.
test('♡ na home aparece em /desejos/', async ({ page }) => {
	await page.goto('/');
	const card = page.locator(CARD).nth(3);
	const id = await card.getAttribute('data-id');
	await card.getByRole('button', { name: 'Lista de desejos' }).click();
	await expect(page.locator('[data-topo] [data-contador]')).toHaveText('1');
	await page.locator('[data-topo]').getByRole('link', { name: 'Lista de desejos' }).click();
	await expect(page).toHaveURL(/\/desejos\/$/);
	await expect(page.locator(CARD)).toHaveCount(1);
	await expect(page.locator(CARD)).toHaveAttribute('data-id', String(id));
});

// DES-01: todos os favoritos achados, na ordem da lista (expirada incluída, em cinza).
test('lista os favoritos do catálogo', async ({ page }) => {
	await comFavoritos(page, [1003, 20, EXPIRADAS[0]]);
	await expect(page.locator(CARD)).toHaveCount(3);
	const ids = await page
		.locator(CARD)
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')));
	expect(ids).toEqual(['1003', '20', String(EXPIRADAS[0])]);
	await expect(page.locator(CARD).nth(2)).toContainText('Expirada');
});

// DES-02
test('id fora do catálogo: "saiu do ar" e Remover', async ({ page }) => {
	await comFavoritos(page, [999_999, 20]);
	const fora = page.locator('[data-fora-do-ar="999999"]');
	await expect(fora).toContainText('Esta oferta saiu do ar');
	await expect(page.locator(CARD)).toHaveCount(1);
	await fora.getByRole('button', { name: 'Remover' }).click();
	await expect(fora).toHaveCount(0);
	await expect(page.locator('[data-topo] [data-contador]')).toHaveText('1');
	expect(await page.evaluate(() => localStorage.getItem('besave:favoritos'))).toBe('[20]');
});

// DES-02: antes de o catálogo completar, favorito não achado é "Carregando…", nunca "saiu do ar".
test('catálogo incompleto: carregando, não "saiu do ar"', async ({ page }) => {
	let liberar = () => {};
	const segurado = new Promise<void>((r) => (liberar = r));
	await page.goto('/');
	await page.evaluate(() => localStorage.setItem('besave:favoritos', '[1003]'));
	await page.route('**/data/chunks/1-*', async (r) => {
		await segurado;
		await r.fallback();
	});
	await page.goto('/desejos/');
	await expect(page.getByText('Carregando…')).toBeVisible();
	await expect(page.getByText('Esta oferta saiu do ar')).toHaveCount(0);
	liberar();
	await expect(page.locator(CARD)).toHaveAttribute('data-id', '1003');
	await expect(page.getByText('Carregando…')).toHaveCount(0);
});

// DES-03
test('lista vazia mostra aviso e link para a home', async ({ page }) => {
	await page.goto('/desejos/');
	const vazia = page.locator('[data-vazia]');
	await expect(vazia).toContainText('Sua lista está vazia');
	await expect(vazia.getByRole('link', { name: 'Ver ofertas' })).toHaveAttribute('href', '/');
	await expect(page.locator(CARD)).toHaveCount(0);
});
