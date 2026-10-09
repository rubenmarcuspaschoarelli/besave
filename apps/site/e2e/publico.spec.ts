// Subpáginas de público /{slug}/{publico}/, público no caminho, texto e JSON-LD (BSV-33).
import { existsSync, readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { OfertaCard, Publico } from '../src/lib/dados.ts';
import { catalogo, servir, todos } from './fixtura.ts';
import { TEXTO_AREA, TEXTO_SUBPAGINA } from '../src/lib/conteudo/areas.ts';

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
	// Faixa de descontos também só da subpágina (mesmo layout da área, com o público aplicado).
	const faixa = await page
		.locator('[data-faixa] a')
		.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-id'))));
	expect(faixa.length).toBeGreaterThan(0);
	expect(new Set(faixa.map((id) => `${porId.get(id)?.a}/${porId.get(id)?.p}`))).toEqual(
		new Set(['ELAS/MASCULINO'])
	);
});

/** Botão de filtro pelo nome; no celular, abre o painel "Filtros" quando ele está lá dentro. */
async function tocar(page: Page, nome: string) {
	const botao = page.getByRole('button', { name: nome, exact: true });
	if (!(await botao.isVisible()))
		await page.getByRole('button', { name: 'Filtros', exact: true }).click();
	await botao.click();
}

const h1 = (page: Page) => page.getByRole('heading', { level: 1 });

// PUB-01
test('em /elas/, "Masculino" leva a /elas/masculino/ mantendo ?loja=', async ({ page }) => {
	await abrir(page, '/elas/?loja=shopee');
	await tocar(page, 'Masculino');
	await expect(page).toHaveURL(/\/elas\/masculino\/\?loja=shopee$/);
	await expect(h1(page)).toHaveText('Elas · Masculino');
	await expect(page.locator(GRADE).first()).toBeVisible();
	const grade = await naGrade(page);
	const esperados = CARDS.filter(
		(c) => c.a === 'ELAS' && c.p === 'MASCULINO' && c.l === 'SHOPEE' && !c.x
	);
	expect(grade.length).toBe(esperados.length);
	expect(new Set(grade.map((c) => `${c.a}/${c.p}/${c.l}`))).toEqual(
		new Set(['ELAS/MASCULINO/SHOPEE'])
	);
	await expect(pressionado(page, 'Shopee')).toHaveAttribute('aria-pressed', 'true');
});

// PUB-01: de uma subpágina para outra.
test('em /elas/masculino/, "Infantil" leva a /elas/infantil/', async ({ page }) => {
	await abrir(page, '/elas/masculino/?ordem=preco');
	await tocar(page, 'Infantil');
	await expect(page).toHaveURL(/\/elas\/infantil\/\?ordem=preco$/);
	await expect(h1(page)).toHaveText('Elas · Infantil');
	await expect(pressionado(page, 'Infantil')).toHaveAttribute('aria-pressed', 'true');
	await expect(pressionado(page, 'Menor preço')).toHaveAttribute('aria-pressed', 'true');
});

// PUB-02
test('"Todos" volta a /elas/ mantendo ?loja=', async ({ page }) => {
	await abrir(page, '/elas/masculino/?loja=shopee');
	await tocar(page, 'Todos');
	await expect(page).toHaveURL(/\/elas\/\?loja=shopee$/);
	await expect(h1(page)).toHaveText('Ofertas de Elas');
	await expect(page.locator(GRADE).first()).toBeVisible();
	const grade = await naGrade(page);
	expect(new Set(grade.map((c) => `${c.a}/${c.l}`))).toEqual(new Set(['ELAS/SHOPEE']));
	expect(new Set(grade.map((c) => c.p)).size).toBeGreaterThan(1);
	await expect(pressionado(page, 'Todos')).toHaveAttribute('aria-pressed', 'true');
});

// PUB-02
test('"Limpar filtros" numa subpágina volta a /elas/ sem filtros', async ({ page }) => {
	await abrir(page, '/elas/masculino/?loja=shopee');
	await page.getByRole('button', { name: 'Limpar filtros' }).first().click();
	await expect(page).toHaveURL(/\/elas\/$/);
	await expect(h1(page)).toHaveText('Ofertas de Elas');
});

// PUB-03
test('/elas/?publico=infantil vai para /elas/infantil/ sem entrada nova no histórico', async ({
	page
}) => {
	await servir(page, variado());
	await page.goto('/tech/');
	await page.goto('/elas/?publico=infantil&loja=shopee');
	await expect(page).toHaveURL(/\/elas\/infantil\/\?loja=shopee$/);
	await expect(h1(page)).toHaveText('Elas · Infantil');
	await expect(page.locator(GRADE).first()).toBeVisible();
	const grade = await naGrade(page);
	expect(new Set(grade.map((c) => `${c.a}/${c.p}/${c.l}`))).toEqual(
		new Set(['ELAS/INFANTIL/SHOPEE'])
	);
	await page.goBack();
	await expect(page).toHaveURL(/\/tech\/$/);
});

// PUB-04
test('na home, público continua em ?publico=', async ({ page }) => {
	await abrir(page, '/');
	await tocar(page, 'Masculino');
	await expect(page).toHaveURL(/\/\?publico=masculino$/);
	expect(new URL(page.url()).pathname).toBe('/');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Besave: ofertas e cupons');
});

/** Posição do fim do `<h1>` e do texto no HTML. */
function depoisDoH1(html: string, texto: string) {
	const h1 = html.indexOf('</h1>');
	const pos = html.indexOf(texto);
	expect(h1).toBeGreaterThan(0);
	expect(pos, texto).toBeGreaterThan(h1);
}

// TXT-02
test('texto da área e da subpágina no HTML, sem JavaScript, abaixo do h1', async ({ request }) => {
	const area = await (await request.get('/elas/')).text();
	depoisDoH1(area, TEXTO_AREA.ELAS);
	const sub = await (await request.get('/elas/unissex/')).text();
	depoisDoH1(sub, TEXTO_SUBPAGINA['ELAS/UNISSEX'] as string);
	depoisDoH1(sub, TEXTO_AREA.ELAS);
	// Sem frase própria: só o texto da área.
	const semFrase = await (await request.get('/elas/masculino/')).text();
	depoisDoH1(semFrase, TEXTO_AREA.ELAS);
	for (const t of Object.values(TEXTO_SUBPAGINA)) expect(semFrase).not.toContain(t);
	for (const slug of SLUGS) expect(ler(`${slug}/index.html`)).toContain('data-texto-area');
});

// TXT-02: visível na página.
test('texto da área aparece abaixo do h1 em /pets/', async ({ page }) => {
	await abrir(page, '/pets/');
	const texto = page.locator('[data-texto-area]');
	await expect(texto).toHaveText(TEXTO_AREA.PETS);
	await expect(texto).toBeVisible();
	const h1 = await page.getByRole('heading', { level: 1 }).boundingBox();
	const caixa = await texto.boundingBox();
	expect(caixa!.y).toBeGreaterThan(h1!.y);
});

/** Catálogo sem nenhuma oferta de ELES. */
const semEles = () =>
	new Map([...variado()].map(([n, cs]) => [n, cs.filter((c) => c.a !== 'ELES')]));

// TXT-03
for (const url of ['/eles/', '/eles/masculino/'])
	test(`${url} sem ofertas: texto, aviso e links para outras áreas`, async ({ page }) => {
		await servir(page, semEles());
		await page.goto(url);
		const vazio = page.locator('[data-sem-ofertas]');
		await expect(vazio).toBeVisible();
		await expect(vazio).toContainText('Ainda não temos ofertas aqui');
		await expect(page.locator('[data-texto-area]')).toContainText(TEXTO_AREA.ELES);
		const links = vazio.getByRole('link');
		await expect(links).toHaveCount(9);
		const hrefs = await links.evaluateAll((els) => els.map((e) => e.getAttribute('href')));
		expect(hrefs).toContain('/elas/');
		expect(hrefs).toContain('/outros/');
		expect(hrefs).not.toContain('/eles/');
		await expect(page.locator(GRADE)).toHaveCount(0);
	});

// TXT-03: com ofertas, nada de estado vazio.
test('/elas/ com ofertas não mostra o aviso de área vazia', async ({ page }) => {
	await abrir(page, '/elas/');
	await expect(page.locator('[data-sem-ofertas]')).toHaveCount(0);
});

// TXT-04: textos fora do JS que a home baixa ao abrir.
test('texto das áreas fora do bundle inicial da home', () => {
	const html = ler('index.html');
	expect(html).not.toContain(TEXTO_AREA.ELAS);
	const vistos = new Set<string>();
	const fila = [...html.matchAll(/(?:href="|import\(")(\/_app\/[^"]+\.js)"/g)].map((m) => m[1]);
	while (fila.length) {
		const f = fila.shift() as string;
		if (vistos.has(f)) continue;
		vistos.add(f);
		const codigo = ler(f.slice(1));
		expect(codigo, f).not.toContain('Ofertas de beleza e cuidados pessoais');
		for (const m of codigo.matchAll(/(?:from|import)\s*"(\.{1,2}\/[^"]+\.js)"/g))
			fila.push(new URL(m[1], `http://x${f}`).pathname);
	}
	expect(vistos.size).toBeGreaterThan(5);
});

/** Objetos JSON-LD do HTML (cada `<script type="application/ld+json">` tem de fazer parse). */
function jsonLd(html: string): Record<string, unknown>[] {
	return [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) =>
		JSON.parse(m[1])
	);
}

// JLD-01
for (const [url, trilha] of [
	[
		'/elas/',
		[
			['Início', 'https://besave.com.br/'],
			['Elas', 'https://besave.com.br/elas/']
		]
	],
	[
		'/familia/infantil/',
		[
			['Início', 'https://besave.com.br/'],
			['Família & filhos', 'https://besave.com.br/familia/'],
			['Infantil', 'https://besave.com.br/familia/infantil/']
		]
	]
] as const)
	test(`${url}: JSON-LD BreadcrumbList válido no HTML prerenderizado`, async ({ request }) => {
		const html = await (await request.get(url)).text();
		const lds = jsonLd(html);
		expect(lds).toHaveLength(1);
		expect(lds[0]).toEqual({
			'@context': 'https://schema.org',
			'@type': 'BreadcrumbList',
			itemListElement: trilha.map(([name, item], i) => ({
				'@type': 'ListItem',
				position: i + 1,
				name,
				item
			}))
		});
	});

// JLD-01: a home não tem trilha.
test('home sem BreadcrumbList', () => {
	expect(jsonLd(ler('index.html'))).toHaveLength(0);
});

// PUB-01 (decisão da tabela): trocar de público na área é trocar de página; voltar retorna.
test('voltar no navegador depois de "Masculino" retorna a /elas/', async ({ page }) => {
	await abrir(page, '/elas/?loja=shopee');
	await tocar(page, 'Masculino');
	await expect(page).toHaveURL(/\/elas\/masculino\/\?loja=shopee$/);
	await page.goBack();
	await expect(page).toHaveURL(/\/elas\/\?loja=shopee$/);
	await expect(h1(page)).toHaveText('Ofertas de Elas');
	await expect(pressionado(page, 'Todos')).toHaveAttribute('aria-pressed', 'true');
});
