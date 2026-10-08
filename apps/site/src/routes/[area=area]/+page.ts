// /{slug}/ das 10 áreas (CONTRATO §2.3), prerender; slug fora da lista não casa com a rota.
import { AREAS } from '#lib/dados.ts';
import type { Area } from '#lib/dados.ts';
import { SLUG_AREA } from '#lib/formato.ts';
import type { EntryGenerator, PageLoad } from './$types';

export const entries: EntryGenerator = () => AREAS.map((a) => ({ area: SLUG_AREA[a] }));

export const load: PageLoad = ({ params }) => ({
	area: AREAS.find((a) => SLUG_AREA[a] === params.area) as Area
});
