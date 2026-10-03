import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Páginas provisórias (BSV-16): enviadas à mão ao S3 até o deploy do site (BSV-30).
const ler = (f) => readFileSync(new URL(`../../static/${f}`, import.meta.url), 'utf8');
const pagina404 = ler('404.html');
const inicio = ler('index.html');
// Canal público da marca (decisão do dono na revisão da BSV-16).
const CANAL = 'https://t.me/besaveofertas';
// CONTRATO.md §2.3: slugs de URL das áreas.
const AREAS = ['tech', 'players', 'meu-lar', 'elas', 'eles', 'cultura', 'familia', 'pets', 'esporte-vida', 'outros'];

test('CF-12: 404.html é noindex', () => {
  assert.match(pagina404, /<meta name="robots" content="noindex">/);
});

test('PAG-01: index.html tem o nome, "site em construção" e o link do canal', () => {
  assert.match(inicio, /<title>[^<]*besave[^<]*<\/title>/i);
  assert.match(inicio, /site em construção/i);
  assert.ok(inicio.includes(`href="${CANAL}"`));
});

test('PAG-02: 404.html diz "Oferta encerrada ou não encontrada" e linka início e canal', () => {
  assert.match(pagina404, /Oferta encerrada ou não encontrada/);
  assert.match(pagina404, /href="\/"/);
  assert.ok(pagina404.includes(`href="${CANAL}"`));
});

test('PAG-03: 404.html não linka páginas de área (ainda dão 404)', () => {
  for (const area of AREAS) assert.doesNotMatch(pagina404, new RegExp(`href="/${area}/?"`), area);
  const links = [...pagina404.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
  assert.deepEqual(links.sort(), ['/', CANAL].sort());
});

test('PAG-04: o único link do Telegram é o canal da marca; nenhum telefone nem marcador', () => {
  for (const [nome, html] of [['index.html', inicio], ['404.html', pagina404]]) {
    assert.deepEqual([...html.matchAll(/t\.me\/[^"'\s<]*/gi)].map((m) => m[0]), ['t.me/besaveofertas'], nome);
    assert.doesNotMatch(html, /\{CANAL_TELEGRAM\}/, nome);
    assert.doesNotMatch(html, /\+?\d[\d\s().-]{7,}\d/, nome);
  }
});
