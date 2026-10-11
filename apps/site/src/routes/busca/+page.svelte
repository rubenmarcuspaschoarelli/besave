<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { ativasPrimeiro, buscar, maioresDescontos, normalizar } from '#lib/dados.ts';
	import type { Area, Filtro } from '#lib/dados.ts';
	import { escreverBusca, lerBusca } from '#lib/busca.ts';
	import { passagem } from '#lib/destino-busca.ts';
	import { PADRAO, temFiltro } from '#lib/filtros.ts';
	import type { EstadoFiltros } from '#lib/filtros.ts';
	import { AREAS_MENU, ROTULO_AREA, SLUG_AREA } from '#lib/formato.ts';
	import { vitrine } from '#lib/vitrine.svelte.ts';
	import BarraFiltros from '#lib/componentes/BarraFiltros.svelte';
	import Busca from '#lib/componentes/Busca.svelte';
	import FaixaDescontos from '#lib/componentes/FaixaDescontos.svelte';
	import Grade from '#lib/componentes/Grade.svelte';
	import PaginaOfertas from '#lib/componentes/PaginaOfertas.svelte';

	// `/busca/?q=&area=` + filtros (BSV-34). Prerender sem resultado; tudo no cliente (AD-061).
	const POR_VEZ = 40;
	/** Espera entre teclas antes de trocar a URL (`replaceState`). */
	const ESPERA_MS = 300;
	const AREAS_SUGERIDAS = [...AREAS_MENU, { valor: 'OUTROS' as Area, rotulo: ROTULO_AREA.OUTROS }];

	let q = $state('');
	let area = $state<Area>();
	let filtros = $state<EstadoFiltros>(PADRAO);
	let limite = $state(POR_VEZ);
	/** URL lida (no prerender ainda não há `q`). */
	let lido = $state(false);

	const termo = $derived(q.trim());
	const buscando = $derived(normalizar(q).length >= 2);
	const filtro = $derived<Filtro>({ ...(area ? { area } : {}), ...filtros });
	const resultado = $derived.by(() => {
		void vitrine.versao;
		if (!vitrine.pronto || !buscando) return null;
		const todos = ativasPrimeiro(buscar(vitrine.cat, q, filtro, Infinity).itens);
		return { itens: todos.slice(0, limite), total: todos.length };
	});
	const progresso = $derived.by(() => {
		void vitrine.versao;
		return vitrine.pronto && !vitrine.completo
			? { x: vitrine.cat.ofertasCarregadas, y: vitrine.cat.ofertasTotal }
			: null;
	});
	const faixa = $derived.by(() => {
		void vitrine.versao;
		return vitrine.pronto
			? maioresDescontos(vitrine.cat, vitrine.agora, 8, area ? { area } : {})
			: null;
	});
	const sufixoArea = $derived(area ? ` em ${ROTULO_AREA[area]}` : '');
	const contagem = $derived.by(() => {
		if (!resultado) return 'Buscando…';
		const n = resultado.total;
		if (n === 0) return `Nenhuma oferta para “${termo}”${sufixoArea}`;
		const ofertas = n === 1 ? '1 oferta' : `${n.toLocaleString('pt-BR')} ofertas`;
		return `${ofertas} para “${termo}”${sufixoArea}`;
	});

	let espera: ReturnType<typeof setTimeout> | undefined;
	/** Troca a URL sem entrada nova no histórico; `ja` = sem espera (Enter, filtro, área). */
	function gravar(ja = false) {
		clearTimeout(espera);
		const trocar = () =>
			void goto(escreverBusca(new URL(location.href), { q, area, filtros }), {
				shallow: true,
				replace: true
			});
		if (ja) trocar();
		else espera = setTimeout(trocar, ESPERA_MS);
	}

	function digitar(v: string) {
		q = v;
		limite = POR_VEZ;
		gravar();
	}

	function filtrar(e: EstadoFiltros) {
		filtros = e;
		limite = POR_VEZ;
		gravar(true);
	}

	function tirarArea() {
		area = undefined;
		limite = POR_VEZ;
		gravar(true);
	}

	onMount(() => {
		const e = lerBusca(new URL(location.href).searchParams);
		// Vindo do campo de outra página: o texto (com o que foi digitado na navegação) e o foco.
		const levado = passagem.texto;
		passagem.texto = null;
		q = levado ?? e.q;
		area = e.area;
		filtros = e.filtros;
		lido = true;
		vitrine.iniciar();
		if (levado !== null) {
			scrollTo(0, 0);
			if (levado !== e.q) gravar();
			void tick().then(() => {
				const campo = document.getElementById('busca') as HTMLInputElement | null;
				campo?.focus();
				campo?.setSelectionRange(levado.length, levado.length);
			});
		}
		return () => clearTimeout(espera);
	});
</script>

<svelte:head>
	<title>{termo ? `Busca: ${termo} · Besave` : 'Busca · Besave'}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

{#snippet linksAreas()}
	<nav aria-label="Áreas sugeridas" class="flex flex-wrap gap-2" data-sugestao-areas>
		{#each AREAS_SUGERIDAS as a (a.valor)}
			<a
				class="rounded-full border border-borda bg-fundo px-3.5 py-1.5 text-[13px] text-texto hover:border-suave"
				href="/{SLUG_AREA[a.valor]}/">{a.rotulo}</a
			>
		{/each}
	</nav>
{/snippet}

<!-- Casca da home (barra, topo, rodapé): mesmo grupo de módulos, sem custo no bundle da home. -->
<PaginaOfertas area={null}>
	{#snippet campo()}
		<Busca valor={q} {area} aoMudar={digitar} aoEnviar={() => gravar(true)} />
	{/snippet}
	{#snippet conteudo()}
		<main class="mx-auto grid max-w-290 grid-cols-1 gap-5.5 px-3.5 pt-3.5 pb-8 sm:px-5 sm:pt-4.5">
			{#if vitrine.erro}
				<h1 class="sr-only">Busca</h1>
				<p class="rounded-cartao bg-superficie p-4 text-sm" role="alert">
					Não foi possível carregar as ofertas. Tente de novo em instantes.
				</p>
			{:else if lido && !buscando}
				<section class="grid gap-3" data-sugestoes>
					<h1 class="text-lg leading-tight font-black text-marca">Buscar ofertas</h1>
					<p class="text-sm text-suave">Digite pelo menos 2 letras ou escolha uma área.</p>
					{@render linksAreas()}
				</section>
				<FaixaDescontos cards={faixa} />
			{:else}
				<section aria-labelledby="titulo-busca" class="grid grid-cols-1 gap-3">
					<BarraFiltros estado={filtros} total={resultado?.total ?? null} aoMudar={filtrar}>
						{#snippet titulo()}
							<h1
								id="titulo-busca"
								class="mr-auto text-lg leading-tight font-black text-marca"
								aria-live="polite"
								data-resultado
							>
								{lido ? contagem : 'Buscando…'}
							</h1>
						{/snippet}
					</BarraFiltros>
					{#if area}
						<button
							type="button"
							class="min-h-11 justify-self-start rounded-full border border-borda px-4 text-sm font-semibold text-texto hover:border-suave"
							onclick={tirarArea}>Buscar em todas as áreas</button
						>
					{/if}
					{#if progresso}
						<p class="text-sm text-suave" data-progresso>
							Buscando em {progresso.x.toLocaleString('pt-BR')} de {progresso.y.toLocaleString(
								'pt-BR'
							)} ofertas…
						</p>
					{/if}
					{#if resultado && resultado.total === 0}
						{#if !progresso}
							<div class="grid justify-items-start gap-3" data-vazio>
								<p class="text-sm text-suave">Confira a grafia · Use menos palavras</p>
								{#if temFiltro(filtros)}
									<button
										type="button"
										class="min-h-11 rounded-full bg-destaque px-5 text-sm font-bold text-sobre-destaque hover:brightness-95"
										onclick={() => filtrar(PADRAO)}>Limpar filtros</button
									>
								{/if}
								{@render linksAreas()}
							</div>
						{/if}
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
	{/snippet}
</PaginaOfertas>
