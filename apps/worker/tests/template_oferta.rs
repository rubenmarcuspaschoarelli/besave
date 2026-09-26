//! BSV-20: página estática da oferta (docs/specs/BSV-20.md, .specs/features/BSV-20/spec.md).

mod comum;

use std::path::PathBuf;

use comum::fixture;
use serde_json::Value;
use worker::modelo::{Area, Loja, OfertaPagina, Status};
use worker::pagina_html::{TABELA, TemplateOferta};

fn raiz() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn oferta_ok() -> OfertaPagina {
    serde_json::from_str(&fixture("oferta-pagina-ok.json")).unwrap()
}

fn oferta_encerrada() -> OfertaPagina {
    OfertaPagina {
        status: Status::Encerrada,
        ..oferta_ok()
    }
}

fn render(o: &OfertaPagina) -> String {
    TemplateOferta::novo().unwrap().renderizar(o).unwrap()
}

/// Primeira tag que começa com `inicio` (ex.: `<a class="cta"`), até o `>`.
fn tag<'a>(html: &'a str, inicio: &str) -> &'a str {
    let i = html.find(inicio).unwrap_or_else(|| panic!("sem {inicio}"));
    &html[i..i + html[i..].find('>').unwrap() + 1]
}

/// Trecho entre `abre` (primeira ocorrência) e o próximo `fecha`.
fn trecho<'a>(html: &'a str, abre: &str, fecha: &str) -> &'a str {
    let i = html.find(abre).unwrap_or_else(|| panic!("sem {abre}"));
    &html[i..i + html[i..].find(fecha).unwrap()]
}

fn jsonld(html: &str) -> Value {
    let abre = r#"<script type="application/ld+json">"#;
    serde_json::from_str(&trecho(html, abre, "</script>")[abre.len()..]).unwrap()
}

fn ocorrencias(html: &str, t: &str) -> usize {
    html.matches(t).count()
}

/// Linhas `| \`VALOR\` | rótulo | \`slug\` | …` da tabela de CONTRATO §2.3.
fn areas_do_contrato() -> Vec<(String, String, String)> {
    let doc = std::fs::read_to_string(raiz().join("docs/CONTRATO.md")).unwrap();
    let secao = doc
        .split("### 2.3")
        .nth(1)
        .unwrap()
        .split("\n## ")
        .next()
        .unwrap();
    secao
        .lines()
        .filter(|l| l.starts_with("| `"))
        .map(|l| {
            let c: Vec<&str> = l.split('|').map(str::trim).collect();
            let limpa = |s: &str| s.trim_matches('`').to_string();
            (limpa(c[1]), c[2].to_string(), limpa(c[3]))
        })
        .collect()
}

// TAB-01
#[test]
fn tabela_de_areas_igual_ao_contrato() {
    let tabela: Value = serde_json::from_str(TABELA).unwrap();
    let areas: Vec<(String, String, String)> = tabela["areas"]
        .as_array()
        .unwrap()
        .iter()
        .map(|a| {
            let s = |k: &str| a[k].as_str().unwrap().to_string();
            (s("valor"), s("rotulo"), s("slug"))
        })
        .collect();
    let contrato = areas_do_contrato();
    assert_eq!(contrato.len(), 10);
    assert_eq!(areas, contrato);

    let enums: Value = serde_json::from_str(
        &std::fs::read_to_string(raiz().join("packages/contract/schema/enums.schema.json"))
            .unwrap(),
    )
    .unwrap();
    let valores = |def: &str| -> Vec<String> {
        enums["$defs"][def]["enum"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect()
    };
    assert_eq!(
        areas.iter().map(|a| a.0.clone()).collect::<Vec<_>>(),
        valores("Area")
    );

    let publicos: Vec<(String, String)> = tabela["publicos"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| {
            (
                p["valor"].as_str().unwrap().into(),
                p["slug"].as_str().unwrap().into(),
            )
        })
        .collect();
    let esperado: Vec<(String, String)> = valores("Publico")
        .into_iter()
        .map(|v| (v.clone(), v.to_lowercase()))
        .collect();
    assert_eq!(publicos, esperado);

    let lojas = tabela["lojas"].as_object().unwrap();
    let mut chaves: Vec<String> = lojas.keys().cloned().collect();
    let mut enum_lojas = valores("Loja");
    chaves.sort();
    enum_lojas.sort();
    assert_eq!(chaves, enum_lojas);
}

#[test]
fn renderiza_fixture_do_contrato() {
    let html = render(&oferta_ok());
    assert!(html.starts_with("<!doctype html>"));
}

// PAG-03
#[test]
fn head_com_title_description_canonical_og_css_e_viewport() {
    let html = render(&oferta_ok());
    let titulo = "Fone Bluetooth XYZ com ANC, 40h de bateria, resistente a água";
    let descricao = "Fone over-ear com cancelamento ativo de ruído e 40 horas de bateria.";
    let url = "https://besave.com.br/oferta/5412/";
    assert!(html.contains(&format!("<title>{titulo} | Besave</title>")));
    assert!(html.contains(&format!(
        r#"<meta name="description" content="{descricao}">"#
    )));
    assert!(html.contains(&format!(r#"<link rel="canonical" href="{url}">"#)));
    assert!(html.contains(&format!(r#"<meta property="og:url" content="{url}">"#)));
    assert!(html.contains(&format!(r#"<meta property="og:title" content="{titulo}">"#)));
    assert!(html.contains(&format!(
        r#"<meta property="og:description" content="{descricao}">"#
    )));
    assert!(html.contains(
        r#"<meta property="og:image" content="https://besave.com.br/img/ofertas/5412.webp">"#
    ));
    assert!(html.contains(r#"<link rel="stylesheet" href="/assets/besave.css">"#));
    let viewport = tag(&html, r#"<meta name="viewport""#);
    assert!(viewport.contains("viewport-fit=cover"), "{viewport}");
}

// PAG-03
#[test]
fn description_com_155_caracteres_ou_titulo() {
    let mut o = oferta_ok();
    // 200 caracteres sem espaço nas pontas do corte: o 155º é 'x'.
    let longa = "x".repeat(200);
    o.produto.as_mut().unwrap().descricao = longa;
    let html = render(&o);
    let esperado = "x".repeat(155);
    assert!(html.contains(&format!(
        r#"<meta name="description" content="{esperado}">"#
    )));
    assert!(!html.contains(&format!(r#"<meta name="description" content="{esperado}x"#)));

    // Acentos contam como 1 caractere.
    o.produto.as_mut().unwrap().descricao = "é".repeat(160);
    let html = render(&o);
    assert!(html.contains(&format!(
        r#"<meta name="description" content="{}">"#,
        "é".repeat(155)
    )));

    o.produto = None;
    o.titulo = "Kit de pincéis".into();
    let html = render(&o);
    assert!(html.contains(r#"<meta name="description" content="Kit de pincéis">"#));
    assert!(html.contains(r#"<meta property="og:description" content="Kit de pincéis">"#));
}

// PAG-04
#[test]
fn jsonld_product_com_offer() {
    let ld = jsonld(&render(&oferta_ok()));
    assert_eq!(ld["@context"], "https://schema.org");
    assert_eq!(ld["@type"], "Product");
    assert_eq!(
        ld["name"],
        "Fone Bluetooth XYZ com ANC, 40h de bateria, resistente a água"
    );
    assert_eq!(ld["image"], "https://besave.com.br/img/ofertas/5412.webp");
    let offer = &ld["offers"];
    assert_eq!(offer["@type"], "Offer");
    assert_eq!(offer["price"], "199.90");
    assert_eq!(offer["priceCurrency"], "BRL");
    assert_eq!(offer["availability"], "https://schema.org/InStock");
    assert_eq!(offer["url"], "https://besave.com.br/oferta/5412/");

    let ld = jsonld(&render(&oferta_encerrada()));
    assert_eq!(
        ld["offers"]["availability"],
        "https://schema.org/Discontinued"
    );

    let mut o = oferta_ok();
    o.preco_por = 5;
    assert_eq!(jsonld(&render(&o))["offers"]["price"], "0.05");
    o.preco_por = 123_456;
    assert_eq!(jsonld(&render(&o))["offers"]["price"], "1234.56");
}

// PAG-05
#[test]
fn ativa_sem_noindex_e_cta_para_redirect() {
    let html = render(&oferta_ok());
    assert!(!html.contains("noindex"));
    assert_eq!(
        tag(&html, r#"<a class="cta""#),
        r#"<a class="cta" href="/ir/5412" rel="nofollow sponsored">"#
    );
    assert_eq!(tag(&html, "<body"), "<body>");
    assert!(!html.contains("Oferta expirada"));
}

// PAG-06
#[test]
fn encerrada_noindex_classe_faixa_e_cta_desabilitado() {
    let html = render(&oferta_encerrada());
    assert!(html.contains(r#"<meta name="robots" content="noindex">"#));
    assert_eq!(tag(&html, "<body"), r#"<body class="encerrada">"#);
    let h1_fim = html.find("</h1>").unwrap() + "</h1>".len();
    assert!(
        html[h1_fim..]
            .trim_start()
            .starts_with(r#"<p class="expirada">Oferta expirada</p>"#),
        "faixa logo após o h1"
    );
    let cta = tag(&html, r#"<a class="cta""#);
    assert!(!cta.contains("href"), "{cta}");
    assert!(cta.contains(r#"aria-disabled="true""#), "{cta}");
    assert!(!html.contains("/ir/"));
}

// PAG-07
#[test]
fn cabecalho_com_10_areas_e_rodape() {
    let html = render(&oferta_ok());
    let topo = trecho(&html, "<header", "</header>");
    assert!(topo.contains(r#"<a class="logo" href="/">Besave</a>"#));
    for (_, rotulo, slug) in areas_do_contrato() {
        let rotulo = rotulo.replace('&', "&amp;");
        assert!(
            topo.contains(&format!(r#"<a href="/{slug}/">{rotulo}</a>"#)),
            "{slug}"
        );
    }
    assert_eq!(ocorrencias(topo, "<a href=\"/"), 10);

    let mut o = oferta_ok();
    o.area = Area::MeuLar;
    let html = render(&o);
    let rodape = trecho(&html, "<footer", "</footer>");
    assert!(rodape.contains(r#"<a href="/meu-lar/">"#));
    assert!(rodape.contains(r#"<a href="/">"#));
}

// PAG-08
#[test]
fn imagem_com_dimensoes_alt_e_fallback_como_unico_js() {
    let mut o = oferta_ok();
    o.area = Area::EsporteVida;
    let html = render(&o);
    let img = tag(&html, "<img");
    for atributo in [
        r#"src="/img/ofertas/5412.webp""#,
        r#"width="600""#,
        r#"height="600""#,
        r#"loading="eager""#,
        r#"alt="Fone Bluetooth XYZ com ANC, 40h de bateria, resistente a água""#,
        r#"onerror="this.onerror=null;this.src='/img/placeholder/esporte-vida.webp'""#,
    ] {
        assert!(img.contains(atributo), "{atributo} em {img}");
    }
    assert_eq!(ocorrencias(&html, "<img"), 1);
    // O único <script> é o JSON-LD (dado, não JS); o único handler é o onerror.
    assert_eq!(ocorrencias(&html, "<script"), 1);
    assert_eq!(
        ocorrencias(&html, r#"<script type="application/ld+json">"#),
        1
    );
    let handlers: Vec<&str> = html
        .split(|c: char| c.is_whitespace() || c == '<')
        .filter(|t| t.starts_with("on") && t.contains("=\""))
        .collect();
    assert_eq!(handlers.len(), 1, "{handlers:?}");
    assert!(handlers[0].starts_with("onerror="));
    assert!(!html.contains("javascript:"));
}

// PAG-09
#[test]
fn bloco_de_preco() {
    let html = render(&oferta_ok());
    let preco = trecho(&html, r#"<section class="preco""#, "</section>");
    assert!(preco.contains("<s>R$ 299,90</s>"));
    assert!(preco.contains("<strong>R$ 199,90</strong>"));
    assert!(preco.contains("-33%"));
    assert!(preco.contains(">Amazon<"));
    assert!(preco.contains(
        r#"publicada em <time datetime="2026-09-24T12:40:00Z">24/09/2026 às 09:40</time>"#
    ));

    let mut o = oferta_ok();
    o.preco_de = None;
    o.desconto_pct = None;
    o.preco_por = 129_990;
    o.loja = Loja::MercadoLivre;
    o.dt_oferta = "2026-03-01T01:10:00Z".into();
    let html = render(&o);
    assert!(!html.contains("<s>"));
    assert!(!html.contains("desconto"));
    assert!(html.contains("<strong>R$ 1.299,90</strong>"));
    assert!(html.contains(">Mercado Livre<"));
    // Virada de dia e de mês (UTC−3).
    assert!(html.contains(">28/02/2026 às 22:10</time>"));

    o.loja = Loja::Shopee;
    o.dt_oferta = "2027-01-01T02:59:00Z".into();
    let html = render(&o);
    assert!(html.contains(">Shopee<"));
    assert!(html.contains(">31/12/2026 às 23:59</time>"));
}

// PAG-10
#[test]
fn cupom_so_quando_presente() {
    let html = render(&oferta_ok());
    assert!(html.contains(r#"<code class="codigo">BESAVE10</code>"#));
    let mut o = oferta_ok();
    o.cupom = None;
    let html = render(&o);
    assert!(!html.contains(r#"class="cupom""#));
    assert!(!html.contains("<code"));
}

// PAG-11
#[test]
fn avaliacao_so_com_nota_e_quantidade() {
    let html = render(&oferta_ok());
    assert!(
        html.contains(
            r#"<p class="avaliacao">Nota <strong>4,6</strong> de 5 · 1.832 avaliações</p>"#
        )
    );
    let mut o = oferta_ok();
    o.nota = Some(4.0);
    assert!(render(&o).contains("<strong>4,0</strong>"));
    o.qt_avaliacoes = None;
    assert!(!render(&o).contains("avaliacao"));
    let mut o = oferta_ok();
    o.nota = None;
    assert!(!render(&o).contains("avaliacao"));
}

// PAG-12
#[test]
fn ficha_sem_linhas_vazias() {
    let html = render(&oferta_ok());
    let dl = trecho(&html, "<dl", "</dl>");
    assert_eq!(ocorrencias(dl, "<dt>"), 4);
    assert_eq!(ocorrencias(dl, "<dd>"), 4);
    for par in [
        "<dt>Marca</dt><dd>XYZ</dd>",
        "<dt>Fabricante</dt><dd>XYZ Audio Ltda</dd>",
        "<dt>Modelo</dt><dd>XZ-400</dd>",
        "<dt>País de origem</dt><dd>China</dd>",
    ] {
        assert!(dl.contains(par), "{par}");
    }
    assert!(!dl.contains("Gênero") && !dl.contains("Faixa etária"));
    assert!(!html.contains("<dd></dd>"));

    let mut o = oferta_ok();
    let p = o.produto.as_mut().unwrap();
    p.genero = Some("Unissex".into());
    p.faixa_etaria = Some("Adulto".into());
    p.marca = Some(String::new());
    let html = render(&o);
    assert!(html.contains("<dt>Gênero</dt><dd>Unissex</dd>"));
    assert!(html.contains("<dt>Faixa etária</dt><dd>Adulto</dd>"));
    assert!(!html.contains("<dt>Marca</dt>"));

    let p = o.produto.as_mut().unwrap();
    for campo in [
        &mut p.marca,
        &mut p.fabricante,
        &mut p.modelo,
        &mut p.pais_origem,
        &mut p.genero,
        &mut p.faixa_etaria,
    ] {
        *campo = None;
    }
    let html = render(&o);
    assert!(!html.contains("<dl"));
    assert!(
        html.contains(
            "<p>Fone over-ear com cancelamento ativo de ruído e 40 horas de bateria.</p>"
        )
    );

    o.produto = None;
    let html = render(&o);
    assert!(!html.contains("Detalhes do produto"));
    assert!(!html.contains("<dl"));
    assert!(!html.contains(r#"class="faixa""#));
}

// PAG-13
#[test]
fn faixa_de_preco_so_quando_min_menor_que_max() {
    let html = render(&oferta_ok());
    // (19990 − 17990) × 100 ÷ (34990 − 17990) = 11,7 → 11
    let faixa = trecho(&html, r#"<section class="faixa">"#, "</section>");
    assert!(faixa.contains(r#"style="left:11%""#));
    assert!(faixa.contains("R$ 179,90") && faixa.contains("R$ 349,90"));

    let com = |min: Option<i64>, max: Option<i64>, por: i64| {
        let mut o = oferta_ok();
        o.preco_por = por;
        let p = o.produto.as_mut().unwrap();
        p.preco_min = min;
        p.preco_max = max;
        render(&o)
    };
    let sem_faixa = |html: String| !html.contains(r#"class="faixa""#);
    assert!(sem_faixa(com(Some(17990), Some(17990), 17990)));
    assert!(sem_faixa(com(Some(20000), Some(17990), 19990)));
    assert!(sem_faixa(com(None, Some(34990), 19990)));
    assert!(sem_faixa(com(Some(17990), None, 19990)));
    assert!(com(Some(17990), Some(17991), 17990).contains(r#"style="left:0%""#));
    assert!(com(Some(17990), Some(34990), 10000).contains(r#"style="left:0%""#));
    assert!(com(Some(17990), Some(34990), 40000).contains(r#"style="left:100%""#));
    assert!(com(Some(0), Some(200), 100).contains(r#"style="left:50%""#));
}

// PAG-14
#[test]
fn titulo_com_script_vira_texto() {
    let titulo = r#"<script>alert("x")</script> & 'aspas'"#;
    let mut o = oferta_ok();
    o.titulo = titulo.into();
    o.produto.as_mut().unwrap().marca = Some("<b>XYZ</b>".into());
    let html = render(&o);
    assert_eq!(ocorrencias(&html, "<script"), 1, "só o JSON-LD");
    assert_eq!(ocorrencias(&html, "</script>"), 1);
    assert!(html.contains(
        r#"<h1 class="titulo">&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#x27;aspas&#x27;</h1>"#
    ));
    assert!(html.contains("<dd>&lt;b&gt;XYZ&lt;/b&gt;</dd>"));
    assert!(!html.contains("<b>"));
    assert_eq!(jsonld(&html)["name"], titulo);
}

// PAG-15
#[test]
fn exatamente_um_h1() {
    for o in [oferta_ok(), oferta_encerrada()] {
        assert_eq!(ocorrencias(&render(&o), "<h1"), 1);
    }
}
