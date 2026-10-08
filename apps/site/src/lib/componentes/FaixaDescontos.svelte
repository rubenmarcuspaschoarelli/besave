<script lang="ts">
	import type { OfertaCard } from '#lib/dados.ts';
	import CardMini from './CardMini.svelte';

	/** `null` enquanto o catálogo não carregou: esqueleto do mesmo tamanho (sem layout shift). */
	let { cards }: { cards: OfertaCard[] | null } = $props();
</script>

<section aria-labelledby="titulo-descontos" class="min-w-0">
	<h2
		id="titulo-descontos"
		class="mb-2.5 flex items-baseline gap-2.5 text-lg leading-tight font-black text-marca"
	>
		Maiores descontos de hoje <small class="font-sans text-xs font-normal text-suave"
			>últimas 24 h</small
		>
	</h2>
	<div class="flex min-h-40 gap-2.5 overflow-x-auto pb-1 sm:min-h-45" data-faixa>
		{#if cards === null}
			{#each { length: 8 }, i (i)}
				<div class="w-32 flex-none rounded-cartao bg-superficie sm:w-37" aria-hidden="true"></div>
			{/each}
		{:else if cards.length === 0}
			<p class="self-center text-sm text-suave">Sem descontos novos nas últimas 24 h.</p>
		{:else}
			{#each cards as card (card.id)}
				<CardMini {card} />
			{/each}
		{/if}
	</div>
</section>
