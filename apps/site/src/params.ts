// Matchers de rota (SvelteKit 3: um arquivo, `defineParams`).
import { defineParams } from '@sveltejs/kit/params';
import { AREAS } from '#lib/dados.ts';
import { SLUG_AREA } from '#lib/formato.ts';

const SLUGS = new Set<string>(AREAS.map((a) => SLUG_AREA[a]));

export const params = defineParams({
	/** Só os 10 slugs do CONTRATO §2.3; o resto não casa e vira 404 (AD-020). */
	area: (p) => (SLUGS.has(p) ? p : undefined)
});
