<script lang="ts">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';

	/**
	 * Painel do celular (< 640 px), carregado só ao tocar em "Filtros" (bundle da home, BSV-33):
	 * `<dialog>` modal, que deixa o fundo inerte e prende o foco. `grupos` vem da barra.
	 */
	let { total, grupos, aoFechar }: { total: number | null; grupos: Snippet; aoFechar: () => void } =
		$props();

	let dialogo: HTMLDialogElement | undefined = $state();

	const contagem = (n: number) => (n === 1 ? '1 oferta' : `${n.toLocaleString('pt-BR')} ofertas`);

	onMount(() => {
		dialogo?.showModal();
		dialogo?.querySelector('button')?.focus();
	});

	/** O modal já deixa o fundo inerte; o Tab do último botão daria a volta pela barra do navegador. */
	function cicloTab(e: KeyboardEvent) {
		if (e.key !== 'Tab' || !dialogo) return;
		const botoes = [...dialogo.querySelectorAll('button')];
		const alvo = e.shiftKey ? botoes[botoes.length - 1] : botoes[0];
		const borda = e.shiftKey ? botoes[0] : botoes[botoes.length - 1];
		if (document.activeElement === borda) {
			e.preventDefault();
			alvo.focus();
		}
	}

	/** Toque fora da folha (no `::backdrop`) fecha. */
	function tocouFora(e: MouseEvent) {
		if (!dialogo || e.target !== dialogo) return;
		const r = dialogo.getBoundingClientRect();
		const dentro =
			e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
		if (!dentro) dialogo.close();
	}
</script>

<!-- Esc (evento `close` nativo), fundo ou "Ver N ofertas" fecham. -->
<dialog
	bind:this={dialogo}
	aria-label="Filtros"
	class="m-0 mt-auto max-h-[85vh] w-full max-w-none gap-4 overflow-y-auto rounded-t-2xl bg-fundo px-4 pt-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-texto shadow-2xl backdrop:bg-black/40 open:grid sm:hidden"
	onclose={aoFechar}
	onclick={tocouFora}
	onkeydown={cicloTab}
>
	<p class="text-lg font-black text-marca">Filtros</p>
	{@render grupos()}
	<button
		type="button"
		class="min-h-11 rounded-full bg-destaque px-5 text-sm font-bold text-sobre-destaque hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
		onclick={() => dialogo?.close()}
		>{total === null ? 'Ver ofertas' : `Ver ${contagem(total)}`}</button
	>
</dialog>
