// Página de busca `/busca/` (BSV-34): resultados no cliente sobre o catálogo da fixtura.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { catalogo, servir, todos } from './fixtura.ts';

const GRADE = '[data-grade] article';
const CARDS = todos(catalogo());
const PROTETOR = CARDS.filter((c) => /\bprotetor/i.test(c.t));
const contagem = (page: Page) => page.locator('[data-resultado]');
const ids = (page: Page) =>
	page.locator(GRADE).evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))));
const ordenados = (xs: number[]) => [...xs].sort((a, b) => a - b);

test.beforeEach(async ({ page }) => {
	await servir(page);
});

// BUS-01, BUS-08
test('q=protetor mostra a contagem e só cards com a palavra; noindex e título', async ({
	page
}) => {
	expect(PROTETOR.length).toBe(32);
	await page.goto('/busca/?q=protetor');
	await expect(contagem(page)).toHaveText('32 ofertas para “protetor”');
	await expect(page.locator(GRADE)).toHaveCount(32);
	expect(ordenados(await ids(page))).toEqual(ordenados(PROTETOR.map((c) => c.id)));
	for (const t of await page.locator(`${GRADE} h3`).allTextContents())
		expect(t).toMatch(/protetor/i);
	await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex');
	await expect(page).toHaveTitle('Busca: protetor · Besave');
	await expect(page.getByRole('searchbox', { name: 'Buscar ofertas' })).toHaveValue('protetor');
});

// TOP-07
test('formulário com role=search e contagem em região aria-live', async ({ page }) => {
	await page.goto('/busca/?q=protetor');
	await expect(
		page.getByRole('search').getByRole('searchbox', { name: 'Buscar ofertas' })
	).toBeVisible();
	await expect(contagem(page)).toHaveAttribute('aria-live', 'polite');
});

// BUS-08: o HTML prerenderizado já é noindex (sem depender do JS).
test('HTML da /busca/ traz noindex e título sem termo', async ({ request }) => {
	const html = await (await request.get('/busca/')).text();
	expect(html).toContain('<meta name="robots" content="noindex"');
	expect(html).toMatch(/<title>Busca · Besave<\/title>/);
});

// BUS-03, BUS-10
test('&loja=shopee filtra e recarregar mantém', async ({ page }) => {
	const shopee = PROTETOR.filter((c) => c.l === 'SHOPEE');
	expect(shopee.length).toBeGreaterThan(0);
	expect(shopee.length).toBeLessThan(PROTETOR.length);
	await page.goto('/busca/?q=protetor&loja=shopee');
	await expect(contagem(page)).toHaveText(`${shopee.length} ofertas para “protetor”`);
	expect(ordenados(await ids(page))).toEqual(ordenados(shopee.map((c) => c.id)));
	await page.reload();
	await expect(page).toHaveURL(/\/busca\/\?q=protetor&loja=shopee$/);
	await expect(contagem(page)).toHaveText(`${shopee.length} ofertas para “protetor”`);
	expect(ordenados(await ids(page))).toEqual(ordenados(shopee.map((c) => c.id)));
});

// BUS-03: mudar filtro mantém q e área.
test('"Limpar filtros" mantém q e area na URL', async ({ page }) => {
	await page.goto('/busca/?q=protetor&area=elas&loja=shopee');
	const limpar = page.locator('[data-filtros]').getByRole('button', { name: 'Limpar filtros' });
	await limpar.click();
	await expect(page).toHaveURL(/\/busca\/\?q=protetor&area=elas$/);
	const elas = PROTETOR.filter((c) => c.a === 'ELAS');
	await expect(contagem(page)).toHaveText(`${elas.length} ofertas para “protetor” em Elas`);
});

// BUS-02
test('area=elas restringe à área e o botão tira a área', async ({ page }) => {
	const elas = PROTETOR.filter((c) => c.a === 'ELAS');
	expect(elas.length).toBeLessThan(PROTETOR.length);
	await page.goto('/busca/?q=protetor&area=elas');
	await expect(contagem(page)).toHaveText(`${elas.length} ofertas para “protetor” em Elas`);
	expect(ordenados(await ids(page))).toEqual(ordenados(elas.map((c) => c.id)));
	await page.getByRole('button', { name: 'Buscar em todas as áreas' }).click();
	await expect(page).toHaveURL(/\/busca\/\?q=protetor$/);
	await expect(contagem(page)).toHaveText('32 ofertas para “protetor”');
	await expect(page.getByRole('button', { name: 'Buscar em todas as áreas' })).toHaveCount(0);
});

// Borda: área inválida é ignorada.
test('area inválida busca em todas as áreas', async ({ page }) => {
	await page.goto('/busca/?q=protetor&area=xyz');
	await expect(contagem(page)).toHaveText('32 ofertas para “protetor”');
	await expect(page.getByRole('button', { name: 'Buscar em todas as áreas' })).toHaveCount(0);
});

// BUS-06
test('q de 1 caractere (ou só pontuação) mostra sugestões', async ({ page }) => {
	for (const url of ['/busca/?q=p', '/busca/?q=-+-', '/busca/']) {
		await page.goto(url);
		const sugestoes = page.locator('[data-sugestoes]');
		await expect(sugestoes, url).toBeVisible();
		await expect(sugestoes.locator('[data-sugestao-areas] a')).toHaveCount(10);
		await expect(sugestoes.locator('a[href="/elas/"]')).toHaveText('Elas');
		await expect(page.getByRole('heading', { name: /Maiores descontos de hoje/ })).toBeVisible();
		await expect(page.locator('[data-faixa] a').first()).toBeVisible();
		await expect(page.locator(GRADE)).toHaveCount(0);
		await expect(contagem(page)).toHaveCount(0);
	}
});

// BUS-07
test('termo inexistente mostra o estado vazio', async ({ page }) => {
	await page.goto('/busca/?q=xyzabc');
	await expect(contagem(page)).toHaveText('Nenhuma oferta para “xyzabc”');
	const vazio = page.locator('[data-vazio]');
	await expect(vazio).toContainText('Confira a grafia');
	await expect(vazio).toContainText('Use menos palavras');
	await expect(vazio.locator('[data-sugestao-areas] a')).toHaveCount(10);
	await expect(page.locator(GRADE)).toHaveCount(0);
});

// BUS-09
test('"Ver mais ofertas" acrescenta 40', async ({ page }) => {
	const produto = CARDS.filter((c) => /\bproduto/i.test(c.t));
	expect(produto.length).toBeGreaterThan(80);
	await page.goto('/busca/?q=produto');
	await expect(contagem(page)).toHaveText(`${produto.length} ofertas para “produto”`);
	await expect(page.locator(GRADE)).toHaveCount(40);
	await page.getByRole('button', { name: 'Ver mais ofertas' }).click();
	await expect(page.locator(GRADE)).toHaveCount(80);
});

// TOP-03, TOP-04
test('digitar na /busca/ atualiza resultados e troca a URL sem entrada nova', async ({ page }) => {
	await page.goto('/busca/?q=protetor');
	await expect(contagem(page)).toHaveText('32 ofertas para “protetor”');
	const entradas = await page.evaluate(() => history.length);
	const campo = page.getByRole('searchbox', { name: 'Buscar ofertas' });
	await campo.fill('protetor solar');
	const solar = CARDS.filter((c) => /\bprotetor solar/i.test(c.t));
	await expect(contagem(page)).toHaveText(`${solar.length} ofertas para “protetor solar”`);
	await expect(page).toHaveURL(/\/busca\/\?q=protetor\+solar$/);
	await expect(page).toHaveTitle('Busca: protetor solar · Besave');
	await campo.fill('xyz');
	await campo.press('Enter');
	await expect(page).toHaveURL(/\/busca\/\?q=xyz$/);
	expect(await page.evaluate(() => history.length)).toBe(entradas);
	await expect(campo).toBeFocused();
});

// BUS-05: os 3 chunks de `n` mais alto chegam primeiro (MANIFEST §3.1); o n=0 fica preso.
test('catálogo carregando: "Buscando em X de Y ofertas…" e resultado parcial', async ({ page }) => {
	const c = catalogo();
	const [modelo] = c.get(1) ?? [];
	for (const n of [2, 3])
		c.set(
			n,
			[0, 1].map((i) => ({ ...modelo, id: n * 1000 + i }))
		);
	await servir(page, c);
	let soltar: () => void = () => {};
	const preso = new Promise<void>((r) => (soltar = r));
	await page.route('**/data/chunks/0-*', async (r) => {
		await preso;
		await r.fulfill({ json: c.get(0) ?? [] });
	});
	await page.goto('/busca/?q=protetor');
	const total = todos(c).length;
	const primeiros = [1, 2, 3].flatMap((n) => c.get(n) ?? []);
	const parcial = primeiros.filter((x) => /\bprotetor/i.test(x.t));
	const completo = todos(c).filter((x) => /\bprotetor/i.test(x.t));
	expect(parcial.length).toBeGreaterThan(0);
	expect(parcial.length).toBeLessThan(completo.length);
	await expect(page.locator('[data-progresso]')).toHaveText(
		`Buscando em ${primeiros.length} de ${total} ofertas…`
	);
	await expect(contagem(page)).toHaveText(`${parcial.length} ofertas para “protetor”`);
	expect(ordenados(await ids(page))).toEqual(ordenados(parcial.map((x) => x.id)));
	soltar();
	await expect(contagem(page)).toHaveText(`${completo.length} ofertas para “protetor”`);
	await expect(page.locator('[data-progresso]')).toHaveCount(0);
});

// BUS-04: expiradas por último, em cinza, com "Encerrada"; só expiradas não é estado vazio.
test('expiradas aparecem depois das ativas com "Encerrada"', async ({ page }) => {
	const c = catalogo();
	// 1000 e 10 (Protetor solar, ELAS) expiram: 1000 é o mais recente de todos.
	const expiradas = [1000, 10];
	for (const cards of c.values())
		for (const card of cards) if (expiradas.includes(card.id)) card.x = 1;
	await servir(page, c);
	await page.goto('/busca/?q=protetor');
	await expect(contagem(page)).toHaveText('32 ofertas para “protetor”');
	const lista = await ids(page);
	expect(lista.slice(-2)).toEqual(expiradas);
	for (const id of lista.slice(0, -2)) expect(expiradas).not.toContain(id);
	for (const id of expiradas) {
		const card = page.locator(`${GRADE}[data-id="${id}"]`);
		await expect(card).toContainText('Encerrada');
		await expect(card.locator('img')).toHaveClass(/grayscale/);
	}
	await expect(page.locator(`${GRADE}[data-id="${lista[0]}"]`)).not.toContainText('Encerrada');

	await page.goto('/busca/?q=protetor+solar+fps+1000');
	await expect(contagem(page)).toHaveText('1 oferta para “protetor solar fps 1000”');
	await expect(page.locator(GRADE)).toHaveCount(1);
	await expect(page.locator('[data-vazio]')).toHaveCount(0);
});
