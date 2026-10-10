<script lang="ts">
	import { FAIXAS, PUBLICOS, ROTULO_LOJA } from '#lib/dados.ts';
	import type { Loja } from '#lib/dados.ts';
	import { ROTULO_PUBLICO } from '#lib/formato.ts';
	import { BOTAO_FILTRO, ROTULO_FAIXA, ROTULO_GRUPO, ROTULO_ORDEM } from '#lib/filtros.ts';
	import type { EstadoFiltros, Grupo } from '#lib/filtros.ts';

	/**
	 * Botões de opção dos grupos (BSV-31), fora do bundle inicial: carregados com o painel do
	 * celular ou no primeiro clique num item da linha compacta (BSV-37). `rotuloOculto`: na faixa
	 * do computador o item já nomeia o grupo; o rótulo fica para leitor de tela.
	 */
	let {
		estado,
		grupos,
		aoMudar,
		rotuloOculto = false
	}: {
		estado: EstadoFiltros;
		grupos: (Grupo | 'cupom')[];
		aoMudar: (parcial: Partial<EstadoFiltros>) => void;
		rotuloOculto?: boolean;
	} = $props();

	const LOJAS: Loja[] = ['AMAZON', 'MERCADO_LIVRE', 'SHOPEE'];
	/** `undefined` = "Todos"/"Todas"; ordem e preço não têm. */
	const OPCOES: Record<Grupo, [string | undefined, string][]> = {
		ordem: Object.entries(ROTULO_ORDEM),
		publico: [
			[undefined, 'Todos'],
			...PUBLICOS.map((p): [string, string] => [p, ROTULO_PUBLICO[p]])
		],
		loja: [[undefined, 'Todas'], ...LOJAS.map((l): [string, string] => [l, ROTULO_LOJA[l]])],
		faixa: FAIXAS.map((f): [string, string] => [f, ROTULO_FAIXA[f]])
	};
	const ID: Record<Grupo, string> = {
		ordem: 'filtro-ordem',
		publico: 'filtro-publico',
		loja: 'filtro-loja',
		faixa: 'filtro-preco'
	};
</script>

{#each grupos as g (g)}
	{#if g === 'cupom'}
		<button
			type="button"
			class="{BOTAO_FILTRO} justify-self-start"
			aria-pressed={estado.soComCupom}
			onclick={() => aoMudar({ soComCupom: !estado.soComCupom })}>Só com cupom</button
		>
	{:else}
		{@const atual = estado[g]}
		<div
			class="flex flex-wrap items-center gap-2"
			role="group"
			aria-labelledby={ID[g]}
			data-grupo-filtro
		>
			<span id={ID[g]} class={['text-xs font-bold text-suave', rotuloOculto && 'sr-only']}
				>{ROTULO_GRUPO[g]}</span
			>
			{#each OPCOES[g] as [valor, texto] (texto)}
				<!-- Preço: tocar de novo desmarca. -->
				<button
					type="button"
					class={BOTAO_FILTRO}
					aria-pressed={atual === valor}
					onclick={() => aoMudar({ [g]: g === 'faixa' && atual === valor ? undefined : valor })}
					>{texto}</button
				>
			{/each}
		</div>
	{/if}
{/each}
