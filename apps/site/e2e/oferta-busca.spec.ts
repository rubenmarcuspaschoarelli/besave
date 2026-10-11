// Busca no topo da página da oferta (BSV-34, OFE-04): HTML do worker (golden) sobre o besave.css do build.
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { servir } from './fixtura.ts';

const HTML = readFileSync(
	new URL('../../worker/tests/fixtures/paginas/oferta-pagina-ok.html', import.meta.url),
	'utf8'
);
const OFERTA = '/oferta/5412/';

for (const js of [true, false]) {
	test.describe(js ? 'com JavaScript' : 'sem JavaScript', () => {
		test.use({ javaScriptEnabled: js });

		test('digitar e enviar abre /busca/?q=…', async ({ page }) => {
			await servir(page);
			await page.route(`**${OFERTA}`, (r) => r.fulfill({ contentType: 'text/html', body: HTML }));
			await page.goto(OFERTA);
			const form = page.getByRole('search');
			const campo = form.getByRole('searchbox', { name: 'Buscar ofertas' });
			await expect(campo).toBeVisible();
			await campo.fill('protetor solar');
			await campo.press('Enter');
			await expect(page).toHaveURL(/\/busca\/\?q=protetor\+solar$/);
			if (js) {
				await expect(page.locator('[data-resultado]')).toContainText('para “protetor solar”');
				// A lupa também envia.
				await page.goto(OFERTA);
				await page.getByRole('searchbox', { name: 'Buscar ofertas' }).fill('fone');
				await page.getByRole('button', { name: 'Buscar' }).click();
				await expect(page).toHaveURL(/\/busca\/\?q=fone$/);
			}
		});
	});
}

// OFE-03: a lupa tem área de toque de 44 px e o campo fica no topo, acima da foto.
test('campo e lupa no topo, com área de toque', async ({ page }) => {
	await page.route('**/img/**', (r) => r.fulfill({ status: 404, body: '' }));
	await page.route(`**${OFERTA}`, (r) => r.fulfill({ contentType: 'text/html', body: HTML }));
	await page.goto(OFERTA);
	const lupa = await page.getByRole('button', { name: 'Buscar' }).boundingBox();
	expect(lupa?.width).toBeGreaterThanOrEqual(44);
	expect(lupa?.height).toBeGreaterThanOrEqual(44);
	const campo = await page.getByRole('searchbox', { name: 'Buscar ofertas' }).boundingBox();
	const foto = await page.locator('.foto').boundingBox();
	expect(campo && foto && campo.y + campo.height <= foto.y).toBe(true);
	// O rótulo existe só para leitor de tela.
	const rotulo = await page.locator('label.oculto').boundingBox();
	expect(rotulo?.width ?? 0).toBeLessThanOrEqual(1);
	// As 10 áreas continuam no cabeçalho.
	await expect(page.locator('.menu a')).toHaveCount(10);
	await expect(page.locator('.menu a').first()).toBeVisible();
});
