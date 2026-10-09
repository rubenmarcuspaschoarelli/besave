import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { build } from 'vite';
import { describe, expect, it } from 'vitest';
import { Catalogo, buscar } from '../dados.ts';
import type { Filtro } from '../dados.ts';
import { gerarCards, gerarManifest } from './gerador.ts';

// Orçamentos da BSV-35 (Node, 30 mil cards do gerador).
const pub = gerarManifest(gerarCards(30_000, 42));

function carregar(): Catalogo {
	const cat = new Catalogo();
	cat.alvo(pub.manifest);
	for (const ref of pub.manifest.chunks) cat.aplicarChunk(ref, pub.chunks.get(ref.arquivo)!);
	return cat;
}

function cronometrar(f: () => void): number {
	const t = performance.now();
	f();
	return performance.now() - t;
}

const mediana = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

const CONSULTAS = [
	'protetor solar',
	'serum',
	'vitamina c',
	'hidratante',
	'mascara',
	'cilios',
	'batom',
	'matte',
	'base liquida',
	'shampoo',
	'condicionador',
	'oleo capilar',
	'perfume',
	'escova secadora',
	'prancha',
	'pinceis',
	'paleta',
	'anti idade',
	'agua micelar',
	'sabonete',
	'tonico',
	'esmalte',
	'desodorante',
	'lencol',
	'panela',
	'organizador',
	'tenis',
	'garrafa termica',
	'fone',
	'cafe',
	'toalha',
	'luminaria',
	'legging',
	'natura',
	'boticario',
	'la roche',
	'vult',
	'ruby rose',
	'salon line',
	'mondial',
	'tramontina',
	'nivea',
	'besave',
	'mercado livre',
	'amazon',
	'shopee',
	'acido hialuronico',
	'kit 3',
	'pele oleosa',
	'xyzw inexistente'
];

describe('orçamentos de desempenho', () => {
	it('DES-01: aplicar todos os chunks de 30 mil cards ≤ 400 ms (mediana de 5)', () => {
		const tempos = Array.from({ length: 5 }, () => cronometrar(() => carregar()));
		expect(carregar().lista({ mostrarExpiradas: true })).toHaveLength(30_000);
		expect(mediana(tempos)).toBeLessThanOrEqual(400);
	});

	it('DES-02: buscar p95 de 50 consultas ≤ 20 ms', () => {
		expect(CONSULTAS).toHaveLength(50);
		const cat = carregar();
		const tempos = CONSULTAS.map((q) => cronometrar(() => buscar(cat, q)));
		expect(buscar(cat, 'protetor solar').total).toBeGreaterThan(0);
		const p95 = [...tempos].sort((a, b) => a - b)[Math.ceil(0.95 * tempos.length) - 1];
		expect(p95).toBeLessThanOrEqual(20);
	});

	it('DES-03: lista com área + ordem ≤ 40 ms (mediana de 5)', () => {
		const cat = carregar();
		for (const ordem of ['recentes', 'desconto', 'preco'] as const) {
			const tempos = Array.from({ length: 5 }, () =>
				cronometrar(() => cat.lista({ area: 'ELAS', ordem }))
			);
			expect(mediana(tempos)).toBeLessThanOrEqual(40);
		}
		expect(cat.lista({ area: 'ELAS' }).length).toBeGreaterThan(15_000);
	});

	it('DAD-04: trocar filtro (público, loja, faixa, cupom, ordem) ≤ 50 ms (mediana de 5, com aquecimento)', () => {
		const cat = carregar();
		const filtros: Filtro[] = [
			{},
			{ publico: 'FEMININO' },
			{ loja: 'AMAZON', ordem: 'desconto' },
			{ faixa: 'ate50' },
			{ soComCupom: true, ordem: 'preco' },
			{
				area: 'ELAS',
				publico: 'FEMININO',
				loja: 'AMAZON',
				faixa: '50a100',
				soComCupom: true,
				ordem: 'desconto'
			}
		];
		for (const f of filtros) {
			cat.lista(f);
			cat.lista(f);
			const tempos = Array.from({ length: 5 }, () => cronometrar(() => cat.lista(f)));
			expect(mediana(tempos), JSON.stringify(f)).toBeLessThanOrEqual(50);
		}
		expect(cat.lista({ faixa: 'ate50' }).length).toBeGreaterThan(1000);
		expect(cat.lista({ soComCupom: true }).length).toBeGreaterThan(1000);
	});
});

describe('bundle e pureza', async () => {
	const entrada = fileURLToPath(new URL('../dados.ts', import.meta.url));
	const saida = await build({
		configFile: false,
		logLevel: 'silent',
		build: { lib: { entry: entrada, formats: ['es'] }, write: false, minify: true }
	});
	const codigo = [saida]
		.flat()
		.flatMap((o) => ('output' in o ? o.output : []))
		.map((c) => ('code' in c ? c.code : ''))
		.join('\n');

	it('DES-04: módulo ≤ 10 KB gzip', () => {
		expect(codigo.length).toBeGreaterThan(1000);
		expect(gzipSync(codigo).length).toBeLessThanOrEqual(10 * 1024);
	});

	it('PUR-01: sem window/document nem módulos do Node no bundle', () => {
		expect(codigo).not.toMatch(/\b(window|document)\b/);
		expect(codigo).not.toMatch(/node:/);
	});

	it('PUR-01: sem dependência de runtime', () => {
		const pkg = JSON.parse(
			readFileSync(new URL('../../../package.json', import.meta.url), 'utf8')
		) as Record<string, unknown>;
		expect(pkg.dependencies ?? {}).toEqual({});
	});
});
