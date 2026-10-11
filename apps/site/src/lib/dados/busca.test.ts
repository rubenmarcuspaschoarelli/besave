import { describe, expect, it } from 'vitest';
import { card, manifest, ref } from './apoio-teste.ts';
import { ativasPrimeiro, buscar } from './busca.ts';
import { Catalogo } from './catalogo.ts';
import type { OfertaCard } from './tipos.ts';

const cards = [
	card(1, { t: 'Protetor Solar Facial FPS 50', l: 'AMAZON', dt: '2026-09-20T00:00:00Z' }),
	card(2, { t: 'Café em Grãos Torrado 1kg', l: 'AMAZON' }),
	card(3, { t: 'Kit Skincare Vitamina C', c: 'BESAVE10', l: 'SHOPEE' }),
	card(4, { t: 'Escova Secadora Rosa', l: 'MERCADO_LIVRE' }),
	card(5, { t: 'Protetor Térmico Capilar', l: 'SHOPEE', x: 1, dt: '2026-09-25T00:00:00Z' }),
	card(6, { t: 'Lanterna Solar de Jardim', l: 'AMAZON', a: 'MEU_LAR' })
];

function cat(cs: OfertaCard[] = cards): Catalogo {
	const c = new Catalogo();
	c.alvo(manifest([ref(0)]));
	c.aplicarChunk(ref(0), cs);
	return c;
}

const ids = (cs: OfertaCard[]) => cs.map((c) => c.id).sort((a, b) => a - b);

describe('buscar', () => {
	const c = cat();

	it('BUS-01: "protetor solar" acha "Protetor Solar Facial FPS 50"', () => {
		expect(ids(buscar(c, 'protetor solar').itens)).toEqual([1]);
	});

	it('BUS-02: caixa e acento não mudam o resultado', () => {
		const r = ids(buscar(c, 'protetor').itens);
		expect(r).toEqual([1, 5]);
		expect(ids(buscar(c, 'PROTETOR').itens)).toEqual(r);
		expect(ids(buscar(c, 'protetór').itens)).toEqual(r);
	});

	it('BUS-03: "cafe" acha "Café"', () => {
		expect(ids(buscar(c, 'cafe').itens)).toEqual([2]);
	});

	it('BUS-04: só prefixo de palavra: "olar" não acha "Solar"', () => {
		expect(buscar(c, 'olar').total).toBe(0);
		expect(ids(buscar(c, 'sol').itens)).toEqual([1, 6]);
	});

	it('BUS-05: "besave" acha o cupom BESAVE10', () => {
		expect(ids(buscar(c, 'besave').itens)).toEqual([3]);
	});

	it('BUS-06: "mercado livre" acha a loja', () => {
		expect(ids(buscar(c, 'mercado livre').itens)).toEqual([4]);
	});

	it('BUS-07: consulta normalizada com menos de 2 caracteres → vazio', () => {
		expect(buscar(c, 'a')).toEqual({ itens: [], total: 0, completo: true });
		expect(buscar(c, ' é ')).toEqual({ itens: [], total: 0, completo: true });
		expect(buscar(c, '')).toEqual({ itens: [], total: 0, completo: true });
		expect(buscar(c, '!!')).toEqual({ itens: [], total: 0, completo: true });
	});

	it('BUS-08: inclui expiradas (com x:1)', () => {
		const r = buscar(c, 'termico');
		expect(r.itens.map((i) => i.id)).toEqual([5]);
		expect(r.itens[0].x).toBe(1);
	});

	it('BUS-08: todos os termos precisam casar (E)', () => {
		expect(buscar(c, 'protetor jardim').total).toBe(0);
		expect(ids(buscar(c, 'solar jardim').itens)).toEqual([6]);
	});

	it('BUS-08: respeita filtro, ordem e limite; informa total e completo', () => {
		expect(ids(buscar(c, 'solar', { area: 'MEU_LAR' }).itens)).toEqual([6]);
		// recentes: 5 (25/09) antes de 1 (20/09)
		expect(buscar(c, 'protetor').itens.map((i) => i.id)).toEqual([5, 1]);
		const r = buscar(c, 'protetor', {}, 1);
		expect(r.itens.map((i) => i.id)).toEqual([5]);
		expect(r.total).toBe(2);
		const parcial = new Catalogo();
		parcial.alvo(manifest([ref(0), ref(1)]));
		parcial.aplicarChunk(ref(0), cards);
		expect(buscar(parcial, 'protetor').completo).toBe(false);
	});

	it('título alterado no chunk novo é o pesquisado', () => {
		const c2 = cat();
		c2.aplicarChunk(ref(0, 'b'), [card(1, { t: 'Hidratante Labial' })]);
		expect(buscar(c2, 'protetor solar').total).toBe(0);
		expect(ids(buscar(c2, 'hidratante').itens)).toEqual([1]);
	});
});

describe('buscar com faixa e cupom (BSV-31)', () => {
	const c = cat([
		card(1, { t: 'Serum facial', pp: 5000 }),
		card(2, { t: 'Serum capilar', pp: 5001, c: 'CUPOM5' }),
		card(3, { t: 'Serum noturno', pp: 20001, c: 'CUPOM9' })
	]);

	it('DAD-01: buscar respeita a faixa', () => {
		expect(ids(buscar(c, 'serum', { faixa: 'ate50' }).itens)).toEqual([1]);
		expect(ids(buscar(c, 'serum', { faixa: '50a100' }).itens)).toEqual([2]);
		expect(ids(buscar(c, 'serum', { faixa: 'acima200' }).itens)).toEqual([3]);
	});

	it('DAD-02: buscar respeita soComCupom', () => {
		expect(ids(buscar(c, 'serum', { soComCupom: true }).itens)).toEqual([2, 3]);
		expect(buscar(c, 'serum', { soComCupom: true }).total).toBe(2);
	});
});

describe('ativasPrimeiro (BSV-34)', () => {
	const c = cat([
		card(1, { t: 'Protetor A', dp: '2026-10-01T00:00:00Z', pp: 900, pd: 1000 }),
		card(2, { t: 'Protetor B', dp: '2026-10-05T00:00:00Z', x: 1, pp: 100, pd: 1000 }),
		card(3, { t: 'Protetor C', dp: '2026-10-03T00:00:00Z', pp: 500, pd: 1000 }),
		card(4, { t: 'Protetor D', dp: '2026-10-04T00:00:00Z', x: 1, pp: 800, pd: 1000 }),
		card(5, { t: 'Protetor E', dp: '2026-10-02T00:00:00Z', pp: 300, pd: 1000 })
	]);
	const ordem = (o: 'recentes' | 'desconto' | 'preco') =>
		ativasPrimeiro(buscar(c, 'protetor', { ordem: o }, Infinity).itens).map((i) => i.id);

	it('BUS-04: expiradas depois das ativas, cada grupo na ordem escolhida', () => {
		// Ativas 3, 5, 1 por dp desc; expiradas 2, 4 por dp desc.
		expect(ordem('recentes')).toEqual([3, 5, 1, 2, 4]);
		// Desconto: ativas 5 (70%), 3 (50%), 1 (10%); expiradas 2 (90%), 4 (20%).
		expect(ordem('desconto')).toEqual([5, 3, 1, 2, 4]);
		// Preço: ativas 5 (300), 3 (500), 1 (900); expiradas 2 (100), 4 (800).
		expect(ordem('preco')).toEqual([5, 3, 1, 2, 4]);
	});

	it('BUS-04: só expiradas ou só ativas não mudam de ordem', () => {
		const exp = [card(9, { x: 1 }), card(8, { x: 1 })];
		expect(ativasPrimeiro(exp)).toEqual(exp);
		const atv = [card(7), card(6)];
		expect(ativasPrimeiro(atv)).toEqual(atv);
		expect(ativasPrimeiro([])).toEqual([]);
	});
});
