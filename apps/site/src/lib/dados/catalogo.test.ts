import { describe, expect, it } from 'vitest';
import { Catalogo } from './catalogo.ts';
import { card, manifest, ref } from './apoio-teste.ts';
import type { OfertaCard } from './tipos.ts';

/** Catálogo completo com um chunk n=0. */
function completo(cards: OfertaCard[]): Catalogo {
	const cat = new Catalogo();
	cat.alvo(manifest([ref(0)]));
	cat.aplicarChunk(ref(0), cards);
	return cat;
}

const ids = (cs: OfertaCard[]) => cs.map((c) => c.id);

describe('Catalogo.lista', () => {
	const cards = [
		card(1, { dt: '2026-09-20T10:00:00Z', pp: 5000, pd: 10000, a: 'ELAS', p: 'FEMININO' }),
		card(2, { dt: '2026-09-22T10:00:00Z', pp: 2000, pd: null, a: 'TECH', l: 'SHOPEE' }),
		card(3, { dt: '2026-09-21T10:00:00Z', pp: 9000, pd: 10000, a: 'ELAS', p: 'UNISSEX' }),
		card(4, { dt: '2026-09-22T10:00:00Z', pp: 1000, pd: 4000, x: 1 }),
		card(5, { dt: '2026-09-22T10:00:00Z', pp: 3000, pd: 6000, l: 'MERCADO_LIVRE' })
	];
	const cat = completo(cards);

	it('CAT-01: padrão exclui expiradas (x:1)', () => {
		expect(ids(cat.lista())).not.toContain(4);
		expect(cat.lista()).toHaveLength(4);
	});

	it('CAT-02: mostrarExpiradas inclui x:1', () => {
		expect(ids(cat.lista({ mostrarExpiradas: true }))).toContain(4);
		expect(cat.lista({ mostrarExpiradas: true })).toHaveLength(5);
	});

	it('CAT-03: filtros de área, público e loja', () => {
		expect(ids(cat.lista({ area: 'ELAS' })).sort()).toEqual([1, 3, 5]);
		expect(ids(cat.lista({ publico: 'UNISSEX' }))).toEqual([3]);
		expect(ids(cat.lista({ loja: 'SHOPEE' }))).toEqual([2]);
		expect(ids(cat.lista({ area: 'ELAS', loja: 'MERCADO_LIVRE' }))).toEqual([5]);
	});

	it('CAT-04: recentes = dt desc, desempate id desc (padrão)', () => {
		expect(ids(cat.lista())).toEqual([5, 2, 3, 1]);
		expect(ids(cat.lista({ ordem: 'recentes' }))).toEqual([5, 2, 3, 1]);
	});

	it('CAT-05: desconto desc, pd nulo por último', () => {
		// 1: 50%, 3: 10%, 5: 50% (mais recente), 2: sem pd
		expect(ids(cat.lista({ ordem: 'desconto' }))).toEqual([5, 1, 3, 2]);
	});

	it('CAT-06: preço asc', () => {
		expect(ids(cat.lista({ ordem: 'preco' }))).toEqual([2, 5, 1, 3]);
	});
});

describe('Catalogo: novas e mudanças (regra 8)', () => {
	const base = [card(1), card(2, { pp: 2000 }), card(3)];

	function comNovas() {
		const cat = completo(base);
		const antes = ids(cat.lista());
		cat.aplicarChunk(ref(0, 'b'), [
			...base,
			card(10, { x: 1 }),
			card(11, { dt: '2026-08-20T00:00:00Z' }),
			card(12, { dt: '2026-09-30T00:00:00Z' }),
			card(13, { dt: '2026-09-30T01:00:00Z' })
		]);
		return { cat, antes };
	}

	it('CAT-07: 4 ids novos (1 expirado, 1 com dt antigo) → novas() == 3', () => {
		const { cat } = comNovas();
		expect(cat.novas()).toBe(3);
	});

	it('CAT-08: lista inalterada até confirmarNovas(); depois inclui as novas', () => {
		const { cat, antes } = comNovas();
		expect(ids(cat.lista())).toEqual(antes);
		cat.confirmarNovas();
		expect(cat.novas()).toBe(0);
		expect(ids(cat.lista()).sort((a, b) => a - b)).toEqual([1, 2, 3, 11, 12, 13]);
	});

	it('CAT-09: mudança de preço num id exibido aparece sem confirmar', () => {
		const cat = completo(base);
		cat.aplicarChunk(ref(0, 'b'), [card(1), card(2, { pp: 1500 }), card(3), card(20)]);
		expect(cat.novas()).toBe(1);
		expect(cat.lista().find((c) => c.id === 2)?.pp).toBe(1500);
		expect(ids(cat.lista())).not.toContain(20);
	});

	it('antes de completo, todo card aplicado aparece na lista (primeira carga)', () => {
		const cat = new Catalogo();
		cat.alvo(manifest([ref(0), ref(1)]));
		cat.aplicarChunk(ref(1), [card(1001)]);
		expect(cat.novas()).toBe(0);
		expect(ids(cat.lista())).toEqual([1001]);
	});

	it('id que some do chunk e chunk descartado saem da lista', () => {
		const cat = new Catalogo();
		cat.alvo(manifest([ref(0), ref(1)]));
		cat.aplicarChunk(ref(0), [card(1), card(2)]);
		cat.aplicarChunk(ref(1), [card(1001)]);
		cat.aplicarChunk(ref(0, 'b'), [card(2)]);
		expect(ids(cat.lista()).sort((a, b) => a - b)).toEqual([2, 1001]);
		cat.descartar(1);
		expect(ids(cat.lista())).toEqual([2]);
	});
});

describe('Catalogo: progresso', () => {
	it('CAT-10: carregados/total contam chunks; completo só com todos do alvo', () => {
		const cat = new Catalogo();
		expect(cat.completo).toBe(false);
		cat.alvo(manifest([ref(0), ref(1)]));
		expect([cat.carregados, cat.total, cat.completo]).toEqual([0, 2, false]);
		cat.aplicarChunk(ref(1), [card(1001), card(1002)]);
		expect([cat.carregados, cat.total, cat.completo]).toEqual([1, 2, false]);
		cat.aplicarChunk(ref(0, 'z'), [card(1)]);
		expect([cat.carregados, cat.total, cat.completo]).toEqual([1, 2, false]);
		cat.aplicarChunk(ref(0), [card(1)]);
		expect([cat.carregados, cat.total, cat.completo]).toEqual([2, 2, true]);
	});

	it('manifest com 0 chunks → catálogo vazio e completo', () => {
		const cat = new Catalogo();
		cat.alvo(manifest([]));
		expect(cat.completo).toBe(true);
		expect(cat.lista()).toEqual([]);
	});
});
