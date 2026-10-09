<script lang="ts">
	import { tick } from 'svelte';
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

	/**
	 * Painel do celular (< 640 px): `<dialog>` modal, que deixa o fundo inerte e prende o foco.
	 * Os grupos ficam num lugar só: no diálogo enquanto aberto, senão na linha (desktop).
	 */
	let aberto = $state(false);
	let dialogo: HTMLDialogElement | undefined = $state();
	let gatilho: HTMLButtonElement | undefined = $state();

	async function abrir() {
		aberto = true;
		await tick();
		dialogo?.showModal();
		dialogo?.querySelector('button')?.focus();
	}

	/** Esc (evento `close` nativo), fundo ou "Ver N ofertas". */
	function aoFechar() {
		aberto = false;
		gatilho?.focus();
	}

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

{#snippet escolhas<T>(
	id: string,
	titulo: string,
	opcoes: [T, string][],
	atual: T,
	campo: keyof EstadoFiltros,
	linha = false
)}
	<!-- `linha`: no celular não quebra e o rótulo some (fica para leitor de tela). -->
	<div
		class={['flex items-center gap-2', linha ? 'flex-none sm:flex-wrap' : 'flex-wrap']}
		role="group"
		aria-labelledby={id}
	>
		<span {id} class={['text-xs font-bold text-suave', linha && 'max-sm:sr-only']}>{titulo}</span>
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

{#snippet grupos()}
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
		class="{botao} justify-self-start"
		aria-pressed={estado.soComCupom}
		onclick={() => mudar({ soComCupom: !estado.soComCupom })}>Só com cupom</button
	>
{/snippet}

<div class="grid gap-3" data-filtros>
	<!-- Celular: "Filtros" + ordem numa linha que rola; desktop: tudo numa linha que quebra. -->
	<div
		class="-mx-3.5 flex items-center gap-2 overflow-x-auto px-3.5 py-1 [scrollbar-width:none] sm:mx-0 sm:py-0 sm:flex-wrap sm:gap-x-5 sm:gap-y-3 sm:overflow-visible sm:px-0"
	>
		<button
			type="button"
			class="{botao} font-bold sm:hidden"
			aria-expanded={aberto}
			aria-haspopup="dialog"
			bind:this={gatilho}
			onclick={abrir}>Filtros</button
		>
		{@render escolhas('filtro-ordem', 'Ordem', ORDENS, estado.ordem, 'ordem', true)}
		{#if !aberto}
			<div class="hidden sm:contents">{@render grupos()}</div>
		{/if}
	</div>

	<dialog
		bind:this={dialogo}
		aria-label="Filtros"
		class="m-0 mt-auto max-h-[85vh] w-full max-w-none gap-4 overflow-y-auto rounded-t-2xl bg-fundo px-4 pt-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-texto shadow-2xl backdrop:bg-black/40 open:grid sm:hidden"
		onclose={aoFechar}
		onclick={tocouFora}
		onkeydown={cicloTab}
	>
		{#if aberto}
			<p class="text-lg font-black text-marca">Filtros</p>
			{@render grupos()}
			<button
				type="button"
				class="min-h-11 rounded-full bg-destaque px-5 text-sm font-bold text-sobre-destaque hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
				onclick={() => dialogo?.close()}
				>{total === null ? 'Ver ofertas' : `Ver ${contagem(total)}`}</button
			>
		{/if}
	</dialog>

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
