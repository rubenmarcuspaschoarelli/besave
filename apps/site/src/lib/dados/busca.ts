import { Selecao, casaFiltro, normalizar } from './catalogo.ts';
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
	// O termo mais longo (em geral o mais raro) guia a varredura com indexOf.
	const [guia, ...resto] = [...new Set(q.split(' '))]
		.map((t) => ' ' + t)
		.sort((a, b) => b.length - a.length);
	const achados = new Selecao();
	for (const { cards, texto, inicios, tempos } of cat.trechos()) {
		const k = inicios.length;
		let i = 0;
		let pos = texto.indexOf(guia);
		while (pos !== -1) {
			// Acertos vêm em ordem: o card avança, nunca volta.
			while (i + 1 < k && inicios[i + 1] <= pos) i++;
			const fim = i + 1 < k ? inicios[i + 1] - 1 : texto.length;
			let ok = true;
			if (resto.length > 0) {
				const seg = texto.slice(inicios[i], fim);
				for (let j = 0; ok && j < resto.length; j++) ok = seg.includes(resto[j]);
			}
			if (ok && casaFiltro(cards[i], f)) achados.incluir(cards[i], tempos[i]);
			pos = texto.indexOf(guia, fim);
		}
	}
	const itens = achados.ordenar(f.ordem);
	return { itens: itens.slice(0, limite), total: itens.length, completo: cat.completo };
}
