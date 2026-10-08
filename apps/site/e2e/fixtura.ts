// Catálogo sintético servido no lugar de manifest.json e dos chunks (MANIFEST §2, §3).
import type { Page } from '@playwright/test';
import type { Area, OfertaCard } from '../src/lib/dados.ts';

const AREAS: Area[] = [
	'ELAS',
	'MEU_LAR',
	'TECH',
	'ESPORTE_VIDA',
	'FAMILIA',
	'PETS',
	'PLAYERS',
	'CULTURA',
	'ELES',
	'OUTROS'
];
export const EXPIRADAS = [7, 77];

function card(id: number, agora: number): OfertaCard {
	const a = AREAS[id % AREAS.length];
	const pp = 1000 + id * 37;
	return {
		id,
		l: id % 2 ? 'AMAZON' : 'SHOPEE',
		t: id % 10 === 0 ? `Protetor solar FPS ${id} toque seco` : `Produto ${id} da área ${a}`,
		pd: id % 3 === 0 ? pp * 2 : null,
		pp,
		dt: new Date(agora - 48 * 3_600_000).toISOString(),
		// Mais recente = id maior; todos nas últimas 24 h.
		dp: new Date(agora - (2000 - id) * 30_000).toISOString(),
		a,
		p: 'UNISSEX',
		...(EXPIRADAS.includes(id) ? { x: 1 as const } : {})
	};
}

/** Cards por `n` do chunk: ids 1..150 (n = 0) e 1000..1009 (n = 1). */
export function catalogo(agora = Date.now()): Map<number, OfertaCard[]> {
	const ids = [
		...Array.from({ length: 150 }, (_, i) => i + 1),
		...Array.from({ length: 10 }, (_, i) => 1000 + i)
	];
	const chunks = new Map<number, OfertaCard[]>();
	for (const id of ids) {
		const n = Math.floor(id / 1000);
		chunks.set(n, [...(chunks.get(n) ?? []), card(id, agora)]);
	}
	return chunks;
}

export const todos = (c: Map<number, OfertaCard[]>) => [...c.values()].flat();

/** Intercepta manifest, chunks, imagens e páginas de oferta. */
export async function servir(page: Page, c = catalogo()): Promise<Map<number, OfertaCard[]>> {
	const chunks = [...c].map(([n, cards]) => ({
		n,
		arquivo: `data/chunks/${n}-${String(n).repeat(16)}.json.br`,
		ids: [Math.max(1, n * 1000), n * 1000 + 999],
		qtd: cards.length,
		bytes: 1
	}));
	await page.route('**/manifest.json', (r) =>
		r.fulfill({
			json: {
				contrato: '1.5.0',
				versao: 20261008000000,
				gerado_em: new Date().toISOString(),
				total_ofertas: todos(c).length,
				chunks,
				busca: null,
				areas: {}
			}
		})
	);
	await page.route('**/data/chunks/*', (r) => {
		const arquivo = new URL(r.request().url()).pathname.split('/').pop() ?? '';
		return r.fulfill({ json: c.get(Number(arquivo.split('-')[0])) ?? [] });
	});
	await page.route('**/img/**', (r) => r.fulfill({ status: 404, body: '' }));
	await page.route('**/oferta/**', (r) =>
		r.fulfill({
			contentType: 'text/html',
			body: '<!doctype html><title>oferta</title><h1>Oferta</h1>'
		})
	);
	return c;
}
