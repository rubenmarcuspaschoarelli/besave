<script lang="ts">
	import type { Faixa, Loja, Ordem, Publico } from '#lib/dados.ts';
	import { PADRAO, foraDoPadrao } from '#lib/filtros.ts';
	import type { EstadoFiltros } from '#lib/filtros.ts';

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
</script>

{#snippet escolhas<T>(
	id: string,
	titulo: string,
	opcoes: [T, string][],
	atual: T,
	campo: keyof EstadoFiltros
)}
	<div class="flex flex-wrap items-center gap-2" role="group" aria-labelledby={id}>
		<span {id} class="text-xs font-bold text-suave">{titulo}</span>
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

{#snippet ordem()}
	{@render escolhas('filtro-ordem', 'Ordem', ORDENS, estado.ordem, 'ordem')}
{/snippet}

{#snippet filtros()}
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
		class={botao}
		aria-pressed={estado.soComCupom}
		onclick={() => mudar({ soComCupom: !estado.soComCupom })}>Só com cupom</button
	>
{/snippet}

<div class="grid gap-3" data-filtros>
	<div class="flex flex-wrap items-center gap-x-5 gap-y-3">
		{@render ordem()}
		{@render filtros()}
	</div>

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
