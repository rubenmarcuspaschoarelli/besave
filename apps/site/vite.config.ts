import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// Sem fallback SPA (AD-020): toda rota é prerenderizada.
			adapter: adapter({ pages: 'build', assets: 'build', fallback: undefined, strict: true }),
			// A 404.html é servida em qualquer path: assets sempre a partir da raiz.
			paths: { relative: false }
		})
	],
	// sincronizador.ts lê a versão do contrato em packages/contract (regra 4).
	server: { fs: { allow: ['../../packages/contract'] } },
	test: {
		// besave-css.test.ts lê o CSS processado (imports resolvidos), como no build.
		css: { include: [/estilo[/\\]besave\.css/] },
		expect: { requireAssertions: true },
		environment: 'node',
		// Orçamentos de tempo (desempenho.test.ts) não podem disputar CPU com outros arquivos.
		fileParallelism: false,
		include: ['src/**/*.test.ts'],
		testTimeout: 30_000
	}
});
