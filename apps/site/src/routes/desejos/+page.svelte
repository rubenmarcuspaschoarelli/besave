<script lang="ts">
	import Areas from '#lib/componentes/Areas.svelte';
	import Busca from '#lib/componentes/Busca.svelte';
	import Rodape from '#lib/componentes/Rodape.svelte';
	import Topo from '#lib/componentes/Topo.svelte';
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
</main>

<Rodape />
