# MANIFEST.md — Layout do bucket, manifest e cache (BSV-2)

Como os dados do CONTRATO.md ficam no S3 e como o cliente descobre o que mudou.
Princípio: **um único arquivo mutável com TTL curto (`manifest.json`); todo o resto é
imutável e endereçado por conteúdo.** Isso dá hit rate máximo no CloudFront e elimina
a lista de tombstones: se um chunk mudou (oferta nova, alterada ou encerrada), seu hash
muda, o manifest aponta para o novo arquivo e o cliente rebaixa só aquele chunk.

---

## 1. Layout do bucket `besave-site` (um bucket, prefixos por tipo)

```
/                                   ← build do SvelteKit (index.html, _app/…)
/manifest.json                      ← ÚNICO arquivo mutável de dados
/data/chunks/{n}-{hash}.json.br     ← OfertaCard[] (imutável)
/data/busca/{hash}.json.br          ← índice de busca compacto (F3, imutável)
/oferta/{id}/index.html             ← página estática da oferta (OfertaPagina)
/{area}/index.html                  ← página de área, prerender (ex.: /elas/)
/{area}/{publico}/index.html        ← ex.: /elas/feminino/
/img/ofertas/{id}.webp
/img/ofertas/{id}-small.webp
/img/produtos/{id_produto}.webp
/img/placeholder/{area}.webp
/sitemap.xml                        ← sitemap index
/sitemap-{n}.xml                    ← ≤ 50.000 URLs cada
/robots.txt
```

O que foi proposto como `server\s3\ofertas\img` e `server\s3\produtos\img` são os
prefixos `img/ofertas/` e `img/produtos/`. Um bucket só: menos política, menos IaC.

---

## 2. `manifest.json`

```json
{
  "contrato": "1.3.0",
  "versao": 20260924130500,
  "gerado_em": "2026-09-24T13:05:00Z",
  "total_ofertas": 30412,
  "chunks": [
    { "n": 0,  "arquivo": "data/chunks/0-9f2a1c3b4d5e6f70.json.br",  "ids": [1, 999],       "qtd": 812, "bytes": 41210 },
    { "n": 30, "arquivo": "data/chunks/30-77b0e4d5c6b7a890.json.br", "ids": [30000, 30999], "qtd": 640, "bytes": 33980 }
  ],
  "busca": { "arquivo": "data/busca/aa310912ab34cd56.json.br", "bytes": 1480200 },
  "areas": { "TECH": 4120, "ELAS": 9800 }
}
```

Regras:
- `versao` = timestamp numérico UTC `YYYYMMDDhhmmss`; sempre crescente.
- `chunks[].ids` = `[id_min, id_max]` da faixa; `n = floor(id / 1000)`. A faixa é fixa
  por `n`, então **oferta nova só altera o último chunk**; oferta encerrada/alterada altera
  só o chunk da sua faixa.
- Chunks vazios (faixa sem ofertas ativas) não aparecem.
- `hash` = 16 hex do SHA-256 do conteúdo **antes** da compressão.
- `busca` é `null` até F3.
- `areas` = contagem de ativas por área, para o menu mostrar "(4.120)" sem baixar tudo.

---

## 3. Chunks

- Conteúdo: array JSON de `OfertaCard` (CONTRATO.md §3), ordenado por `id` crescente.
- Compressão: Brotli nível 9, sufixo `.json.br`, servido com `Content-Encoding: br` e
  `Content-Type: application/json`.
- Orçamento: **≤ 60 KB comprimido por chunk** (gate no CI do worker sobre fixtures).
- Imutável: se o conteúdo muda, o hash muda, o nome muda. O worker apaga arquivos de
  chunk que não estão em nenhum manifest há mais de 24 h.

### 3.1 Algoritmo do cliente (F3, referência para o agente)
1. `GET /manifest.json` (respeita `max-age`; polling a cada 5 min enquanto a aba está visível).
2. Para cada `chunks[]`: se `arquivo` ≠ o que tenho em memória para aquele `n`, baixar.
   Chunks não listados no novo manifest são descartados.
3. Ordenar/filtrar localmente por `dt`, `a`, `p`; busca sobre o índice.
4. Se houve chunk novo e há cards com `dt` maior que o maior `dt` já exibido → toast
   "N novas ofertas" (não insere no topo; o usuário clica).
5. Primeira carga: baixar primeiro os 3 chunks de `n` mais alto (ofertas mais recentes),
   renderizar, depois os demais em `requestIdleCallback`.

---

## 4. Headers por prefixo (definidos no upload pelo worker; S3 devolve, CloudFront respeita)

| prefixo | `Cache-Control` | `Content-Type` | `Content-Encoding` |
|---|---|---|---|
| `manifest.json` | `public, max-age=300, stale-while-revalidate=60` | `application/json` | — (CloudFront comprime) |
| `data/chunks/*`, `data/busca/*` | `public, max-age=31536000, immutable` | `application/json` | `br` (pré-comprimido) |
| `oferta/*/index.html` | `public, max-age=600, stale-while-revalidate=300` | `text/html; charset=utf-8` | — (CloudFront comprime) |
| `{area}/**/index.html` | `public, max-age=300` | `text/html; charset=utf-8` | — |
| `img/**` | `public, max-age=31536000, immutable` | `image/webp` | — |
| `_app/**` (build Svelte, nomes com hash) | `public, max-age=31536000, immutable` | conforme | — |
| `index.html`, `sitemap*.xml`, `robots.txt` | `public, max-age=300` | conforme | — |

Nota: chunks pré-comprimidos em Brotli exigem que o CloudFront **não** recomprima (ele só
comprime quando não há `Content-Encoding`). Cliente sem suporte a `br` recebe bytes br
mesmo assim — aceito: todos os browsers-alvo suportam Brotli.

---

## 5. CloudFront — behaviors (BSV-4)

Uma distribuição **nova** (ver specs/BSV-4.md), origem S3 com OAC (bucket privado `besave-site`,
sem website hosting). A distribuição atual `E28G93A17WHHD` e o bucket público `besave.com.br`
continuam servindo o protótipo até a virada de DNS.

| ordem | path pattern | política de cache | compressão | função de borda |
|---|---|---|---|---|
| 1 | `/ir/*` | desabilitada | — | CloudFront Function `redirect-afiliado` (BSV-23): lê `id` do path, consulta KeyValueStore `id → url`, responde 302 com `Cache-Control: no-store`; se não achar, 302 para `/`. |
| 2 | `/manifest.json` | TTL mín 0 / padrão 300 / máx 300 | gzip+br | — |
| 3 | `/data/*` | TTL 1 ano, chave = path | não (pré-br) | — |
| 4 | `/img/*` | TTL 1 ano, chave = path | não | — |
| 5 | `/oferta/*` | TTL padrão 600 | gzip+br | Function `rewrite-index`: `/oferta/x/` → `/oferta/x/index.html` |
| 6 | default `*` | TTL padrão 300 | gzip+br | Function `rewrite-index`. Sem fallback SPA (AD-020): o site não tem rota client-side |

Erros (valem para a distribuição inteira): 403 e 404 do S3 → **404** com `/404.html`, TTL de erro 60 s.
Com OAC o S3 devolve 403 para objeto inexistente; o visitante sempre vê 404. Nenhuma error response
devolve 200 — chunk ausente em `/data/*` precisa falhar como 404. O deploy do site sempre publica
`/404.html` (`noindex`); SvelteKit adapter-static com fallback desabilitado.

KeyValueStore do CloudFront: limite 5 MB por store; 30k entradas de `id → url curta`
(~90 B cada) ≈ 2,7 MB. Cabe hoje; **não cabe se dobrar** — acima de ~45k ofertas ativas,
trocar por Lambda@Edge + DynamoDB. O worker atualiza a KVS via API a cada ciclo (só os ids
que mudaram). Cliques: logs padrão do CloudFront → S3 `besave-logs/` (análise fica para
depois; o dado já existe).

---

## 6. Worker — ordem de publicação (evita janela inconsistente)

1. Upload de imagens novas.
2. Upload de chunks e índice de busca novos (nomes novos, nunca sobrescreve).
3. Upload/atualização de páginas HTML e sitemaps.
4. Atualização da KVS de redirects.
5. **Por último**, upload do `manifest.json`.
6. Limpeza de chunks órfãos (> 24 h fora do manifest).
7. Ids presentes no manifest anterior e ausentes no Oracle (expurgo, CONTRATO.md §7) → apagar
   `oferta/{id}/`, `img/ofertas/{id}*` e a chave na KVS.

Se falhar antes do passo 5, o manifest antigo continua válido e aponta para arquivos que
ainda existem. Idempotente: rodar duas vezes sem mudança no Oracle não altera nenhum
objeto (comparar hash antes do upload).

---

## 7. Orçamentos (gates de CI e de revisão)

| item | limite |
|---|---|
| chunk comprimido | ≤ 60 KB |
| `OfertaCard` bruto | ≤ 220 B (média ≤ 160 B) |
| índice de busca comprimido | ≤ 2 MB |
| HTML de oferta (sem imagens) | ≤ 30 KB |
| imagem `-small` | ≤ 25 KB |
| geração completa (30k páginas + chunks) no worker | ≤ 2 min |
