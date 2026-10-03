import { casaFiltro, normalizar, ordenar } from './catalogo.ts';
import type { Catalogo } from './catalogo.ts';
import type { Filtro, OfertaCard } from './tipos.ts';

export interface ResultadoBusca {
	itens: OfertaCard[];
	total: number;
	/** false enquanto nem todos os chunks chegaram. */
	completo: boolean;
}

/**
 * Busca no cliente (AD-061): todos os termos casam como prefixo de palavra no texto
 * pré-computado (título + cupom + loja). Inclui expiradas; ordem do filtro.
 */
export function buscar(
	cat: Catalogo,
	consulta: string,
	f: Filtro = {},
	limite = 200
): ResultadoBusca {
	const q = normalizar(consulta);
	if (q.length < 2) return { itens: [], total: 0, completo: cat.completo };
	const termos = [...new Set(q.split(' '))].map((t) => ' ' + t);
	const achados: OfertaCard[] = [];
	for (const { card, texto } of cat.entradas()) {
		if (termos.every((t) => texto.includes(t)) && casaFiltro(card, f)) achados.push(card);
	}
	ordenar(achados, f.ordem);
	return { itens: achados.slice(0, limite), total: achados.length, completo: cat.completo };
}
