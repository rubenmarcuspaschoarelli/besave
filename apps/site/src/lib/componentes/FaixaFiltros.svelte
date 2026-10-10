<script lang="ts">
	import { onMount } from 'svelte';
	import type { EstadoFiltros, Grupo } from '#lib/filtros.ts';
	import GruposFiltros from './GruposFiltros.svelte';

	/**
	 * Faixa de opções do item aberto na linha compacta (BSV-37), importada no primeiro clique.
	 * Esc ou clique fora chamam `aoFechar(true)` (foco volta ao item); clique fora que já pôs o
	 * foco em outro lugar (busca, link) chama `aoFechar(false)`.
	 */
	let {
		grupo,
		estado,
		aoEscolher,
		aoFechar
	}: {
		grupo: Grupo;
		estado: EstadoFiltros;
		aoEscolher: (parcial: Partial<EstadoFiltros>) => void;
		aoFechar: (focar: boolean) => void;
	} = $props();

	let faixa: HTMLDivElement | undefined = $state();

	onMount(() => {
		const linha = faixa?.closest('[data-filtros]')?.querySelector('[data-compacta]');
		const tecla = (e: KeyboardEvent) => {
			if (e.key === 'Escape') aoFechar(true);
		};
		const clique = (e: MouseEvent) => {
			const alvo = e.target as Node;
			if (!alvo.isConnected || linha?.contains(alvo) || faixa?.contains(alvo)) return;
			const a = document.activeElement;
			aoFechar(!a || a === document.body);
		};
		document.addEventListener('keydown', tecla);
		document.addEventListener('click', clique);
		return () => {
			document.removeEventListener('keydown', tecla);
			document.removeEventListener('click', clique);
		};
	});
</script>

<div
	id="faixa-filtros"
	class="rounded-cartao bg-superficie p-4"
	bind:this={faixa}
	data-faixa-filtros
>
	<GruposFiltros {estado} grupos={[grupo]} aoMudar={aoEscolher} rotuloOculto />
</div>
