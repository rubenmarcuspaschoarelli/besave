// Subpáginas de público /{slug}/{publico}/, público no caminho, texto e JSON-LD (BSV-33).
import { existsSync, readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { OfertaCard, Publico } from '../src/lib/dados.ts';
import { catalogo, servir, todos } from './fixtura.ts';

const GRADE = '[data-grade] article';
const BUILD = new URL('../build/', import.meta.url);
const ler = (arquivo: string) => readFileSync(new URL(arquivo, BUILD), 'utf8');

const SLUGS = [
	'tech',
	'players',
	'meu-lar',
	'elas',
	'eles',
	'cultura',
	'familia',
	'pets',
	'esporte-vida',
	'outros'
];
const PUBLICOS: Publico[] = ['FEMININO', 'MASCULINO', 'UNISSEX', 'INFANTIL'];

/** Catálogo da fixtura com o público variando por dezena de id (ELAS = ids múltiplos de 10). */
function variado(): Map<number, OfertaCard[]> {
	return new Map(
		[...catalogo()].map(([n, cs]) => [
			n,
			cs.map((c) => ({ ...c, p: PUBLICOS[Math.floor(c.id / 10) % 4] }))
		])
	);
}
const CARDS = todos(variado());
const porId = new Map(CARDS.map((c) => [c.id, c]));

async function abrir(page: Page, url: string, c = variado()) {
	await servir(page, c);
	const r = await page.goto(url);
	await expect(page.locator(GRADE).first()).toBeVisible();
	return r;
}

const naGrade = async (page: Page) =>
	(
		await page
			.locator(GRADE)
			.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))))
	).map((id) => porId.get(id)!);

const pressionado = (page: Page, nome: string) =>
	page.locator('[data-filtros] button[aria-pressed]', { hasText: new RegExp(`^${nome}$`) });

// SUB-01
test('/elas/masculino/: 200, h1, title, description e canonical próprios', async ({ page }) => {
	const r = await abrir(page, '/elas/masculino/');
	expect(r?.status()).toBe(200);
	const h1 = page.getByRole('heading', { level: 1 });
	await expect(h1).toHaveText('Elas · Masculino');
	await expect(h1).toBeVisible();
	await expect(page).toHaveTitle('Ofertas de Elas · Masculino · Besave');
	await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
		'href',
		'https://besave.com.br/elas/masculino/'
	);
	const descricao = await page.locator('meta[name="description"]').getAttribute('content');
	expect(descricao).toContain('Elas');
	expect(descricao).toContain('masculino');
	// No HTML do build, sem depender de JS.
	const html = ler('elas/masculino/index.html');
	expect(html).toContain('<link rel="canonical" href="https://besave.com.br/elas/masculino/"');
	expect(html).toMatch(/<h1[^>]*>\s*Elas · Masculino\s*<\/h1>/);
	expect(html).not.toMatch(/<meta name="robots"[^>]*noindex/);
});

// SUB-01: as 40 combinações saem prerenderizadas, cada uma com o próprio canonical.
test('as 40 subpáginas existem no build', () => {
	for (const slug of SLUGS)
		for (const p of PUBLICOS) {
			const caminho = `${slug}/${p.toLowerCase()}/index.html`;
			expect(existsSync(new URL(caminho, BUILD)), caminho).toBe(true);
			expect(ler(caminho)).toContain(
				`<link rel="canonical" href="https://besave.com.br/${slug}/${p.toLowerCase()}/"`
			);
		}
});

// SUB-02
test('slug ou público fora da lista responde 404', async ({ request }) => {
	for (const p of ['/elas/xyz/', '/xyz/feminino/', '/elas/feminina/']) {
		expect((await request.get(p)).status(), p).toBe(404);
	}
});

// SUB-03
test('breadcrumb Início › Elas › Masculino', async ({ page }) => {
	await abrir(page, '/elas/masculino/');
	const trilha = page.getByRole('navigation', { name: 'Trilha' });
	await expect(trilha).toBeVisible();
	await expect(trilha.getByRole('listitem').filter({ hasNotText: '›' })).toHaveText([
		'Início',
		'Elas',
		'Masculino'
	]);
	await expect(trilha.getByRole('link', { name: 'Início' })).toHaveAttribute('href', '/');
	await expect(trilha.getByRole('link', { name: 'Elas' })).toHaveAttribute('href', '/elas/');
	await expect(trilha.locator('[aria-current="page"]')).toHaveText('Masculino');
	expect(ler('elas/masculino/index.html')).toContain('aria-label="Trilha"');
});

// SUB-04
test('/elas/masculino/: grade só ELAS + MASCULINO, com o público marcado', async ({ page }) => {
	const esperados = CARDS.filter((c) => c.a === 'ELAS' && c.p === 'MASCULINO' && !c.x);
	expect(esperados.length).toBeGreaterThan(1);
	await abrir(page, '/elas/masculino/');
	const grade = await naGrade(page);
	expect(grade.length).toBe(esperados.length);
	expect(new Set(grade.map((c) => `${c.a}/${c.p}`))).toEqual(new Set(['ELAS/MASCULINO']));
	await expect(pressionado(page, 'Masculino')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Todos')).toHaveAttribute('aria-pressed', 'false');
});
