<script lang="ts">
	/** Na home filtra a grade (`aoMudar`); fora dela envia `/?q=` (GET). */
	let { valor = '', aoMudar }: { valor?: string; aoMudar?: (q: string) => void } = $props();
</script>

<form
	role="search"
	action="/"
	method="get"
	class="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-borda bg-superficie px-4 py-2 text-suave focus-within:border-suave"
	onsubmit={(e) => {
		if (aoMudar) e.preventDefault();
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
		oninput={(e) => aoMudar?.(e.currentTarget.value)}
	/>
</form>
