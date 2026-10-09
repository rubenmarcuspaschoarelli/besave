<script lang="ts">
	import type { Component, ComponentProps } from 'svelte';
	import type { Faixa, Loja, Ordem, Publico } from '#lib/dados.ts';
	import { PADRAO, foraDoPadrao } from '#lib/filtros.ts';
	import type { EstadoFiltros } from '#lib/filtros.ts';
	import type PainelFiltros from './PainelFiltros.svelte';

	/** `total` = ofertas do resultado (`null` enquanto o catálogo não carregou). */
	let {
		estado,
		total,
		aoMudar
	}: { estado: EstadoFiltros; total: number | null; aoMudar: (e: EstadoFiltros) => void } =
		$props();

	const ORDENS: [Ordem, string][] = [
		['recentes', 'Recentes'],
		['desconto', 'Maior desconto'],
		['preco', 'Menor preço']
	];
	const PUBLICOS: [Publico | undefined, string][] = [
		[undefined, 'Todos'],
		['FEMININO', 'Feminino'],
		['MASCULINO', 'Masculino'],
		['UNISSEX', 'Unissex'],
		['INFANTIL', 'Infantil']
	];
	const LOJAS: [Loja | undefined, string][] = [
		[undefined, 'Todas'],
		['AMAZON', 'Amazon'],
		['MERCADO_LIVRE', 'Mercado Livre'],
		['SHOPEE', 'Shopee']
	];
	const FAIXAS: [Faixa, string][] = [
		['ate50', 'Até R$ 50'],
		['50a100', 'R$ 50–100'],
		['100a200', 'R$ 100–200'],
		['acima200', 'Acima de R$ 200']
	];

	const botao =
		'min-h-11 flex-none rounded-full border border-borda bg-fundo px-3.5 text-[13px] whitespace-nowrap text-texto hover:border-suave focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco aria-pressed:border-marca aria-pressed:bg-marca aria-pressed:text-white';

	const mudar = (parcial: Partial<EstadoFiltros>) => aoMudar({ ...estado, ...parcial });
	const contagem = (n: number) => (n === 1 ? '1 oferta' : `${n.toLocaleString('pt-BR')} ofertas`);

	/**
	 * Painel do celular (< 640 px), em `PainelFiltros`, importado ao tocar em "Filtros" (fora do
	 * bundle inicial da home, BSV-33). Os grupos ficam num lugar só: no painel enquanto aberto,
	 * senão na linha (desktop).
	 */
	let aberto = $state(false);
	let Painel: Component<ComponentProps<typeof PainelFiltros>> | undefined = $state();
	let gatilho: HTMLButtonElement | undefined = $state();

	async function abrir() {
		Painel ??= (await import('./PainelFiltros.svelte')).default;
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
</script>

{#snippet escolhas<T>(
	id: string,
	titulo: string,
	opcoes: [T, string][],
	atual: T,
	campo: keyof EstadoFiltros,
	linha = false
)}
	<!-- `linha`: no celular não quebra e o rótulo some (fica para leitor de tela). -->
	<div
		class={['flex items-center gap-2', linha ? 'flex-none sm:flex-wrap' : 'flex-wrap']}
		role="group"
		aria-labelledby={id}
	>
		<span {id} class={['text-xs font-bold text-suave', linha && 'max-sm:sr-only']}>{titulo}</span>
		{#each opcoes as [valor, texto] (texto)}
			<button
				type="button"
				class={botao}
				aria-pressed={atual === valor}
				onclick={() => mudar({ [campo]: valor })}>{texto}</button
			>
		{/each}
	</div>
{/snippet}

{#snippet grupos()}
	{@render escolhas('filtro-publico', 'Público', PUBLICOS, estado.publico, 'publico')}
	{@render escolhas('filtro-loja', 'Loja', LOJAS, estado.loja, 'loja')}
	<div class="flex flex-wrap items-center gap-2" role="group" aria-labelledby="filtro-preco">
		<span id="filtro-preco" class="text-xs font-bold text-suave">Preço</span>
		{#each FAIXAS as [valor, texto] (valor)}
			<!-- Tocar de novo desmarca. -->
			<button
				type="button"
				class={botao}
				aria-pressed={estado.faixa === valor}
				onclick={() => mudar({ faixa: estado.faixa === valor ? undefined : valor })}>{texto}</button
			>
		{/each}
	</div>
	<button
		type="button"
		class="{botao} justify-self-start"
		aria-pressed={estado.soComCupom}
		onclick={() => mudar({ soComCupom: !estado.soComCupom })}>Só com cupom</button
	>
{/snippet}

<div class="grid gap-3" data-filtros>
	<!-- Celular: "Filtros" + ordem numa linha que rola; desktop: tudo numa linha que quebra. -->
	<div class="relative -mx-3.5 min-w-0 sm:mx-0">
		<div
			class="flex items-center gap-2 overflow-x-auto px-3.5 py-1 [scrollbar-width:none] sm:flex-wrap sm:gap-x-5 sm:gap-y-3 sm:overflow-visible sm:px-0 sm:py-0"
			bind:this={linha}
			onscroll={medirLinha}
			data-linha
		>
			<button
				type="button"
				class="{botao} font-bold sm:hidden"
				aria-expanded={aberto}
				aria-haspopup="dialog"
				bind:this={gatilho}
				onclick={abrir}>Filtros</button
			>
			{@render escolhas('filtro-ordem', 'Ordem', ORDENS, estado.ordem, 'ordem', true)}
			{#if !aberto}
				<div class="hidden sm:contents">{@render grupos()}</div>
			{/if}
		</div>
		<div
			class="pointer-events-none absolute inset-y-0 right-0 w-12 bg-[linear-gradient(to_left,var(--cor-fundo),transparent)] sm:hidden"
			hidden={!mais}
			aria-hidden="true"
			data-mais
		></div>
	</div>

	{#if aberto && Painel}
		<Painel {total} {grupos} {aoFechar} />
	{/if}

	<div class="flex flex-wrap items-center gap-3">
		{#if total !== null}
			<p class="text-sm text-suave" aria-live="polite" data-contagem>{contagem(total)}</p>
		{/if}
		{#if foraDoPadrao(estado)}
			<button
				type="button"
				class="min-h-11 rounded-full px-2 text-sm font-bold text-marca underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
				onclick={() => aoMudar(PADRAO)}>Limpar filtros</button
			>
		{/if}
	</div>
</div>
