<script lang="ts">
	import type { OfertaCard } from '#lib/dados.ts';
	import Card from './Card.svelte';

	/** `null` enquanto o catálogo não carregou: esqueleto de cards. */
	let { cards, agora }: { cards: OfertaCard[] | null; agora: number } = $props();

	/** As 4 primeiras fotos entram na primeira dobra: sem `lazy`; a 1ª é o LCP. */
	const prioridade = (i: number) => (i === 0 ? 'alta' : i < 4 ? 'normal' : undefined);
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
		{#each cards as card, i (card.id)}
			<Card {card} {agora} prioridade={prioridade(i)} />
		{/each}
	{/if}
</div>
