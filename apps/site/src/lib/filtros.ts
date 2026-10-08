// Filtros da grade no endereço (BSV-31): `?ordem=&publico=&loja=&preco=&cupom=1`, valores em minúsculas.
import { FAIXAS, LOJAS, PUBLICOS } from './dados.ts';
import type { Faixa, Loja, Ordem, Publico } from './dados.ts';

export interface EstadoFiltros {
	ordem: Ordem;
	publico?: Publico;
	loja?: Loja;
	faixa?: Faixa;
	soComCupom: boolean;
}

export const PADRAO: EstadoFiltros = { ordem: 'recentes', soComCupom: false };

const ORDENS: readonly Ordem[] = ['recentes', 'desconto', 'preco'];
/** `MERCADO_LIVRE` → `mercado-livre`, como nos slugs de área. */
const naUrl = (v: string) => v.toLowerCase().replace(/_/g, '-');
const CHAVES = ['ordem', 'publico', 'loja', 'preco', 'cupom'] as const;

function achar<T extends string>(lista: readonly T[], v: string | null): T | undefined {
	return v === null ? undefined : lista.find((x) => naUrl(x) === v);
}

/** Valor ausente ou inválido fica no padrão. */
export function lerFiltros(p: URLSearchParams): EstadoFiltros {
	const e: EstadoFiltros = {
		ordem: achar(ORDENS, p.get('ordem')) ?? 'recentes',
		soComCupom: p.get('cupom') === '1'
	};
	const publico = achar(PUBLICOS, p.get('publico'));
	const loja = achar(LOJAS, p.get('loja'));
	const faixa = achar(FAIXAS, p.get('preco'));
	if (publico) e.publico = publico;
	if (loja) e.loja = loja;
	if (faixa) e.faixa = faixa;
	return e;
}

/** Path + query + hash de `url` com os filtros de `e`; padrão fora, outros parâmetros mantidos. */
export function escreverFiltros(url: URL, e: EstadoFiltros): string {
	const p = new URLSearchParams(url.search);
	for (const k of CHAVES) p.delete(k);
	if (e.ordem !== 'recentes') p.set('ordem', e.ordem);
	if (e.publico) p.set('publico', naUrl(e.publico));
	if (e.loja) p.set('loja', naUrl(e.loja));
	if (e.faixa) p.set('preco', e.faixa);
	if (e.soComCupom) p.set('cupom', '1');
	const q = p.toString();
	return url.pathname + (q ? `?${q}` : '') + url.hash;
}

export function foraDoPadrao(e: EstadoFiltros): boolean {
	return (
		e.ordem !== 'recentes' ||
		e.publico !== undefined ||
		e.loja !== undefined ||
		e.faixa !== undefined ||
		e.soComCupom
	);
}
