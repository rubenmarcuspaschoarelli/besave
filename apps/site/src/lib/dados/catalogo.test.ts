import { describe, expect, it } from 'vitest';
import { Catalogo, maioresDescontos } from './catalogo.ts';
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

// BSV-36: `recentes` por `dp` (sem `dp`, `dt`); "Maiores descontos de hoje".
describe('dp: data de publicação no site', () => {
	it('SIT-01: recentes segue dp desc mesmo contra a ordem de dt; empate de dp por id desc', () => {
		const cat = completo([
			card(1, { dt: '2026-09-30T10:00:00Z', dp: '2026-10-06T10:00:00Z' }),
			card(2, { dt: '2026-10-05T10:00:00Z', dp: '2026-10-06T09:00:00Z' }),
			card(3, { dt: '2026-09-01T10:00:00Z', dp: '2026-10-07T08:00:00Z' }),
			card(5, { dt: '2026-10-06T23:00:00Z', dp: '2026-10-06T09:00:00Z' })
		]);
		// Por dt seria [5, 2, 1, 3].
		expect(ids(cat.lista({ ordem: 'recentes' }))).toEqual([3, 1, 5, 2]);
	});

	it('SIT-02: card sem dp (chunk antigo) entra na ordem pelo dt', () => {
		const cat = completo([
			card(1, { dt: '2026-09-30T10:00:00Z', dp: '2026-10-06T10:00:00Z' }),
			card(2, { dt: '2026-10-05T10:00:00Z', dp: '2026-10-06T09:00:00Z' }),
			card(4, { dt: '2026-10-06T09:30:00Z' })
		]);
		expect(ids(cat.lista())).toEqual([1, 4, 2]);
	});

	describe('maioresDescontos', () => {
		const agora = Date.parse('2026-10-07T12:00:00Z');
		const promo = (id: number, dp: string | undefined, pp: number, o: Partial<OfertaCard> = {}) =>
			card(id, { dt: '2026-10-01T00:00:00Z', ...(dp ? { dp } : {}), pd: 10000, pp, ...o });
		const cat = completo([
			promo(10, '2026-10-07T11:00:00Z', 5000), // 50%
			promo(11, '2026-10-07T10:00:00Z', 2000), // 80%
			promo(12, '2026-10-06T11:00:00Z', 1000), // 90%, dp de 25 h
			promo(13, '2026-10-07T09:00:00Z', 500, { x: 1 }), // 95%, expirada
			promo(14, '2026-10-07T08:00:00Z', 5000), // 50%, dp mais antigo que o de 10
			promo(9, '2026-10-07T11:30:00Z', 5000, { pd: null }), // sem desconto
			promo(15, '2026-10-06T12:00:00Z', 4000), // 60%, exatamente 24 h
			promo(16, undefined, 3000, { dt: '2026-10-07T07:00:00Z' }) // 70%, sem dp: usa dt
		]);

		it('SIT-03: ativas das últimas 24 h por desconto desc, empate por dp desc', () => {
			expect(ids(maioresDescontos(cat, agora, 10))).toEqual([11, 16, 15, 10, 14]);
		});

		it('SIT-03: devolve no máximo n', () => {
			expect(ids(maioresDescontos(cat, agora, 2))).toEqual([11, 16]);
		});

		it('SIT-04: dp de 25 h fica de fora', () => {
			expect(ids(maioresDescontos(cat, agora, 10))).not.toContain(12);
		});

		it('SIT-05: expirada fica de fora', () => {
			expect(ids(maioresDescontos(cat, agora, 10))).not.toContain(13);
		});

		// ARE-04: a faixa da página de área só traz a área, na mesma ordem de desconto.
		it('ARE-04: filtro de área', () => {
			const porArea = completo([
				promo(20, '2026-10-07T11:00:00Z', 5000, { a: 'ELAS' }), // 50%
				promo(21, '2026-10-07T10:00:00Z', 1000, { a: 'TECH' }), // 90%
				promo(22, '2026-10-07T09:00:00Z', 2000, { a: 'ELAS' }), // 80%
				promo(23, '2026-10-07T08:00:00Z', 4000, { a: 'MEU_LAR' }) // 60%
			]);
			expect(ids(maioresDescontos(porArea, agora, 10, { area: 'ELAS' }))).toEqual([22, 20]);
			expect(ids(maioresDescontos(porArea, agora, 10, { area: 'TECH' }))).toEqual([21]);
			expect(ids(maioresDescontos(porArea, agora, 10, { area: 'PETS' }))).toEqual([]);
			expect(ids(maioresDescontos(porArea, agora, 10))).toEqual([21, 22, 23, 20]);
		});
	});
});

describe('faixa de preço e cupom (BSV-31)', () => {
	// Um card de cada lado de cada fronteira (CONTRATO §3: pp em centavos).
	const fronteira = [
		card(1, { pp: 1, dt: '2026-09-20T01:00:00Z' }),
		card(2, { pp: 5000, dt: '2026-09-20T02:00:00Z' }),
		card(3, { pp: 5001, dt: '2026-09-20T03:00:00Z' }),
		card(4, { pp: 10000, dt: '2026-09-20T04:00:00Z' }),
		card(5, { pp: 10001, dt: '2026-09-20T05:00:00Z' }),
		card(6, { pp: 20000, dt: '2026-09-20T06:00:00Z' }),
		card(7, { pp: 20001, dt: '2026-09-20T07:00:00Z' }),
		card(8, { pp: 999999, dt: '2026-09-20T08:00:00Z' })
	];
	const cat = completo(fronteira);
	const ordenados = (cs: OfertaCard[]) => ids(cs).sort((a, b) => a - b);

	it('DAD-01: ate50 = pp ≤ 5000', () => {
		expect(ordenados(cat.lista({ faixa: 'ate50' }))).toEqual([1, 2]);
	});

	it('DAD-01: 50a100 = 5001..10000', () => {
		expect(ordenados(cat.lista({ faixa: '50a100' }))).toEqual([3, 4]);
	});

	it('DAD-01: 100a200 = 10001..20000', () => {
		expect(ordenados(cat.lista({ faixa: '100a200' }))).toEqual([5, 6]);
	});

	it('DAD-01: acima200 = pp > 20000', () => {
		expect(ordenados(cat.lista({ faixa: 'acima200' }))).toEqual([7, 8]);
	});

	it('DAD-01: sem faixa não filtra', () => {
		expect(cat.lista()).toHaveLength(8);
		expect(cat.lista({ faixa: undefined })).toHaveLength(8);
	});

	const comCupom = completo([
		card(1, { c: 'BESAVE10' }),
		card(2),
		card(3, { c: 'X' }),
		card(4, { c: 'Y', x: 1 })
	]);

	it('DAD-02: soComCupom só deixa cards com c', () => {
		expect(ordenados(comCupom.lista({ soComCupom: true }))).toEqual([1, 3]);
	});

	it('DAD-02: soComCupom ausente ou false não filtra', () => {
		expect(ordenados(comCupom.lista())).toEqual([1, 2, 3]);
		expect(ordenados(comCupom.lista({ soComCupom: false }))).toEqual([1, 2, 3]);
	});

	it('DAD-03: público + loja + faixa + cupom com ordem desconto = interseção ordenada', () => {
		const mix = completo([
			// casam: FEMININO, AMAZON, ≤ 5000, com cupom
			card(1, { p: 'FEMININO', l: 'AMAZON', pp: 4000, pd: 5000, c: 'A' }), // 20%
			card(2, { p: 'FEMININO', l: 'AMAZON', pp: 1000, pd: 4000, c: 'B' }), // 75%
			card(3, { p: 'FEMININO', l: 'AMAZON', pp: 5000, pd: null, c: 'C' }), // sem pd
			// cada um falha num critério
			card(4, { p: 'MASCULINO', l: 'AMAZON', pp: 1000, pd: 9000, c: 'D' }),
			card(5, { p: 'FEMININO', l: 'SHOPEE', pp: 1000, pd: 9000, c: 'E' }),
			card(6, { p: 'FEMININO', l: 'AMAZON', pp: 5001, pd: 90000, c: 'F' }),
			card(7, { p: 'FEMININO', l: 'AMAZON', pp: 1000, pd: 9000 })
		]);
		const f = {
			publico: 'FEMININO',
			loja: 'AMAZON',
			faixa: 'ate50',
			soComCupom: true
		} as const;
		expect(ids(mix.lista({ ...f, ordem: 'desconto' }))).toEqual([2, 1, 3]);
		expect(ids(mix.lista({ ...f, ordem: 'preco' }))).toEqual([2, 1, 3]);
		// recentes: mesmo dt, desempate id desc.
		expect(ids(mix.lista(f))).toEqual([3, 2, 1]);
	});
});
