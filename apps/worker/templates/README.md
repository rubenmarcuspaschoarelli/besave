# Template da página de oferta (BSV-20)

`oferta.html` (minijinja) + `areas.json` → `/oferta/{id}/index.html`. CSS em
`../assets/css/besave.css`, servido como `/assets/besave.css`. Render: `worker::pagina_html::TemplateOferta`
(template e tabela embutidos no binário com `include_str!`). BSV-21 liga à geração.

## Comandos (em `apps/worker/`)

```sh
# inspecionar no browser
cargo run --bin render-oferta -- ../../packages/contract/fixtures/oferta-pagina-ok.json > out.html

# regenerar os goldens (manual; revise o diff antes de commitar)
cargo run --bin render-oferta -- ../../packages/contract/fixtures/oferta-pagina-ok.json > tests/fixtures/paginas/oferta-pagina-ok.html
cargo run --bin render-oferta -- tests/fixtures/paginas/oferta-pagina-encerrada.json > tests/fixtures/paginas/oferta-pagina-encerrada.html

# validar o HTML (config em .htmlvalidate.json)
npx html-validate tests/fixtures/paginas/*.html
```

`.htmlvalidate.json` usa `html-validate:recommended` sem `no-inline-style`: o único `style` é a
posição do marcador da faixa de preço (`left:{pct}%`), calculada no template como a spec pede.
Templates, CSS e goldens são `eol=lf` (`.gitattributes`): os goldens são comparados byte a byte.

## Variáveis do template

| variável | tipo | origem |
|---|---|---|
| `o` | `OfertaPagina` | CONTRATO §4 (campos com os nomes do contrato) |
| `tabela.areas` | lista `{valor, rotulo, slug}` | `areas.json`, ordem do enum `Area` |
| `tabela.publicos` | lista `{valor, slug}` | `areas.json` (ainda não usada na página) |
| `tabela.lojas` | mapa `valor → rótulo` | `areas.json` |
| `url` | string | `https://besave.com.br/oferta/{id}/` (canonical, `og:url`) |
| `imagem` | string | `https://besave.com.br/img/ofertas/{id}.webp` (`og:image`) |
| `encerrada` | bool | `o.status == ENCERRADA` |
| `descricao` | string | 155 primeiros caracteres de `produto.descricao` (ou do título) |
| `jsonld` | objeto | `schema.org/Product` + `Offer`, serializado com `tojson` |

Filtros: `reais` (centavos → `R$ 1.299,90`), `milhar` (`1.832`), `nota` (`4,6`),
`data_br` (ISO UTC → `24/09/2026 às 09:40`, horário de Brasília, UTC−3).

`areas.json` é a tabela única de rótulos e slugs; o teste `tabela_de_areas_igual_ao_contrato`
falha se ela divergir de CONTRATO §2.3 ou do `enums.schema.json`.

## Classes que BSV-30 precisa manter

O teste `classes_do_template_existem_no_css` falha se o template usar classe sem regra no CSS.

| classe | elemento | papel |
|---|---|---|
| `encerrada` | `<body>` | oferta expirada: imagem em cinza, preço apagado |
| `topo`, `logo`, `menu` | cabeçalho | logo "Besave" e links das 10 áreas |
| `oferta` | `<main>` | contêiner da página |
| `titulo` | `<h1>` | título integral |
| `expirada` | `<p>` | faixa "Oferta expirada" (só encerrada) |
| `compra` | `<div>` | grade imagem + painel (lado a lado a partir de 1024 px) |
| `foto` | `<div>` | caixa quadrada da imagem (`object-fit: contain`) |
| `painel` | `<div>` | preço, cupom, CTA, avaliação |
| `preco`, `loja`, `de`, `por`, `desconto`, `data` | bloco de preço | loja, preço de (riscado), preço por, selo `-N%`, data de publicação |
| `cupom`, `codigo` | `<p>`, `<code>` | caixa do cupom |
| `cta` | `<a>` | "Acesse a oferta"; `[aria-disabled="true"]` sem `href` quando encerrada |
| `avaliacao` | `<p>` | nota e quantidade de avaliações |
| `detalhes`, `ficha` | `<section>`, `<dl>` | descrição e ficha técnica (linhas `div > dt + dd`) |
| `faixa`, `barra`, `marcador`, `limites` | faixa de preço | barra min → max com marcador em `left:{pct}%` |
| `rodape` | `<footer>` | links para a área e para a home |

Variáveis CSS (`:root`): `--fundo`, `--superficie`, `--borda`, `--texto`, `--suave`, `--marca`,
`--marca-escura`, `--sobre-marca`, `--desconto`, `--aviso-fundo`, `--aviso-texto`, `--foco`,
`--raio`, `--largura`.
