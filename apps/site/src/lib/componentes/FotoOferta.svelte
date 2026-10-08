<script lang="ts">
	import type { OfertaCard } from '#lib/dados.ts';
	import { SLUG_AREA } from '#lib/formato.ts';

	let { card, pct, tamanho }: { card: OfertaCard; pct: number | null; tamanho: number } = $props();
	const placeholder = $derived(`/img/placeholder/${SLUG_AREA[card.a]}.webp`);
	let falhou = $state(false);
</script>

<div class="relative aspect-square overflow-hidden bg-white">
	<img
		src={falhou ? placeholder : `/img/ofertas/${card.id}-small.webp`}
		data-placeholder={placeholder}
		alt=""
		width={tamanho}
		height={tamanho}
		loading="lazy"
		decoding="async"
		class={['size-full object-contain', card.x && 'grayscale']}
		onerror={() => (falhou = true)}
	/>
	{#if pct}
		<span
			class="absolute top-2 left-2 rounded-md bg-destaque px-1.5 py-1 font-titulo text-xs leading-none font-black text-sobre-destaque tabular-nums"
			>-{pct}%</span
		>
	{/if}
</div>
