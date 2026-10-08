import { describe, expect, it } from 'vitest';
import { AREAS_MENU, haQuanto, reais, SLUG_AREA } from './formato.ts';

const H = 3_600_000;
const AGORA = Date.parse('2026-10-08T12:00:00Z');
const antes = (ms: number) => new Date(AGORA - ms).toISOString();

describe('haQuanto', () => {
	// TEM-01
	it('menos de 24 h: horas inteiras (floor)', () => {
		expect(haQuanto({ dp: antes(1 * H), dt: antes(100 * H) }, AGORA)).toBe('há 1 h');
		expect(haQuanto({ dp: antes(2.9 * H), dt: antes(100 * H) }, AGORA)).toBe('há 2 h');
		expect(haQuanto({ dp: antes(24 * H - 1000), dt: antes(100 * H) }, AGORA)).toBe('há 23 h');
	});

	it('menos de 1 h: minutos, nunca zero nem negativo', () => {
		expect(haQuanto({ dp: antes(5 * 60_000), dt: antes(H) }, AGORA)).toBe('há 5 min');
		expect(haQuanto({ dp: antes(10_000), dt: antes(H) }, AGORA)).toBe('há 1 min');
		expect(haQuanto({ dp: antes(-H), dt: antes(H) }, AGORA)).toBe('há 1 min');
	});

	// TEM-02
	it('de 24 h a 7 dias: dias', () => {
		expect(haQuanto({ dp: antes(24 * H), dt: antes(H) }, AGORA)).toBe('há 1 d');
		expect(haQuanto({ dp: antes(7 * 24 * H - 1000), dt: antes(H) }, AGORA)).toBe('há 6 d');
	});

	// TEM-03: data em Brasília (UTC−3 fixo, AD-032), não em UTC.
	it('7 dias ou mais: data de Brasília', () => {
		expect(haQuanto({ dp: '2026-10-01T02:00:00Z', dt: antes(H) }, AGORA)).toBe('em 30/09');
		expect(haQuanto({ dp: '2026-09-15T03:00:00Z', dt: antes(H) }, AGORA)).toBe('em 15/09');
		expect(haQuanto({ dp: antes(7 * 24 * H), dt: antes(H) }, AGORA)).toBe('em 01/10');
	});

	// TEM-04
	it('sem dp usa dt', () => {
		expect(haQuanto({ dt: antes(3 * H) }, AGORA)).toBe('há 3 h');
	});
});

describe('reais', () => {
	it('centavos em BRL', () => {
		expect(reais(19990).replace(/\s/g, ' ')).toBe('R$ 199,90');
		expect(reais(129990).replace(/\s/g, ' ')).toBe('R$ 1.299,90');
	});
});

describe('áreas', () => {
	it('menu com as 9 áreas na ordem aprovada; Outros fica de fora', () => {
		expect(AREAS_MENU.map((a) => a.rotulo)).toEqual([
			'Elas',
			'Meu Lar',
			'Tech',
			'Esporte & vida',
			'Família & filhos',
			'Pets',
			'Players',
			'Cultura',
			'Eles'
		]);
	});

	it('slugs do CONTRATO §2.3', () => {
		expect(SLUG_AREA).toEqual({
			TECH: 'tech',
			PLAYERS: 'players',
			MEU_LAR: 'meu-lar',
			ELAS: 'elas',
			ELES: 'eles',
			CULTURA: 'cultura',
			FAMILIA: 'familia',
			PETS: 'pets',
			ESPORTE_VIDA: 'esporte-vida',
			OUTROS: 'outros'
		});
	});
});
