// Página da oferta com cupom (BSV-38): HTML gerado pelo worker (golden) sobre o besave.css do build.
import { readFileSync } from 'node:fs';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const HTML = readFileSync(
	new URL('../../worker/tests/fixtures/paginas/oferta-pagina-ok.html', import.meta.url),
	'utf8'
);
const CODIGO = 'BESAVE10';
const OFERTA = '/oferta/5412/';
const LOJA = '/ir/5412';

/** Serve a página do worker em /oferta/5412/ e uma "loja" em /ir/5412 (o 302 real fica na borda). */
async function servirOferta(context: BrowserContext) {
	await context.route('**/img/**', (r) => r.fulfill({ status: 404, body: '' }));
	await context.route(`**${OFERTA}`, (r) => r.fulfill({ contentType: 'text/html', body: HTML }));
	await context.route(`**${LOJA}`, (r) =>
		r.fulfill({ contentType: 'text/html', body: '<!doctype html><title>loja</title><p>loja</p>' })
	);
}

const lerClipboard = (page: Page) => page.evaluate(() => navigator.clipboard.readText());
const selecao = (page: Page) => page.evaluate(() => window.getSelection()?.toString() ?? '');

test.describe('com JavaScript', () => {
	test.beforeEach(async ({ page, context, baseURL }) => {
		await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: baseURL });
		await servirOferta(context);
		// Relógio controlado: o aviso só some quando o teste avança o tempo.
		await page.clock.install({ time: new Date('2026-10-09T12:00:00Z') });
		await page.clock.pauseAt(new Date('2026-10-09T12:00:01Z'));
	});

	// CUP-07
	test('ícone copia o código e mostra o aviso por ~2 s', async ({ page }) => {
		await page.goto(OFERTA);
		const icone = page.getByRole('button', { name: 'Copiar cupom' });
		await expect(icone).toBeVisible();
		const caixa = await icone.boundingBox();
		expect(caixa?.width).toBeGreaterThanOrEqual(44);
		expect(caixa?.height).toBeGreaterThanOrEqual(44);
		await page.evaluate(() => navigator.clipboard.writeText('outro'));

		await icone.click();
		await expect.poll(() => lerClipboard(page)).toBe(CODIGO);
		const aviso = page.getByRole('status');
		await expect(aviso).toHaveText('Cupom copiado!');
		await expect(icone).toContainClass('copiado');
		await page.clock.runFor(1900);
		await expect(aviso).toHaveText('Cupom copiado!');
		await page.clock.runFor(200);
		await expect(aviso).toHaveText('');
		await expect(icone).not.toContainClass('copiado');
		// Só a página nesta aba: o ícone não navega.
		expect(new URL(page.url()).pathname).toBe(OFERTA);
	});

	// Edge case: clique repetido dentro de 2 s recomeça o temporizador.
	test('segundo clique antes de 2 s mantém o aviso por mais 2 s', async ({ page }) => {
		await page.goto(OFERTA);
		const icone = page.getByRole('button', { name: 'Copiar cupom' });
		const aviso = page.getByRole('status');
		await icone.click();
		await expect(aviso).toHaveText('Cupom copiado!');
		await page.clock.runFor(1500);
		await icone.click();
		await page.clock.runFor(1000);
		await expect(aviso).toHaveText('Cupom copiado!');
		await page.clock.runFor(1100);
		await expect(aviso).toHaveText('');
	});

	// CUP-09
	test('botão principal copia e abre /ir/{id} em aba nova', async ({ page, context }) => {
		await page.goto(OFERTA);
		await page.evaluate(() => navigator.clipboard.writeText('outro'));
		const cta = page.getByRole('link', { name: 'Copiar cupom e ir para a loja' });
		const [loja] = await Promise.all([context.waitForEvent('page'), cta.click()]);
		await loja.waitForLoadState();
		expect(new URL(loja.url()).pathname).toBe(LOJA);
		expect(new URL(page.url()).pathname).toBe(OFERTA);
		await expect.poll(() => lerClipboard(loja)).toBe(CODIGO);
		await expect(page.getByRole('status')).toHaveText('Cupom copiado!');
	});

	// CUP-08 + CUP-09: clipboard negado.
	test('com o clipboard negado, a aba abre e o ícone seleciona o código', async ({
		page,
		context
	}) => {
		await page.addInitScript(() => {
			Object.defineProperty(Clipboard.prototype, 'writeText', {
				value: () => Promise.reject(new DOMException('negado', 'NotAllowedError'))
			});
		});
		await page.goto(OFERTA);
		const cta = page.getByRole('link', { name: 'Copiar cupom e ir para a loja' });
		const [loja] = await Promise.all([context.waitForEvent('page'), cta.click()]);
		await loja.waitForLoadState();
		expect(new URL(loja.url()).pathname).toBe(LOJA);
		await loja.close();

		await page.getByRole('button', { name: 'Copiar cupom' }).click();
		await expect.poll(() => selecao(page)).toBe(CODIGO);
		// Relógio parado: um "Cupom copiado!" indevido não sumiria sozinho.
		await expect(page.getByRole('status')).toHaveText('');
		await expect(page.locator('.copiar')).not.toContainClass('copiado');
	});

	// CUP-08: navegador sem a API.
	test('sem navigator.clipboard, o ícone seleciona o código', async ({ page }) => {
		await page.addInitScript(() => {
			Object.defineProperty(Navigator.prototype, 'clipboard', { get: () => undefined });
		});
		await page.goto(OFERTA);
		await page.getByRole('button', { name: 'Copiar cupom' }).click();
		await expect.poll(() => selecao(page)).toBe(CODIGO);
		// Relógio parado: um "Cupom copiado!" indevido não sumiria sozinho.
		await expect(page.getByRole('status')).toHaveText('');
		await expect(page.locator('.copiar')).not.toContainClass('copiado');
	});
});

// CUP-10
test.describe('sem JavaScript', () => {
	test.use({ javaScriptEnabled: false });

	test('ícone oculto e botão é link comum para /ir/{id}', async ({ page, context }) => {
		await servirOferta(context);
		await page.goto(OFERTA);
		await expect(page.locator('.codigo')).toHaveText(CODIGO);
		await expect(page.locator('button.copiar')).toHaveCount(1);
		await expect(page.locator('button.copiar')).toBeHidden();
		const cta = page.getByRole('link', { name: 'Copiar cupom e ir para a loja' });
		await expect(cta).toHaveAttribute('href', LOJA);
		await expect(cta).toHaveAttribute('target', '_blank');
		const [loja] = await Promise.all([context.waitForEvent('page'), cta.click()]);
		await loja.waitForLoadState();
		expect(new URL(loja.url()).pathname).toBe(LOJA);
	});
});
