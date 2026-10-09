<script lang="ts">
	import type { Area, Publico } from '#lib/dados.ts';
	import { textoDaPagina } from '#lib/conteudo/areas.ts';
	import { trilha } from '#lib/conteudo/trilha.ts';
	import { ROTULO_AREA, ROTULO_PUBLICO } from '#lib/formato.ts';

	/** Trilha, `<h1>` e texto de `/{slug}/` e `/{slug}/{publico}/` (BSV-33), no HTML prerenderizado. O JSON-LD da trilha entra pelo hooks.server.ts. */
	let { area, publico }: { area: Area; publico?: Publico } = $props();

	const passos = $derived(trilha(area, publico));
</script>

<div class="grid gap-1.5">
	<nav aria-label="Trilha" data-trilha>
		<ol class="flex flex-wrap items-center gap-1.5 text-xs text-suave">
			{#each passos as t, i (t.caminho)}
				{#if i > 0}<li aria-hidden="true">›</li>{/if}
				<li>
					{#if i === passos.length - 1}
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
	<div class="grid max-w-2xl gap-1.5 text-sm text-suave" data-texto-area>
		{#each textoDaPagina(area, publico) as p (p)}
			<p>{p}</p>
		{/each}
	</div>
</div>
