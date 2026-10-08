<script lang="ts">
	import { onMount } from 'svelte';
	import type { OfertaCard } from '#lib/dados.ts';
	import { favoritos } from '#lib/favoritos.svelte.ts';
	import { vitrine } from '#lib/vitrine.svelte.ts';
	import Areas from '#lib/componentes/Areas.svelte';
	import Busca from '#lib/componentes/Busca.svelte';
	import Card from '#lib/componentes/Card.svelte';
	import Rodape from '#lib/componentes/Rodape.svelte';
	import Topo from '#lib/componentes/Topo.svelte';

	/** Favoritos na ordem da lista; `card` nulo = ainda não achado no catálogo. */
	const itens = $derived.by(() => {
		void vitrine.versao;
		const procurados = new Set(favoritos.ids);
		const achados: Record<number, OfertaCard> = {};
		for (const { cards } of vitrine.cat.trechos()) {
			for (const c of cards) if (procurados.has(c.id)) achados[c.id] = c;
		}
		return favoritos.ids.map((id) => ({ id, card: achados[id] ?? null }));
	});

	onMount(() => vitrine.iniciar());
</script>

<svelte:head>
	<title>Lista de desejos · Besave</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<Topo>
	{#snippet busca()}<Busca />{/snippet}
	{#snippet areas()}<Areas />{/snippet}
</Topo>

<main class="mx-auto grid max-w-290 grid-cols-1 gap-4 px-3.5 pt-4 pb-8 sm:px-5">
	<h1 class="text-xl font-black text-marca">Lista de desejos</h1>
	{#if itens.length === 0}
		<p class="text-sm text-suave" data-vazia>
			Sua lista está vazia. Toque no ♡ de uma oferta para guardá-la aqui, neste aparelho.
			<a class="font-semibold text-marca underline underline-offset-2" href="/">Ver ofertas</a>
		</p>
	{:else}
		<div
			class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3.5 md:grid-cols-4 lg:grid-cols-5"
			data-grade
		>
			{#each itens as { id, card } (id)}
				{#if card}
					<Card {card} agora={vitrine.agora} />
				{:else if vitrine.completo}
					<div
						class="grid content-center justify-items-center gap-3 rounded-cartao border border-dashed border-borda p-4 text-center text-sm text-suave"
						data-fora-do-ar={id}
					>
						<p>Esta oferta saiu do ar.</p>
						<button
							type="button"
							class="rounded-full border border-borda px-3.5 py-1.5 font-semibold text-texto hover:border-suave"
							onclick={() => favoritos.remover(id)}>Remover</button
						>
					</div>
				{:else}
					<div
						class="grid aspect-[3/4] place-items-center rounded-cartao bg-superficie text-sm text-suave"
					>
						Carregando…
					</div>
				{/if}
			{/each}
		</div>
	{/if}
</main>

<Rodape />
