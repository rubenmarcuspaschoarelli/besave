// Busca no endereço (BSV-34): `/busca/?q=&area={slug}` + filtros da BSV-31 (`filtros.ts`).
import { AREAS } from './dados.ts';
import type { Area } from './dados.ts';
import { PADRAO, escreverFiltros, lerFiltros } from './filtros.ts';
import type { EstadoFiltros } from './filtros.ts';
import { SLUG_AREA } from './formato.ts';

export interface EstadoBusca {
	q: string;
	area?: Area;
	filtros: EstadoFiltros;
}

/** Área fora dos slugs do CONTRATO §2.3 é ignorada. */
export function lerBusca(p: URLSearchParams): EstadoBusca {
	const slug = p.get('area');
	const area = AREAS.find((a) => SLUG_AREA[a] === slug);
	return { q: p.get('q') ?? '', ...(area ? { area } : {}), filtros: lerFiltros(p) };
}

/** Path + query + hash de `url` com `q` e `area` à frente e os filtros; `q` vazio sai. */
export function escreverBusca(url: URL, e: EstadoBusca): string {
	const p = new URLSearchParams();
	if (e.q) p.set('q', e.q);
	if (e.area) p.set('area', SLUG_AREA[e.area]);
	for (const [k, v] of url.searchParams) if (k !== 'q' && k !== 'area') p.append(k, v);
	const u = new URL(url);
	u.search = p.toString();
	return escreverFiltros(u, e.filtros);
}

/** Para onde o campo do topo leva (TOP-01, TOP-02). */
export const destinoBusca = (q: string, area?: Area | null) =>
	escreverBusca(new URL('/busca/', 'http://x'), {
		q,
		...(area ? { area } : {}),
		filtros: PADRAO
	});
