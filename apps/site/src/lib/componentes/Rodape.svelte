<script lang="ts">
	import { CONFIG, comLink } from '#lib/config.ts';

	const ROTULO = {
		x: 'X',
		facebook: 'Facebook',
		instagram: 'Instagram',
		youtube: 'YouTube',
		discord: 'Discord',
		android: 'Android',
		ios: 'iOS'
	};
	const redes = comLink(CONFIG.redes);
	const apps = comLink(CONFIG.apps);
	const link = 'underline underline-offset-2 hover:text-white';
</script>

<footer class="bg-rodape text-[13px] text-rodape-texto">
	<div class="mx-auto grid max-w-290 gap-5 px-3.5 py-6 sm:grid-cols-[1.3fr_1fr_1fr] sm:px-5">
		<div>
			<h2 class="mb-2 text-[13px] font-black tracking-wide uppercase">Sobre a Besave</h2>
			<p>
				Ofertas e cupons da Amazon, Mercado Livre e Shopee. Os links são de afiliado: quando você
				compra por eles, a Besave pode receber uma comissão, sem custo extra para você.
			</p>
			<p class="mt-2"><a class={link} href="/desejos/">Lista de desejos</a></p>
		</div>
		<div>
			<h2 class="mb-2 text-[13px] font-black tracking-wide uppercase">Siga-nos</h2>
			<ul class="grid gap-1">
				<li><a class={link} href={CONFIG.canal} rel="noopener">Canal do Telegram</a></li>
				{#each redes as r (r.chave)}
					<li><a class={link} href={r.url} rel="noopener">{ROTULO[r.chave]}</a></li>
				{/each}
			</ul>
		</div>
		<!-- Espaço dos apps (AD-077): só aparece com link. -->
		<div data-apps>
			{#if apps.length > 0}
				<h2 class="mb-2 text-[13px] font-black tracking-wide uppercase">Aplicativos</h2>
				<ul class="grid gap-1">
					{#each apps as a (a.chave)}
						<li><a class={link} href={a.url} rel="noopener">{ROTULO[a.chave]}</a></li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
</footer>
