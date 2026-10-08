<script lang="ts">
	import { onMount } from 'svelte';
	import { AREAS, buscar, maioresDescontos, normalizar } from '#lib/dados.ts';
	import type { Area } from '#lib/dados.ts';
	import { ROTULO_AREA, SLUG_AREA } from '#lib/formato.ts';
	import { vitrine } from '#lib/vitrine.svelte.ts';
	import Areas from '#lib/componentes/Areas.svelte';
	import BarraCanal from '#lib/componentes/BarraCanal.svelte';
	import Busca from '#lib/componentes/Busca.svelte';
	import FaixaDescontos from '#lib/componentes/FaixaDescontos.svelte';
	import Grade from '#lib/componentes/Grade.svelte';
	import Rodape from '#lib/componentes/Rodape.svelte';
	import Topo from '#lib/componentes/Topo.svelte';

	const POR_VEZ = 40;

	let consulta = $state('');
	let area = $state<Area | null>(null);
	let limite = $state(POR_VEZ);

	const buscando = $derived(normalizar(consulta).length >= 2);
	const faixa = $derived.by(() => {
		void vitrine.versao;
		return vitrine.pronto ? maioresDescontos(vitrine.cat, vitrine.agora, 8) : null;
	});
	const resultado = $derived.by(() => {
		void vitrine.versao;
		if (!vitrine.pronto) return null;
		const f = area ? { area } : {};
		if (buscando) {
			const r = buscar(vitrine.cat, consulta, f, limite);
			return { itens: r.itens, total: r.total };
		}
		const todos = vitrine.cat.lista(f);
		return { itens: todos.slice(0, limite), total: todos.length };
	});

	function filtrar(mudar: () => void) {
		mudar();
		limite = POR_VEZ;
	}

	onMount(() => {
		const p = new URL(location.href).searchParams;
		consulta = p.get('q') ?? '';
		const slug = p.get('area');
		area = AREAS.find((a) => SLUG_AREA[a] === slug) ?? null;
		vitrine.iniciar();
	});
</script>

<svelte:head>
	<title>Besave · ofertas e cupons da Amazon, Mercado Livre e Shopee</title>
	<meta
		name="description"
		content="As melhores ofertas e cupons da Amazon, Mercado Livre e Shopee, atualizadas a cada 5 minutos."
	/>
	<link rel="canonical" href="https://besave.com.br/" />
</svelte:head>

<BarraCanal />
<Topo>
	{#snippet busca()}
		<Busca valor={consulta} aoMudar={(q) => filtrar(() => (consulta = q))} />
	{/snippet}
	{#snippet areas()}
		<Areas ativa={area} aoEscolher={(a) => filtrar(() => (area = a))} />
	{/snippet}
</Topo>

<main class="mx-auto grid max-w-290 grid-cols-1 gap-5.5 px-3.5 pt-3.5 pb-8 sm:px-5 sm:pt-4.5">
	<h1 class="sr-only">Besave: ofertas e cupons</h1>
	{#if vitrine.erro}
		<p class="rounded-cartao bg-superficie p-4 text-sm" role="alert">
			Não foi possível carregar as ofertas. Tente de novo em instantes.
		</p>
	{:else}
		{#if !buscando}
			<FaixaDescontos cards={faixa} />
		{/if}
		<section aria-labelledby="titulo-recentes" class="grid grid-cols-1 gap-3">
			<h2
				id="titulo-recentes"
				class="flex flex-wrap items-baseline gap-x-2.5 text-lg leading-tight font-black text-marca"
			>
				{buscando ? `Resultados para “${consulta.trim()}”` : 'Mais recentes'}
				{#if area}<span class="font-sans text-sm font-semibold text-texto"
						>· {ROTULO_AREA[area]}</span
					>{/if}
				{#if resultado}
					<small class="font-sans text-xs font-normal text-suave" data-total
						>{resultado.itens.length.toLocaleString('pt-BR')} de {resultado.total.toLocaleString(
							'pt-BR'
						)} ofertas</small
					>
				{/if}
			</h2>
			{#if resultado && resultado.total === 0}
				<p class="text-sm text-suave">
					{buscando ? 'Nenhuma oferta encontrada.' : 'Nenhuma oferta nesta área agora.'}
				</p>
			{:else}
				<Grade cards={resultado?.itens ?? null} agora={vitrine.agora} />
			{/if}
			{#if resultado && resultado.itens.length < resultado.total}
				<button
					type="button"
					class="justify-self-center rounded-full bg-destaque px-5 py-2.5 text-sm font-bold text-sobre-destaque hover:brightness-95"
					onclick={() => (limite += POR_VEZ)}>Ver mais ofertas</button
				>
			{/if}
		</section>
	{/if}
</main>

<Rodape />
