// Casos de borda da spec (BSV-30, "Edge Cases").
import { expect, test } from '@playwright/test';
import { catalogo, servir } from './fixtura.ts';

const GRADE = '[data-grade] article';

// Manifest ilegível antes da primeira carga: aviso no lugar da grade e da faixa.
test('manifest ilegível mostra aviso de erro', async ({ page }) => {
	await servir(page);
	await page.route('**/manifest.json', (r) =>
		r.fulfill({ contentType: 'application/json', body: '{nao e json' })
	);
	await page.goto('/');
	await expect(page.getByRole('alert')).toHaveText(
		'Não foi possível carregar as ofertas. Tente de novo em instantes.'
	);
	await expect(page.locator('[data-grade]')).toHaveCount(0);
	await expect(page.locator('[data-faixa]')).toHaveCount(0);
});

// Nenhum desconto nas últimas 24 h: a faixa diz isso e a grade continua.
test('faixa de descontos vazia', async ({ page }) => {
	const c = catalogo();
	for (const cards of c.values()) for (const card of cards) card.pd = null;
	await servir(page, c);
	await page.goto('/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	const faixa = page.locator('[data-faixa]');
	await expect(faixa).toHaveText('Sem descontos novos nas últimas 24 h.');
	await expect(faixa.locator('a')).toHaveCount(0);
	await expect(page.locator(GRADE)).toHaveCount(40);
});

// Busca (BSV-34, TOP-01, TOP-05): 1 caractere (normalizado) não sai da home nem filtra a grade;
// 2 caracteres levam a /busca/.
test('menos de 2 caracteres fica na home com a lista normal', async ({ page }) => {
	await servir(page);
	await page.goto('/');
	await expect(page.locator(GRADE)).toHaveCount(40);
	const primeiros = await page
		.locator(GRADE)
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')));
	const busca = page.getByRole('searchbox', { name: 'Buscar ofertas' });
	for (const q of ['p', ' p ', 'é', '-']) {
		await busca.fill(q);
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('#titulo-recentes')).toContainText('Mais recentes');
		await expect(page.locator('[data-faixa]')).toBeVisible();
		const ids = await page
			.locator(GRADE)
			.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')));
		expect(ids, q).toEqual(primeiros);
	}
	// Com 2 caracteres já vai para a busca (fronteira).
	await busca.fill('pr');
	await expect(page).toHaveURL(/\/busca\/\?q=pr$/);
});
