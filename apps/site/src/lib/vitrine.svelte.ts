// Catálogo vivo do navegador: um por aba, compartilhado pela home e pela lista de desejos.
import { Catalogo, criarSincronizador } from './dados.ts';
// Fora de dados.ts: o barril da camada de dados não pode citar window/document (PUR-01).
import { depsNavegador } from './dados/navegador.ts';
import type { Area, Evento } from './dados.ts';

const MINUTO = 60_000;

/** "(N) " antes do título da aba enquanto há ofertas novas pendentes. */
export function tituloComNovas(titulo: string, n: number): string {
	const base = titulo.replace(/^\(\d+\) /, '');
	return n > 0 ? `(${n}) ${base}` : base;
}

export class Vitrine {
	readonly cat = new Catalogo();
	/** Muda a cada chunk aplicado: `$derived` que leem o catálogo dependem dela. */
	versao = $state(0);
	pronto = $state(false);
	completo = $state(false);
	/** Manifest ilegível antes da primeira carga. */
	erro = $state(false);
	/** Relógio de "há X h", atualizado a cada minuto. */
	agora = $state(Date.now());
	/** Pendentes (AD-063) no total e por área; recontados quando o sincronizador avisa. */
	novasTotal = $state(0);
	#novasPorArea = $state<Record<string, number>>({});
	#iniciada = false;

	/** Novas pendentes: da `area`, ou todas na home (`null`). */
	novasEm(area: Area | null): number {
		return area ? (this.#novasPorArea[area] ?? 0) : this.novasTotal;
	}

	/** Pendente = card ativo no catálogo que a lista ainda não mostra. */
	recontarNovas(): void {
		const total = this.cat.novas();
		const porArea: Record<string, number> = {};
		if (total > 0) {
			const visiveis: Record<number, true> = {};
			for (const c of this.cat.lista({ mostrarExpiradas: true })) visiveis[c.id] = true;
			for (const { cards } of this.cat.trechos())
				for (const c of cards) if (!c.x && !visiveis[c.id]) porArea[c.a] = (porArea[c.a] ?? 0) + 1;
		}
		this.novasTotal = total;
		this.#novasPorArea = porArea;
	}

	/** Coloca as pendentes no início da lista. */
	confirmarNovas(): void {
		this.cat.confirmarNovas();
		this.recontarNovas();
		this.versao++;
	}

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
		} else if (e.tipo === 'atualizado') {
			this.versao++;
			this.recontarNovas();
		} else if (e.tipo === 'novas') this.recontarNovas();
		else if (e.tipo === 'completo') this.completo = true;
		else if (e.tipo === 'erro' && e.erro === 'manifest' && !this.pronto) this.erro = true;
	}
}

export const vitrine = new Vitrine();
