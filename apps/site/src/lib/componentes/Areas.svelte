<script lang="ts">
	import type { Area } from '#lib/dados.ts';
	import { AREAS_MENU, ROTULO_AREA, SLUG_AREA } from '#lib/formato.ts';

	/** Na home filtra a grade (`aoEscolher`); fora dela leva a `/?area=`. */
	let { ativa = null, aoEscolher }: { ativa?: Area | null; aoEscolher?: (a: Area | null) => void } =
		$props();

	const pilula =
		'block flex-none rounded-full border border-borda bg-fundo px-3.5 py-1.5 text-[13px] whitespace-nowrap text-texto hover:border-suave aria-pressed:border-marca aria-pressed:bg-marca aria-pressed:text-white';
	const visiveis: { valor: Area | null; rotulo: string }[] = [
		{ valor: null, rotulo: 'Todas' },
		...AREAS_MENU
	];
	const noMais: { valor: Area; rotulo: string }[] = [
		{ valor: 'OUTROS', rotulo: ROTULO_AREA.OUTROS }
	];
	let mais: HTMLDetailsElement | undefined = $state();

	function escolher(a: Area | null) {
		aoEscolher?.(a);
		if (mais) mais.open = false;
	}
</script>

{#snippet item(valor: Area | null, rotulo: string)}
	{#if aoEscolher}
		<button
			type="button"
			class={pilula}
			aria-pressed={ativa === valor}
			onclick={() => escolher(valor)}>{rotulo}</button
		>
	{:else}
		<a class={pilula} href={valor ? `/?area=${SLUG_AREA[valor]}` : '/'}>{rotulo}</a>
	{/if}
{/snippet}

<nav class="mx-auto flex max-w-290 items-center gap-2 px-3.5 pb-3 sm:px-5" aria-label="Áreas">
	<div class="flex min-w-0 flex-initial gap-2 overflow-x-auto [scrollbar-width:none]">
		{#each visiveis as a (a.rotulo)}
			{@render item(a.valor, a.rotulo)}
		{/each}
	</div>
	<details class="relative flex-none" bind:this={mais}>
		<summary
			class="{pilula} cursor-pointer list-none [&::-webkit-details-marker]:hidden"
			class:!bg-marca={ativa === 'OUTROS'}
			class:!text-white={ativa === 'OUTROS'}>Mais ▾</summary
		>
		<div
			class="absolute top-full right-0 z-20 mt-1.5 grid min-w-36 gap-1 rounded-cartao border border-borda bg-fundo p-2 shadow-lg"
		>
			{#each noMais as a (a.valor)}
				{@render item(a.valor, a.rotulo)}
			{/each}
		</div>
	</details>
</nav>
