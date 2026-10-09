import { describe, expect, it } from 'vitest';
import { AREAS, PUBLICOS } from '../dados.ts';
import { TEXTO_AREA, TEXTO_SUBPAGINA, textoDaPagina } from './areas.ts';

/** Frases = trechos terminados em `.`, `!` ou `?`. */
const frases = (t: string) => t.split(/(?<=[.!?])\s+/).filter((f) => f.trim() !== '');

/** Subpáginas com volume em 08/10/2026 (≥ 20 ativas e ≤ 90% da área). */
const COM_VOLUME = [
	'ELAS/UNISSEX',
	'MEU_LAR/FEMININO',
	'ESPORTE_VIDA/UNISSEX',
	'ESPORTE_VIDA/FEMININO',
	'ESPORTE_VIDA/MASCULINO',
	'FAMILIA/INFANTIL',
	'FAMILIA/UNISSEX'
];

describe('textos das áreas (BSV-33)', () => {
	it('TXT-01: cada uma das 10 áreas tem 2 a 3 frases', () => {
		expect(Object.keys(TEXTO_AREA).sort()).toEqual([...AREAS].sort());
		for (const a of AREAS) {
			const n = frases(TEXTO_AREA[a]).length;
			expect(n, a).toBeGreaterThanOrEqual(2);
			expect(n, a).toBeLessThanOrEqual(3);
		}
	});

	it('TXT-01: uma frase para cada subpágina com volume, e só para elas', () => {
		expect(Object.keys(TEXTO_SUBPAGINA).sort()).toEqual([...COM_VOLUME].sort());
		for (const k of COM_VOLUME)
			expect(frases(TEXTO_SUBPAGINA[k as keyof typeof TEXTO_SUBPAGINA] ?? ''), k).toHaveLength(1);
	});

	it('TXT-01: sem promessa de preço', () => {
		const todos = [...Object.values(TEXTO_AREA), ...Object.values(TEXTO_SUBPAGINA)].join(' ');
		expect(todos).not.toMatch(/menor preço|mais barat|garanti|melhor preço|imperdív/i);
	});

	it('subpágina com frase própria mostra a frase e o texto da área; sem frase, só a área', () => {
		expect(textoDaPagina('ELAS', 'UNISSEX')).toEqual([
			TEXTO_SUBPAGINA['ELAS/UNISSEX'],
			TEXTO_AREA.ELAS
		]);
		expect(textoDaPagina('ELAS', 'MASCULINO')).toEqual([TEXTO_AREA.ELAS]);
		expect(textoDaPagina('PETS')).toEqual([TEXTO_AREA.PETS]);
		for (const a of AREAS)
			for (const p of PUBLICOS) expect(textoDaPagina(a, p).at(-1)).toBe(TEXTO_AREA[a]);
	});
});
