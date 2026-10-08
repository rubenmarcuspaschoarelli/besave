<script lang="ts" module>
	/** Lida antes da pintura por um script em app.html (sem piscar ao recarregar). */
	export const CHAVE_BARRA = 'besave:barra-canal';
</script>

<script lang="ts">
	import { CONFIG } from '#lib/config.ts';

	function fechar() {
		document.documentElement.dataset.barraFechada = '';
		try {
			localStorage.setItem(CHAVE_BARRA, 'fechada');
		} catch {
			// Sem localStorage: fecha só nesta página.
		}
	}
</script>

<div
	class="relative flex items-center justify-center bg-marca py-2 pr-11 pl-3.5 text-center text-xs text-white sm:text-[13px] [html[data-barra-fechada]_&]:hidden"
	data-barra-canal
>
	<p>
		Receba as ofertas primeiro no nosso
		<a class="font-bold underline underline-offset-2" href={CONFIG.canal} rel="noopener"
			>canal do Telegram</a
		>
	</p>
	<button
		type="button"
		class="absolute top-1/2 right-1.5 grid size-8 -translate-y-1/2 place-items-center rounded-full text-lg leading-none hover:bg-marca-escura"
		aria-label="Fechar aviso do canal"
		onclick={fechar}>×</button
	>
</div>
