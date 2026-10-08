// /assets/besave.css (AD-078): gerado no build a partir dos tokens do site; o deploy publica.
import css from '#lib/estilo/besave.css?inline';

export const prerender = true;

export function GET(): Response {
	return new Response(css, { headers: { 'content-type': 'text/css; charset=utf-8' } });
}
