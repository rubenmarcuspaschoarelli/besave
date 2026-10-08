import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import Grade from './Grade.svelte';
import type { OfertaCard } from '#lib/dados.ts';

const AGORA = Date.parse('2026-10-08T12:00:00Z');
const card = (id: number): OfertaCard => ({
	id,
	l: 'AMAZON',
	t: `Produto ${id}`,
	pd: 20000,
	pp: 10000,
	dt: '2026-10-08T09:00:00Z',
	a: 'ELAS',
	p: 'FEMININO'
});

/** Tags `<img>` na ordem da grade. */
function imgs(n: number): string[] {
	const html = render(Grade, {
		props: { cards: Array.from({ length: n }, (_, i) => card(i + 1)), agora: AGORA }
	}).body;
	return [...html.matchAll(/<img\b[^>]*>/g)].map((m) => m[0]);
}

describe('Grade', () => {
	// IMG-01
	it('4 primeiras fotos sem lazy; só a 1ª com fetchpriority="high"', () => {
		const t = imgs(7);
		expect(t).toHaveLength(7);
		for (const img of t.slice(0, 4)) expect(img).not.toMatch(/\bloading=/);
		expect(t[0]).toMatch(/\bfetchpriority="high"/);
		for (const img of t.slice(1)) expect(img).not.toMatch(/\bfetchpriority=/);
	});

	// IMG-02
	it('da 5ª em diante, lazy', () => {
		for (const img of imgs(7).slice(4)) expect(img).toMatch(/\bloading="lazy"/);
	});

	// IMG-01 com menos de 4 cards: nenhuma lazy.
	it('grade com 2 cards: as duas sem lazy', () => {
		const t = imgs(2);
		expect(t).toHaveLength(2);
		for (const img of t) expect(img).not.toMatch(/\bloading=/);
	});
});
