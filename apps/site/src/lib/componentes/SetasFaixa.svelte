<script lang="ts">
	import { onMount, tick } from 'svelte';

	/**
	 * Setas ‹ › da faixa de descontos (BSV-37), importadas só com ponteiro fino e hover, ao
	 * lado do trilho `[data-faixa]`. Cada clique rola uma largura visível; a seta some no
	 * início/fim. Remede ao rolar, ao mudar de tamanho e quando os cards chegam.
	 */
	let trilho: HTMLElement;

	let inicio = $state(true);
	let fim = $state(true);
	let antes: HTMLButtonElement | undefined = $state();
	let depois: HTMLButtonElement | undefined = $state();

	function medir() {
		const focada = document.activeElement;
		inicio = trilho.scrollLeft <= 1;
		fim = trilho.scrollLeft + trilho.clientWidth >= trilho.scrollWidth - 1;
		// A seta com foco some na borda: o foco passa para a outra (já visível depois do tick).
		const outra = inicio && focada === antes ? depois : fim && focada === depois ? antes : null;
		if (outra && !(inicio && fim)) void tick().then(() => outra.focus());
	}

	onMount(() => {
		trilho = antes?.parentElement?.querySelector<HTMLElement>('[data-faixa]') as HTMLElement;
		medir();
		trilho.addEventListener('scroll', medir, { passive: true });
		const ro = new ResizeObserver(medir);
		ro.observe(trilho);
		const mo = new MutationObserver(medir);
		mo.observe(trilho, { childList: true });
		return () => {
			trilho.removeEventListener('scroll', medir);
			ro.disconnect();
			mo.disconnect();
		};
	});

	function rolar(sentido: 1 | -1) {
		const suave = !matchMedia('(prefers-reduced-motion: reduce)').matches;
		trilho.scrollBy({ left: sentido * trilho.clientWidth, behavior: suave ? 'smooth' : 'instant' });
	}

	const seta =
		'absolute top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-full border border-borda bg-fundo text-2xl leading-none text-marca shadow-lg hover:bg-superficie';
</script>

<button
	type="button"
	class="{seta} left-0"
	aria-label="Ver descontos anteriores"
	hidden={inicio}
	bind:this={antes}
	onclick={() => rolar(-1)}
	data-seta="anterior">‹</button
>
<button
	type="button"
	class="{seta} right-0"
	aria-label="Ver descontos seguintes"
	hidden={fim}
	bind:this={depois}
	onclick={() => rolar(1)}
	data-seta="seguinte">›</button
>
