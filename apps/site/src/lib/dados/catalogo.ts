import { ROTULO_LOJA } from './tipos.ts';
import type { ChunkRef, Filtro, Manifest, OfertaCard, Ordem } from './tipos.ts';

/** Minúsculas, sem diacríticos; todo não alfanumérico vira um espaço. */
export function normalizar(s: string): string {
	return s
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, ' ')
		.trim();
}

/** Card + texto pesquisável (título + cupom + loja), com espaço à frente para casar prefixo de palavra. */
export interface Entrada {
	card: OfertaCard;
	texto: string;
}

function textoDe(c: OfertaCard): string {
	return ' ' + normalizar(`${c.t} ${c.c ?? ''} ${ROTULO_LOJA[c.l] ?? ''}`);
}

function porRecentes(a: OfertaCard, b: OfertaCard): number {
	if (a.dt !== b.dt) return a.dt < b.dt ? 1 : -1;
	return b.id - a.id;
}

/** pp/pd: menor = maior desconto; sem `pd` vai para o fim. */
function razao(c: OfertaCard): number {
	return c.pd ? c.pp / c.pd : Infinity;
}

const COMPARADORES: Record<Ordem, (a: OfertaCard, b: OfertaCard) => number> = {
	recentes: porRecentes,
	desconto: (a, b) => razao(a) - razao(b) || porRecentes(a, b),
	preco: (a, b) => a.pp - b.pp || porRecentes(a, b)
};

export function ordenar(cards: OfertaCard[], ordem: Ordem = 'recentes'): OfertaCard[] {
	return cards.sort(COMPARADORES[ordem]);
}

export function casaFiltro(c: OfertaCard, f: Filtro): boolean {
	return (
		(f.area === undefined || c.a === f.area) &&
		(f.publico === undefined || c.p === f.publico) &&
		(f.loja === undefined || c.l === f.loja)
	);
}

export class Catalogo {
	#porId = new Map<number, Entrada>();
	#porN = new Map<number, { arquivo: string; ids: number[] }>();
	#alvo: Map<number, string> | null = null;
	/** Ids exibidos; fixada no primeiro `completo` (regra 8). */
	#base: Set<number> | null = null;
	#pendentes = new Set<number>();

	/** Define os chunks esperados (manifest atual). */
	alvo(m: Manifest): void {
		this.#alvo = new Map(m.chunks.map((c) => [c.n, c.arquivo]));
		this.#fixarBase();
	}

	aplicarChunk(ref: ChunkRef, cards: OfertaCard[]): void {
		const ids = cards.map((c) => c.id);
		const antigo = this.#porN.get(ref.n);
		if (antigo) {
			const ficam = new Set(ids);
			for (const id of antigo.ids) if (!ficam.has(id)) this.#remover(id);
		}
		for (const card of cards) {
			const e = this.#porId.get(card.id);
			const mesmoTexto = e && e.card.t === card.t && e.card.c === card.c && e.card.l === card.l;
			this.#porId.set(card.id, { card, texto: mesmoTexto ? e.texto : textoDe(card) });
			if (this.#base && !this.#base.has(card.id)) {
				if (card.x) {
					this.#base.add(card.id);
					this.#pendentes.delete(card.id);
				} else this.#pendentes.add(card.id);
			}
		}
		this.#porN.set(ref.n, { arquivo: ref.arquivo, ids });
		this.#fixarBase();
	}

	descartar(n: number): void {
		const antigo = this.#porN.get(n);
		if (!antigo) return;
		for (const id of antigo.ids) this.#remover(id);
		this.#porN.delete(n);
	}

	/** `arquivo` carregado por `n`. */
	arquivos(): Map<number, string> {
		return new Map([...this.#porN].map(([n, v]) => [n, v.arquivo]));
	}

	entradas(): IterableIterator<Entrada> {
		return this.#porId.values();
	}

	lista(f: Filtro = {}): OfertaCard[] {
		const r: OfertaCard[] = [];
		for (const { card } of this.#porId.values()) {
			if (this.#pendentes.has(card.id)) continue;
			if (card.x && !f.mostrarExpiradas) continue;
			if (casaFiltro(card, f)) r.push(card);
		}
		return ordenar(r, f.ordem);
	}

	novas(): number {
		return this.#pendentes.size;
	}

	confirmarNovas(): void {
		for (const id of this.#pendentes) this.#base?.add(id);
		this.#pendentes.clear();
	}

	get total(): number {
		return this.#alvo?.size ?? 0;
	}

	get carregados(): number {
		let k = 0;
		for (const [n, arquivo] of this.#alvo ?? []) if (this.#porN.get(n)?.arquivo === arquivo) k++;
		return k;
	}

	get completo(): boolean {
		return this.#alvo !== null && this.carregados === this.total;
	}

	#remover(id: number): void {
		this.#porId.delete(id);
		this.#pendentes.delete(id);
		this.#base?.delete(id);
	}

	#fixarBase(): void {
		if (!this.#base && this.completo) this.#base = new Set(this.#porId.keys());
	}
}
