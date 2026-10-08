// Lista de desejos no aparelho (AD-076): ids no localStorage, mais recente primeiro.
export const CHAVE_FAVORITOS = 'besave:favoritos';

export interface Armazem {
	getItem(chave: string): string | null;
	setItem(chave: string, valor: string): void;
}

/** Ids válidos (inteiros ≥ 1, sem repetição) de um texto salvo; lixo vira lista vazia. */
function lerIds(texto: string | null): number[] {
	try {
		const v: unknown = JSON.parse(texto ?? '[]');
		if (!Array.isArray(v)) return [];
		return [...new Set(v.filter((x): x is number => Number.isSafeInteger(x) && x >= 1))];
	} catch {
		return [];
	}
}

export class Favoritos {
	ids = $state<number[]>([]);
	#armazem: Armazem | null;

	constructor(armazem: Armazem | null) {
		this.#armazem = armazem;
	}

	/** Lê o armazenamento (no navegador, depois da hidratação). */
	carregar(): void {
		try {
			this.ids = lerIds(this.#armazem?.getItem(CHAVE_FAVORITOS) ?? null);
		} catch {
			this.ids = [];
		}
	}

	get total(): number {
		return this.ids.length;
	}

	tem(id: number): boolean {
		return this.ids.includes(id);
	}

	adicionar(id: number): void {
		if (!this.tem(id)) this.#gravar([id, ...this.ids]);
	}

	remover(id: number): void {
		if (this.tem(id)) this.#gravar(this.ids.filter((x) => x !== id));
	}

	alternar(id: number): void {
		if (this.tem(id)) this.remover(id);
		else this.adicionar(id);
	}

	#gravar(ids: number[]): void {
		this.ids = ids;
		try {
			this.#armazem?.setItem(CHAVE_FAVORITOS, JSON.stringify(ids));
		} catch {
			// Modo privado ou cota cheia: segue só em memória.
		}
	}
}

function localStorageSeguro(): Armazem | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null;
	}
}

export const favoritos = new Favoritos(localStorageSeguro());
