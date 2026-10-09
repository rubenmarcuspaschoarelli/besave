<script lang="ts">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { buscar, maioresDescontos, normalizar } from '#lib/dados.ts';
	import type { Area, Filtro, Publico } from '#lib/dados.ts';
	import { PADRAO, destinoArea, escreverFiltros, lerFiltros, temFiltro } from '#lib/filtros.ts';
	import type { EstadoFiltros } from '#lib/filtros.ts';
	import { vitrine } from '#lib/vitrine.svelte.ts';
	import AvisoNovas from './AvisoNovas.svelte';
	import Areas from './Areas.svelte';
	import BarraFiltros from './BarraFiltros.svelte';
	import BarraCanal from './BarraCanal.svelte';
	import Busca from './Busca.svelte';
	import FaixaDescontos from './FaixaDescontos.svelte';
	import Grade from './Grade.svelte';
	import Rodape from './Rodape.svelte';
	import Topo from './Topo.svelte';

	/**
	 * `area` fixa a página na área (`/{slug}/`); `null` é a home, com todas. `publico` fixa a
	 * subpágina (`/{slug}/{publico}/`, BSV-33). `cabecalho` substitui o `<h1>` oculto da home.
	 */
	let { area, publico, cabecalho }: { area: Area | null; publico?: Publico; cabecalho?: Snippet } =
		$props();

	const POR_VEZ = 40;

	let consulta = $state('');
	let limite = $state(POR_VEZ);
	let filtros = $state<EstadoFiltros>(PADRAO);

	/** Filtros da grade (BSV-31); a faixa de descontos só respeita a área. */
	const filtro = $derived<Filtro>({ ...(area ? { area } : {}), ...filtros });
	const comFiltro = $derived(temFiltro(filtros));

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
		if (buscando) {
			const r = buscar(vitrine.cat, consulta, filtro, limite);
			return { itens: r.itens, total: r.total };
		}
		const todos = vitrine.cat.lista(filtro);
		return { itens: todos.slice(0, limite), total: todos.length };
	});

	function buscarPor(q: string) {
		consulta = q;
		limite = POR_VEZ;
	}

	function filtrar(e: EstadoFiltros) {
		// Na área, público é caminho (BSV-33): trocar de público é trocar de página.
		if (area && e.publico !== publico) {
			void goto(destinoArea(new URL(location.href), area, e), { reset: false });
			return;
		}
		filtros = e;
		limite = POR_VEZ;
		const url = new URL(location.href);
		void goto(area ? destinoArea(url, area, e) : escreverFiltros(url, e), {
			shallow: true,
			replace: true
		});
	}

	onMount(() => {
		const url = new URL(location.href);
		const p = url.searchParams;
		const lido = lerFiltros(p);
		// `/{slug}/?publico=x` → `/{slug}/x/`, sem nova entrada no histórico (BSV-33).
		if (area && lido.publico) {
			void goto(destinoArea(url, area, lido), { replace: true });
			return;
		}
		consulta = p.get('q') ?? '';
		filtros = publico ? { ...lido, publico } : lido;
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
	{#if cabecalho}
		{@render cabecalho()}
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
			<BarraFiltros estado={filtros} total={resultado?.total ?? null} aoMudar={filtrar} />
			{#if resultado && resultado.total === 0 && comFiltro}
				<div class="grid justify-items-start gap-2" data-vazio>
					<p class="text-sm text-suave">Nenhuma oferta com esses filtros</p>
					<button
						type="button"
						class="min-h-11 rounded-full bg-destaque px-5 text-sm font-bold text-sobre-destaque hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
						onclick={() => filtrar(PADRAO)}>Limpar filtros</button
					>
				</div>
			{:else if resultado && resultado.total === 0}
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
