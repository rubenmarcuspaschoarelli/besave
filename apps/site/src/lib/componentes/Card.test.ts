import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import Card from './Card.svelte';
import type { OfertaCard } from '#lib/dados.ts';

const AGORA = Date.parse('2026-10-08T12:00:00Z');
const BASE: OfertaCard = {
	id: 5412,
	l: 'AMAZON',
	t: 'Protetor solar facial FPS 50 com cor',
	pd: 29990,
	pp: 19990,
	c: 'BESAVE10',
	dt: '2026-10-07T12:00:00Z',
	dp: '2026-10-08T09:00:00Z',
	a: 'ELAS',
	p: 'FEMININO'
};

const html = (card: OfertaCard) =>
	render(Card, { props: { card, agora: AGORA } }).body.replace(/\s/g, ' ');

describe('Card', () => {
	// CAR-01: desconto do contrato round((1 - 19990/29990) * 100) = 33.
	it('com pd: selo -N% e preço "de" riscado', () => {
		const h = html(BASE);
		expect(h).toMatch(/<span data-selo[^>]*>-33%<\/span>/);
		expect(h).toMatch(/<s[^>]*>R\$ 299,90<\/s>/);
	});

	// CAR-02
	it('sem pd: sem selo e sem "de"', () => {
		for (const pd of [null, undefined]) {
			const h = html({ ...BASE, pd });
			expect(h).not.toContain('data-selo');
			expect(h).not.toMatch(/-[^\s<>"]*%/);
			expect(h).not.toMatch(/<s[\s>]/);
			expect(h).not.toContain('R$ 299,90');
			expect(h).toContain('R$ 199,90');
		}
	});

	// CAR-03
	it('leva a /oferta/{id}/, sem /ir/ e sem cupom', () => {
		const h = html(BASE);
		expect(h).toContain('href="/oferta/5412/"');
		expect(h).not.toContain('/ir/');
		expect(h).not.toContain('BESAVE10');
	});

	// CAR-04
	it('imagem -small com lazy, tamanho fixo e placeholder da área', () => {
		const h = html(BASE);
		const img = h.match(/<img[^>]*>/)?.[0] ?? '';
		expect(img).toContain('src="/img/ofertas/5412-small.webp"');
		expect(img).toContain('loading="lazy"');
		expect(img).toMatch(/width="\d+"/);
		expect(img).toMatch(/height="\d+"/);
		expect(h).toContain('data-placeholder="/img/placeholder/elas.webp"');
		const h2 = html({ ...BASE, a: 'ESPORTE_VIDA' });
		expect(h2).toContain('data-placeholder="/img/placeholder/esporte-vida.webp"');
	});

	// CAR-05: "há X h" a partir de dp (09:00Z → 3 h antes de 12:00Z), não de dt.
	it('preço por, loja e tempo desde dp', () => {
		const h = html(BASE);
		expect(h).toContain('R$ 199,90');
		expect(h).toContain('Amazon');
		expect(h).toContain('há 3 h');
		expect(html({ ...BASE, l: 'MERCADO_LIVRE' })).toContain('Mercado Livre');
	});

	// CAR-06
	it('expirada em cinza', () => {
		const ativa = html(BASE);
		expect(ativa).not.toContain('Expirada');
		expect(ativa).not.toContain('grayscale');
		const h = html({ ...BASE, x: 1 });
		expect(h).toContain('Expirada');
		expect(h).toMatch(/<img[^>]*class="[^"]*grayscale/);
	});

	it('botão ♡ fora do link da oferta', () => {
		const h = html(BASE);
		expect(h).toMatch(/<button[^>]*aria-pressed="false"/);
		const link = h.match(/<a [^>]*href="\/oferta\/5412\/"[^>]*>.*?<\/a>/)?.[0] ?? '';
		expect(link).not.toContain('<button');
	});
});
