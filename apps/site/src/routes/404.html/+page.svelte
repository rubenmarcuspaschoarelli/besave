<script lang="ts">
	import { CONFIG } from '#lib/config.ts';
	import Areas from '#lib/componentes/Areas.svelte';
	import Busca from '#lib/componentes/Busca.svelte';
	import Rodape from '#lib/componentes/Rodape.svelte';
	import Topo from '#lib/componentes/Topo.svelte';
</script>

<svelte:head>
	<title>Oferta encerrada ou não encontrada · Besave</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<Topo>
	{#snippet busca()}<Busca />{/snippet}
	{#snippet areas()}<Areas />{/snippet}
</Topo>

<main class="mx-auto grid max-w-290 grid-cols-1 justify-items-start gap-4 px-3.5 py-10 sm:px-5">
	<h1 class="text-2xl leading-tight font-black text-marca">Oferta encerrada ou não encontrada</h1>
	<p class="max-w-prose text-suave">
		Ofertas duram pouco: esta pode ter acabado ou o link está errado. Veja as mais recentes ou siga
		o canal para receber as próximas primeiro.
	</p>
	<div class="flex flex-wrap gap-3">
		<a
			class="rounded-full bg-destaque px-5 py-2.5 text-sm font-bold text-sobre-destaque hover:brightness-95"
			href="/">Ir para o início</a
		>
		<a
			class="rounded-full border border-marca px-5 py-2.5 text-sm font-bold text-marca hover:bg-superficie"
			href={CONFIG.canal}
			rel="noopener">Canal do Telegram</a
		>
	</div>
</main>

<Rodape />
