import { describe, expect, it } from 'vitest';
import {
	PADRAO,
	destinoArea,
	escreverFiltros,
	foraDoPadrao,
	lerFiltros,
	temFiltro,
	valorEscolhido
} from './filtros.ts';
import type { EstadoFiltros } from './filtros.ts';

const ler = (q: string) => lerFiltros(new URLSearchParams(q));
const escrever = (href: string, e: Partial<EstadoFiltros>) =>
	escreverFiltros(new URL(href), { ...PADRAO, ...e });

describe('lerFiltros', () => {
	it('URL-01: URL sem parâmetros = padrão', () => {
		expect(ler('')).toEqual({ ordem: 'recentes', soComCupom: false });
	});

	it('URL-01: exemplo da spec', () => {
		expect(ler('ordem=desconto&publico=feminino&loja=amazon&preco=ate50&cupom=1')).toEqual({
			ordem: 'desconto',
			publico: 'FEMININO',
			loja: 'AMAZON',
			faixa: 'ate50',
			soComCupom: true
		});
	});

	it('URL-01: todos os valores válidos', () => {
		expect(ler('ordem=preco').ordem).toBe('preco');
		expect(ler('ordem=recentes').ordem).toBe('recentes');
		expect(ler('publico=masculino').publico).toBe('MASCULINO');
		expect(ler('publico=unissex').publico).toBe('UNISSEX');
		expect(ler('publico=infantil').publico).toBe('INFANTIL');
		expect(ler('loja=shopee').loja).toBe('SHOPEE');
		expect(ler('loja=mercado-livre').loja).toBe('MERCADO_LIVRE');
		expect(ler('preco=50a100').faixa).toBe('50a100');
		expect(ler('preco=100a200').faixa).toBe('100a200');
		expect(ler('preco=acima200').faixa).toBe('acima200');
	});

	it('URL-02: inválido é ignorado sem afetar os outros', () => {
		expect(ler('loja=xyz&publico=feminino')).toEqual({
			ordem: 'recentes',
			publico: 'FEMININO',
			soComCupom: false
		});
		expect(ler('ordem=DESCONTO&preco=ate50')).toEqual({
			ordem: 'recentes',
			faixa: 'ate50',
			soComCupom: false
		});
		expect(ler('publico=FEMININO').publico).toBeUndefined();
		expect(ler('loja=AMAZON').loja).toBeUndefined();
		expect(ler('loja=mercado_livre').loja).toBeUndefined();
		expect(ler('preco=ate60').faixa).toBeUndefined();
		expect(ler('cupom=0').soComCupom).toBe(false);
		expect(ler('cupom=true').soComCupom).toBe(false);
		expect(ler('ordem=').ordem).toBe('recentes');
	});

	it('URL-02: parâmetro repetido vale o primeiro', () => {
		expect(ler('loja=amazon&loja=shopee').loja).toBe('AMAZON');
	});
});

describe('escreverFiltros', () => {
	it('URL-03: padrão fica fora da URL e sem "?"', () => {
		expect(escrever('https://besave.com.br/elas/', {})).toBe('/elas/');
		expect(escrever('https://besave.com.br/elas/?ordem=desconto&loja=amazon', {})).toBe('/elas/');
	});

	it('URL-03: valores em minúsculas, na ordem da spec', () => {
		expect(
			escrever('https://besave.com.br/', {
				ordem: 'desconto',
				publico: 'FEMININO',
				loja: 'AMAZON',
				faixa: 'ate50',
				soComCupom: true
			})
		).toBe('/?ordem=desconto&publico=feminino&loja=amazon&preco=ate50&cupom=1');
		expect(escrever('https://besave.com.br/', { loja: 'MERCADO_LIVRE', ordem: 'preco' })).toBe(
			'/?ordem=preco&loja=mercado-livre'
		);
	});

	it('URL-03: preserva q e utm_*', () => {
		expect(
			escrever('https://besave.com.br/?q=serum&utm_source=telegram&loja=amazon', {
				loja: 'SHOPEE'
			})
		).toBe('/?q=serum&utm_source=telegram&loja=shopee');
		expect(escrever('https://besave.com.br/?q=serum&cupom=1', {})).toBe('/?q=serum');
	});

	it('URL-01/03: ida e volta', () => {
		const e: EstadoFiltros = {
			ordem: 'preco',
			publico: 'INFANTIL',
			loja: 'MERCADO_LIVRE',
			faixa: 'acima200',
			soComCupom: true
		};
		const href = escreverFiltros(new URL('https://besave.com.br/tech/'), e);
		expect(lerFiltros(new URL(href, 'https://besave.com.br').searchParams)).toEqual(e);
	});
});

describe('foraDoPadrao', () => {
	it('BAR-04: falso só no padrão', () => {
		expect(foraDoPadrao(PADRAO)).toBe(false);
		expect(foraDoPadrao({ ...PADRAO, ordem: 'desconto' })).toBe(true);
		expect(foraDoPadrao({ ...PADRAO, publico: 'FEMININO' })).toBe(true);
		expect(foraDoPadrao({ ...PADRAO, loja: 'SHOPEE' })).toBe(true);
		expect(foraDoPadrao({ ...PADRAO, faixa: 'ate50' })).toBe(true);
		expect(foraDoPadrao({ ...PADRAO, soComCupom: true })).toBe(true);
	});
});

describe('temFiltro', () => {
	it('BAR-08: ordem sozinha não é filtro', () => {
		expect(temFiltro(PADRAO)).toBe(false);
		expect(temFiltro({ ...PADRAO, ordem: 'preco' })).toBe(false);
		expect(temFiltro({ ...PADRAO, publico: 'INFANTIL' })).toBe(true);
		expect(temFiltro({ ...PADRAO, loja: 'AMAZON' })).toBe(true);
		expect(temFiltro({ ...PADRAO, faixa: 'acima200' })).toBe(true);
		expect(temFiltro({ ...PADRAO, soComCupom: true })).toBe(true);
	});
});

describe('destinoArea (BSV-33)', () => {
	const destino = (href: string, e: Partial<EstadoFiltros>) =>
		destinoArea(new URL(href), 'ELAS', { ...PADRAO, ...e });

	it('PUB-01: público vira caminho e os demais filtros ficam na query', () => {
		expect(destino('https://x/elas/?loja=amazon', { publico: 'MASCULINO', loja: 'AMAZON' })).toBe(
			'/elas/masculino/?loja=amazon'
		);
		expect(
			destino('https://x/elas/feminino/?loja=amazon&cupom=1', {
				publico: 'INFANTIL',
				loja: 'AMAZON',
				soComCupom: true
			})
		).toBe('/elas/infantil/?loja=amazon&cupom=1');
	});

	it('PUB-02: "Todos" volta a /{slug}/ com os demais filtros', () => {
		expect(destino('https://x/elas/masculino/?loja=amazon', { loja: 'AMAZON' })).toBe(
			'/elas/?loja=amazon'
		);
	});

	it('PUB-02: "Limpar filtros" volta a /{slug}/ sem filtros na query', () => {
		expect(destino('https://x/elas/masculino/?loja=amazon&ordem=preco', {})).toBe('/elas/');
	});

	it('PUB-03: ?publico= sai da query e vai para o caminho; outros parâmetros ficam', () => {
		expect(
			destino('https://x/elas/?publico=infantil&utm_source=telegram', { publico: 'INFANTIL' })
		).toBe('/elas/infantil/?utm_source=telegram');
	});
});

// CMP-04 (BSV-37): o item da linha compacta mostra `Nome: Valor`; sem escolha, só o nome.
describe('valorEscolhido', () => {
	const e: EstadoFiltros = {
		ordem: 'preco',
		publico: 'FEMININO',
		loja: 'MERCADO_LIVRE',
		faixa: 'ate50',
		soComCupom: false
	};
	it('rótulo do valor de cada grupo', () => {
		expect(valorEscolhido(e, 'ordem')).toBe('Menor preço');
		expect(valorEscolhido(e, 'publico')).toBe('Feminino');
		expect(valorEscolhido(e, 'loja')).toBe('Mercado Livre');
		expect(valorEscolhido(e, 'faixa')).toBe('Até R$ 50');
		expect(valorEscolhido({ ...e, faixa: 'acima200' }, 'faixa')).toBe('Acima de R$ 200');
	});
	it('sem escolha: undefined; ordem padrão: "Recentes"', () => {
		for (const g of ['publico', 'loja', 'faixa'] as const)
			expect(valorEscolhido(PADRAO, g)).toBeUndefined();
		expect(valorEscolhido(PADRAO, 'ordem')).toBe('Recentes');
	});
});
