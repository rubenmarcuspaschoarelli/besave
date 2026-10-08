<script lang="ts">
	import { onMount } from 'svelte';
	import { buscar, maioresDescontos, normalizar } from '#lib/dados.ts';
	import type { Area } from '#lib/dados.ts';
	import { ROTULO_AREA } from '#lib/formato.ts';
	import { vitrine } from '#lib/vitrine.svelte.ts';
	import AvisoNovas from './AvisoNovas.svelte';
	import Areas from './Areas.svelte';
	import BarraCanal from './BarraCanal.svelte';
	import Busca from './Busca.svelte';
	import FaixaDescontos from './FaixaDescontos.svelte';
	import Grade from './Grade.svelte';
	import Rodape from './Rodape.svelte';
	import Topo from './Topo.svelte';

	/** `area` fixa a página na área (`/{slug}/`); `null` é a home, com todas. */
	let { area }: { area: Area | null } = $props();

	const POR_VEZ = 40;

	let consulta = $state('');
	let limite = $state(POR_VEZ);

	const buscando = $derived(normalizar(consulta).length >= 2);
	const faixa = $derived.by(() => {
		void vitrine.versao;
		return vitrine.pronto
			? maioresDescontos(vitrine.cat, vitrine.agora, 8, area ? { area } : {})
			: null;
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

	function buscarPor(q: string) {
		consulta = q;
		limite = POR_VEZ;
	}

	onMount(() => {
		const p = new URL(location.href).searchParams;
		consulta = p.get('q') ?? '';
		vitrine.iniciar();
	});
</script>

<BarraCanal />
<Topo>
	{#snippet busca()}
		<Busca valor={consulta} aoMudar={buscarPor} />
	{/snippet}
	{#snippet areas()}
		<Areas ativa={area} />
	{/snippet}
</Topo>
<AvisoNovas {area} />

<main class="mx-auto grid max-w-290 grid-cols-1 gap-5.5 px-3.5 pt-3.5 pb-8 sm:px-5 sm:pt-4.5">
	{#if area}
		<h1 class="text-2xl leading-tight font-black text-marca">Ofertas de {ROTULO_AREA[area]}</h1>
	{:else}
		<h1 class="sr-only">Besave: ofertas e cupons</h1>
	{/if}
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
