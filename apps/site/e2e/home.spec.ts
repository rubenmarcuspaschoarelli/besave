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

// HOM-04 → LNK-01..04 (BSV-30b): áreas são links; Outros só no menu Mais.
test('áreas são links; Meu Lar abre /meu-lar/ ativo e Todas volta', async ({ page }) => {
	const nav = page.getByRole('navigation', { name: 'Áreas' });
	const ativos = () =>
		nav.locator('a[aria-current="page"]').evaluateAll((els) => els.map((e) => e.textContent));
	await expect(nav.getByRole('button')).toHaveCount(0);
	expect(await ativos()).toEqual(['Todas']);

	await nav.getByRole('link', { name: 'Meu Lar', exact: true }).click();
	await expect(page).toHaveURL(/\/meu-lar\/$/);
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Ofertas de Meu Lar');
	expect(await ativos()).toEqual(['Meu Lar']);
	const areas = await atributos(page, 'data-area');
	expect(areas.length).toBeGreaterThan(0);
	expect(new Set(areas)).toEqual(new Set(['MEU_LAR']));

	await nav.getByRole('link', { name: 'Todas', exact: true }).click();
	await expect(page).toHaveURL(/:\d+\/$/);
	expect(await ativos()).toEqual(['Todas']);
	await expect(page.locator(GRADE)).toHaveCount(40);
});

// LNK-04
test('Outros só no menu Mais, leva a /outros/ com Mais destacado', async ({ page }) => {
	const nav = page.getByRole('navigation', { name: 'Áreas' });
	await expect(nav.getByRole('link', { name: 'Outros' })).toBeHidden();
	const mais = nav.getByText('Mais ▾');
	await expect(mais).not.toHaveAttribute('data-ativo');
	await mais.click();
	await nav.getByRole('link', { name: 'Outros' }).click();
	await expect(page).toHaveURL(/\/outros\/$/);
	// Menu Mais fechado: o link existe, escondido, e é o atual.
	const outros = nav.locator('a[href="/outros/"]');
	await expect(outros).toBeHidden();
	await expect(outros).toHaveAttribute('aria-current', 'page');
	await expect(mais).toHaveAttribute('data-ativo', '');
	await expect(mais).toHaveCSS('background-color', 'rgb(11, 110, 79)');
});

// LNK-01: mesmos links em toda página com a navegação.
test('links de área iguais na home, área, desejos e 404', async ({ page }) => {
	const esperado = [
		['Todas', '/'],
		['Elas', '/elas/'],
		['Meu Lar', '/meu-lar/'],
		['Tech', '/tech/'],
		['Esporte & vida', '/esporte-vida/'],
		['Família & filhos', '/familia/'],
		['Pets', '/pets/'],
		['Players', '/players/'],
		['Cultura', '/cultura/'],
		['Eles', '/eles/'],
		['Outros', '/outros/']
	];
	for (const url of ['/', '/elas/', '/desejos/', '/404.html']) {
		await page.goto(url);
		const links = await page
			.getByRole('navigation', { name: 'Áreas' })
			.locator('a')
			.evaluateAll((els) => els.map((e) => [e.textContent?.trim(), e.getAttribute('href')]));
		expect(links, url).toEqual(esperado);
	}
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
	// Mais recentes primeiro: na fixtura, id maior = dp mais recente.
	expect(primeiros.slice(0, 3)).toEqual(['1009', '1008', '1007']);
	await page.getByRole('button', { name: 'Ver mais ofertas' }).click();
	await expect(page.locator(GRADE)).toHaveCount(80);
	const depois = await atributos(page, 'data-id');
	expect(depois.slice(0, 40)).toEqual(primeiros);
	expect(depois).toHaveLength(80);
	expect(depois.map(Number)).not.toContain(EXPIRADAS[1]);
	// A 147 cairia dentro dos 80 se não fosse expirada: 146 e 148 aparecem.
	expect(depois.map(Number)).toEqual(expect.arrayContaining([146, 148]));
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
		await expect(rodape.getByText(r, { exact: true })).toHaveCount(0);
	}
	await expect(rodape).not.toContainText('Aplicativos');
});

// CAR-04: sem `-small` no bucket, a imagem cai no placeholder da área.
test('imagem ausente vira o placeholder da área', async ({ page }) => {
	const slug: Record<string, string> = {
		ELAS: 'elas',
		MEU_LAR: 'meu-lar',
		TECH: 'tech',
		ESPORTE_VIDA: 'esporte-vida',
		FAMILIA: 'familia',
		PETS: 'pets',
		PLAYERS: 'players',
		CULTURA: 'cultura',
		ELES: 'eles',
		OUTROS: 'outros'
	};
	for (const i of [0, 1, 2]) {
		const card = page.locator(GRADE).nth(i);
		const area = (await card.getAttribute('data-area')) ?? '';
		await expect(card.locator('img')).toHaveAttribute('src', `/img/placeholder/${slug[area]}.webp`);
	}
});

// IMG-01, IMG-02: primeira dobra da grade sem lazy; faixa e o resto lazy.
test('prioridade das fotos da grade', async ({ page }) => {
	const fotos = page.locator(`${GRADE} img`);
	await expect(fotos).toHaveCount(40);
	const attrs = await fotos.evaluateAll((els) =>
		els.map((e) => [e.getAttribute('loading'), e.getAttribute('fetchpriority')])
	);
	expect(attrs.slice(0, 4)).toEqual([
		[null, 'high'],
		[null, null],
		[null, null],
		[null, null]
	]);
	for (const a of attrs.slice(4)) expect(a).toEqual(['lazy', null]);
	const faixa = await page
		.locator('[data-faixa] img')
		.evaluateAll((els) =>
			els.map((e) => [e.getAttribute('loading'), e.getAttribute('fetchpriority')])
		);
	expect(faixa).toHaveLength(8);
	for (const a of faixa) expect(a).toEqual(['lazy', null]);
});
