// /{slug}/{publico}/ das 40 combinações área × público (BSV-33), prerender; fora da lista → 404.
import { AREAS, PUBLICOS } from '#lib/dados.ts';
import type { Area, Publico } from '#lib/dados.ts';
import { SLUG_AREA } from '#lib/formato.ts';
import type { EntryGenerator, PageLoad } from './$types';

export const entries: EntryGenerator = () =>
	AREAS.flatMap((a) => PUBLICOS.map((p) => ({ area: SLUG_AREA[a], publico: p.toLowerCase() })));

export const load: PageLoad = ({ params }) => ({
	area: AREAS.find((a) => SLUG_AREA[a] === params.area) as Area,
	publico: PUBLICOS.find((p) => p.toLowerCase() === params.publico) as Publico
});
