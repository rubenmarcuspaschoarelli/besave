<script lang="ts">
	import { goto } from '$app/navigation';
	import { normalizar } from '#lib/dados.ts';
	import type { Area } from '#lib/dados.ts';
	import { destinoBusca, passagem } from '#lib/destino-busca.ts';

	/**
	 * Fora da `/busca/`: 2+ caracteres (ou Enter) levam a `/busca/?q=` (`&area=` na página de
	 * área), com o texto e o foco. Na `/busca/`, `aoMudar` recebe cada tecla e `aoEnviar` o Enter.
	 * Sem JS, GET `/busca/?q=` (a página de busca precisa de JS de qualquer jeito) (BSV-34).
	 */
	let {
		valor = '',
		area = null,
		aoMudar,
		aoEnviar
	}: {
		valor?: string;
		area?: Area | null;
		aoMudar?: (q: string) => void;
		aoEnviar?: () => void;
	} = $props();

	/** Teclas durante a navegação só atualizam o texto levado. */
	function ir(q: string) {
		const indo = passagem.texto !== null;
		passagem.texto = q;
		if (indo) return;
		goto(destinoBusca(q, area), { reset: false }).catch(() => (passagem.texto = null));
	}
</script>

<form
	role="search"
	action="/busca/"
	method="get"
	class="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-borda bg-superficie px-4 py-2 text-suave focus-within:border-suave"
	onsubmit={(e) => {
		e.preventDefault();
		if (aoEnviar) aoEnviar();
		else ir(new FormData(e.currentTarget).get('q')?.toString() ?? '');
	}}
>
	<svg
		class="flex-none"
		width="17"
		height="17"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg
	>
	<label class="sr-only" for="busca">Buscar ofertas</label>
	<input
		id="busca"
		name="q"
		type="search"
		autocomplete="off"
		placeholder="Buscar ofertas, marcas e lojas"
		class="w-full min-w-0 bg-transparent text-sm text-texto outline-none placeholder:text-suave"
		value={valor}
		oninput={(e) => {
			const v = e.currentTarget.value;
			if (aoMudar) aoMudar(v);
			else if (passagem.texto !== null || normalizar(v).length >= 2) ir(v);
		}}
	/>
</form>
