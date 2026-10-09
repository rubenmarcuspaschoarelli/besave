<script lang="ts">
	import { ROTULO_AREA, SLUG_AREA } from '#lib/formato.ts';
	import CabecalhoArea from '#lib/componentes/CabecalhoArea.svelte';
	import PaginaOfertas from '#lib/componentes/PaginaOfertas.svelte';

	let { data } = $props();
	const rotulo = $derived(ROTULO_AREA[data.area]);
</script>

<svelte:head>
	<title>Ofertas de {rotulo} · Besave</title>
	<meta
		name="description"
		content="Ofertas e cupons de {rotulo} na Amazon, Mercado Livre e Shopee, atualizados a cada 5 minutos."
	/>
	<link rel="canonical" href="https://besave.com.br/{SLUG_AREA[data.area]}/" />
</svelte:head>

<!-- Componente novo por área: busca e "Ver mais" voltam ao início ao trocar de área. -->
{#key data.area}
	<PaginaOfertas area={data.area}>
		{#snippet cabecalho()}
			<CabecalhoArea area={data.area} />
		{/snippet}
	</PaginaOfertas>
{/key}
