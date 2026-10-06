// pnpm medir — roda a camada de dados contra o CloudFront real (BSV-35, "Real (dono)").
// BESAVE_BASE_URL=https://<distribuição>.cloudfront.net pnpm medir
// Não imprime o domínio: a saída pode ir direto para o PR.
import { Catalogo, buscar, criarSincronizador } from '../src/lib/dados.ts';
import type { ChunkRef, Deps, Evento, Manifest, OfertaCard } from '../src/lib/dados.ts';

const CONSULTAS = [
	'protetor solar',
	'serum',
	'vitamina c',
	'hidratante',
	'mascara de cilios',
	'batom',
	'base',
	'shampoo',
	'condicionador',
	'perfume feminino',
	'escova secadora',
	'paleta',
	'creme',
	'kit',
	'oleo',
	'sabonete',
	'esmalte',
	'cabelo cacheado',
	'mercado livre',
	'natura'
];

const base = process.env.BESAVE_BASE_URL;
if (!base || !/^https?:\/\//.test(base)) {
	console.error('defina BESAVE_BASE_URL (https://...)');
	process.exit(1);
}

const baixados: { arquivo: string; cards: OfertaCard[] }[] = [];
let manifest: Manifest | null = null;
const t0 = performance.now();
const marcas: Record<string, number> = {};
const erros: Evento[] = [];

const deps: Deps = {
	base: base.replace(/\/?$/, '/'),
	async fetch(url, init) {
		const r = await fetch(url, init);
		const arquivo = url.slice(deps.base!.length);
		return {
			ok: r.ok,
			status: r.status,
			async json() {
				const v: unknown = await r.json();
				if (arquivo === 'manifest.json') manifest = v as Manifest;
				else if (r.ok) baixados.push({ arquivo, cards: v as OfertaCard[] });
				return v;
			}
		};
	},
	agora: () => Date.now(),
	agendar: (cb, ms) => setTimeout(cb, ms),
	cancelar: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
	ocioso: (cb) => setImmediate(cb),
	visivel: () => true,
	aoMudarVisibilidade: () => () => {},
	aoEvento(e) {
		marcas[e.tipo] ??= performance.now() - t0;
		if (e.tipo === 'erro' || e.tipo === 'atualizarApp') erros.push(e);
	}
};

const ms = (v: number | undefined) => (v === undefined ? '—' : `${v.toFixed(0)} ms`);
const pct = (xs: number[], p: number) =>
	[...xs].sort((a, b) => a - b)[Math.ceil(p * xs.length) - 1];

const cat = new Catalogo();
const sinc = criarSincronizador(cat, deps);
await sinc.sincronizarAgora();

const m = manifest as Manifest | null;
if (!m) {
	console.error('manifest não lido', erros);
	process.exit(1);
}
const refs = new Map<string, ChunkRef>(m.chunks.map((c) => [c.arquivo, c]));
const cards = baixados.reduce((s, b) => s + b.cards.length, 0);
const bytes = baixados.reduce((s, b) => s + (refs.get(b.arquivo)?.bytes ?? 0), 0);

// Aplicação isolada da rede: mesmos chunks num catálogo novo, mediana de 5.
const tempos = Array.from({ length: 5 }, () => {
	const c = new Catalogo();
	c.alvo(m);
	const t = performance.now();
	for (const b of baixados) c.aplicarChunk(refs.get(b.arquivo)!, b.cards);
	return performance.now() - t;
});
const buscas = CONSULTAS.map((q) => {
	const t = performance.now();
	buscar(cat, q);
	return performance.now() - t;
});

const antes = baixados.length;
await sinc.sincronizarAgora();

console.log(`contrato ${m.contrato} · versao ${m.versao} · ${m.chunks.length} chunks no manifest`);
console.log(`cards: ${cards} (lista padrão: ${cat.lista().length}) · completo: ${cat.completo}`);
console.log(`bytes (br, manifest): ${bytes} · ${(bytes / 1024).toFixed(0)} KB`);
console.log(`até pronto: ${ms(marcas.pronto)} · até completo: ${ms(marcas.completo)}`);
console.log(`aplicar todos os chunks (mediana de 5): ${ms(pct(tempos, 0.5))}`);
console.log(`busca p95 (${CONSULTAS.length} consultas): ${pct(buscas, 0.95).toFixed(1)} ms`);
console.log(
	`2ª passada: ${baixados.length - antes} chunks baixados${erros.length ? ` · eventos: ${JSON.stringify(erros)}` : ''}`
);
