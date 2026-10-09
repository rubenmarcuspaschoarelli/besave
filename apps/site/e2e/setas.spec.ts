// BSV-37: faixa "Maiores descontos de hoje" sem barra de rolagem; setas com ponteiro fino.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { catalogo, servir } from './fixtura.ts';

const FAIXA = '[data-faixa]';
const ANTES = 'Ver descontos anteriores';
const DEPOIS = 'Ver descontos seguintes';

async function abrir(page: Page, c = catalogo()) {
	await servir(page, c);
	await page.goto('/');
	await expect(page.locator(`${FAIXA} a`).first()).toBeVisible();
}

const seta = (page: Page, nome: string) => page.getByRole('button', { name: nome, exact: true });
const rolagem = (page: Page) =>
	page.locator(FAIXA).evaluate((e) => ({
		esq: e.scrollLeft,
		max: e.scrollWidth - e.clientWidth,
		largura: e.clientWidth
	}));

/** SET-01: nenhuma barra ocupa altura no trilho (e o estilo pede `scrollbar-width: none`). */
async function semBarra(page: Page) {
	const t = await page.locator(FAIXA).evaluate((e) => ({
		barra: (e as HTMLElement).offsetHeight - e.clientHeight,
		estilo: getComputedStyle(e).scrollbarWidth
	}));
	expect(t).toEqual({ barra: 0, estilo: 'none' });
}

test.describe('computador (1280 px)', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	// SET-01, SET-02, SET-03
	test('sem barra; › rola, ‹ aparece; no fim a › some', async ({ page }) => {
		await page.emulateMedia({ reducedMotion: 'reduce' });
		await abrir(page);
		await semBarra(page);
		await expect(page.locator(`${FAIXA} a`)).toHaveCount(8);
		const r0 = await rolagem(page);
		expect(r0.max).toBeGreaterThan(0);
		expect(r0.esq).toBe(0);
		await expect(seta(page, ANTES)).toBeHidden();
		await expect(seta(page, DEPOIS)).toBeVisible();
		// Área de clique ≥ 44 px.
		const caixa = await seta(page, DEPOIS).boundingBox();
		expect(caixa!.width).toBeGreaterThanOrEqual(44);
		expect(caixa!.height).toBeGreaterThanOrEqual(44);
		await seta(page, DEPOIS).click();
		// Uma largura visível, limitada ao fim; instantâneo com movimento reduzido.
		expect((await rolagem(page)).esq).toBe(Math.min(r0.largura, r0.max));
		await expect(seta(page, ANTES)).toBeVisible();
		await expect(seta(page, DEPOIS)).toBeHidden();
		await seta(page, ANTES).click();
		expect((await rolagem(page)).esq).toBe(0);
		await expect(seta(page, ANTES)).toBeHidden();
		await expect(seta(page, DEPOIS)).toBeVisible();
	});

	// SET-03: teclado (Tab + Enter); a seta que some passa o foco para a outra.
	test('Tab + Enter na seta rola; foco não se perde no fim', async ({ page }) => {
		await page.emulateMedia({ reducedMotion: 'reduce' });
		await abrir(page);
		await expect(seta(page, DEPOIS)).toBeVisible();
		await page.locator(`${FAIXA} a`).last().focus();
		await page.keyboard.press('Tab');
		await expect(seta(page, DEPOIS)).toBeFocused();
		await page.keyboard.press('Enter');
		const r = await rolagem(page);
		expect(r.esq).toBe(r.max);
		await expect(seta(page, DEPOIS)).toBeHidden();
		await expect(seta(page, ANTES)).toBeFocused();
		await page.keyboard.press('Enter');
		expect((await rolagem(page)).esq).toBe(0);
		await expect(seta(page, DEPOIS)).toBeFocused();
	});

	// SET-03: sem movimento reduzido, a rolagem é suave e chega ao mesmo lugar.
	test('rolagem suave sem prefers-reduced-motion', async ({ page }) => {
		await page.emulateMedia({ reducedMotion: 'no-preference' });
		await abrir(page);
		const r0 = await rolagem(page);
		const alvo = Math.min(r0.largura, r0.max);
		// Posições de cada evento de rolagem: suave passa por valores intermediários.
		await page.locator(FAIXA).evaluate((e) => {
			const g = globalThis as unknown as { posicoes: number[] };
			g.posicoes = [];
			e.addEventListener('scroll', () => g.posicoes.push(e.scrollLeft));
		});
		await seta(page, DEPOIS).click();
		await expect.poll(async () => (await rolagem(page)).esq).toBe(alvo);
		const posicoes = await page.evaluate(
			() => (globalThis as unknown as { posicoes: number[] }).posicoes
		);
		expect(posicoes.some((p) => p > 0 && p < alvo)).toBe(true);
	});

	// Borda: cards que cabem sem rolar, sem seta nenhuma.
	test('faixa que cabe inteira não mostra setas', async ({ page }) => {
		const c = catalogo();
		// Só três com desconto (ids múltiplos de 3 têm `pd`): os outros perdem o `pd`.
		const poucos = new Map(
			[...c].map(([n, cards]) => [
				n,
				cards.map((k) => (k.id === 3 || k.id === 6 || k.id === 9 ? k : { ...k, pd: null }))
			])
		);
		await abrir(page, poucos);
		await expect(page.locator(`${FAIXA} a`)).toHaveCount(3);
		expect((await rolagem(page)).max).toBe(0);
		await expect(seta(page, ANTES)).toBeHidden();
		await expect(seta(page, DEPOIS)).toBeHidden();
	});
});

// SET-03: com o trilho mais estreito que o conteúdo duas vezes, cada clique rola uma largura.
test.describe('computador estreito (500 px, ponteiro fino)', () => {
	test.use({ viewport: { width: 500, height: 900 } });

	test('cada clique rola uma largura visível', async ({ page }) => {
		await page.emulateMedia({ reducedMotion: 'reduce' });
		await abrir(page);
		const r0 = await rolagem(page);
		expect(r0.max).toBeGreaterThan(r0.largura);
		await seta(page, DEPOIS).click();
		expect((await rolagem(page)).esq).toBe(r0.largura);
		await expect(seta(page, ANTES)).toBeVisible();
		await expect(seta(page, DEPOIS)).toBeVisible();
		await seta(page, DEPOIS).click();
		expect((await rolagem(page)).esq).toBe(r0.max);
		await expect(seta(page, DEPOIS)).toBeHidden();
		await seta(page, ANTES).click();
		expect((await rolagem(page)).esq).toBe(r0.max - r0.largura);
	});
});

// SET-04
test.describe('celular com toque (390 px)', () => {
	test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

	test('sem setas nem barra; rola com o dedo', async ({ page }) => {
		await abrir(page);
		await semBarra(page);
		await expect(page.locator('[data-seta]')).toHaveCount(0);
		await expect(seta(page, DEPOIS)).toHaveCount(0);
		const caixa = (await page.locator(FAIXA).boundingBox())!;
		const y = Math.round(caixa.y + caixa.height / 2);
		const x0 = Math.round(caixa.x + caixa.width - 30);
		// Arrasta o dedo da direita para a esquerda, em passos (toque real via CDP).
		const cdp = await page.context().newCDPSession(page);
		const toque = (type: 'touchStart' | 'touchMove' | 'touchEnd', x: number) =>
			cdp.send('Input.dispatchTouchEvent', {
				type,
				touchPoints: type === 'touchEnd' ? [] : [{ x, y }]
			});
		await toque('touchStart', x0);
		for (let i = 1; i <= 10; i++) await toque('touchMove', x0 - i * 25);
		await toque('touchEnd', x0 - 250);
		await expect.poll(async () => (await rolagem(page)).esq).toBeGreaterThan(100);
	});
});
