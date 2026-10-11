// Campo do topo → `/busca/` (BSV-34). Fora de `busca.ts`: a home não carrega a leitura da URL.
import type { Area } from './dados.ts';
import { SLUG_AREA } from './formato.ts';

/** `/busca/?q=…&area={slug}`, no formato de `escreverBusca` (TOP-01, TOP-02). */
export function destinoBusca(q: string, area?: Area | null): string {
	const p = new URLSearchParams();
	if (q) p.set('q', q);
	if (area) p.set('area', SLUG_AREA[area]);
	const s = p.toString();
	return '/busca/' + (s ? `?${s}` : '');
}

/** Texto levado do campo de outra página para a `/busca/` (com o que for digitado na navegação). */
export const passagem: { texto: string | null } = { texto: null };
