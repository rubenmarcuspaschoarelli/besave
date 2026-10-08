// Deps do sincronizador no navegador: o único lugar do site que chama fetch (CLAUDE.md do site).
import type { Deps, Evento } from './sincronizador.ts';

export function depsNavegador(aoEvento: (e: Evento) => void): Deps {
	return {
		fetch: (url, init) => fetch(url, init),
		agora: () => Date.now(),
		agendar: (cb, ms) => setTimeout(cb, ms),
		cancelar: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
		ocioso:
			typeof requestIdleCallback === 'function'
				? (cb) => void requestIdleCallback(() => cb(), { timeout: 2000 })
				: undefined,
		visivel: () => document.visibilityState === 'visible',
		aoMudarVisibilidade: (cb) => {
			document.addEventListener('visibilitychange', cb);
			return () => document.removeEventListener('visibilitychange', cb);
		},
		aoEvento
	};
}
