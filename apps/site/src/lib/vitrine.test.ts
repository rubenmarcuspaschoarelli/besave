// BSV-32: contagem de novas (total e por área), confirmar e título da aba.
import { describe, expect, it } from 'vitest';
import { card, manifest, ref } from './dados/apoio-teste.ts';
import { Vitrine, tituloComNovas } from './vitrine.svelte.ts';

const dp = (min: number) => new Date(Date.UTC(2026, 9, 8, 12, min)).toISOString();

/** Vitrine com 3 ofertas exibidas (ELAS) e um segundo ciclo com 3 ids novos, 1 expirado. */
function comNovas() {
	const v = new Vitrine();
	const base = [1, 2, 3].map((id) => card(id, { dp: dp(id) }));
	v.cat.alvo(manifest([ref(0, 'a')]));
	v.cat.aplicarChunk(ref(0, 'a'), base);
	const novos = [
		card(10, { dp: dp(10), a: 'MEU_LAR' }),
		card(11, { dp: dp(11), a: 'MEU_LAR' }),
		card(12, { dp: dp(12), a: 'ELAS', x: 1 })
	];
	v.cat.aplicarChunk(ref(0, 'b'), [...base, ...novos]);
	v.recontarNovas();
	return v;
}

describe('Vitrine: novas', () => {
	// NOV-01
	it('conta só ativas pendentes; expirada não conta', () => {
		const v = comNovas();
		expect(v.novasEm(null)).toBe(2);
		expect(v.novasTotal).toBe(v.cat.novas());
	});

	// NOV-02
	it('por área conta só as da área', () => {
		const v = comNovas();
		expect(v.novasEm('MEU_LAR')).toBe(2);
		expect(v.novasEm('ELAS')).toBe(0);
	});

	// NOV-03
	it('confirmar zera e põe os ids no início da lista', () => {
		const v = comNovas();
		expect(v.cat.lista().map((c) => c.id)).toEqual([3, 2, 1]);
		const antes = v.versao;
		v.confirmarNovas();
		expect(v.novasEm(null)).toBe(0);
		expect(v.novasEm('MEU_LAR')).toBe(0);
		expect(v.cat.lista().map((c) => c.id)).toEqual([11, 10, 3, 2, 1]);
		expect(v.versao).toBeGreaterThan(antes);
	});

	// NOV-04
	it('sem pendentes a contagem é 0', () => {
		const v = new Vitrine();
		v.recontarNovas();
		expect(v.novasEm(null)).toBe(0);
	});
});

describe('tituloComNovas', () => {
	// NOV-05
	it('prefixa "(N) " e volta ao normal com 0', () => {
		expect(tituloComNovas('Besave', 2)).toBe('(2) Besave');
		expect(tituloComNovas('(2) Besave', 0)).toBe('Besave');
		expect(tituloComNovas('(2) Besave', 3)).toBe('(3) Besave');
	});
});
