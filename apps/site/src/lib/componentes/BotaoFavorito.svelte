<script lang="ts">
	import { favoritos } from '#lib/favoritos.svelte.ts';

	let { id }: { id: number } = $props();
	const marcado = $derived(favoritos.tem(id));
</script>

<button
	type="button"
	class="relative z-10 grid size-9 shrink-0 place-items-center rounded-full text-suave hover:bg-superficie hover:text-texto aria-pressed:text-destaque"
	aria-pressed={marcado}
	aria-label="Lista de desejos"
	title={marcado ? 'Tirar da lista de desejos' : 'Guardar na lista de desejos'}
	onclick={() => favoritos.alternar(id)}
>
	<svg
		width="20"
		height="20"
		viewBox="0 0 24 24"
		fill={marcado ? 'currentColor' : 'none'}
		stroke="currentColor"
		stroke-width="2"
		aria-hidden="true"
		><path
			d="M12 20s-7-4.4-9.2-8.6C1.2 8.2 3.1 4.5 6.6 4.5c2.1 0 3.5 1.2 4.4 2.6.9-1.4 2.3-2.6 4.4-2.6 3.5 0 5.4 3.7 3.8 6.9C19 15.6 12 20 12 20Z"
		/></svg
	>
</button>
