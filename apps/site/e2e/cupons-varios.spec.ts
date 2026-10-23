// Página da oferta com vários códigos (BSV-50): HTML do worker (golden) sobre o besave.css do build.
import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

const HTML = readFileSync(
	new URL('../../worker/tests/fixtures/paginas/oferta-pagina-cupons.html', import.meta.url),
	'utf8'
);
const ENCERRADA = readFileSync(
	new URL('../../worker/tests/fixtures/paginas/oferta-pagina-encerrada.html', import.meta.url),
	'utf8'
);
const CODIGOS = ['MELI26TODOSITE', 'SITEMELI26', 'MELI26SITETODO'];
const OFERTA = '/oferta/5412/';

test.beforeEach(async ({ page, context, baseURL }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: baseURL });
	await context.route('**/img/**', (r) => r.fulfill({ status: 404, body: '' }));
	await context.route('**/ir/5412', (r) =>
		r.fulfill({ contentType: 'text/html', body: '<!doctype html><title>loja</title>' })
	);
	await context.route(`**${OFERTA}`, (r) => r.fulfill({ contentType: 'text/html', body: HTML }));
	await page.clock.install({ time: new Date('2026-10-09T12:00:00Z') });
	await page.clock.pauseAt(new Date('2026-10-09T12:00:01Z'));
});

const lerClipboard = (page: Page) => page.evaluate(() => navigator.clipboard.readText());

test('lista os três códigos e cada ícone copia o seu', async ({ page }, info) => {
	await page.goto(OFERTA);
	await expect(page.locator('.cupons .codigo')).toHaveText(CODIGOS);
	for (const codigo of CODIGOS) {
		const icone = page.getByRole('button', { name: `Copiar cupom ${codigo}` });
		await expect(icone).toBeVisible();
		const caixa = await icone.boundingBox();
		expect(caixa?.width).toBeGreaterThanOrEqual(44);
		expect(caixa?.height).toBeGreaterThanOrEqual(44);
	}
	for (const codigo of CODIGOS) {
		await page.getByRole('button', { name: `Copiar cupom ${codigo}` }).click();
		await expect.poll(() => lerClipboard(page)).toBe(codigo);
		await expect(page.getByRole('status')).toHaveText('Cupom copiado!');
		// Só o ícone clicado fica marcado.
		await expect(page.locator('.copiar.copiado')).toHaveCount(1);
		await expect(page.getByRole('button', { name: `Copiar cupom ${codigo}` })).toContainClass(
			'copiado'
		);
	}
	await page.screenshot({ path: info.outputPath('tres-cupons.png') });
});

test('botão principal copia o primeiro código e abre a loja', async ({ page, context }) => {
	await page.goto(OFERTA);
	await page.evaluate(() => navigator.clipboard.writeText('outro'));
	const cta = page.getByRole('link', { name: 'Copiar cupom e ir para a loja', exact: true });
	const [loja] = await Promise.all([context.waitForEvent('page'), cta.click()]);
	await loja.waitForLoadState();
	expect(new URL(loja.url()).pathname).toBe('/ir/5412');
	await expect.poll(() => lerClipboard(loja)).toBe(CODIGOS[0]);
});

test.describe('sem JavaScript', () => {
	test.use({ javaScriptEnabled: false });

	test('códigos visíveis, ícones ocultos e CTA é link para /ir/{id}', async ({ page }) => {
		await page.goto(OFERTA);
		await expect(page.locator('.cupons .codigo')).toHaveText(CODIGOS);
		await expect(page.locator('button.copiar')).toHaveCount(3);
		await expect(page.locator('button.copiar').first()).toBeHidden();
		const cta = page.getByRole('link', { name: 'Ir para a loja', exact: true });
		await expect(cta).toHaveAttribute('href', '/ir/5412');
	});
});

test('oferta encerrada mostra a faixa "Encerrada"', async ({ page, context }, info) => {
	await context.route(`**${OFERTA}`, (r) =>
		r.fulfill({ contentType: 'text/html', body: ENCERRADA })
	);
	await page.goto(OFERTA);
	const faixa = page.locator('.expirada');
	await expect(faixa).toHaveText('Encerrada');
	await expect(faixa).toBeVisible();
	await expect(page.getByText('Oferta expirada')).toHaveCount(0);
	await page.screenshot({ path: info.outputPath('encerrada.png') });
});
