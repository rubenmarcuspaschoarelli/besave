import { describe, expect, it } from 'vitest';
import { CHAVE_FAVORITOS, Favoritos } from './favoritos.svelte.ts';
import type { Armazem } from './favoritos.svelte.ts';

function memoria(
	inicial: Record<string, string> = {}
): Armazem & { dados: Record<string, string> } {
	const dados = { ...inicial };
	return {
		dados,
		getItem: (k) => (k in dados ? dados[k] : null),
		setItem: (k, v) => void (dados[k] = v)
	};
}

const salvos = (a: { dados: Record<string, string> }) =>
	JSON.parse(a.dados[CHAVE_FAVORITOS]) as number[];

describe('Favoritos', () => {
	it('usa a chave besave:favoritos', () => {
		expect(CHAVE_FAVORITOS).toBe('besave:favoritos');
	});

	// FAV-01
	it('adicionar guarda o id na memória e no armazenamento', () => {
		const a = memoria();
		const f = new Favoritos(a);
		f.carregar();
		f.adicionar(5412);
		expect(f.tem(5412)).toBe(true);
		expect(f.total).toBe(1);
		expect(salvos(a)).toEqual([5412]);
	});

	// FAV-02
	it('remover tira o id e atualiza o armazenamento', () => {
		const a = memoria({ [CHAVE_FAVORITOS]: '[1,2,3]' });
		const f = new Favoritos(a);
		f.carregar();
		f.remover(2);
		expect(f.tem(2)).toBe(false);
		expect(f.ids).toEqual([1, 3]);
		expect(salvos(a)).toEqual([1, 3]);
	});

	// FAV-03
	it('nova instância sobre o mesmo armazenamento restaura os ids', () => {
		const a = memoria();
		const f = new Favoritos(a);
		f.carregar();
		f.adicionar(10);
		f.adicionar(20);
		const g = new Favoritos(a);
		g.carregar();
		expect(g.tem(10) && g.tem(20)).toBe(true);
		expect(g.total).toBe(2);
	});

	it('mais recente primeiro', () => {
		const f = new Favoritos(memoria());
		f.carregar();
		f.adicionar(10);
		f.adicionar(20);
		expect(f.ids).toEqual([20, 10]);
	});

	// FAV-04
	it('remover id que não é favorito não muda nada', () => {
		const a = memoria({ [CHAVE_FAVORITOS]: '[7]' });
		const f = new Favoritos(a);
		f.carregar();
		f.remover(999);
		expect(f.ids).toEqual([7]);
		expect(salvos(a)).toEqual([7]);
	});

	// FAV-05
	it('conteúdo inválido no armazenamento começa vazio', () => {
		for (const lixo of ['{nao e json', '"texto"', '{"a":1}', 'null']) {
			const f = new Favoritos(memoria({ [CHAVE_FAVORITOS]: lixo }));
			f.carregar();
			expect(f.ids, lixo).toEqual([]);
		}
	});

	it('mantém só ids inteiros ≥ 1', () => {
		const f = new Favoritos(memoria({ [CHAVE_FAVORITOS]: '[3,"4",0,-1,2.5,null,8]' }));
		f.carregar();
		expect(f.ids).toEqual([3, 8]);
	});

	// FAV-06
	it('adicionar duas vezes guarda uma', () => {
		const a = memoria();
		const f = new Favoritos(a);
		f.carregar();
		f.adicionar(5);
		f.adicionar(5);
		expect(f.ids).toEqual([5]);
		expect(salvos(a)).toEqual([5]);
	});

	it('alternar adiciona e remove', () => {
		const f = new Favoritos(memoria());
		f.carregar();
		f.alternar(9);
		expect(f.tem(9)).toBe(true);
		f.alternar(9);
		expect(f.tem(9)).toBe(false);
	});

	// Edge case: localStorage indisponível (modo privado) → só memória.
	it('armazenamento que lança continua funcionando em memória', () => {
		const quebrado: Armazem = {
			getItem: () => {
				throw new Error('SecurityError');
			},
			setItem: () => {
				throw new Error('QuotaExceededError');
			}
		};
		const f = new Favoritos(quebrado);
		f.carregar();
		f.adicionar(1);
		expect(f.tem(1)).toBe(true);
		const sem = new Favoritos(null);
		sem.carregar();
		sem.adicionar(2);
		expect(sem.ids).toEqual([2]);
	});
});
