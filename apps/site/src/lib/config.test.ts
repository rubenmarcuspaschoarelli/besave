import { describe, expect, it } from 'vitest';
import { CONFIG, botoesLigados, comLink } from './config.ts';
import type { Config } from './config.ts';

const com = (m: Partial<Config>): Config => ({ ...CONFIG, ...m });

describe('config', () => {
	// CFG-03
	it('padrão: canal do Telegram, nenhum link de rede/app, flags desligadas', () => {
		expect(CONFIG.canal).toBe('https://t.me/besaveofertas');
		expect(Object.values(CONFIG.redes).every((v) => v === null)).toBe(true);
		expect(Object.keys(CONFIG.redes).sort()).toEqual([
			'discord',
			'facebook',
			'instagram',
			'x',
			'youtube'
		]);
		expect(CONFIG.apps).toEqual({ android: null, ios: null });
		expect(CONFIG.flags).toEqual({
			postar: false,
			notificacoes: false,
			entrar: false,
			social: false
		});
	});

	// CFG-01
	it('esconde redes e apps sem link', () => {
		expect(comLink(CONFIG.redes)).toEqual([]);
		expect(comLink(CONFIG.apps)).toEqual([]);
		const c = com({
			redes: { ...CONFIG.redes, instagram: 'https://instagram.com/besave' },
			apps: { android: null, ios: 'https://apps.apple.com/app/besave' }
		});
		expect(comLink(c.redes)).toEqual([{ chave: 'instagram', url: 'https://instagram.com/besave' }]);
		expect(comLink(c.apps)).toEqual([{ chave: 'ios', url: 'https://apps.apple.com/app/besave' }]);
	});

	it('link vazio conta como sem link', () => {
		expect(comLink({ x: '', youtube: '  ' })).toEqual([]);
	});

	// CFG-02
	it('esconde botões de flag desligada', () => {
		expect(botoesLigados(CONFIG.flags)).toEqual([]);
		expect(botoesLigados({ ...CONFIG.flags, entrar: true, postar: true })).toEqual([
			'postar',
			'entrar'
		]);
	});
});
