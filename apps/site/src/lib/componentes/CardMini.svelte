<script lang="ts">
	import { descontoPct } from '#lib/dados.ts';
	import type { OfertaCard } from '#lib/dados.ts';
	import { reais } from '#lib/formato.ts';
	import FotoOferta from './FotoOferta.svelte';

	let { card }: { card: OfertaCard } = $props();
	const pct = $derived(descontoPct(card));
</script>

<a
	href="/oferta/{card.id}/"
	class="grid w-32 flex-none gap-1.5 rounded-cartao border border-borda bg-fundo p-2 sm:w-37"
	data-id={card.id}
>
	<span class="overflow-hidden rounded-md"><FotoOferta {card} {pct} tamanho={160} /></span>
	<span class="sr-only">{card.t}</span>
	<b class="font-titulo text-[15px] font-black tabular-nums">{reais(card.pp)}</b>
</a>
