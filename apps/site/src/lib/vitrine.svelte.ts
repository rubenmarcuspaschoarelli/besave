// Catálogo vivo do navegador: um por aba, compartilhado pela home e pela lista de desejos.
import { Catalogo, criarSincronizador } from './dados.ts';
// Fora de dados.ts: o barril da camada de dados não pode citar window/document (PUR-01).
import { depsNavegador } from './dados/navegador.ts';
import type { Evento } from './dados.ts';

const MINUTO = 60_000;

class Vitrine {
	readonly cat = new Catalogo();
	/** Muda a cada chunk aplicado: `$derived` que leem o catálogo dependem dela. */
	versao = $state(0);
	pronto = $state(false);
	completo = $state(false);
	/** Manifest ilegível antes da primeira carga. */
	erro = $state(false);
	/** Relógio de "há X h", atualizado a cada minuto. */
	agora = $state(Date.now());
	#iniciada = false;

	iniciar(): void {
		if (this.#iniciada) return;
		this.#iniciada = true;
		this.agora = Date.now();
		setInterval(() => (this.agora = Date.now()), MINUTO);
		const sync = criarSincronizador(
			this.cat,
			depsNavegador((e) => this.#evento(e))
		);
		void sync.iniciar();
	}

	#evento(e: Evento): void {
		if (e.tipo === 'pronto') {
			this.pronto = true;
			this.erro = false;
			this.versao++;
		} else if (e.tipo === 'atualizado') this.versao++;
		else if (e.tipo === 'completo') this.completo = true;
		else if (e.tipo === 'erro' && e.erro === 'manifest' && !this.pronto) this.erro = true;
	}
}

export const vitrine = new Vitrine();
