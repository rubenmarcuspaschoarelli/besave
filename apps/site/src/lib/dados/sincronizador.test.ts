import { describe, expect, it } from 'vitest';
import { buscar } from './busca.ts';
import { Catalogo } from './catalogo.ts';
import { gerarCards, gerarManifest, type Publicacao } from './gerador.ts';
import { criarSincronizador, diferenca, type Deps, type Evento } from './sincronizador.ts';
import type { Manifest, OfertaCard } from './tipos.ts';
import { card, manifest, ref } from './apoio-teste.ts';

const MIN = 60_000;
const nome = (url: string) => url.replace(/^\//, '');
const nDe = (arquivo: string) => Number(/chunks\/(\d+)-/.exec(arquivo)![1]);

/** Servidor, relógio e visibilidade falsos; registra fetches e eventos em `log`. */
function ambiente(pub: Publicacao) {
	const arquivos = new Map<string, OfertaCard[]>(pub.chunks);
	let manifestAtual: Manifest = pub.manifest;
	const falhar = new Map<string, number>(); // arquivo → quantas vezes ainda falha
	const log: string[] = [];
	const inits: (string | undefined)[] = [];
	const eventos: Evento[] = [];
	const emVooNaChamada: number[] = [];
	let emVoo = 0;
	let agora = 0;
	let visivel = true;
	let seq = 0;
	const timers: { id: number; quando: number; cb: () => void }[] = [];
	const ouvintes = new Set<() => void>();

	const deps: Deps = {
		async fetch(url, init) {
			const arq = nome(url);
			log.push(arq);
			emVoo++;
			emVooNaChamada.push(emVoo);
			try {
				await null;
				await null;
				if (arq === 'manifest.json') {
					inits.push(init?.cache);
					const m = structuredClone(manifestAtual);
					return { ok: true, status: 200, json: async () => m };
				}
				const resta = falhar.get(arq) ?? 0;
				if (resta > 0) {
					falhar.set(arq, resta - 1);
					return { ok: false, status: 404, json: async () => null };
				}
				const cards = arquivos.get(arq);
				if (!cards) return { ok: false, status: 404, json: async () => null };
				const copia = structuredClone(cards);
				return { ok: true, status: 200, json: async () => copia };
			} finally {
				emVoo--;
			}
		},
		agora: () => agora,
		agendar(cb, ms) {
			const id = ++seq;
			timers.push({ id, quando: agora + ms, cb });
			return id;
		},
		cancelar(h) {
			const i = timers.findIndex((t) => t.id === h);
			if (i >= 0) timers.splice(i, 1);
		},
		ocioso: (cb) => setImmediate(cb),
		visivel: () => visivel,
		aoMudarVisibilidade(cb) {
			ouvintes.add(cb);
			return () => ouvintes.delete(cb);
		},
		aoEvento(e) {
			eventos.push(e);
			log.push(e.tipo);
		}
	};

	const assentar = async () => {
		for (let i = 0; i < 100; i++) await new Promise((r) => setImmediate(r));
	};

	return {
		deps,
		log,
		inits,
		eventos,
		emVooNaChamada,
		falhar,
		publicar(p: Publicacao) {
			for (const [k, v] of p.chunks) arquivos.set(k, v);
			manifestAtual = p.manifest;
		},
		servirManifest(m: Manifest) {
			manifestAtual = m;
		},
		chunksBaixados: () => log.filter((l) => l.startsWith('data/chunks/')),
		manifests: () => log.filter((l) => l === 'manifest.json').length,
		limpar() {
			log.length = 0;
			eventos.length = 0;
			inits.length = 0;
		},
		async avancar(ms: number) {
			const fim = agora + ms;
			for (;;) {
				timers.sort((a, b) => a.quando - b.quando || a.id - b.id);
				const t = timers[0];
				if (!t || t.quando > fim) break;
				timers.shift();
				agora = t.quando;
				t.cb();
				await assentar();
			}
			agora = fim;
		},
		async mudarVisibilidade(v: boolean) {
			visivel = v;
			for (const cb of ouvintes) cb();
			await assentar();
		}
	};
}

/** 6 chunks (n 0..5) com a semente 1. */
function publicacao(versao = 20261002120000, cards = gerarCards(4000, 1)) {
	return { cards, pub: gerarManifest(cards, versao) };
}

function comPreco(cards: OfertaCard[], id: number, pp: number) {
	return cards.map((c) => (c.id === id ? { ...c, pp, pd: null } : c));
}

describe('diferenca', () => {
	const m1 = manifest([ref(0), ref(1), ref(2)]);

	it('DIF-01: sem manifest atual → baixa tudo em n decrescente', () => {
		const d = diferenca(null, m1);
		expect(d.baixar.map((c) => c.n)).toEqual([2, 1, 0]);
		expect(d.descartar).toEqual([]);
	});

	it('DIF-01: manifest igual → nada; 1 alterado → 1; n ausente → descartar', () => {
		expect(diferenca(m1, manifest([ref(0), ref(1), ref(2)]))).toEqual({
			baixar: [],
			descartar: []
		});
		const d = diferenca(m1, manifest([ref(0), ref(1, 'b'), ref(3)]));
		expect(d.baixar.map((c) => c.n)).toEqual([3, 1]);
		expect(d.descartar).toEqual([2]);
	});
});

describe('sincronizador: primeira carga e diff', () => {
	it('SIN-01: manifest → 3 maiores n → pronto → resto em n decrescente, um por vez → completo', async () => {
		const { pub, cards } = publicacao();
		const ns = pub.manifest.chunks.map((c) => c.n).sort((a, b) => b - a);
		expect(ns.length).toBeGreaterThanOrEqual(5);
		const amb = ambiente(pub);
		const cat = new Catalogo();
		await criarSincronizador(cat, amb.deps).sincronizarAgora();

		const chunks = amb.log.filter((l) => l.startsWith('data/'));
		expect(amb.log[0]).toBe('manifest.json');
		expect(amb.log.slice(1, 4).map(nDe)).toEqual(ns.slice(0, 3));
		expect(amb.log[4]).toBe('pronto');
		expect(amb.log.slice(5, 5 + ns.length - 3).map(nDe)).toEqual(ns.slice(3));
		expect(amb.log.at(-1)).toBe('atualizado');
		expect(amb.log.indexOf('completo')).toBe(5 + ns.length - 3);
		expect(chunks).toHaveLength(ns.length);
		// 3 em paralelo, depois um por vez
		expect(Math.max(...amb.emVooNaChamada.slice(1, 4))).toBe(3);
		expect(amb.emVooNaChamada.slice(4)).toEqual(Array(ns.length - 3).fill(1));
		expect(cat.completo).toBe(true);
		expect(cat.lista()).toHaveLength(cards.filter((c) => !c.x).length);
	});

	it('SIN-02: manifest pedido com cache no-cache', async () => {
		const amb = ambiente(publicacao().pub);
		await criarSincronizador(new Catalogo(), amb.deps).sincronizarAgora();
		expect(amb.inits).toEqual(['no-cache']);
	});

	it('SIN-03: manifest igual → 0 chunks', async () => {
		const amb = ambiente(publicacao().pub);
		const s = criarSincronizador(new Catalogo(), amb.deps);
		await s.sincronizarAgora();
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.manifests()).toBe(1);
		expect(amb.chunksBaixados()).toEqual([]);
	});

	it('SIN-04: 1 chunk alterado → 1 fetch, e o preço novo aparece', async () => {
		const { pub, cards } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const alvo = cards.find((c) => c.id >= 2000 && !c.x)!;
		const pub2 = gerarManifest(comPreco(cards, alvo.id, 123), 20261002120500);
		amb.publicar(pub2);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.chunksBaixados().map(nDe)).toEqual([Math.floor(alvo.id / 1000)]);
		expect(cat.lista().find((c) => c.id === alvo.id)?.pp).toBe(123);
		expect(amb.log).toContain('atualizado');
	});

	it('SIN-05: n removido → cards dele fora de lista e buscar', async () => {
		const { pub, cards } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const sem1 = cards.filter((c) => Math.floor(c.id / 1000) !== 1);
		amb.publicar(gerarManifest(sem1, 20261002120500));
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.chunksBaixados()).toEqual([]);
		expect(cat.lista({ mostrarExpiradas: true }).some((c) => c.id >= 1000 && c.id < 2000)).toBe(
			false
		);
		expect(buscar(cat, 'kit', {}, 100_000).itens.some((c) => c.id >= 1000 && c.id < 2000)).toBe(
			false
		);
		expect(cat.lista({ mostrarExpiradas: true })).toHaveLength(sem1.length);
	});
});

describe('sincronizador: versão, contrato e falhas', () => {
	it('SIN-06: versao menor → ignorado', async () => {
		const { pub, cards } = publicacao(20261002120500);
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const antes = JSON.stringify(cat.lista({ mostrarExpiradas: true }));
		amb.publicar(gerarManifest(comPreco(cards, cards[0].id, 1), 20261002120000));
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.chunksBaixados()).toEqual([]);
		expect(JSON.stringify(cat.lista({ mostrarExpiradas: true }))).toBe(antes);
	});

	it('SIN-07: contrato 2.0.0 → atualizarApp e nada aplicado', async () => {
		const { pub, cards } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const antes = JSON.stringify(cat.lista({ mostrarExpiradas: true }));
		const p2 = gerarManifest(cards.slice(0, 10), 20261002120500);
		amb.publicar({ ...p2, manifest: { ...p2.manifest, contrato: '2.0.0' } });
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos).toEqual([{ tipo: 'atualizarApp', contrato: '2.0.0' }]);
		expect(amb.chunksBaixados()).toEqual([]);
		expect(JSON.stringify(cat.lista({ mostrarExpiradas: true }))).toBe(antes);

		const amb2 = ambiente({ ...p2, manifest: { ...p2.manifest, contrato: '2.0.0' } });
		const vazio = new Catalogo();
		await criarSincronizador(vazio, amb2.deps).sincronizarAgora();
		expect(amb2.log).toEqual(['manifest.json', 'atualizarApp']);
		expect(vazio.total).toBe(0);
	});

	it('SIN-08: chunk 404 → 1 novo manifest + 1 nova tentativa', async () => {
		const { pub } = publicacao();
		const amb = ambiente(pub);
		const alvo = pub.manifest.chunks[0].arquivo;
		amb.falhar.set(alvo, 1);
		const cat = new Catalogo();
		await criarSincronizador(cat, amb.deps).sincronizarAgora();
		expect(amb.manifests()).toBe(2);
		expect(amb.log.filter((l) => l === alvo)).toHaveLength(2);
		expect(amb.log.indexOf('manifest.json', 1)).toBeGreaterThan(amb.log.indexOf(alvo));
		expect(amb.eventos.some((e) => e.tipo === 'erro')).toBe(false);
		expect(cat.completo).toBe(true);
	});

	it('SIN-09: 404 persistente → dados antigos mantidos, erro, e nova tentativa no ciclo seguinte', async () => {
		const { pub, cards } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const alvo = cards.find((c) => c.id >= 3000 && c.id < 4000 && !c.x)!;
		const pub2 = gerarManifest(comPreco(cards, alvo.id, 77), 20261002120500);
		const arq = pub2.manifest.chunks.find((c) => c.n === 3)!.arquivo;
		amb.publicar(pub2);
		amb.falhar.set(arq, 99);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.manifests()).toBe(2);
		expect(amb.chunksBaixados()).toEqual([arq, arq]);
		expect(amb.eventos).toContainEqual({ tipo: 'erro', erro: 'chunk', n: 3 });
		expect(cat.lista().find((c) => c.id === alvo.id)?.pp).toBe(alvo.pp);
		expect(cat.lista({ mostrarExpiradas: true })).toHaveLength(cards.length);

		amb.falhar.delete(arq);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.chunksBaixados()).toEqual([arq]);
		expect(cat.lista().find((c) => c.id === alvo.id)?.pp).toBe(77);
	});

	it('falha no manifest → erro("manifest") e catálogo mantido', async () => {
		const { pub } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const n = cat.lista().length;
		amb.servirManifest({ lixo: true } as unknown as Manifest);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos).toEqual([{ tipo: 'erro', erro: 'manifest' }]);
		expect(cat.lista()).toHaveLength(n);
	});

	it('n que falhou e sumiu do manifest refeito é descartado', async () => {
		const { pub, cards } = publicacao();
		const amb = ambiente(pub);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		const pub2 = gerarManifest(
			comPreco(cards, cards.find((c) => c.id >= 4000)!.id, 5),
			20261002120500
		);
		const arq = pub2.manifest.chunks.find((c) => c.n === 4)!.arquivo;
		amb.publicar(pub2);
		amb.falhar.set(arq, 99);
		// O manifest refeito (3ª chamada) já não tem n=4.
		const sem4 = gerarManifest(
			cards.filter((c) => Math.floor(c.id / 1000) !== 4),
			20261002121000
		);
		const fetchOrig = amb.deps.fetch;
		let k = 0;
		amb.deps.fetch = (url, init) => {
			if (nome(url) === 'manifest.json' && ++k === 2) amb.publicar(sem4);
			return fetchOrig(url, init);
		};
		amb.limpar();
		await s.sincronizarAgora();
		expect(cat.lista({ mostrarExpiradas: true }).some((c) => Math.floor(c.id / 1000) === 4)).toBe(
			false
		);
		expect(amb.eventos.some((e) => e.tipo === 'erro')).toBe(false);
		expect(cat.completo).toBe(true);
	});

	it('novas(n) = total pendente até confirmarNovas(), não só o que chegou no ciclo', async () => {
		const cards = [card(1), card(2)];
		const amb = ambiente(gerarManifest(cards));
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		amb.publicar(gerarManifest([...cards, card(3)], 20261002120500));
		await s.sincronizarAgora();
		amb.publicar(gerarManifest([...cards, card(3), card(4)], 20261002121000));
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos.filter((e) => e.tipo === 'novas')).toEqual([{ tipo: 'novas', n: 2 }]);
		expect(cat.novas()).toBe(2);
	});

	it('novas(n) volta a ser emitido depois de confirmarNovas(); sync sem mudança não emite', async () => {
		const cards = [card(1), card(2)];
		const amb = ambiente(gerarManifest(cards));
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		amb.publicar(gerarManifest([...cards, card(3)], 20261002120500));
		await s.sincronizarAgora();
		cat.confirmarNovas();
		amb.publicar(gerarManifest([...cards, card(3), card(4)], 20261002121000));
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos).toContainEqual({ tipo: 'novas', n: 1 });
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos.filter((e) => e.tipo === 'novas')).toEqual([]);
	});

	it('SIN-01: 404 persistente na primeira carga → pronto e erro, sem completo; completo no ciclo seguinte', async () => {
		const { pub } = publicacao();
		const amb = ambiente(pub);
		const arq = pub.manifest.chunks[0].arquivo;
		amb.falhar.set(arq, 99);
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		expect(amb.log).toContain('pronto');
		expect(amb.eventos).toContainEqual({
			tipo: 'erro',
			erro: 'chunk',
			n: pub.manifest.chunks[0].n
		});
		expect(amb.log).not.toContain('completo');
		expect(cat.completo).toBe(false);
		amb.falhar.delete(arq);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos.filter((e) => e.tipo === 'completo')).toHaveLength(1);
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.log).not.toContain('completo');
	});

	it('novas: chunk com ids novos depois de completo emite novas(n)', async () => {
		const cards = [card(1), card(2)];
		const amb = ambiente(gerarManifest(cards));
		const cat = new Catalogo();
		const s = criarSincronizador(cat, amb.deps);
		await s.sincronizarAgora();
		amb.publicar(gerarManifest([...cards, card(3), card(4, { x: 1 })], 20261002120500));
		amb.limpar();
		await s.sincronizarAgora();
		expect(amb.eventos).toContainEqual({ tipo: 'novas', n: 1 });
		expect(cat.novas()).toBe(1);
	});
});

describe('sincronizador: polling por visibilidade', () => {
	async function iniciado() {
		const amb = ambiente(publicacao().pub);
		const s = criarSincronizador(new Catalogo(), amb.deps);
		await s.iniciar();
		expect(amb.manifests()).toBe(1);
		amb.limpar();
		return { amb, s };
	}

	it('POL-01: 15 min visível → 3 polls, um a cada 5 min', async () => {
		const { amb } = await iniciado();
		await amb.avancar(5 * MIN - 1);
		expect(amb.manifests()).toBe(0);
		await amb.avancar(1);
		expect(amb.manifests()).toBe(1);
		await amb.avancar(10 * MIN);
		expect(amb.manifests()).toBe(3);
	});

	it('POL-02: 15 min oculta → 0 fetch', async () => {
		const { amb } = await iniciado();
		await amb.mudarVisibilidade(false);
		await amb.avancar(15 * MIN);
		expect(amb.log).toEqual([]);
	});

	it('POL-03: volta a ficar visível após 12 min oculta → 1 poll imediato', async () => {
		const { amb } = await iniciado();
		await amb.mudarVisibilidade(false);
		await amb.avancar(12 * MIN);
		expect(amb.manifests()).toBe(0);
		await amb.mudarVisibilidade(true);
		expect(amb.manifests()).toBe(1);
		await amb.avancar(5 * MIN - 1);
		expect(amb.manifests()).toBe(1);
		await amb.avancar(1);
		expect(amb.manifests()).toBe(2);
	});

	it('volta a ficar visível antes de 5 min → sem poll imediato; poll no vencimento', async () => {
		const { amb } = await iniciado();
		await amb.avancar(1 * MIN);
		await amb.mudarVisibilidade(false);
		await amb.avancar(2 * MIN);
		await amb.mudarVisibilidade(true);
		expect(amb.manifests()).toBe(0);
		await amb.avancar(2 * MIN);
		expect(amb.manifests()).toBe(1);
	});

	it('iniciar com a aba oculta não faz fetch; parar encerra o polling', async () => {
		const amb = ambiente(publicacao().pub);
		await amb.mudarVisibilidade(false);
		const s = criarSincronizador(new Catalogo(), amb.deps);
		await s.iniciar();
		expect(amb.log).toEqual([]);
		await amb.mudarVisibilidade(true);
		expect(amb.manifests()).toBe(1);
		s.parar();
		amb.limpar();
		await amb.avancar(15 * MIN);
		await amb.mudarVisibilidade(true);
		expect(amb.log).toEqual([]);
	});
});
