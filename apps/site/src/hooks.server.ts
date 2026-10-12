// Prerender: JSON-LD `BreadcrumbList` nas áreas e subpáginas (BSV-33) e o rodapé de toda página
// (BSV-39). Roda só no build; o cliente não carrega este código (bundle da home, BUD-01).
import type { Handle } from '@sveltejs/kit/hooks';
import { render } from 'svelte/server';
import Rodape from '#lib/componentes/Rodape.svelte';
import { jsonLdTrilha, paginaDoCaminho, trilha } from '#lib/conteudo/trilha.ts';

/**
 * Estático e igual em toda página: entra no `<!--rodape-->` do app.html, depois da raiz do Svelte
 * (sem hidratação) e dentro do contêiner do kit, que continua tratando os cliques nos links.
 */
const RODAPE = render(Rodape).body;

export const handle: Handle = ({ event, resolve }) => {
	const p = paginaDoCaminho(event.url.pathname);
	const ld = p ? jsonLdTrilha(trilha(p.area, p.publico)) : '';
	return resolve(event, {
		transformPageChunk: ({ html }) =>
			html.replace('</head>', `${ld}</head>`).replace('<!--rodape-->', RODAPE)
	});
};
