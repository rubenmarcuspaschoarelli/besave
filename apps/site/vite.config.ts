import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// Sem fallback SPA (AD-020): toda rota é prerenderizada.
			adapter: adapter({ pages: 'build', assets: 'build', fallback: undefined, strict: true })
		})
	],
	test: {
		expect: { requireAssertions: true },
		environment: 'node',
		include: ['src/**/*.test.ts'],
		testTimeout: 30_000
	}
});
