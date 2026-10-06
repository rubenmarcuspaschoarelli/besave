// Construtores de dados para os testes.
import type { ChunkRef, Manifest, OfertaCard } from './tipos.ts';

export function card(id: number, o: Partial<OfertaCard> = {}): OfertaCard {
	return {
		id,
		l: 'AMAZON',
		t: `Oferta ${id}`,
		pd: null,
		pp: 1000,
		dt: '2026-09-20T10:00:00Z',
		a: 'ELAS',
		p: 'FEMININO',
		...o
	};
}

export function ref(n: number, tag = 'a'): ChunkRef {
	return {
		n,
		arquivo: `data/chunks/${n}-${tag.repeat(16).slice(0, 16)}.json.br`,
		ids: [Math.max(1, n * 1000), n * 1000 + 999],
		qtd: 1,
		bytes: 1
	};
}

export function manifest(chunks: ChunkRef[], versao = 20261001000000): Manifest {
	return {
		contrato: '1.3.3',
		versao,
		gerado_em: '2026-10-01T00:00:00Z',
		total_ofertas: 0,
		chunks,
		busca: null,
		areas: {}
	};
}
