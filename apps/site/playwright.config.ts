import { defineConfig, devices } from '@playwright/test';

// Fluxos da BSV-30 sobre o build (`pnpm build` antes). Manifest e chunks vêm de e2e/fixtura.ts.
// Nunca reaproveita servidor: outro worktree na mesma porta seria testado no lugar deste build
// (BSV-37). Porta ocupada falha; `E2E_PORTA=4187 pnpm e2e` roda em outra.
const PORTA = Number(process.env.E2E_PORTA ?? 4173);

export default defineConfig({
	testDir: 'e2e',
	fullyParallel: true,
	retries: 0,
	use: { baseURL: `http://localhost:${PORTA}`, trace: 'retain-on-failure' },
	projects: [
		{
			name: 'celular',
			use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } }
		},
		{
			name: 'desktop',
			use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } }
		}
	],
	webServer: {
		command: `npm run preview -- --port ${PORTA} --strictPort`,
		port: PORTA,
		reuseExistingServer: false
	}
});
