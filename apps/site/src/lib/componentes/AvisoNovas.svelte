<script lang="ts">
	import { tick } from 'svelte';
	import type { Area } from '#lib/dados.ts';
	import { tituloComNovas, vitrine } from '#lib/vitrine.svelte.ts';

	/** `null` na home: conta todas; numa área, só as dela. */
	let { area }: { area: Area | null } = $props();

	const n = $derived(vitrine.novasEm(area));
	let topo = $state(0);

	$effect(() => {
		const el = document.querySelector<HTMLElement>('[data-topo]');
		if (!el) return;
		const medir = () => (topo = el.offsetHeight);
		medir();
		const ro = new ResizeObserver(medir);
		ro.observe(el);
		return () => ro.disconnect();
	});

	$effect(() => {
		const total = n;
		const base = document.title;
		document.title = tituloComNovas(base, total);
		return () => (document.title = tituloComNovas(document.title, 0));
	});

	async function mostrar() {
		vitrine.confirmarNovas();
		await tick();
		const titulo = document.getElementById('titulo-recentes');
		if (!titulo) return;
		titulo.tabIndex = -1;
		const suave = !matchMedia('(prefers-reduced-motion: reduce)').matches;
		const y = titulo.getBoundingClientRect().top + scrollY - topo - 12;
		scrollTo({ top: Math.max(0, y), behavior: suave ? 'smooth' : 'instant' });
		titulo.focus({ preventScroll: true });
	}
</script>

<div
	class="pointer-events-none sticky z-10 flex h-0 items-start justify-center"
	style:top="{topo}px"
	aria-live="polite"
	data-aviso-novas
>
	{#if n > 0}
		<button
			type="button"
			class="pointer-events-auto mt-2 rounded-full bg-destaque px-4 py-2 text-sm font-bold text-sobre-destaque shadow-lg hover:brightness-95"
			onclick={mostrar}
			>{n === 1 ? '1 nova oferta' : `${n.toLocaleString('pt-BR')} novas ofertas`}</button
		>
	{/if}
</div>
