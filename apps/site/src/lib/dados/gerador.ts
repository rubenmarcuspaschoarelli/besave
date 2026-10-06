// Gerador sintético determinístico (só testes e Node; não entra no bundle).
// Distribuição medida em produção em 02/10/2026 (docs/specs/BSV-35.md, regra 13).
import { createHash } from 'node:crypto';
import { brotliCompressSync, constants } from 'node:zlib';
import type { Area, ChunkRef, Loja, Manifest, OfertaCard, Publico } from './tipos.ts';

/** mulberry32: PRNG de 32 bits, determinístico por semente. */
export function prng(semente: number): () => number {
	let a = semente >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

type Pesos<T> = ReadonlyArray<readonly [T, number]>;

const AREA: Pesos<Area> = [
	['ELAS', 0.72],
	['MEU_LAR', 0.18],
	['ESPORTE_VIDA', 0.05],
	['TECH', 0.03],
	['PLAYERS', 0.02 / 6],
	['ELES', 0.02 / 6],
	['CULTURA', 0.02 / 6],
	['FAMILIA', 0.02 / 6],
	['PETS', 0.02 / 6],
	['OUTROS', 0.02 / 6]
];
const PUBLICO: Pesos<Publico> = [
	['FEMININO', 0.68],
	['UNISSEX', 0.29],
	['MASCULINO', 0.02],
	['INFANTIL', 0.01]
];
const LOJA: Pesos<Loja> = [
	['MERCADO_LIVRE', 0.55],
	['AMAZON', 0.37],
	['SHOPEE', 0.08]
];

const PRODUTOS = [
	'Protetor Solar Facial FPS 50',
	'Sérum Facial Vitamina C',
	'Hidratante Corporal',
	'Máscara de Cílios',
	'Batom Líquido Matte',
	'Base Líquida',
	'Shampoo Antiqueda',
	'Condicionador Nutritivo',
	'Óleo Capilar',
	'Perfume Feminino',
	'Escova Secadora',
	'Prancha Alisadora',
	'Kit Pincéis de Maquiagem',
	'Paleta de Sombras',
	'Creme Anti-idade',
	'Água Micelar',
	'Sabonete Facial',
	'Tônico Facial',
	'Esmalte em Gel',
	'Desodorante Aerossol',
	'Jogo de Lençol',
	'Panela Antiaderente',
	'Organizador de Gaveta',
	'Tênis de Corrida',
	'Garrafa Térmica',
	'Fone Bluetooth',
	'Café em Cápsulas',
	'Toalha de Banho',
	'Luminária de Mesa',
	'Legging Fitness'
];
const MARCAS = [
	'La Roche-Posay',
	'Neutrogena',
	'Eudora',
	'O Boticário',
	'Natura',
	'Vult',
	'Ruby Rose',
	'Salon Line',
	'Lola Cosmetics',
	'Mondial',
	'Tramontina',
	'Nivea',
	'Dove',
	'Garnier',
	'Avon'
];
const DETALHES = [
	'com Ácido Hialurônico',
	'Pele Oleosa',
	'Toque Seco',
	'Longa Duração',
	'Vegano',
	'Sem Fragrância',
	'Hipoalergênico',
	'Antioxidante',
	'Efeito Matte',
	'Cor Nude',
	'Kit com 3 Unidades',
	'Edição Limitada',
	'à Prova d’Água',
	'Original',
	'Lançamento',
	'para Cabelos Cacheados',
	'Nutrição Intensa',
	'Reparação Noturna',
	'Rosé',
	'Preto',
	'Bivolt',
	'Aço Inox',
	'Algodão Egípcio',
	'Microfibra',
	'Antiderrapante',
	'Fórmula Leve',
	'Ação Rápida',
	'Proteção Térmica',
	'30ml',
	'50ml',
	'200ml',
	'1 Litro',
	'500g',
	'60 Cápsulas',
	'Tamanho Médio',
	'Pacote Econômico'
];
const CUPONS = ['BESAVE10', 'BELEZA15', 'PRIMEIRA', 'FRETEGRATIS', 'VOLTA20', 'APP10', 'SKIN-30'];

const BASE_DT = Date.UTC(2026, 9, 2, 12, 0, 0);
const JANELA_S = 45 * 86400;

function escolher<T>(r: () => number, pesos: Pesos<T>): T {
	let x = r();
	for (const [v, p] of pesos) {
		if (x < p) return v;
		x -= p;
	}
	return pesos[pesos.length - 1][0];
}

function item<T>(r: () => number, lista: readonly T[]): T {
	return lista[Math.floor(r() * lista.length)];
}

function normal(r: () => number): number {
	const u = 1 - r();
	return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}

function titulo(r: () => number): string {
	// Log-normal: média ~70, p95 ~150 (produção).
	const alvo = Math.min(200, Math.max(20, Math.round(57 * Math.exp(0.55 * normal(r)))));
	let t = `${item(r, PRODUTOS)} ${item(r, MARCAS)}`;
	while (t.length < alvo) {
		const prox = `${t} ${item(r, DETALHES)}`;
		if (prox.length > 200) break;
		t = prox;
	}
	return t;
}

function centavos90(v: number): number {
	return Math.max(190, Math.floor(v / 100) * 100 + 90);
}

/** `qtd` cards determinísticos por `semente`, ids crescentes com lacunas. */
export function gerarCards(qtd: number, semente: number): OfertaCard[] {
	const r = prng(semente);
	const cards: OfertaCard[] = [];
	let id = 0;
	for (let i = 0; i < qtd; i++) {
		id += r() < 0.8 ? 1 : 2 + Math.floor(r() * 4);
		const l = escolher(r, LOJA);
		const t = titulo(r);
		const pp = centavos90(6990 * Math.exp(0.8 * normal(r)));
		const pd = r() < 0.17 ? null : centavos90(pp * (1.1 + r() * 1.4));
		const c = r() < 0.32 ? item(r, CUPONS) : undefined;
		const dt =
			new Date(BASE_DT - Math.floor(r() * JANELA_S) * 1000).toISOString().slice(0, 19) + 'Z';
		const a = escolher(r, AREA);
		const p = escolher(r, PUBLICO);
		const x = r() < 0.05;
		// Ordem de chaves do contrato (CONTRATO §3).
		cards.push({
			id,
			l,
			t,
			pd,
			pp,
			...(c ? { c } : {}),
			dt,
			a,
			p,
			...(x ? { x: 1 as const } : {})
		});
	}
	return cards;
}

export interface Publicacao {
	manifest: Manifest;
	/** `arquivo` → cards do chunk. */
	chunks: Map<string, OfertaCard[]>;
}

/** Monta manifest e chunks como o worker (MANIFEST §2, §3): n = floor(id/1000), hash SHA-256/16, Brotli 9. */
export function gerarManifest(cards: OfertaCard[], versao = 20261002120000): Publicacao {
	const grupos = new Map<number, OfertaCard[]>();
	for (const c of [...cards].sort((a, b) => a.id - b.id)) {
		const n = Math.floor(c.id / 1000);
		const g = grupos.get(n);
		if (g) g.push(c);
		else grupos.set(n, [c]);
	}
	const refs: ChunkRef[] = [];
	const chunks = new Map<string, OfertaCard[]>();
	for (const [n, g] of [...grupos].sort((a, b) => a[0] - b[0])) {
		const json = JSON.stringify(g);
		const hash = createHash('sha256').update(json).digest('hex').slice(0, 16);
		const br = brotliCompressSync(Buffer.from(json), {
			params: { [constants.BROTLI_PARAM_QUALITY]: 9 }
		});
		const arquivo = `data/chunks/${n}-${hash}.json.br`;
		refs.push({
			n,
			arquivo,
			ids: [Math.max(1, n * 1000), n * 1000 + 999],
			qtd: g.length,
			bytes: br.length
		});
		chunks.set(arquivo, g);
	}
	const areas: Partial<Record<Area, number>> = {};
	for (const c of cards) if (!c.x) areas[c.a] = (areas[c.a] ?? 0) + 1;
	const s = String(versao);
	const gerado_em = `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T${s.slice(8, 10)}:${s.slice(10, 12)}:${s.slice(12, 14)}Z`;
	return {
		manifest: {
			contrato: '1.3.3',
			versao,
			gerado_em,
			total_ofertas: cards.length,
			chunks: refs,
			busca: null,
			areas
		},
		chunks
	};
}
