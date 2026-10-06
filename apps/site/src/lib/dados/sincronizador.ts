// Sincroniza o Catalogo com manifest.json (MANIFEST §3.1, AD-062). Sem window/document:
// tudo que é do navegador entra por Deps.
import contrato from '../../../../../packages/contract/package.json' with { type: 'json' };
import type { Catalogo } from './catalogo.ts';
import { ehChunk, ehManifest, major } from './tipos.ts';
import type { ChunkRef, Manifest, OfertaCard } from './tipos.ts';

export const INTERVALO_MS = 5 * 60_000;
const PRIMEIROS = 3;
const MAJOR = major(contrato.version);

export interface Resposta {
	ok: boolean;
	status: number;
	json(): Promise<unknown>;
}

export type Evento =
	| { tipo: 'pronto' }
	| { tipo: 'completo' }
	| { tipo: 'atualizado' }
	| { tipo: 'novas'; n: number }
	| { tipo: 'erro'; erro: 'manifest' }
	| { tipo: 'erro'; erro: 'chunk'; n: number }
	| { tipo: 'atualizarApp'; contrato: string };

export interface Deps {
	fetch(url: string, init?: { cache?: 'no-cache' }): Promise<Resposta>;
	/** Prefixo das URLs; padrão '/'. */
	base?: string;
	/** Relógio em ms. */
	agora(): number;
	agendar(cb: () => void, ms: number): unknown;
	cancelar(h: unknown): void;
	/** requestIdleCallback; sem ele, agendar(cb, 0). */
	ocioso?(cb: () => void): void;
	visivel(): boolean;
	/** Inscreve `cb`; devolve a função que cancela a inscrição. */
	aoMudarVisibilidade(cb: () => void): () => void;
	aoEvento?(e: Evento): void;
}

export interface Sincronizador {
	iniciar(): Promise<void>;
	parar(): void;
	sincronizarAgora(): Promise<void>;
}

function diferencaDe(carregados: Map<number, string>, novo: Manifest) {
	const ns = new Set(novo.chunks.map((c) => c.n));
	return {
		baixar: novo.chunks.filter((c) => carregados.get(c.n) !== c.arquivo).sort((a, b) => b.n - a.n),
		descartar: [...carregados.keys()].filter((n) => !ns.has(n))
	};
}

/** Chunks a baixar (n decrescente) e `n` a descartar. */
export function diferenca(
	atual: Manifest | null,
	novo: Manifest
): { baixar: ChunkRef[]; descartar: number[] } {
	return diferencaDe(new Map((atual?.chunks ?? []).map((c) => [c.n, c.arquivo])), novo);
}

export function criarSincronizador(cat: Catalogo, deps: Deps): Sincronizador {
	const base = (deps.base ?? '/').replace(/\/?$/, '/');
	const ocioso = deps.ocioso ?? ((cb: () => void) => void deps.agendar(cb, 0));
	const emitir = (e: Evento) => deps.aoEvento?.(e);

	let atual: Manifest | null = null;
	let ultimoSync = -Infinity;
	let emCurso: Promise<void> | null = null;
	let ativo = false;
	let timer: unknown = null;
	let desinscrever: (() => void) | null = null;
	let prontoEmitido = false;
	let completoEmitido = false;

	async function lerManifest(): Promise<Manifest | null> {
		try {
			const r = await deps.fetch(base + 'manifest.json', { cache: 'no-cache' });
			if (!r.ok) return null;
			const m = await r.json();
			return ehManifest(m) ? m : null;
		} catch {
			return null;
		}
	}

	async function lerChunk(ref: ChunkRef): Promise<OfertaCard[] | null> {
		try {
			const r = await deps.fetch(base + ref.arquivo);
			if (!r.ok) return null;
			const cards = await r.json();
			return ehChunk(cards) ? cards : null;
		} catch {
			return null;
		}
	}

	/** Aplica `m` sobre o que está carregado; devolve os chunks que falharam. */
	async function aplicar(m: Manifest): Promise<{ falhas: ChunkRef[]; mudou: boolean }> {
		const { baixar, descartar } = diferencaDe(cat.arquivos(), m);
		for (const n of descartar) cat.descartar(n);
		cat.alvo(m);
		let mudou = descartar.length > 0;
		const falhas: ChunkRef[] = [];
		const um = async (ref: ChunkRef) => {
			const cards = await lerChunk(ref);
			if (cards) {
				cat.aplicarChunk(ref, cards);
				mudou = true;
			} else falhas.push(ref);
		};
		await Promise.all(baixar.slice(0, PRIMEIROS).map(um));
		if (!prontoEmitido) {
			prontoEmitido = true;
			emitir({ tipo: 'pronto' });
		}
		for (const ref of baixar.slice(PRIMEIROS)) {
			await new Promise<void>((r) => ocioso(r));
			await um(ref);
		}
		return { falhas, mudou };
	}

	function aceitavel(m: Manifest | null): m is Manifest {
		if (!m) {
			emitir({ tipo: 'erro', erro: 'manifest' });
			return false;
		}
		if (major(m.contrato) !== MAJOR) {
			emitir({ tipo: 'atualizarApp', contrato: m.contrato });
			return false;
		}
		// Borda servindo o manifest anterior. Versão igual segue: o diff contra o
		// carregado dá 0 chunks, ou refaz um `n` que falhou no ciclo anterior.
		return !(atual && m.versao < atual.versao);
	}

	async function sincronizar(): Promise<void> {
		ultimoSync = deps.agora();
		const m = await lerManifest();
		if (!aceitavel(m)) return;
		atual = m;
		// Antes do diff: confirmarNovas() zera a contagem fora daqui.
		const novasAntes = cat.novas();
		let { falhas, mudou } = await aplicar(m);
		if (falhas.length > 0) {
			// Regra 5: refaz o manifest uma vez e tenta de novo.
			const m2 = await lerManifest();
			if (m2 && major(m2.contrato) === MAJOR && m2.versao >= m.versao) atual = m2;
			const r = await aplicar(atual);
			falhas = r.falhas;
			mudou ||= r.mudou;
			for (const f of falhas) emitir({ tipo: 'erro', erro: 'chunk', n: f.n });
		}
		if (cat.completo && !completoEmitido) {
			completoEmitido = true;
			emitir({ tipo: 'completo' });
		}
		if (mudou) emitir({ tipo: 'atualizado' });
		const novas = cat.novas();
		if (novas !== novasAntes) emitir({ tipo: 'novas', n: novas });
	}

	function sincronizarAgora(): Promise<void> {
		emCurso ??= sincronizar().finally(() => (emCurso = null));
		return emCurso;
	}

	function cancelarTimer() {
		if (timer !== null) deps.cancelar(timer);
		timer = null;
	}

	function programar(ms = INTERVALO_MS) {
		cancelarTimer();
		if (ativo && deps.visivel()) timer = deps.agendar(() => void tique(), ms);
	}

	async function tique(): Promise<void> {
		timer = null;
		if (!ativo || !deps.visivel()) return;
		await sincronizarAgora();
		programar();
	}

	function aoMudar() {
		if (!ativo) return;
		if (!deps.visivel()) return cancelarTimer();
		const passou = deps.agora() - ultimoSync;
		if (passou >= INTERVALO_MS) void tique();
		else programar(INTERVALO_MS - passou);
	}

	return {
		async iniciar() {
			if (ativo) return;
			ativo = true;
			desinscrever = deps.aoMudarVisibilidade(aoMudar);
			if (deps.visivel()) await tique();
		},
		parar() {
			ativo = false;
			cancelarTimer();
			desinscrever?.();
			desinscrever = null;
		},
		sincronizarAgora
	};
}
