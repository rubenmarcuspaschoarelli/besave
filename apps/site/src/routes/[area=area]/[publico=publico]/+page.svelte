<script lang="ts">
	import { ROTULO_AREA, ROTULO_PUBLICO, caminhoArea } from '#lib/formato.ts';
	import CabecalhoArea from '#lib/componentes/CabecalhoArea.svelte';
	import PaginaOfertas from '#lib/componentes/PaginaOfertas.svelte';

	let { data } = $props();
	const area = $derived(ROTULO_AREA[data.area]);
	const publico = $derived(ROTULO_PUBLICO[data.publico]);
</script>

<svelte:head>
	<title>Ofertas de {area} · {publico} · Besave</title>
	<meta
		name="description"
		content="Ofertas e cupons de {area} para o público {publico.toLowerCase()} na Amazon, Mercado Livre e Shopee, atualizados a cada 5 minutos."
	/>
	<link rel="canonical" href="https://besave.com.br{caminhoArea(data.area, data.publico)}" />
</svelte:head>

<!-- Componente novo por página: filtros e "Ver mais" voltam ao início ao trocar de área ou público. -->
{#key `${data.area}/${data.publico}`}
	<PaginaOfertas area={data.area} publico={data.publico}>
		{#snippet cabecalho()}
			<CabecalhoArea area={data.area} publico={data.publico} />
		{/snippet}
	</PaginaOfertas>
{/key}
