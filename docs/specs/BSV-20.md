# BSV-20 · Template HTML da página de oferta (estático, SEO-first)

**Papel:** Frontend · **Pasta:** `apps/worker/templates/` + `apps/worker/assets/css/` (HTML/CSS puro; sem
Svelte neste ticket) · **Depende de:** contrato 1.3 (`OfertaPagina`, CONTRATO §4, §5, §6, §7.1). MANIFEST §1.

## Contexto
A página `/oferta/{id}/` é HTML estático gerado pelo worker (AD-002). Este ticket entrega **só o
template e o CSS**, testáveis com as fixtures do contrato, sem tocar na geração (BSV-21 liga o
template ao worker). Referência visual: promobit.com.br (página de oferta), sem copiar marca,
ícones ou textos.

## Objetivo
Um template (minijinja) que, dado um `OfertaPagina` JSON, produz uma página completa, indexável,
rápida e legível em celular, para oferta ativa e para oferta encerrada.

## Entregáveis
1. `apps/worker/templates/oferta.html` (minijinja) + `apps/worker/templates/partials/` se precisar.
2. `apps/worker/assets/css/besave.css` — Tailwind compilado **ou** CSS puro com variáveis; ≤ 20 KB
   comprimido. Este arquivo será substituído pelo build do site em BSV-30; a interface é o nome e as
   classes usadas pelo template, documentadas em `apps/worker/templates/README.md`.
3. `apps/worker/tests/fixtures/paginas/` — os HTML esperados (golden) para `oferta-pagina-ok.json`
   e para uma variante encerrada.
4. Um binário de desenvolvimento `cargo run --bin render-oferta -- fixture.json > out.html` para
   inspecionar no browser (pequeno, sem lógica além de carregar o template).

## Estrutura da página (ordem)
1. `<head>`: `<title>` = título integral + " | Besave"; `<meta name="description">` = primeiros 155
   caracteres da descrição do produto (ou do título); `<link rel="canonical" href="https://besave.com.br/oferta/{id}/">`;
   Open Graph (`og:title`, `og:description`, `og:image` = `img/ofertas/{id}.webp` absoluta, `og:url`);
   `schema.org/Product` com `offers` (`Offer`: `price` em reais decimal, `priceCurrency` BRL,
   `availability` InStock/Discontinued conforme `status`, `url` canônica) em JSON-LD; `<meta name="robots"
   content="noindex">` **só** quando `status = ENCERRADA`; `<link rel="stylesheet" href="/assets/besave.css">`;
   viewport com `viewport-fit=cover`.
2. Cabeçalho mínimo: logo texto "Besave" → `/`, links para as 10 áreas por slug (CONTRATO §2.3).
3. Faixa "Oferta expirada" abaixo do título quando `ENCERRADA` (classe `encerrada` no `<body>`).
4. Imagem `img/ofertas/{id}.webp` com `width`/`height` fixos, `loading="eager"`, `alt` = título;
   fallback `img/placeholder/{area}.webp` via `onerror` — **exceção única** de JS na página, inline,
   uma linha.
5. Bloco de preço: `preco_de` riscado (se houver), `preco_por` em destaque, selo `-{desconto_pct}%`
   (se houver), loja (rótulo do enum), tempo desde `dt_oferta` renderizado **no servidor** como data
   absoluta legível ("publicada em 24/09/2026 12:40") — sem JS de relógio.
6. Cupom: caixa com o código quando `cupom` não é nulo; sem botão "copiar" (JS) nesta versão.
7. CTA "Acesse a oferta" → `/ir/{id}` com `rel="nofollow sponsored"`; desabilitado (sem `href`,
   `aria-disabled`) quando `ENCERRADA`.
8. Avaliação: `nota` (1 decimal) e `qt_avaliacoes` quando ambos não nulos.
9. Detalhes do produto: `descricao` em parágrafo; lista `<dl>` com marca, fabricante, modelo,
   país, gênero, faixa etária — cada linha só se não nula.
10. Faixa de preço (barra min → atual → max) só quando `preco_min < preco_max`; CSS puro (posição
    calculada no template como percentual).
11. Rodapé: links para a área da oferta (`/{slug_area}/`) e para a home.

## Regras
- Zero JavaScript além do `onerror` da imagem. Nada de framework. Nada de fonte externa (system stack).
- Todo texto vindo do JSON escapado (minijinja `autoescape` ligado). Testar com título contendo `<script>`.
- HTML válido (validar com `html5ever`/`html-validate` no teste ou script de dev).
- Orçamento: HTML ≤ 30 KB bruto sem CSS inline; CSS ≤ 20 KB comprimido.
- Acessibilidade mínima: um `<h1>`, `alt` em toda imagem, contraste AA no preço e no CTA, foco visível.
- Rótulos e slugs de área e público vêm de uma tabela única no template (`areas.json` gerado a partir
  de CONTRATO §2.3 — não duplicar à mão em dois lugares).
- Mobile-first; a 360 px de largura nada quebra; a 1280 px a imagem fica ao lado do preço.

## Fora de escopo
Geração em massa e sitemap (BSV-21), busca, header definitivo e design system (BSV-30), botão copiar
cupom, "ofertas similares", comentários, compartilhamento.

## Critério de aceite
- Golden test: renderizar `oferta-pagina-ok.json` e a variante encerrada → igual byte a byte aos
  fixtures (regenerar goldens é um comando documentado, não automático).
- Página ativa: sem `noindex`; JSON-LD válido (parse + campos obrigatórios); `canonical` correto;
  CTA com `href="/ir/5412"` e `rel="nofollow sponsored"`.
- Página encerrada: `noindex` presente; `<body class="encerrada">`; CTA sem `href`; faixa visível.
- Escape: título com `<script>` aparece como texto.
- Campos nulos do produto não geram linhas vazias no `<dl>`; faixa de preço ausente quando `preco_min ≥ preco_max`.
- Lighthouse (dono, no browser sobre o `out.html` servido localmente): Performance ≥ 95, SEO ≥ 95,
  Acessibilidade ≥ 90 em mobile.
- HTML de `oferta-pagina-ok` ≤ 30 KB; `besave.css` ≤ 20 KB comprimido.

## Definition of done
PR com screenshots mobile e desktop (ativa e encerrada), relatório Lighthouse colado, README do
template com a lista de classes/variáveis que o BSV-30 precisa manter.
