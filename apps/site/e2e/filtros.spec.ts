// Filtros, ordens e faixa de preço da grade "Mais recentes" (BSV-31).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { Loja, OfertaCard, Publico } from '../src/lib/dados.ts';
import { servir } from './fixtura.ts';

const GRADE = '[data-grade] article';
const LOJAS: Loja[] = ['AMAZON', 'SHOPEE', 'MERCADO_LIVRE'];
const PUBLICOS: Publico[] = ['FEMININO', 'MASCULINO', 'UNISSEX', 'INFANTIL'];
/** Um preço de cada lado das fronteiras de faixa (centavos). */
const PRECOS = [3000, 5000, 5001, 9000, 15000, 25000, 4990];

/** 130 cards variados num chunk; Infantil nunca tem cupom (estado vazio). */
function cards(agora = Date.now()): OfertaCard[] {
	return Array.from({ length: 130 }, (_, i) => {
		const id = i + 1;
		const pp = PRECOS[id % PRECOS.length];
		const p = PUBLICOS[id % 4];
		const desconto = id % 2 === 0 ? ((id * 7) % 9) + 1 : 0;
		return {
			id,
			l: LOJAS[id % 3],
			t: `Produto ${id}`,
			pd: desconto ? Math.round(pp / (1 - desconto / 10)) : null,
			pp,
			...(id % 5 === 0 && p !== 'INFANTIL' ? { c: `CUPOM${id}` } : {}),
			dt: new Date(agora - 48 * 3_600_000).toISOString(),
			dp: new Date(agora - (2000 - id) * 30_000).toISOString(),
			a: id % 2 ? 'ELAS' : 'TECH',
			p
		};
	});
}

const CARDS = cards();
const porId = new Map(CARDS.map((c) => [c.id, c]));
const pct = (c: OfertaCard) => (c.pd ? 1 - c.pp / c.pd : -1);

async function abrir(page: Page, url = '/') {
	await servir(page, new Map([[0, cards()]]));
	await page.goto(url);
	await expect(page.locator(GRADE).first()).toBeVisible();
}

const idsNaGrade = (page: Page) =>
	page.locator(GRADE).evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))));

const naGrade = async (page: Page) => (await idsNaGrade(page)).map((id) => porId.get(id)!);

/** Botão de filtro pelo nome; no celular, abre o painel "Filtros" quando ele está lá dentro. */
async function escolher(page: Page, nome: string) {
	const botao = page.getByRole('button', { name: nome, exact: true });
	if (await botao.isVisible()) return botao.click();
	await page.getByRole('button', { name: 'Filtros', exact: true }).click();
	await botao.click();
	await page.getByRole('button', { name: /^Ver \d+ ofertas?$/ }).click();
}

const pressionado = (page: Page, nome: string) =>
	page.locator('[data-filtros] button[aria-pressed]', { hasText: new RegExp(`^${nome}$`) });

const contagem = (page: Page) => page.locator('[data-contagem]');

// BAR-01, BAR-03
test('"Maior desconto" ordena a grade por desconto', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Maior desconto');
	await expect(pressionado(page, 'Maior desconto')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Recentes')).toHaveAttribute('aria-pressed', 'false');
	await expect(page).toHaveURL(/\/\?ordem=desconto$/);
	const grade = await naGrade(page);
	const maior = Math.max(...CARDS.map(pct));
	expect(pct(grade[0])).toBeCloseTo(maior, 5);
	for (let i = 1; i < grade.length; i++)
		expect(pct(grade[i])).toBeLessThanOrEqual(pct(grade[i - 1]));
});

// BAR-01, BAR-05
test('"Menor preço" ordena por preço crescente', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Menor preço');
	await expect.poll(async () => (await naGrade(page))[0]?.pp).toBe(3000);
	const precos = (await naGrade(page)).map((c) => c.pp);
	expect(precos).toEqual([...precos].sort((a, b) => a - b));
	await expect(page).toHaveURL(/\/\?ordem=preco$/);
});

// BAR-03, BAR-05
test('"Shopee" só mostra Shopee e o contador bate', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Shopee');
	const esperado = CARDS.filter((c) => c.l === 'SHOPEE').length;
	await expect(contagem(page)).toHaveText(`${esperado} ofertas`);
	expect(new Set((await naGrade(page)).map((c) => c.l))).toEqual(new Set(['SHOPEE']));
	await expect(page).toHaveURL(/\/\?loja=shopee$/);
});

// BAR-03, DAD-01
test('"Até R$ 50" só mostra preço ≤ R$ 50; tocar de novo desmarca', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Até R$ 50');
	const esperado = CARDS.filter((c) => c.pp <= 5000).length;
	await expect(contagem(page)).toHaveText(`${esperado} ofertas`);
	const precos = (await naGrade(page)).map((c) => c.pp);
	expect(precos.length).toBeGreaterThan(0);
	expect(Math.max(...precos)).toBeLessThanOrEqual(5000);
	expect(precos).toContain(5000);
	await expect(page).toHaveURL(/\/\?preco=ate50$/);
	// BAR-02
	await escolher(page, 'Até R$ 50');
	await expect(contagem(page)).toHaveText(`${CARDS.length} ofertas`);
	await expect(pressionado(page, 'Até R\\$ 50')).toHaveAttribute('aria-pressed', 'false');
	await expect(page).toHaveURL(/\/$/);
});

// BAR-03, BAR-02
test('"Só com cupom" só mostra cards com cupom e alterna', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Só com cupom');
	const esperado = CARDS.filter((c) => c.c).length;
	await expect(contagem(page)).toHaveText(`${esperado} ofertas`);
	expect((await naGrade(page)).every((c) => !!c.c)).toBe(true);
	await expect(pressionado(page, 'Só com cupom')).toHaveAttribute('aria-pressed', 'true');
	await expect(page).toHaveURL(/\/\?cupom=1$/);
	await escolher(page, 'Só com cupom');
	await expect(contagem(page)).toHaveText(`${CARDS.length} ofertas`);
});

// BAR-03, URL-03
test('Feminino + Amazon combinados', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Feminino');
	await escolher(page, 'Amazon');
	const esperado = CARDS.filter((c) => c.p === 'FEMININO' && c.l === 'AMAZON');
	expect(esperado.length).toBeGreaterThan(1);
	await expect(contagem(page)).toHaveText(`${esperado.length} ofertas`);
	expect((await idsNaGrade(page)).sort((a, b) => a - b)).toEqual(
		esperado.map((c) => c.id).sort((a, b) => a - b)
	);
	await expect(page).toHaveURL(/\/\?publico=feminino&loja=amazon$/);
});

// URL-05
test('recarregar mantém os filtros', async ({ page }) => {
	await abrir(page);
	await escolher(page, 'Maior desconto');
	await escolher(page, 'Mercado Livre');
	await expect(page).toHaveURL(/\/\?ordem=desconto&loja=mercado-livre$/);
	await page.reload();
	await expect(page.locator(GRADE).first()).toBeVisible();
	await expect(pressionado(page, 'Mercado Livre')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Maior desconto')).toHaveAttribute('aria-pressed', 'true');
	const grade = await naGrade(page);
	expect(new Set(grade.map((c) => c.l))).toEqual(new Set(['MERCADO_LIVRE']));
	for (let i = 1; i < grade.length; i++)
		expect(pct(grade[i])).toBeLessThanOrEqual(pct(grade[i - 1]));
});

// URL-04, URL-05
test('trocar filtro não cria entrada no histórico; voltar restaura', async ({ page }) => {
	await servir(page, new Map([[0, cards()]]));
	await page.goto('/desejos/');
	await page.goto('/');
	await expect(page.locator(GRADE).first()).toBeVisible();
	await escolher(page, 'Shopee');
	await escolher(page, 'Infantil');
	await expect(page).toHaveURL(/\/\?publico=infantil&loja=shopee$/);
	// Sai para uma oferta e volta: a grade volta filtrada.
	await page.goto('/oferta/3/');
	await page.goBack();
	await expect(page).toHaveURL(/\/\?publico=infantil&loja=shopee$/);
	await expect(page.locator(GRADE).first()).toBeVisible();
	const esperado = CARDS.filter((c) => c.l === 'SHOPEE' && c.p === 'INFANTIL').length;
	await expect(contagem(page)).toHaveText(`${esperado} ofertas`);
	await expect(pressionado(page, 'Infantil')).toHaveAttribute('aria-pressed', 'true');
	// Um voltar a mais sai da home: as trocas de filtro substituíram a entrada.
	await page.goBack();
	await expect(page).toHaveURL(/\/desejos\/$/);
});

// URL-05
test('abrir /elas/?loja=shopee já vem filtrado', async ({ page }) => {
	await abrir(page, '/elas/?loja=shopee');
	await expect(pressionado(page, 'Shopee')).toHaveAttribute('aria-pressed', 'true');
	const esperado = CARDS.filter((c) => c.a === 'ELAS' && c.l === 'SHOPEE').length;
	await expect(contagem(page)).toHaveText(`${esperado} ofertas`);
	const grade = await naGrade(page);
	expect(grade.length).toBe(esperado);
	expect(grade.every((c) => c.a === 'ELAS' && c.l === 'SHOPEE')).toBe(true);
});

// URL-02
test('valor inválido na URL é ignorado', async ({ page }) => {
	await abrir(page, '/?loja=xyz&publico=feminino');
	await expect(pressionado(page, 'Feminino')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Todas')).toHaveAttribute('aria-pressed', 'true');
	await expect(contagem(page)).toHaveText(
		`${CARDS.filter((c) => c.p === 'FEMININO').length} ofertas`
	);
});

// BAR-04
test('"Limpar filtros" volta ao padrão e limpa a URL', async ({ page }) => {
	await abrir(page, '/elas/?ordem=preco&publico=masculino&preco=50a100&cupom=1&q=x');
	const limpar = page.locator('[data-filtros]').getByRole('button', { name: 'Limpar filtros' });
	await expect(limpar).toBeVisible();
	await limpar.click();
	await expect(page).toHaveURL(/\/elas\/\?q=x$/);
	await expect(limpar).toHaveCount(0);
	await expect(pressionado(page, 'Recentes')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Todos')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Só com cupom')).toHaveAttribute('aria-pressed', 'false');
	await expect(page.locator('[data-filtros] button[aria-pressed="true"]')).toHaveCount(3);
});

test('"Limpar filtros" não aparece no padrão', async ({ page }) => {
	await abrir(page, '/elas/');
	await expect(page.getByRole('button', { name: 'Limpar filtros' })).toHaveCount(0);
});

// BAR-08
test('estado vazio: "Nenhuma oferta com esses filtros" + Limpar', async ({ page }) => {
	expect(CARDS.filter((c) => c.p === 'INFANTIL' && c.c)).toHaveLength(0);
	await servir(page, new Map([[0, cards()]]));
	await page.goto('/?publico=infantil&cupom=1');
	await expect(page.getByText('Nenhuma oferta com esses filtros')).toBeVisible();
	await expect(page.locator(GRADE)).toHaveCount(0);
	await expect(contagem(page)).toHaveText('0 ofertas');
	await page.locator('[data-vazio]').getByRole('button', { name: 'Limpar filtros' }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.locator(GRADE)).toHaveCount(40);
});

// BAR-06
test('"Ver mais" volta a 40 quando o filtro muda', async ({ page }) => {
	await abrir(page);
	await expect(page.locator(GRADE)).toHaveCount(40);
	await page.getByRole('button', { name: 'Ver mais ofertas' }).click();
	await expect(page.locator(GRADE)).toHaveCount(80);
	await escolher(page, 'Menor preço');
	await expect(page.locator(GRADE)).toHaveCount(40);
});

// BAR-07
test('faixa "Maiores descontos de hoje" não muda com os filtros', async ({ page }) => {
	await abrir(page);
	const faixa = page.locator('[data-faixa] a');
	await expect(faixa.first()).toBeVisible();
	const antes = await faixa.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')));
	await escolher(page, 'Shopee');
	await escolher(page, 'Acima de R$ 200');
	await expect(contagem(page)).toHaveText(
		`${CARDS.filter((c) => c.l === 'SHOPEE' && c.pp > 20000).length} ofertas`
	);
	const depois = await faixa.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')));
	expect(depois).toEqual(antes);
	// A faixa tem card fora do filtro (não é Shopee acima de R$ 200).
	expect(antes.some((id) => porId.get(Number(id))!.l !== 'SHOPEE')).toBe(true);
});

// BAR-09
test('botões de filtro: toque ≥ 44 px e foco visível', async ({ page }) => {
	await abrir(page);
	const ordem = page.getByRole('button', { name: 'Maior desconto', exact: true });
	const caixa = await ordem.boundingBox();
	expect(caixa?.height).toBeGreaterThanOrEqual(44);
	await ordem.focus();
	await page.keyboard.press('Shift+Tab');
	await page.keyboard.press('Tab');
	// Contorno na cor de foco do tema (--cor-foco), não o padrão do navegador.
	const contorno = await ordem.evaluate((e) => {
		const s = getComputedStyle(e);
		return `${s.outlineStyle} ${s.outlineColor}`;
	});
	expect(contorno).toBe('solid rgb(29, 78, 216)');
	const alturas = await page
		.locator('[data-filtros] button')
		.evaluateAll((els) =>
			els
				.filter((e) => (e as HTMLElement).offsetParent !== null)
				.map((e) => e.getBoundingClientRect().height)
		);
	expect(alturas.length).toBeGreaterThan(2);
	for (const h of alturas) expect(h).toBeGreaterThanOrEqual(44);
});
