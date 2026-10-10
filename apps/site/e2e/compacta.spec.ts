// BSV-37: linha compacta de filtros no computador (≥ 1024 px).
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { Loja, OfertaCard, Publico } from '../src/lib/dados.ts';
import { servir } from './fixtura.ts';
import { item } from './linha-compacta.ts';

const GRADE = '[data-grade] article';
const BUILD = new URL('../build/', import.meta.url);
const LOJAS: Loja[] = ['AMAZON', 'SHOPEE', 'MERCADO_LIVRE'];
const PUBLICOS: Publico[] = ['FEMININO', 'MASCULINO', 'UNISSEX', 'INFANTIL'];

/** 60 cards: público, loja e área alternados; um em cada cinco com cupom. */
function cards(agora = Date.now()): OfertaCard[] {
	return Array.from({ length: 60 }, (_, i) => {
		const id = i + 1;
		return {
			id,
			l: LOJAS[id % 3],
			t: `Produto ${id}`,
			pd: id % 2 ? null : 3000 + id * 200,
			pp: 1000 + id * 150,
			...(id % 5 === 0 ? { c: `CUPOM${id}` } : {}),
			dt: new Date(agora - 48 * 3_600_000).toISOString(),
			dp: new Date(agora - (2000 - id) * 30_000).toISOString(),
			a: id % 2 ? 'ELAS' : 'TECH',
			p: PUBLICOS[id % 4]
		};
	});
}
const CARDS = cards();
const porId = new Map(CARDS.map((c) => [c.id, c]));

async function abrir(page: Page, url = '/') {
	await servir(page, new Map([[0, cards()]]));
	await page.goto(url);
	await expect(page.locator(GRADE).first()).toBeVisible();
}

const naGrade = (page: Page) =>
	page
		.locator(GRADE)
		.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))))
		.then((ids) => ids.map((id) => porId.get(id)!));

const faixa = (page: Page) => page.locator('[data-faixa-filtros]');
const opcao = (page: Page, nome: string) => page.getByRole('button', { name: nome, exact: true });
const cupom = (page: Page) =>
	page.locator('[data-compacta]').getByRole('button', { name: 'Só com cupom', exact: true });
const contagem = (page: Page) => page.locator('[data-contagem]');

test.describe('computador (1280 px)', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	// CMP-01
	test('título e filtros numa linha; opções fechadas', async ({ page }) => {
		await abrir(page);
		const titulo = await page.locator('#titulo-recentes').boundingBox();
		const nomes = ['Ordem: Recentes', 'Público', 'Loja', 'Preço', 'Só com cupom'];
		for (const nome of nomes) {
			const caixa = await page.getByRole('button', { name: nome, exact: true }).boundingBox();
			expect(caixa, nome).not.toBeNull();
			// Mesma linha: as faixas verticais do título e do item se sobrepõem, e o item fica à direita.
			expect(caixa!.y, nome).toBeLessThan(titulo!.y + titulo!.height);
			expect(caixa!.y + caixa!.height, nome).toBeGreaterThan(titulo!.y);
			expect(caixa!.x, nome).toBeGreaterThan(titulo!.x + titulo!.width);
		}
		await expect(opcao(page, 'Filtros')).toBeHidden();
		for (const nome of ['Recentes', 'Maior desconto', 'Todos', 'Feminino', 'Shopee', 'Até R$ 50'])
			await expect(opcao(page, nome)).toHaveCount(0);
		await expect(faixa(page)).toHaveCount(0);
		for (const g of ['Ordem', 'Público', 'Loja', 'Preço'])
			await expect(item(page, g)).toHaveAttribute('aria-expanded', 'false');
	});

	// CMP-02
	test('"Público ▾" abre a faixa logo abaixo da linha com as opções', async ({ page }) => {
		await abrir(page);
		const publico = item(page, 'Público');
		await publico.click();
		await expect(publico).toHaveAttribute('aria-expanded', 'true');
		const id = await publico.getAttribute('aria-controls');
		expect(id).toBeTruthy();
		const alvo = page.locator(`[id="${id}"]`);
		await expect(alvo).toBeVisible();
		for (const nome of ['Todos', 'Feminino', 'Masculino', 'Unissex', 'Infantil'])
			await expect(alvo.getByRole('button', { name: nome, exact: true })).toBeVisible();
		await expect(alvo.getByRole('button')).toHaveCount(5);
		// Logo abaixo da linha e antes da grade.
		const [linha, f, grade] = await Promise.all([
			publico.boundingBox(),
			alvo.boundingBox(),
			page.locator(GRADE).first().boundingBox()
		]);
		expect(f!.y).toBeGreaterThanOrEqual(linha!.y + linha!.height);
		expect(f!.y - (linha!.y + linha!.height)).toBeLessThanOrEqual(24);
		expect(f!.y + f!.height).toBeLessThanOrEqual(grade!.y);
	});

	// CMP-04
	test('escolher "Feminino" fecha a faixa, mostra o valor e filtra', async ({ page }) => {
		await abrir(page);
		await item(page, 'Público').click();
		await opcao(page, 'Feminino').click();
		await expect(faixa(page)).toHaveCount(0);
		await expect(item(page, 'Público')).toHaveAccessibleName('Público: Feminino');
		await expect(item(page, 'Público')).toHaveAttribute('aria-expanded', 'false');
		await expect(page).toHaveURL(/\/\?publico=feminino$/);
		const esperado = CARDS.filter((c) => c.p === 'FEMININO');
		await expect(contagem(page)).toHaveText(`${esperado.length} ofertas`);
		const grade = await naGrade(page);
		expect(grade).toHaveLength(esperado.length);
		expect(grade.every((c) => c.p === 'FEMININO')).toBe(true);
		// Sem escolha, só o nome; ordem sempre com o valor.
		await expect(item(page, 'Loja')).toHaveAccessibleName('Loja');
		await expect(item(page, 'Ordem')).toHaveAccessibleName('Ordem: Recentes');
		// Clicar de novo reabre, com a escolha marcada.
		await item(page, 'Público').click();
		await expect(faixa(page)).toBeVisible();
		await expect(opcao(page, 'Feminino')).toHaveAttribute('aria-pressed', 'true');
	});

	// CMP-04: valor de preço e de ordem no item; URL da BSV-31.
	test('"Preço: Até R$ 50" e "Ordem: Menor preço"', async ({ page }) => {
		await abrir(page);
		await item(page, 'Preço').click();
		await opcao(page, 'Até R$ 50').click();
		await expect(item(page, 'Preço')).toHaveAccessibleName('Preço: Até R$ 50');
		await item(page, 'Ordem').click();
		await opcao(page, 'Menor preço').click();
		await expect(item(page, 'Ordem')).toHaveAccessibleName('Ordem: Menor preço');
		await expect(page).toHaveURL(/\/\?ordem=preco&preco=ate50$/);
		const precos = (await naGrade(page)).map((c) => c.pp);
		expect(precos.length).toBe(CARDS.filter((c) => c.pp <= 5000).length);
		expect(precos).toEqual([...precos].sort((a, b) => a - b));
		expect(Math.max(...precos)).toBeLessThanOrEqual(5000);
	});

	// CMP-03
	test('abrir "Loja ▾" fecha a faixa de público', async ({ page }) => {
		await abrir(page);
		await item(page, 'Público').click();
		await expect(opcao(page, 'Feminino')).toBeVisible();
		await item(page, 'Loja').click();
		await expect(item(page, 'Público')).toHaveAttribute('aria-expanded', 'false');
		await expect(item(page, 'Loja')).toHaveAttribute('aria-expanded', 'true');
		await expect(faixa(page)).toHaveCount(1);
		await expect(opcao(page, 'Feminino')).toHaveCount(0);
		for (const nome of ['Todas', 'Amazon', 'Mercado Livre', 'Shopee'])
			await expect(opcao(page, nome)).toBeVisible();
		// Clicar de novo no item aberto fecha.
		await item(page, 'Loja').click();
		await expect(faixa(page)).toHaveCount(0);
	});

	// CMP-05
	test('Esc fecha a faixa e devolve o foco ao item', async ({ page }) => {
		await abrir(page);
		const loja = item(page, 'Loja');
		await loja.focus();
		await page.keyboard.press('Enter');
		await expect(faixa(page)).toBeVisible();
		await opcao(page, 'Shopee').focus();
		await page.keyboard.press('Escape');
		await expect(faixa(page)).toHaveCount(0);
		await expect(loja).toBeFocused();
		await expect(loja).toHaveAttribute('aria-expanded', 'false');
		// Nada escolhido.
		await expect(page).toHaveURL(/\/$/);
	});

	// CMP-06
	test('clique fora fecha a faixa', async ({ page }) => {
		await abrir(page);
		const preco = item(page, 'Preço');
		await preco.click();
		await expect(faixa(page)).toBeVisible();
		// Margem da página, fora da linha e da faixa.
		await page.mouse.click(8, 600);
		await expect(faixa(page)).toHaveCount(0);
		await expect(preco).toBeFocused();
		await expect(page).toHaveURL(/\/$/);
		// Clique na busca fecha e deixa o foco no campo.
		await preco.click();
		await expect(faixa(page)).toBeVisible();
		const busca = page.getByRole('searchbox', { name: 'Buscar ofertas' });
		await busca.click();
		await expect(faixa(page)).toHaveCount(0);
		await expect(busca).toBeFocused();
	});

	// CMP-07
	test('"Só com cupom" liga e desliga', async ({ page }) => {
		await abrir(page);
		await expect(cupom(page)).toHaveAttribute('aria-pressed', 'false');
		await cupom(page).click();
		await expect(cupom(page)).toHaveAttribute('aria-pressed', 'true');
		await expect(page).toHaveURL(/\/\?cupom=1$/);
		const com = CARDS.filter((c) => c.c);
		await expect(contagem(page)).toHaveText(`${com.length} ofertas`);
		expect((await naGrade(page)).every((c) => !!c.c)).toBe(true);
		await cupom(page).click();
		await expect(cupom(page)).toHaveAttribute('aria-pressed', 'false');
		await expect(page).toHaveURL(/\/$/);
		await expect(contagem(page)).toHaveText(`${CARDS.length} ofertas`);
	});

	// CMP-08
	test('"Limpar filtros" na linha volta ao padrão', async ({ page }) => {
		await abrir(page, '/?ordem=desconto&publico=infantil&loja=shopee&preco=50a100&cupom=1');
		const linha = page.locator('[data-compacta]');
		const limpar = linha.getByRole('button', { name: 'Limpar filtros', exact: true });
		await expect(limpar).toBeVisible();
		// Na linha, na altura dos itens; uma só na página.
		await expect(page.getByRole('button', { name: 'Limpar filtros' })).toHaveCount(1);
		await expect(item(page, 'Público')).toHaveAccessibleName('Público: Infantil');
		await expect(item(page, 'Loja')).toHaveAccessibleName('Loja: Shopee');
		await expect(item(page, 'Preço')).toHaveAccessibleName('Preço: R$ 50–100');
		await expect(item(page, 'Ordem')).toHaveAccessibleName('Ordem: Maior desconto');
		await limpar.click();
		await expect(page).toHaveURL(/\/$/);
		await expect(limpar).toHaveCount(0);
		await expect(item(page, 'Ordem')).toHaveAccessibleName('Ordem: Recentes');
		for (const g of ['Público', 'Loja', 'Preço'])
			await expect(item(page, g)).toHaveAccessibleName(g);
		await expect(cupom(page)).toHaveAttribute('aria-pressed', 'false');
		await expect(contagem(page)).toHaveText(`${CARDS.length} ofertas`);
	});

	test('"Limpar filtros" não aparece no padrão', async ({ page }) => {
		await abrir(page);
		await expect(page.getByRole('button', { name: 'Limpar filtros' })).toHaveCount(0);
	});

	// CMP-09
	test('nada da faixa de opções é baixado antes do primeiro clique', async ({ page }) => {
		const js: string[] = [];
		page.on('request', (r) => {
			const u = new URL(r.url());
			if (u.pathname.endsWith('.js')) js.push(u.pathname);
		});
		await abrir(page);
		// Rede parada: o que tinha de chegar na abertura já chegou.
		await page.waitForLoadState('networkidle');
		const comFaixa = (lista: string[]) =>
			lista.filter((f) =>
				readFileSync(new URL(f.slice(1), BUILD), 'utf8').includes('data-grupo-filtro')
			);
		expect(js.length).toBeGreaterThan(5);
		expect(comFaixa(js)).toEqual([]);
		const antes = js.length;
		await item(page, 'Público').click();
		await expect(opcao(page, 'Feminino')).toBeVisible();
		expect(comFaixa(js.slice(antes)).length).toBeGreaterThan(0);
	});

	// CMP-10
	test('itens com ≥ 44 px e foco visível na cor do tema', async ({ page }) => {
		await abrir(page, '/?loja=amazon');
		const linha = page.locator('[data-compacta]');
		const alturas = await linha
			.getByRole('button')
			.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
		// 4 itens + interruptor + "Limpar filtros".
		expect(alturas).toHaveLength(6);
		for (const h of alturas) expect(h).toBeGreaterThanOrEqual(44);
		const publico = item(page, 'Público');
		await item(page, 'Ordem').focus();
		await page.keyboard.press('Tab');
		await expect(publico).toBeFocused();
		const contorno = await publico.evaluate((e) => {
			const s = getComputedStyle(e);
			return `${s.outlineStyle} ${s.outlineColor}`;
		});
		expect(contorno).toBe('solid rgb(29, 78, 216)');
		// Opções da faixa também com ≥ 44 px.
		await publico.press('Enter');
		// A faixa chega por import(): mede só depois que as opções estão na página.
		await expect(faixa(page).getByRole('button')).toHaveCount(5);
		const opcoes = await faixa(page)
			.getByRole('button')
			.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
		expect(opcoes).toHaveLength(5);
		for (const h of opcoes) expect(h).toBeGreaterThanOrEqual(44);
	});

	// CMP-11
	test('na área, o público da faixa navega pelo caminho', async ({ page }) => {
		await abrir(page, '/elas/?loja=shopee');
		await item(page, 'Público').click();
		await opcao(page, 'Masculino').click();
		await expect(page).toHaveURL(/\/elas\/masculino\/\?loja=shopee$/);
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Elas · Masculino');
		await expect(item(page, 'Público')).toHaveAccessibleName('Público: Masculino');
		await expect(page.locator(GRADE).first()).toBeVisible();
		const grade = await naGrade(page);
		const esperado = CARDS.filter((c) => c.a === 'ELAS' && c.p === 'MASCULINO' && c.l === 'SHOPEE');
		expect(grade).toHaveLength(esperado.length);
		// "Todos" volta para a área.
		await item(page, 'Público').click();
		await opcao(page, 'Todos').click();
		await expect(page).toHaveURL(/\/elas\/\?loja=shopee$/);
	});
});

// CEL-01 (complemento): abaixo de 1024 px continua o botão "Filtros" com o painel.
test.describe('tablet (800 px)', () => {
	test.use({ viewport: { width: 800, height: 1000 } });

	test('"Filtros" e painel; sem linha compacta', async ({ page }) => {
		await abrir(page);
		await expect(page.locator('[data-compacta]')).toHaveCount(0);
		await opcao(page, 'Filtros').click();
		const painel = page.getByRole('dialog', { name: 'Filtros' });
		await expect(painel).toBeVisible();
		await painel.getByRole('button', { name: 'Feminino', exact: true }).click();
		await expect(page).toHaveURL(/\/\?publico=feminino$/);
	});
});
