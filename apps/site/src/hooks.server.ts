// Prerender: JSON-LD `BreadcrumbList` nas áreas e subpáginas (BSV-33). Roda só no build; o cliente
// não carrega este código (bundle da home, BUD-01).
import type { Handle } from '@sveltejs/kit/hooks';
import { jsonLdTrilha, paginaDoCaminho, trilha } from '#lib/conteudo/trilha.ts';

export const handle: Handle = ({ event, resolve }) => {
	const p = paginaDoCaminho(event.url.pathname);
	if (!p) return resolve(event);
	const ld = jsonLdTrilha(trilha(p.area, p.publico));
	return resolve(event, {
		transformPageChunk: ({ html }) => html.replace('</head>', `${ld}</head>`)
	});
};
