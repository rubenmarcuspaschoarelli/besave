import { defineConfig, devices } from '@playwright/test';

// Fluxos da BSV-30 sobre o build (`pnpm build` antes). Manifest e chunks vêm de e2e/fixtura.ts.
export default defineConfig({
	testDir: 'e2e',
	fullyParallel: true,
	retries: 0,
	use: { baseURL: 'http://localhost:4173', trace: 'retain-on-failure' },
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
		command: 'npm run preview -- --port 4173 --strictPort',
		port: 4173,
		reuseExistingServer: !process.env.CI
	}
});
