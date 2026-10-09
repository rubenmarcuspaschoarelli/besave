// Espelho de packages/contract/schema (CONTRATO §2, §3; MANIFEST §2).

export const LOJAS = ['AMAZON', 'SHOPEE', 'MERCADO_LIVRE'] as const;
export const PUBLICOS = ['FEMININO', 'MASCULINO', 'UNISSEX', 'INFANTIL'] as const;
export const AREAS = [
	'TECH',
	'PLAYERS',
	'MEU_LAR',
	'ELAS',
	'ELES',
	'CULTURA',
	'FAMILIA',
	'PETS',
	'ESPORTE_VIDA',
	'OUTROS'
] as const;

export type Loja = (typeof LOJAS)[number];
export type Publico = (typeof PUBLICOS)[number];
export type Area = (typeof AREAS)[number];

/** Rótulo de exibição da loja; entra no texto pesquisável. */
export const ROTULO_LOJA: Record<Loja, string> = {
	AMAZON: 'Amazon',
	SHOPEE: 'Shopee',
	MERCADO_LIVRE: 'Mercado Livre'
};

export interface OfertaCard {
	id: number;
	l: Loja;
	t: string;
	/** Centavos; `null` ou ausente quando não há preço "de". */
	pd?: number | null;
	pp: number;
	c?: string;
	/** ISO 8601 UTC. */
	dt: string;
	/** Publicação no site, ISO 8601 UTC (contrato 1.5.0); ausente só em chunk antigo em cache. */
	dp?: string;
	a: Area;
	p: Publico;
	/** Expirada quando presente. */
	x?: 1;
}

export interface ChunkRef {
	n: number;
	arquivo: string;
	ids: [number, number];
	qtd: number;
	bytes: number;
}

export interface Manifest {
	contrato: string;
	versao: number;
	gerado_em: string;
	total_ofertas: number;
	chunks: ChunkRef[];
	busca: null | { arquivo: string; bytes: number };
	areas: Partial<Record<Area, number>>;
}

export type Ordem = 'recentes' | 'desconto' | 'preco';

/** Faixas de `pp` em centavos: ≤ 5000; 5001–10000; 10001–20000; > 20000. */
export const FAIXAS = ['ate50', '50a100', '100a200', 'acima200'] as const;
export type Faixa = (typeof FAIXAS)[number];

export interface Filtro {
	area?: Area;
	publico?: Publico;
	loja?: Loja;
	/** Padrão false. */
	mostrarExpiradas?: boolean;
	/** Padrão 'recentes'. */
	ordem?: Ordem;
	faixa?: Faixa;
	/** Só cards com `c`; padrão false. */
	soComCupom?: boolean;
}

const SEMVER = /^\d+\.\d+\.\d+$/;

/** Validação mínima do manifest recebido; o worker já valida o resto. */
export function ehManifest(v: unknown): v is Manifest {
	if (typeof v !== 'object' || v === null) return false;
	const m = v as Record<string, unknown>;
	return (
		typeof m.contrato === 'string' &&
		SEMVER.test(m.contrato) &&
		typeof m.versao === 'number' &&
		Array.isArray(m.chunks) &&
		m.chunks.every(
			(c: unknown) =>
				typeof c === 'object' &&
				c !== null &&
				typeof (c as ChunkRef).n === 'number' &&
				typeof (c as ChunkRef).arquivo === 'string'
		)
	);
}

/** Validação mínima de um chunk: array de objetos com `id` e `t`. */
export function ehChunk(v: unknown): v is OfertaCard[] {
	return (
		Array.isArray(v) &&
		v.every(
			(c: unknown) =>
				typeof c === 'object' &&
				c !== null &&
				typeof (c as OfertaCard).id === 'number' &&
				typeof (c as OfertaCard).t === 'string'
		)
	);
}

export function major(versao: string): number {
	return Number(versao.split('.')[0]);
}
