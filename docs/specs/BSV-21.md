# BSV-21 · Worker: páginas de oferta em massa, CSS, sitemap e robots.txt

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-20 (`TemplateOferta`, mergeado), BSV-13.
CONTRATO.md §4, §5, §7, §7.1; MANIFEST.md §1, §4, §6, §7

## Contexto
`TemplateOferta::renderizar(&OfertaPagina)` já produz a página (BSV-20). `gerar()` publica imagens,
chunks, KVS e manifest. Falta ligar o template ao ciclo: gerar e publicar `/oferta/{id}/index.html`
para todo o conjunto publicado, o CSS que a página referencia, o sitemap e o `robots.txt` — só
subindo o que mudou.

## Objetivo
Cada execução de `gerar()` deixa no bucket exatamente uma página por oferta publicada (ativa ou
expirada ≤ 7 dias), remove as expurgadas, e mantém sitemap e robots coerentes, com custo de
upload proporcional ao que mudou.

## Saídas (lib)
```rust
pub fn chave_pagina(id: i64) -> String;                  // "oferta/{id}/index.html"
pub fn publicar_paginas(paginas: &[OfertaPagina], t: &TemplateOferta, pub_: &mut dyn Publicador,
                        indice_anterior: &IndicePaginas) -> Result<(IndicePaginas, RelatorioPaginas)>;
pub struct IndicePaginas(BTreeMap<i64, String>);          // id -> hash16 do HTML
pub fn sitemaps(ativas: &[(i64, &str /*dt_oferta*/)], base: &str) -> Vec<(String /*chave*/, Vec<u8>)>;
pub fn robots(indexavel: bool, base: &str) -> String;
```
`RelatorioPaginas`: renderizadas, publicadas, inalteradas, removidas, maior_html, tempo_render_ms.

## Regras
1. **Sem N+1 no Oracle.** Produtos são carregados em lote: adicionar a `FonteOfertas` um método
   `produtos(&[i64]) -> Result<HashMap<i64, LinhaProduto>>` (uma query com `IN`, em blocos de 1000
   por limite do Oracle) e usá-lo; `produto(id)` unitário fica só para teste/compat.
2. **Só sobe o que mudou.** Índice `_estado/paginas.json` (id → hash16 do HTML) guardado no bucket,
   lido uma vez por execução, regravado ao fim (`Cache-Control: no-store`, `application/json`).
   Página com hash igual ao do índice não é enviada. Sem índice (primeira vez) → envia tudo.
   Índice ilegível → trata como ausente e envia tudo (não aborta: páginas são idempotentes).
3. Render determinístico: mesma `OfertaPagina` → mesmos bytes (teste). Oferta que passa de
   ATIVA para ENCERRADA muda de hash e é reenviada.
4. Upload via `gravar_lote` em blocos de 64; `meta_para` já cobre `oferta/*/index.html`.
5. **Expurgo:** id presente no índice anterior e ausente do conjunto atual → `remover(chave_pagina)`
   e sai do índice. Cobrir com teste junto do expurgo de imagens.
6. **CSS:** publicar `assets/css/besave.css` em `/assets/besave.css` quando o hash mudar (mesmo
   índice, chave `_css`). Adicionar a `meta_para` o prefixo `assets/`: `text/css; charset=utf-8`,
   `public, max-age=3600, stale-while-revalidate=86400` (nome sem hash; BSV-30 pode versionar).
7. **Sitemap:** só ofertas **ATIVAS** (expiradas têm `noindex`). `sitemap.xml` = sitemap index;
   `sitemap-{n}.xml` com até 45 000 URLs cada (margem sob o limite de 50 000), `<loc>` =
   `{base}/oferta/{id}/`, `<lastmod>` = data de `dt_oferta` (AAAA-MM-DD). `base` =
   `BESAVE_BASE_URL`, padrão `https://besave.com.br`. Sitemaps só são regravados se o conteúdo mudar.
8. **robots.txt:** `BESAVE_INDEXAVEL` (padrão **false**). false → `User-agent: *` + `Disallow: /`
   (o site ainda está em `*.cloudfront.net` e não pode ser indexado duplicado); true → `Allow: /`
   + `Sitemap: {base}/sitemap.xml`. A virada de DNS liga a flag.
9. Ordem em `gerar()` (MANIFEST §6): imagens → chunks → **CSS, páginas, sitemaps, robots, índice**
   → KVS → manifest → órfãos. Falha em página individual (erro de render) → conta, loga o id,
   não publica aquela página, segue; falha de upload → aborta antes do manifest.
10. Orçamento: HTML ≤ 30 KB por página (gate: erro nomeado se passar); render de 30 000 páginas
    ≤ 60 s em release (teste `#[ignore]`).
11. `--publicar` sem `--sim` lista páginas a enviar/remover no plano (contagem + 5 exemplos, não 30k linhas).

## Fora de escopo
Páginas de área e home (BSV-33), 410 real via borda, imagens de produto, `hreflang`, sitemap de imagens.

## Critério de aceite
- `produtos()` em lote: fonte fake conta chamadas; 10 000 ofertas → ≤ 10 chamadas.
- Primeira execução com 3 ofertas (fixtures) → 3 páginas + CSS + sitemap + robots + índice; segunda
  execução sem mudança → 0 páginas, 0 CSS, 0 sitemaps enviados (só índice/manifest).
- Oferta vira ENCERRADA → só a página dela é reenviada e ela some do sitemap.
- Oferta expurgada → página removida, fora do índice e do sitemap.
- 46 000 ativas sintéticas → 2 arquivos `sitemap-*.xml` + index; XML válido (parse) e ≤ 50 MB.
- robots: `BESAVE_INDEXAVEL` ausente → `Disallow: /`; true → `Sitemap:` com a base.
- Página > 30 KB (fixture sintética) → erro nomeado, manifest não gravado.
- `cargo clippy -D warnings`; `cargo test` sem rede.
- Real (dono): `--publicar --sim`; `curl -I https://<cf>/oferta/<id>/` → 200 `text/html`;
  abrir no navegador (imagem, preço, CTA `/ir/{id}` → loja); `curl https://<cf>/robots.txt` →
  `Disallow: /`; `curl https://<cf>/sitemap.xml` → index válido; segunda execução → 0 páginas enviadas;
  Lighthouse mobile numa página real ≥ 95 em Performance, SEO (ativa), Acessibilidade.

## Definition of done
PR com README (variáveis `BESAVE_BASE_URL`, `BESAVE_INDEXAVEL`, índice `_estado/`), relatório real
(renderizadas / publicadas / tempo / maior_html) e Lighthouse da página no CloudFront, testes verdes.
