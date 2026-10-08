// BSV-32: aviso "N novas ofertas" com a página aberta (MANIFEST §3.1 item 4, AD-063).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { catalogo, servir } from './fixtura.ts';
import type { OfertaCard } from '../src/lib/dados.ts';

const GRADE = '[data-grade] article';
const AVISO = '[data-aviso-novas] button';
const POLLING_MS = 5 * 60_000 + 1000;

/** Uma nova de Meu Lar, outra de Meu Lar, e uma expirada (não conta). */
function novas(c: Map<number, OfertaCard[]>): OfertaCard[] {
	const modelo = c.get(1)?.at(-1) as OfertaCard;
	const dp = new Date(Date.now() + 60_000).toISOString();
	return [
		{ ...modelo, id: 1010, a: 'MEU_LAR', t: 'Nova 1010', dp },
		{ ...modelo, id: 1011, a: 'MEU_LAR', t: 'Nova 1011', dp },
		{ ...modelo, id: 1012, a: 'MEU_LAR', t: 'Nova 1012', dp, x: 1 }
	];
}

/** Publica o ciclo seguinte: chunk 1 ganha as novas e o manifest troca de hash. */
async function publicar(page: Page, c: Map<number, OfertaCard[]>) {
	c.set(1, [...(c.get(1) ?? []), ...novas(c)]);
	await page.route('**/manifest.json', (r) =>
		r.fulfill({
			json: {
				contrato: '1.5.0',
				versao: 20261008000500,
				gerado_em: new Date().toISOString(),
				total_ofertas: 163,
				chunks: [...c].map(([n, cards]) => ({
					n,
					arquivo: `data/chunks/${n}-${n === 1 ? 'b' : String(n)}${'0'.repeat(15)}.json.br`,
					ids: [Math.max(1, n * 1000), n * 1000 + 999],
					qtd: cards.length,
					bytes: 1
				})),
				busca: null,
				areas: {}
			}
		})
	);
}

async function abrir(page: Page, url: string, pronto = GRADE) {
	const c = catalogo();
	await servir(page, c);
	await page.clock.install();
	await page.goto(url);
	await expect(page.locator(pronto).first()).toBeVisible();
	return c;
}

const luz = (rgb: string) => {
	const [r, g, b] = (rgb.match(/[\d.]+/g) ?? []).slice(0, 3).map((v) => {
		const s = Number(v) / 255;
		return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

// NOV-06
test('home: sem aviso na primeira carga; 2 novas após o polling; tocar põe no topo', async ({
	page
}) => {
	const c = await abrir(page, '/');
	const titulo = await page.title();
	await expect(page.locator(AVISO)).toHaveCount(0);
	await publicar(page, c);
	await page.clock.fastForward(POLLING_MS);
	const aviso = page.locator(AVISO);
	await expect(aviso).toHaveText('2 novas ofertas');
	await expect(page).toHaveTitle(`(2) ${titulo}`);
	// Não cobre o cabeçalho.
	const topo = await page.locator('[data-topo]').boundingBox();
	const caixa = await aviso.boundingBox();
	expect((caixa?.y ?? 0) >= (topo?.y ?? 0) + (topo?.height ?? 0)).toBe(true);
	// Botão com corpo de verdade (não achatado pelo contêiner de altura 0).
	expect(caixa?.height ?? 0).toBeGreaterThanOrEqual(32);
	await expect(aviso).toBeInViewport({ ratio: 1 });
	// Nenhuma entrou na lista sozinha.
	await expect(page.locator(`${GRADE}[data-id="1010"]`)).toHaveCount(0);

	// Contraste AA (>= 4.5) do botão.
	const [fundo, texto] = await aviso.evaluate((e) => {
		const s = getComputedStyle(e);
		return [s.backgroundColor, s.color];
	});
	const [a, b] = [luz(fundo), luz(texto)].sort((x, y) => y - x);
	expect((a + 0.05) / (b + 0.05)).toBeGreaterThanOrEqual(4.5);

	await aviso.click();
	await expect(aviso).toHaveCount(0);
	await expect(page).toHaveTitle(titulo);
	const ids = await page
		.locator(GRADE)
		.evaluateAll((els) => els.slice(0, 2).map((e) => e.getAttribute('data-id')));
	expect(ids.sort()).toEqual(['1010', '1011']);
	await expect(page.locator('#titulo-recentes')).toBeFocused();
});

// NOV-07
test('área sem novas: /elas/ não mostra o aviso de Meu Lar', async ({ page }) => {
	const c = await abrir(page, '/elas/');
	await publicar(page, c);
	await page.clock.fastForward(POLLING_MS);
	// Dá tempo de o ciclo aplicar o chunk novo.
	await page.waitForTimeout(500);
	await expect(page.locator(AVISO)).toHaveCount(0);
	await expect(page).toHaveTitle(/^Ofertas de Elas/);
});

// NOV-08
test('área com novas: /meu-lar/ mostra 2', async ({ page }) => {
	const c = await abrir(page, '/meu-lar/');
	await publicar(page, c);
	await page.clock.fastForward(POLLING_MS);
	await expect(page.locator(AVISO)).toHaveText('2 novas ofertas');
});

// NOV-09
test('/desejos/ não tem o aviso', async ({ page }) => {
	const c = await abrir(page, '/desejos/', '[data-topo]');
	await publicar(page, c);
	await page.clock.fastForward(POLLING_MS);
	await page.waitForTimeout(500);
	await expect(page.locator('[data-aviso-novas]')).toHaveCount(0);
});

// NOV-10: aria-live na região do aviso (saída 1).
test('região do aviso é aria-live polite, mesmo antes de haver novas', async ({ page }) => {
	await abrir(page, '/');
	await expect(page.locator('[data-aviso-novas]')).toHaveAttribute('aria-live', 'polite');
});

// NOV-11: rolagem suave, instantânea com prefers-reduced-motion (saída 2).
for (const [reduzido, esperado] of [
	['reduce', 'instant'],
	['no-preference', 'smooth']
] as const) {
	test(`rolagem ${esperado} com reducedMotion=${reduzido}`, async ({ page }) => {
		await page.emulateMedia({ reducedMotion: reduzido });
		await page.addInitScript(() => {
			const orig = window.scrollTo.bind(window);
			window.scrollTo = ((o: ScrollToOptions) => {
				(window as unknown as { __scroll: unknown }).__scroll = o;
				orig(o);
			}) as typeof window.scrollTo;
		});
		const c = await abrir(page, '/');
		await publicar(page, c);
		await page.clock.fastForward(POLLING_MS);
		await page.locator(AVISO).click();
		const o = await page.evaluate(
			() => (window as unknown as { __scroll: ScrollToOptions }).__scroll
		);
		expect(o.behavior).toBe(esperado);
	});
}
