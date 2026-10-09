// Trilha Início › Área › Público (BSV-33): a visível (CabecalhoArea) e o JSON-LD `BreadcrumbList`,
// que entra no HTML no prerender (hooks.server.ts), sem código no cliente.
import { AREAS, PUBLICOS } from '../dados.ts';
import type { Area, Publico } from '../dados.ts';
import { ROTULO_AREA, ROTULO_PUBLICO, SLUG_AREA, caminhoArea } from '../formato.ts';

export interface PassoTrilha {
	nome: string;
	caminho: string;
}

export function trilha(area: Area, publico?: Publico): PassoTrilha[] {
	return [
		{ nome: 'Início', caminho: '/' },
		{ nome: ROTULO_AREA[area], caminho: caminhoArea(area) },
		...(publico ? [{ nome: ROTULO_PUBLICO[publico], caminho: caminhoArea(area, publico) }] : [])
	];
}

/** `/{slug}/` ou `/{slug}/{publico}/` → área e público; qualquer outro caminho → `null`. */
export function paginaDoCaminho(caminho: string): { area: Area; publico?: Publico } | null {
	const m = /^\/([a-z-]+)\/(?:([a-z]+)\/)?$/.exec(caminho);
	const area = m && AREAS.find((a) => SLUG_AREA[a] === m[1]);
	if (!m || !area) return null;
	if (m[2] === undefined) return { area };
	const publico = PUBLICOS.find((p) => p.toLowerCase() === m[2]);
	return publico ? { area, publico } : null;
}

/**
 * `<script type="application/ld+json">` com o `BreadcrumbList` da trilha; `&`, `<` e `>` em escape
 * Unicode, para o texto nunca fechar a tag.
 */
export function jsonLdTrilha(passos: PassoTrilha[], base = 'https://besave.com.br'): string {
	const json = JSON.stringify({
		'@context': 'https://schema.org',
		'@type': 'BreadcrumbList',
		itemListElement: passos.map((t, i) => ({
			'@type': 'ListItem',
			position: i + 1,
			name: t.nome,
			item: base + t.caminho
		}))
	}).replace(/[&<>]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
	return `<script type="application/ld+json">${json}</script>`;
}
