import { describe, expect, it } from 'vitest';
import { destinoBusca, escreverBusca, lerBusca } from './busca.ts';
import { PADRAO } from './filtros.ts';

const ler = (q: string) => lerBusca(new URLSearchParams(q));

describe('lerBusca', () => {
	it('BUS-10: q, área e filtros juntos', () => {
		expect(ler('q=protetor+solar&area=elas&loja=shopee&ordem=desconto&cupom=1')).toEqual({
			q: 'protetor solar',
			area: 'ELAS',
			filtros: { ordem: 'desconto', loja: 'SHOPEE', soComCupom: true }
		});
	});

	it('BUS-10: sem parâmetros = q vazio, sem área, filtros no padrão', () => {
		expect(ler('')).toEqual({ q: '', filtros: PADRAO });
	});

	it('BUS-02: slug com hífen vira a área do enum', () => {
		expect(ler('q=x&area=esporte-vida').area).toBe('ESPORTE_VIDA');
		expect(ler('q=x&area=meu-lar').area).toBe('MEU_LAR');
	});

	it('borda: área inválida é ignorada', () => {
		for (const a of ['xyz', 'ELAS', 'meu_lar', ''])
			expect(ler(`q=x&area=${a}`).area, a).toBe(undefined);
	});
});

describe('escreverBusca', () => {
	it('BUS-03: q e área primeiro, depois os filtros no formato da BSV-31', () => {
		const url = escreverBusca(new URL('https://besave.com.br/busca/'), {
			q: 'protetor',
			area: 'ESPORTE_VIDA',
			filtros: { ordem: 'preco', loja: 'MERCADO_LIVRE', soComCupom: false }
		});
		expect(url).toBe('/busca/?q=protetor&area=esporte-vida&ordem=preco&loja=mercado-livre');
	});

	it('BUS-03: mudar filtro mantém q e área; padrão sai da URL', () => {
		const antes = new URL('https://besave.com.br/busca/?q=protetor&area=elas&loja=shopee');
		const e = lerBusca(antes.searchParams);
		expect(escreverBusca(antes, { ...e, filtros: { ...e.filtros, loja: undefined } })).toBe(
			'/busca/?q=protetor&area=elas'
		);
		expect(escreverBusca(antes, { ...e, filtros: { ...e.filtros, soComCupom: true } })).toBe(
			'/busca/?q=protetor&area=elas&loja=shopee&cupom=1'
		);
	});

	it('BUS-02: tirar a área tira só `area`', () => {
		const antes = new URL('https://besave.com.br/busca/?q=protetor&area=elas&loja=shopee');
		const e = lerBusca(antes.searchParams);
		expect(escreverBusca(antes, { ...e, area: undefined })).toBe('/busca/?q=protetor&loja=shopee');
	});

	it('q vazio sai da URL; acentos e espaços são codificados', () => {
		const base = new URL('https://besave.com.br/busca/?q=a');
		expect(escreverBusca(base, { q: '', filtros: PADRAO })).toBe('/busca/');
		expect(escreverBusca(base, { q: 'sérum facial', filtros: PADRAO })).toBe(
			'/busca/?q=s%C3%A9rum+facial'
		);
	});

	it('BUS-10: escrever e ler devolve o mesmo estado', () => {
		const e = {
			q: 'kit 3 em 1',
			area: 'PETS' as const,
			filtros: {
				ordem: 'desconto' as const,
				publico: 'INFANTIL' as const,
				faixa: '50a100' as const,
				soComCupom: true
			}
		};
		const url = new URL(escreverBusca(new URL('https://besave.com.br/busca/'), e), 'https://x');
		expect(lerBusca(url.searchParams)).toEqual(e);
	});
});

describe('destinoBusca', () => {
	it('TOP-01: home leva só q', () => {
		expect(destinoBusca('protetor')).toBe('/busca/?q=protetor');
	});

	it('TOP-02: área leva &area={slug}', () => {
		expect(destinoBusca('protetor', 'ELAS')).toBe('/busca/?q=protetor&area=elas');
		expect(destinoBusca('bola', 'ESPORTE_VIDA')).toBe('/busca/?q=bola&area=esporte-vida');
	});

	it('TOP-04: Enter com campo vazio vai para /busca/', () => {
		expect(destinoBusca('')).toBe('/busca/');
	});
});
