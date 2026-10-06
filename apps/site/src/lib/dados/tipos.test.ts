import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { AREAS, LOJAS, PUBLICOS, ehChunk, ehManifest } from './tipos.ts';

const contrato = new URL('../../../../../packages/contract/', import.meta.url);
const ler = (p: string): unknown => JSON.parse(readFileSync(new URL(p, contrato), 'utf8'));

describe('tipos do contrato', () => {
	const enums = (ler('schema/enums.schema.json') as { $defs: Record<string, { enum: string[] }> })
		.$defs;

	it('TIP-01: enums iguais aos do schema', () => {
		expect([...LOJAS]).toEqual(enums.Loja.enum);
		expect([...PUBLICOS]).toEqual(enums.Publico.enum);
		expect([...AREAS]).toEqual(enums.Area.enum);
	});

	it('TIP-02: chunk-ok.json carrega como OfertaCard[] com valores dos enums', () => {
		const chunk = ler('fixtures/chunk-ok.json');
		expect(ehChunk(chunk)).toBe(true);
		if (!ehChunk(chunk)) return;
		expect(chunk.map((c) => c.id)).toEqual([5412, 5413, 5420]);
		for (const c of chunk) {
			expect(LOJAS).toContain(c.l);
			expect(AREAS).toContain(c.a);
			expect(PUBLICOS).toContain(c.p);
		}
		expect(chunk[2].x).toBe(1);
	});

	it('TIP-02: manifest-ok.json carrega como Manifest', () => {
		const m = ler('fixtures/manifest-ok.json');
		expect(ehManifest(m)).toBe(true);
		if (!ehManifest(m)) return;
		expect(m.contrato).toBe('1.3.3');
		expect(m.chunks[0]).toEqual({
			n: 5,
			arquivo: 'data/chunks/5-9f2a1c3b4d5e6f70.json.br',
			ids: [5000, 5999],
			qtd: 3,
			bytes: 412
		});
		expect(m.busca).toBeNull();
	});

	it('manifest inválido é recusado', () => {
		expect(ehManifest(null)).toBe(false);
		expect(ehManifest({ contrato: '1.3', versao: 1, chunks: [] })).toBe(false);
		expect(ehManifest({ contrato: '1.3.3', versao: '1', chunks: [] })).toBe(false);
		expect(ehManifest({ contrato: '1.3.3', versao: 1, chunks: {} })).toBe(false);
		expect(ehChunk({})).toBe(false);
	});
});
