<script lang="ts">
	import type { Snippet } from 'svelte';
	import {
		BOTAO_FILTRO,
		ROTULO_ORDEM,
		PADRAO,
		ROTULO_GRUPO,
		foraDoPadrao,
		valorEscolhido
	} from '#lib/filtros.ts';
	import type { Ordem } from '#lib/dados.ts';
	import type { EstadoFiltros, Grupo } from '#lib/filtros.ts';

	/** `total` = ofertas do resultado (`null` enquanto o catálogo não carregou). */
	let {
		estado,
		total,
		aoMudar,
		titulo
	}: {
		estado: EstadoFiltros;
		total: number | null;
		aoMudar: (e: EstadoFiltros) => void;
		titulo: Snippet;
	} = $props();

	const ITENS = Object.entries(ROTULO_GRUPO) as [Grupo, string][];
	const ORDENS = Object.entries(ROTULO_ORDEM) as [Ordem, string][];

	const mudar = (parcial: Partial<EstadoFiltros>) => aoMudar({ ...estado, ...parcial });
	const contagem = (n: number) => (n === 1 ? '1 oferta' : `${n.toLocaleString('pt-BR')} ofertas`);

	/**
	 * < 1024 px: "Filtros" + painel (BSV-31); ≥ 1024 px: linha compacta (BSV-37). O prerender
	 * traz as duas (CSS escolhe); depois de montar, só a do tamanho atual fica no DOM. No
	 * estreito os grupos ficam no DOM, ocultos, com o painel fechado, como na BSV-31.
	 */
	let largo = $state<boolean>();
	$effect(() => {
		const mq = matchMedia('(min-width: 64rem)');
		const medir = () => {
			largo = mq.matches;
			if (mq.matches) aberto = false;
			else {
				aberta = undefined;
				void carregar();
			}
		};
		medir();
		mq.addEventListener('change', medir);
		return () => mq.removeEventListener('change', medir);
	});

	/** Painel, faixas e grupos: importados no primeiro uso (fora do bundle inicial). */
	let sob = $state<typeof import('./filtros-sob-demanda.ts')>();
	const carregar = async () => (sob ??= await import('./filtros-sob-demanda.ts'));

	let aberto = $state(false);
	let gatilho: HTMLButtonElement | undefined = $state();

	async function abrir() {
		await carregar();
		aberto = true;
	}

	/** Esc, fundo ou "Ver N ofertas". */
	function aoFechar() {
		aberto = false;
		gatilho?.focus();
	}

	/** Linha "Filtros"/ordem do celular: degradê à direita enquanto há o que rolar. */
	let linha: HTMLDivElement | undefined = $state();
	let mais = $state(false);
	const medirLinha = () => {
		if (linha) mais = linha.scrollLeft + linha.clientWidth < linha.scrollWidth - 1;
	};
	$effect(() => {
		if (!linha) return;
		const ro = new ResizeObserver(medirLinha);
		ro.observe(linha);
		return () => ro.disconnect();
	});

	/** Computador: item com a faixa aberta (uma por vez); a faixa vem no primeiro clique. */
	let aberta = $state<Grupo>();
	let compacta: HTMLDivElement | undefined = $state();

	async function alternar(g: Grupo) {
		await carregar();
		aberta = aberta === g ? undefined : g;
	}

	function fechar(focar: boolean) {
		if (focar) compacta?.querySelector<HTMLElement>(`[data-item="${aberta}"]`)?.focus();
		aberta = undefined;
	}

	const limpar = 'min-h-11 rounded-full px-2 text-sm font-bold text-marca underline';
</script>

<div class="grid gap-3" data-filtros>
	<div class="flex flex-wrap items-center gap-3">
		{@render titulo()}
		{#if largo !== false}
			<div class="hidden flex-wrap items-center gap-2 lg:flex" bind:this={compacta} data-compacta>
				{#each ITENS as [g, nome] (g)}
					{@const valor = valorEscolhido(estado, g)}
					<button
						type="button"
						class={[
							BOTAO_FILTRO,
							'flex items-center gap-1 aria-expanded:border-marca data-escolhido:border-marca'
						]}
						aria-expanded={aberta === g}
						aria-controls="faixa-filtros"
						data-item={g}
						data-escolhido={g !== 'ordem' && valor ? '' : undefined}
						onclick={() => alternar(g)}
						>{valor ? `${nome}: ${valor}` : nome}<span class="text-[10px]" aria-hidden="true"
							>▾</span
						></button
					>
				{/each}
				<!-- Interruptor: botão alternado (BSV-31) desenhado como trilho + bolinha. -->
				<button
					type="button"
					class="group flex min-h-11 items-center gap-2 rounded-full px-2 text-[13px] whitespace-nowrap"
					aria-pressed={estado.soComCupom}
					onclick={() => mudar({ soComCupom: !estado.soComCupom })}
					><span
						class="flex h-6 w-12 rounded-full bg-suave p-0.5 group-aria-pressed:justify-end group-aria-pressed:bg-marca"
						aria-hidden="true"><span class="size-5 rounded-full bg-white"></span></span
					>Só com cupom</button
				>
				{#if foraDoPadrao(estado)}
					<button type="button" class={limpar} onclick={() => aoMudar(PADRAO)}
						>Limpar filtros</button
					>
				{/if}
			</div>
		{/if}
	</div>

	{#if aberta && sob}
		<sob.FaixaFiltros
			grupo={aberta}
			{estado}
			aoEscolher={(p) => {
				fechar(true);
				mudar(p);
			}}
			aoFechar={fechar}
		/>
	{/if}

	{#if !largo}
		<!-- Celular e tablet: "Filtros" + ordem numa linha que rola. -->
		<div class="relative -mx-3.5 min-w-0 sm:mx-0 lg:hidden">
			<div
				class="flex items-center gap-2 overflow-x-auto px-3.5 py-1 [scrollbar-width:none] sm:px-0"
				bind:this={linha}
				onscroll={medirLinha}
				data-linha
			>
				<button
					type="button"
					class={[BOTAO_FILTRO, 'font-bold']}
					aria-expanded={aberto}
					aria-haspopup="dialog"
					bind:this={gatilho}
					onclick={abrir}>Filtros</button
				>
				<div class="flex flex-none items-center gap-2" role="group" aria-labelledby="filtro-ordem">
					<span id="filtro-ordem" class="sr-only">Ordem</span>
					{#each ORDENS as [valor, texto] (valor)}
						<button
							type="button"
							class={BOTAO_FILTRO}
							aria-pressed={estado.ordem === valor}
							onclick={() => mudar({ ordem: valor })}>{texto}</button
						>
					{/each}
				</div>
			</div>
			<div
				class="pointer-events-none absolute inset-y-0 right-0 w-12 bg-[linear-gradient(to_left,var(--cor-fundo),transparent)]"
				hidden={!mais}
				aria-hidden="true"
				data-mais
			></div>
		</div>

		{#if !aberto && sob}
			<div hidden>
				<sob.GruposFiltros
					{estado}
					grupos={['publico', 'loja', 'faixa', 'cupom']}
					aoMudar={mudar}
				/>
			</div>
		{/if}
		{#if aberto && sob}
			<sob.PainelFiltros {total} {estado} aoMudar={mudar} {aoFechar} />
		{/if}
	{/if}

	<!-- No computador o total visível é o do título; aqui fica o anúncio para leitor de tela. -->
	<div class={['flex flex-wrap items-center gap-3', largo && 'sr-only']}>
		{#if total !== null}
			<p class="text-sm text-suave" aria-live="polite" data-contagem>{contagem(total)}</p>
		{/if}
		{#if foraDoPadrao(estado) && !largo}
			<button type="button" class={limpar} onclick={() => aoMudar(PADRAO)}>Limpar filtros</button>
		{/if}
	</div>
</div>
