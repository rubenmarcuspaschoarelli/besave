import { readFileSync, readdirSync } from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';
import { brotliCompressSync, constants } from 'node:zlib';
import { gerarCards, gerarManifest } from './gerador.ts';
import type { OfertaCard } from './tipos.ts';

const schemas = new URL('../../../../../packages/contract/schema/', import.meta.url);
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
for (const f of readdirSync(schemas))
	ajv.addSchema(JSON.parse(readFileSync(new URL(f, schemas), 'utf8')));
const validarChunk = ajv.getSchema('https://besave.com.br/contract/chunk.schema.json')!;
const validarManifest = ajv.getSchema('https://besave.com.br/contract/manifest.schema.json')!;

const N = 30_000;
const cards = gerarCards(N, 42);
const pub = gerarManifest(cards);

const fracao = (f: (c: OfertaCard) => boolean) => cards.filter(f).length / N;
const PP = 0.015;

describe('gerador sintético', () => {
	it('GER-01: 30 mil cards e o manifest passam no JSON Schema do contrato', () => {
		expect(cards).toHaveLength(N);
		expect(validarChunk(cards), JSON.stringify(validarChunk.errors?.slice(0, 3))).toBe(true);
		for (const chunk of pub.chunks.values()) expect(validarChunk(chunk)).toBe(true);
		expect(validarManifest(pub.manifest), JSON.stringify(validarManifest.errors)).toBe(true);
		const soma = pub.manifest.chunks.reduce((s, c) => s + c.qtd, 0);
		expect(soma).toBe(N);
	});

	it('GER-02: mesma semente → mesmos bytes; semente diferente → outros bytes', () => {
		expect(JSON.stringify(gerarCards(2000, 7))).toBe(JSON.stringify(gerarCards(2000, 7)));
		expect(JSON.stringify(gerarCards(2000, 7))).not.toBe(JSON.stringify(gerarCards(2000, 8)));
		const a = gerarManifest(gerarCards(2000, 7)).manifest;
		const b = gerarManifest(gerarCards(2000, 7)).manifest;
		expect(JSON.stringify(a)).toBe(JSON.stringify(b));
	});

	it('GER-03: distribuição de área, público e loja medida em produção', () => {
		expect(Math.abs(fracao((c) => c.a === 'ELAS') - 0.72)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.a === 'MEU_LAR') - 0.18)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.a === 'ESPORTE_VIDA') - 0.05)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.a === 'TECH') - 0.03)).toBeLessThanOrEqual(PP);
		const demais = ['PLAYERS', 'ELES', 'CULTURA', 'FAMILIA', 'PETS', 'OUTROS'];
		expect(Math.abs(fracao((c) => demais.includes(c.a)) - 0.02)).toBeLessThanOrEqual(PP);
		expect(cards.some((c) => c.a === 'OUTROS')).toBe(true);
		expect(Math.abs(fracao((c) => c.p === 'FEMININO') - 0.68)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.p === 'UNISSEX') - 0.29)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.p === 'MASCULINO') - 0.02)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.p === 'INFANTIL') - 0.01)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.l === 'MERCADO_LIVRE') - 0.55)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.l === 'AMAZON') - 0.37)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.l === 'SHOPEE') - 0.08)).toBeLessThanOrEqual(PP);
	});

	it('GER-03: cupom 32%, pd nulo 17%, expiradas 5%', () => {
		expect(Math.abs(fracao((c) => c.c !== undefined) - 0.32)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.pd === null) - 0.17)).toBeLessThanOrEqual(PP);
		expect(Math.abs(fracao((c) => c.x === 1) - 0.05)).toBeLessThanOrEqual(PP);
		expect(cards.every((c) => c.pd == null || c.pd > c.pp)).toBe(true);
	});

	it('GER-03: títulos pt-BR com acento, média ~70, p95 ~150, máx 200', () => {
		const tam = cards.map((c) => c.t.length).sort((a, b) => a - b);
		const media = tam.reduce((s, v) => s + v, 0) / N;
		const p95 = tam[Math.floor(0.95 * N)];
		expect(media).toBeGreaterThanOrEqual(65);
		expect(media).toBeLessThanOrEqual(75);
		expect(p95).toBeGreaterThanOrEqual(140);
		expect(p95).toBeLessThanOrEqual(160);
		expect(tam[N - 1]).toBeLessThanOrEqual(200);
		expect(fracao((c) => /[áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]/.test(c.t))).toBeGreaterThan(0.5);
		expect(cards.every((c) => c.t === c.t.trim() && !c.t.includes('  '))).toBe(true);
	});

	it('GER-03: ids crescentes com lacunas; dt nos últimos 45 dias', () => {
		const lacunas = cards.slice(1).filter((c, i) => c.id - cards[i].id > 1).length;
		expect(cards.slice(1).every((c, i) => c.id > cards[i].id)).toBe(true);
		expect(lacunas).toBeGreaterThan(0);
		const ts = cards.map((c) => Date.parse(c.dt));
		const max = Math.max(...ts);
		const min = Math.min(...ts);
		expect(max - min).toBeLessThanOrEqual(45 * 86400_000);
		expect(max - min).toBeGreaterThan(40 * 86400_000);
	});
});

// BSV-36 SIT-06 e ORC-01 (AD-074).
describe('gerador sintético: dp', () => {
	it('SIT-06: todo card tem dp ≥ dt', () => {
		expect(cards.every((c) => typeof c.dp === 'string')).toBe(true);
		expect(cards.every((c) => Date.parse(c.dp!) >= Date.parse(c.dt))).toBe(true);
	});

	it('ORC-01: 1 000 cards realistas → média ≤ 230 B e chunk comprimido ≤ 60 KB', () => {
		for (const semente of [1, 2, 3]) {
			const mil = gerarCards(1000, semente);
			const bytes = mil.reduce((s, c) => s + Buffer.byteLength(JSON.stringify(c)), 0);
			expect(bytes / 1000).toBeLessThanOrEqual(230);
			const br = brotliCompressSync(Buffer.from(JSON.stringify(mil)), {
				params: { [constants.BROTLI_PARAM_QUALITY]: 9 }
			});
			expect(br.length).toBeLessThanOrEqual(60 * 1024);
		}
	});
});
