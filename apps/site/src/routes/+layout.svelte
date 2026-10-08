<script lang="ts">
	import { onMount } from 'svelte';
	import { CHAVE_FAVORITOS, favoritos } from '#lib/favoritos.svelte.ts';
	import '../app.css';

	let { children } = $props();

	onMount(() => {
		favoritos.carregar();
		const outraAba = (e: StorageEvent) => {
			if (e.key === CHAVE_FAVORITOS) favoritos.carregar();
		};
		addEventListener('storage', outraAba);
		return () => removeEventListener('storage', outraAba);
	});
</script>

{@render children()}
