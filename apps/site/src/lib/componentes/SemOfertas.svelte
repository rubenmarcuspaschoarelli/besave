<script lang="ts">
	import type { Area } from '#lib/dados.ts';
	import { AREAS_MENU, ROTULO_AREA, caminhoArea } from '#lib/formato.ts';

	/** Página de área ou subpágina sem nenhuma oferta (BSV-33): aviso e links para as outras áreas. */
	let { area }: { area: Area } = $props();

	const outras = $derived(
		[...AREAS_MENU, { valor: 'OUTROS' as const, rotulo: ROTULO_AREA.OUTROS }].filter(
			(a) => a.valor !== area
		)
	);
</script>

<div class="grid justify-items-start gap-3" data-sem-ofertas>
	<p class="text-base font-bold text-texto">Ainda não temos ofertas aqui</p>
	<nav aria-label="Outras áreas">
		<ul class="flex flex-wrap gap-2">
			{#each outras as a (a.valor)}
				<li>
					<a
						class="block rounded-full border border-borda bg-fundo px-3.5 py-1.5 text-[13px] text-texto hover:border-suave"
						href={caminhoArea(a.valor)}>{a.rotulo}</a
					>
				</li>
			{/each}
		</ul>
	</nav>
</div>
