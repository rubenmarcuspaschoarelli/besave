// Filtros da grade no endereço (BSV-31): `?ordem=&publico=&loja=&preco=&cupom=1`, valores em minúsculas.
import { FAIXAS, LOJAS, PUBLICOS, ROTULO_LOJA } from './dados.ts';
import type { Area, Faixa, Loja, Ordem, Publico } from './dados.ts';
import { ROTULO_PUBLICO, caminhoArea } from './formato.ts';

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

/** Algum filtro além da ordem (estado vazio). */
export function temFiltro(e: EstadoFiltros): boolean {
	return e.publico !== undefined || e.loja !== undefined || e.faixa !== undefined || e.soComCupom;
}

/** Ordem ou filtro fora do padrão ("Limpar filtros"). */
export function foraDoPadrao(e: EstadoFiltros): boolean {
	return e.ordem !== 'recentes' || temFiltro(e);
}

/** Área (BSV-33): público no caminho `/{slug}/{publico}/`, os demais filtros na query de `url`. */
export function destinoArea(url: URL, area: Area, e: EstadoFiltros): string {
	const { publico, ...resto } = e;
	return escreverFiltros(new URL(caminhoArea(area, publico) + url.search + url.hash, url), resto);
}

/** Grupos da barra (BSV-37): a linha compacta mostra o valor escolhido de cada um. */
export type Grupo = 'ordem' | 'publico' | 'loja' | 'faixa';

export const ROTULO_ORDEM: Record<Ordem, string> = {
	recentes: 'Recentes',
	desconto: 'Maior desconto',
	preco: 'Menor preço'
};
export const ROTULO_FAIXA: Record<Faixa, string> = {
	ate50: 'Até R$ 50',
	'50a100': 'R$ 50–100',
	'100a200': 'R$ 100–200',
	acima200: 'Acima de R$ 200'
};

/** Nome do grupo na linha compacta e no painel. */
export const ROTULO_GRUPO: Record<Grupo, string> = {
	ordem: 'Ordem',
	publico: 'Público',
	loja: 'Loja',
	faixa: 'Preço'
};

/** Os valores dos quatro grupos não se repetem: um mapa só. */
const ROTULOS: Record<string, string> = {
	...ROTULO_ORDEM,
	...ROTULO_PUBLICO,
	...ROTULO_LOJA,
	...ROTULO_FAIXA
};

/** Rótulo do valor escolhido no grupo; `undefined` sem escolha (ordem sempre tem). */
export const valorEscolhido = (e: EstadoFiltros, g: Grupo): string | undefined =>
	ROTULOS[e[g] ?? ''];

/**
 * Botão de opção (pílula), na linha do celular, no painel e na faixa do computador. O contorno
 * de foco vem do `:focus-visible` base (app.css).
 */
export const BOTAO_FILTRO =
	'min-h-11 flex-none rounded-full border border-borda bg-fundo px-3.5 text-[13px] whitespace-nowrap text-texto hover:border-suave aria-pressed:border-marca aria-pressed:bg-marca aria-pressed:text-white';
