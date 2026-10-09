import { describe, expect, it } from 'vitest';
import { jsonLdTrilha, paginaDoCaminho, trilha } from './trilha.ts';

describe('trilha e JSON-LD (BSV-33)', () => {
	it('JLD-01: só área e subpágina ganham JSON-LD', () => {
		expect(paginaDoCaminho('/elas/')).toEqual({ area: 'ELAS' });
		expect(paginaDoCaminho('/esporte-vida/masculino/')).toEqual({
			area: 'ESPORTE_VIDA',
			publico: 'MASCULINO'
		});
		for (const c of ['/', '/desejos/', '/404.html', '/elas/xyz/', '/xyz/feminino/', '/elas'])
			expect(paginaDoCaminho(c), c).toBeNull();
	});

	it('JLD-01: BreadcrumbList com posições, nomes e URLs absolutas; & e < não quebram a tag', () => {
		const tag = jsonLdTrilha([...trilha('FAMILIA', 'INFANTIL'), { nome: 'a<b', caminho: '/x/' }]);
		const m = /^<script type="application\/ld\+json">(.*)<\/script>$/.exec(tag);
		expect(m).not.toBeNull();
		expect(m![1]).not.toMatch(/[<>&]/);
		expect(JSON.parse(m![1])).toEqual({
			'@context': 'https://schema.org',
			'@type': 'BreadcrumbList',
			itemListElement: [
				{ '@type': 'ListItem', position: 1, name: 'Início', item: 'https://besave.com.br/' },
				{
					'@type': 'ListItem',
					position: 2,
					name: 'Família & filhos',
					item: 'https://besave.com.br/familia/'
				},
				{
					'@type': 'ListItem',
					position: 3,
					name: 'Infantil',
					item: 'https://besave.com.br/familia/infantil/'
				},
				{ '@type': 'ListItem', position: 4, name: 'a<b', item: 'https://besave.com.br/x/' }
			]
		});
	});
});
