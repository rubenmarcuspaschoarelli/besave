<script lang="ts">
	import type { OfertaCard } from '#lib/dados.ts';
	import Card from './Card.svelte';

	/** `null` enquanto o catálogo não carregou: esqueleto de cards. */
	let { cards, agora }: { cards: OfertaCard[] | null; agora: number } = $props();
</script>

<div
	class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3.5 md:grid-cols-4 lg:grid-cols-5"
	data-grade
>
	{#if cards === null}
		{#each { length: 10 }, i (i)}
			<div class="aspect-[3/4] rounded-cartao bg-superficie" aria-hidden="true"></div>
		{/each}
	{:else}
		{#each cards as card (card.id)}
			<Card {card} {agora} />
		{/each}
	{/if}
</div>
