<script lang="ts">
	import type { Snippet } from 'svelte';
	import { CONFIG, botoesLigados } from '#lib/config.ts';
	import { favoritos } from '#lib/favoritos.svelte.ts';

	/** `busca` e `areas` vêm da página (a home liga os filtros; as outras navegam). */
	let { busca, areas }: { busca: Snippet; areas: Snippet } = $props();

	const BOTAO = {
		postar: { rotulo: 'Postar oferta', d: 'M12 5v14M5 12h14' },
		notificacoes: {
			rotulo: 'Notificações',
			d: 'M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15ZM10 20a2 2 0 0 0 4 0'
		},
		entrar: {
			rotulo: 'Entrar',
			d: 'M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5'
		}
	};
	const futuros = botoesLigados(CONFIG.flags);
	const icone =
		'relative grid size-9 place-items-center rounded-full text-suave hover:bg-superficie hover:text-texto';
</script>

<header class="sticky top-0 z-10 border-b border-borda bg-fundo" data-topo>
	<div
		class="mx-auto flex max-w-290 flex-wrap items-center gap-x-2 gap-y-2.5 px-3.5 py-2.5 sm:flex-nowrap sm:gap-4.5 sm:px-5 sm:py-3"
	>
		<a
			class="mr-auto flex-none font-titulo text-[1.3rem] leading-none font-black tracking-tight text-marca sm:mr-0 sm:text-[1.45rem]"
			href="/">Besave</a
		>
		<div class="order-3 flex basis-full sm:order-none sm:basis-auto sm:flex-1">
			{@render busca()}
		</div>
		<div class="flex flex-none gap-1" data-icones>
			{#each futuros as f (f)}
				<button type="button" class={icone} aria-label={BOTAO[f].rotulo}>
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						aria-hidden="true"><path d={BOTAO[f].d} /></svg
					>
				</button>
			{/each}
			<a class={icone} href="/desejos/" aria-label="Lista de desejos" title="Lista de desejos">
				<svg
					width="20"
					height="20"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"
					><path
						d="M12 20s-7-4.4-9.2-8.6C1.2 8.2 3.1 4.5 6.6 4.5c2.1 0 3.5 1.2 4.4 2.6.9-1.4 2.3-2.6 4.4-2.6 3.5 0 5.4 3.7 3.8 6.9C19 15.6 12 20 12 20Z"
					/></svg
				>
				{#if favoritos.total > 0}
					<span
						class="absolute top-0.5 right-0.5 h-4 min-w-4 rounded-full bg-destaque px-1 text-center text-[10px] leading-4 font-bold text-sobre-destaque"
						data-contador>{favoritos.total}</span
					>
				{/if}
			</a>
			<a
				class={icone}
				href={CONFIG.canal}
				rel="noopener"
				aria-label="Canal do Telegram"
				title="Canal do Telegram"
			>
				<svg
					width="20"
					height="20"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"><path d="m21 4-18 7 6 2 2 6 3-4 5 4Z" /><path d="m9 13 8-6" /></svg
				>
			</a>
		</div>
	</div>
	{@render areas()}
</header>
