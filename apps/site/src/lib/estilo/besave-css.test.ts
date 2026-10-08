import { readFileSync } from 'node:fs';
import { brotliCompressSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { GET } from '../../routes/assets/besave.css/+server.ts';

const resposta = GET();
const css = await resposta.text();
const template = (nome: string) =>
	readFileSync(new URL(`../../../../worker/templates/${nome}`, import.meta.url), 'utf8');

/** Classes de todo atributo `class="…"` do template (inclusive dentro de `{% if %}`). */
function classes(html: string): string[] {
	return [...html.matchAll(/class="([^"{]*)"/g)].flatMap((m) => m[1].split(/\s+/)).filter(Boolean);
}

/** Há regra cujo seletor cita `.classe` (fronteira de identificador logo depois). */
function temRegra(classe: string): boolean {
	return new RegExp(`\\.${classe}(?![\\w-])[^{}]*\\{`).test(css);
}

describe('besave.css', () => {
	it('é servido como text/css', () => {
		expect(resposta.headers.get('content-type')).toBe('text/css; charset=utf-8');
	});

	// CSS-01: mesmos tokens do site (TOK-01).
	it('traz os tokens do modelo A', () => {
		for (const [nome, valor] of [
			['fundo', '#fff'],
			['superficie', '#f4f6f5'],
			['borda', '#e1e6e3'],
			['texto', '#17201c'],
			['suave', '#56615b'],
			['marca', '#0b6e4f'],
			['marca-escura', '#084c37'],
			['destaque', '#c2410c'],
			['sobre-destaque', '#fff'],
			['rodape', '#084c37'],
			['rodape-texto', '#e3efe9']
		]) {
			expect(css, nome).toMatch(new RegExp(`--cor-${nome}:\\s*${valor}(fff)?[;}]`, 'i'));
		}
		expect(css).toMatch(/--raio:\s*10px/);
	});

	// CSS-01 + TOK-02: Lato 700 e 900 auto-hospedada, swap. FNT-01 (BSV-30b): o arquivo vem do
	// build (import com hash), não de /assets/fontes/; a URL final é conferida em e2e/saida.spec.ts.
	it('declara a Lato auto-hospedada', () => {
		for (const peso of [700, 900]) {
			const face = css.match(
				new RegExp(`@font-face\\s*\\{[^}]*font-weight:\\s*${peso}[^}]*\\}`)
			)?.[0];
			expect(face, String(peso)).toBeDefined();
			expect(face).toMatch(new RegExp(`url\\(['"]?/[^)]*lato-latin-${peso}-normal[^)]*\\.woff2`));
			expect(face).not.toContain('/assets/fontes/');
			expect(face).toMatch(/font-display:\s*swap/);
		}
	});

	// CSS-02
	it('tem regra para toda classe dos templates do worker', () => {
		const usadas = new Set([
			...classes(template('oferta.html')),
			...classes(template('aviso.html'))
		]);
		for (const c of ['topo', 'logo', 'menu', 'oferta', 'cta', 'encerrada', 'expirada', 'aviso']) {
			expect(usadas.has(c), c).toBe(true);
		}
		for (const c of usadas) expect(temRegra(c), `.${c}`).toBe(true);
	});

	// CSS-03
	it('cabe em 20 KB com brotli', () => {
		expect(css.length).toBeGreaterThan(1000);
		expect(brotliCompressSync(css).length).toBeLessThanOrEqual(20 * 1024);
	});
});
