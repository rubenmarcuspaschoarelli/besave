<script lang="ts">
	import { descontoPct, ROTULO_LOJA } from '#lib/dados.ts';
	import type { OfertaCard } from '#lib/dados.ts';
	import { haQuanto, reais } from '#lib/formato.ts';
	import BotaoFavorito from './BotaoFavorito.svelte';
	import FotoOferta from './FotoOferta.svelte';

	let {
		card,
		agora,
		prioridade
	}: { card: OfertaCard; agora: number; prioridade?: 'alta' | 'normal' } = $props();
	const pct = $derived(descontoPct(card));
</script>

<article
	class="relative grid grid-rows-[auto_1fr] overflow-hidden rounded-cartao border border-borda bg-fundo has-focus-visible:ring-2 has-focus-visible:ring-foco"
	data-id={card.id}
	data-area={card.a}
>
	<FotoOferta {card} {pct} tamanho={320} {prioridade} />
	<div class="grid content-start gap-1.5 px-2.5 py-2 sm:px-3 sm:py-2.5">
		<h3 class="line-clamp-2 min-h-[2.7em] font-sans text-[13.5px] leading-[1.35]">
			<a href="/oferta/{card.id}/" class="outline-none after:absolute after:inset-0">{card.t}</a>
		</h3>
		<p class="flex flex-wrap items-baseline gap-x-2 tabular-nums">
			<strong
				class={[
					'font-titulo text-base leading-none font-black sm:text-lg',
					card.x ? 'text-suave' : 'text-texto'
				]}>{reais(card.pp)}</strong
			>
			{#if pct}<s class="text-xs text-suave">{reais(card.pd ?? 0)}</s>{/if}
		</p>
		<div class="flex items-center gap-2 border-t border-borda pt-1 text-xs text-suave">
			<span class="font-semibold text-texto">{ROTULO_LOJA[card.l]}</span>
			{#if card.x}
				<span class="font-semibold">Expirada</span>
			{:else}
				<time datetime={card.dp ?? card.dt}>{haQuanto(card, agora)}</time>
			{/if}
			<span class="flex-1"></span>
			<BotaoFavorito id={card.id} />
		</div>
	</div>
</article>
