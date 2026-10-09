import { ROTULO_LOJA } from './tipos.ts';
import type { ChunkRef, Faixa, Filtro, Manifest, OfertaCard, Ordem } from './tipos.ts';

/** Minúsculas, sem diacríticos; todo não alfanumérico vira um espaço. */
export function normalizar(s: string): string {
	const min = s.toLowerCase();
	// NFD só quando há não-ASCII: metade dos títulos não tem acento e o NFD domina o custo.
	const base = /[\u0080-\uffff]/.test(min)
		? min.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
		: min;
	return base.replace(/[^a-z0-9]+/g, ' ').trim();
}

/**
 * Chunk carregado. `texto` junta os textos pesquisáveis dos cards (título + cupom + loja,
 * normalizados, cada um com um espaço à frente) separados por quebra de linha;
 * `inicios[i]` é onde começa o do card `i`. Pré-computado ao aplicar o chunk, nunca por consulta.
 */
export interface Trecho {
	arquivo: string;
	cards: OfertaCard[];
	segmentos: string[];
	texto: string;
	inicios: Int32Array;
	/** `dp` em ms (sem `dp`, `dt`), para ordenar sem comparar strings. */
	tempos: Float64Array;
}

function textoDe(c: OfertaCard): string {
	return ' ' + normalizar(`${c.t} ${c.c ?? ''} ${ROTULO_LOJA[c.l] ?? ''}`);
}

/** pp/pd: menor = maior desconto; sem `pd` vai para o fim. */
function razao(c: OfertaCard): number {
	return c.pd ? c.pp / c.pd : Infinity;
}

/** Cards selecionados com o `dp` (ou `dt`) numérico de cada um. */
export class Selecao {
	cards: OfertaCard[] = [];
	tempos: number[] = [];

	incluir(c: OfertaCard, tempo: number): void {
		this.cards.push(c);
		this.tempos.push(tempo);
	}

	/** recentes: dp desc, id desc; desconto e preço desempatam por recentes. */
	ordenar(ordem: Ordem = 'recentes'): OfertaCard[] {
		const { cards, tempos } = this;
		const n = cards.length;
		let chave: Float64Array | null = null;
		if (ordem !== 'recentes') {
			chave = new Float64Array(n);
			for (let i = 0; i < n; i++) chave[i] = ordem === 'preco' ? cards[i].pp : razao(cards[i]);
		}
		const idx = new Uint32Array(n);
		for (let i = 0; i < n; i++) idx[i] = i;
		// Infinity - Infinity = NaN (falso): empate segue para o próximo critério.
		idx.sort(
			(a, b) =>
				(chave ? chave[a] - chave[b] : 0) || tempos[b] - tempos[a] || cards[b].id - cards[a].id
		);
		return Array.from(idx, (i) => cards[i]);
	}
}

const DIA_MS = 86_400_000;

/** Desconto inteiro do contrato (CONTRATO §3), meia para cima como no worker; `null` sem `pd`. */
export function descontoPct(c: OfertaCard): number | null {
	if (!c.pd || c.pd <= c.pp) return null;
	return Math.min(99, Math.floor((200 * (c.pd - c.pp) + c.pd) / (2 * c.pd)));
}

/**
 * "Maiores descontos de hoje": cards da lista padrão (ativos, sem pendentes do toast) com `dp`
 * (ou `dt`) nas últimas 24 h que casam com `f`, por desconto desc, desempate `dp` desc e `id` desc.
 * `agora` em ms.
 */
export function maioresDescontos(
	cat: Catalogo,
	agora: number,
	n: number,
	f: Filtro = {}
): OfertaCard[] {
	const desde = agora - DIA_MS;
	const r: { c: OfertaCard; pct: number }[] = [];
	// `lista()` vem em recentes (dp desc, id desc): para no primeiro fora da janela.
	for (const c of cat.lista(f)) {
		if (Date.parse(c.dp ?? c.dt) < desde) break;
		const pct = descontoPct(c);
		if (pct !== null) r.push({ c, pct });
	}
	// Sort estável: empate de desconto mantém dp desc, id desc.
	r.sort((a, b) => b.pct - a.pct);
	return r.slice(0, n).map((x) => x.c);
}

/** `[min, max]` de `pp` em centavos, inclusivos (BSV-31). */
const FAIXA: Record<Faixa, [number, number]> = {
	ate50: [0, 5000],
	'50a100': [5001, 10000],
	'100a200': [10001, 20000],
	acima200: [20001, Infinity]
};

export function casaFiltro(c: OfertaCard, f: Filtro): boolean {
	return (
		(f.area === undefined || c.a === f.area) &&
		(f.publico === undefined || c.p === f.publico) &&
		(f.loja === undefined || c.l === f.loja) &&
		(f.faixa === undefined || (c.pp >= FAIXA[f.faixa][0] && c.pp <= FAIXA[f.faixa][1])) &&
		(!f.soComCupom || !!c.c)
	);
}

export class Catalogo {
	#porN = new Map<number, Trecho>();
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
		const antigo = this.#porN.get(ref.n);
		const anterior = new Map<number, number>();
		antigo?.cards.forEach((c, i) => anterior.set(c.id, i));
		const segmentos = new Array<string>(cards.length);
		const inicios = new Int32Array(cards.length);
		const tempos = new Float64Array(cards.length);
		let pos = 0;
		for (let i = 0; i < cards.length; i++) {
			const card = cards[i];
			const j = anterior.get(card.id);
			const v = j === undefined ? undefined : antigo?.cards[j];
			segmentos[i] =
				v && j !== undefined && v.t === card.t && v.c === card.c && v.l === card.l
					? (antigo?.segmentos[j] ?? textoDe(card))
					: textoDe(card);
			anterior.delete(card.id);
			inicios[i] = pos;
			tempos[i] = Date.parse(card.dp ?? card.dt);
			pos += segmentos[i].length + 1;
			if (this.#base && !this.#base.has(card.id)) {
				if (card.x) {
					this.#base.add(card.id);
					this.#pendentes.delete(card.id);
				} else this.#pendentes.add(card.id);
			}
		}
		// Ids que saíram do chunk.
		for (const id of anterior.keys()) this.#remover(id);
		this.#porN.set(ref.n, {
			arquivo: ref.arquivo,
			cards,
			segmentos,
			texto: segmentos.join('\n'),
			inicios,
			tempos
		});
		this.#fixarBase();
	}

	descartar(n: number): void {
		const antigo = this.#porN.get(n);
		if (!antigo) return;
		for (const c of antigo.cards) this.#remover(c.id);
		this.#porN.delete(n);
	}

	/** `arquivo` carregado por `n`. */
	arquivos(): Map<number, string> {
		return new Map([...this.#porN].map(([n, v]) => [n, v.arquivo]));
	}

	trechos(): IterableIterator<Trecho> {
		return this.#porN.values();
	}

	lista(f: Filtro = {}): OfertaCard[] {
		const r = new Selecao();
		const pendentes = this.#pendentes.size > 0 ? this.#pendentes : null;
		for (const { cards, tempos } of this.#porN.values()) {
			for (let i = 0; i < cards.length; i++) {
				const card = cards[i];
				if (card.x && !f.mostrarExpiradas) continue;
				if (pendentes?.has(card.id)) continue;
				if (casaFiltro(card, f)) r.incluir(card, tempos[i]);
			}
		}
		return r.ordenar(f.ordem);
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
		this.#pendentes.delete(id);
		this.#base?.delete(id);
	}

	#fixarBase(): void {
		if (this.#base || !this.completo) return;
		this.#base = new Set();
		for (const { cards } of this.#porN.values()) for (const c of cards) this.#base.add(c.id);
	}
}
