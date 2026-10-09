<script lang="ts">
	import type { Area, Publico } from '#lib/dados.ts';
	import { ROTULO_AREA, ROTULO_PUBLICO, caminhoArea } from '#lib/formato.ts';

	/** Trilha e `<h1>` de `/{slug}/` e `/{slug}/{publico}/` (BSV-33). */
	let { area, publico }: { area: Area; publico?: Publico } = $props();

	const trilha = $derived([
		{ nome: 'Início', caminho: '/' },
		{ nome: ROTULO_AREA[area], caminho: caminhoArea(area) },
		...(publico ? [{ nome: ROTULO_PUBLICO[publico], caminho: caminhoArea(area, publico) }] : [])
	]);
</script>

<div class="grid gap-1.5">
	<nav aria-label="Trilha" data-trilha>
		<ol class="flex flex-wrap items-center gap-1.5 text-xs text-suave">
			{#each trilha as t, i (t.caminho)}
				{#if i > 0}<li aria-hidden="true">›</li>{/if}
				<li>
					{#if i === trilha.length - 1}
						<span aria-current="page">{t.nome}</span>
					{:else}
						<a class="underline hover:text-marca" href={t.caminho}>{t.nome}</a>
					{/if}
				</li>
			{/each}
		</ol>
	</nav>
	<h1 class="text-2xl leading-tight font-black text-marca">
		{publico
			? `${ROTULO_AREA[area]} · ${ROTULO_PUBLICO[publico]}`
			: `Ofertas de ${ROTULO_AREA[area]}`}
	</h1>
</div>
