//! HDR-01..04: `meta_para` devolve os headers de MANIFEST §4 por prefixo.

mod comum;

use comum::{AGORA, linha, mapeamento};
use worker::fonte::FakeFonte;
use worker::geracao::gerar;
use worker::publicador::{Meta, Publicador, PublicadorMemoria, meta_para};
use worker::redirects::RedirectsMemoria;

const JSON: &str = "application/json";
const HTML: &str = "text/html; charset=utf-8";
const IMUTAVEL: &str = "public, max-age=31536000, immutable";
const CURTO: &str = "public, max-age=300";

fn meta(ct: &'static str, ce: Option<&'static str>, cc: &'static str) -> Option<Meta> {
    Some(Meta {
        content_type: ct,
        content_encoding: ce,
        cache_control: cc,
    })
}

#[test]
fn tabela_do_manifest_md_secao_4() {
    let manifest = meta(JSON, None, "public, max-age=300, stale-while-revalidate=60");
    let casos = [
        ("manifest.json", manifest),
        (
            "data/chunks/5-9f2a1c3b4d5e6f70.json.br",
            meta(JSON, Some("br"), IMUTAVEL),
        ),
        (
            "data/busca/aa310912ab34cd56.json.br",
            meta(JSON, Some("br"), IMUTAVEL),
        ),
        (
            "oferta/5412/index.html",
            meta(
                HTML,
                None,
                "public, max-age=600, stale-while-revalidate=300",
            ),
        ),
        ("elas/index.html", meta(HTML, None, CURTO)),
        ("elas/feminino/index.html", meta(HTML, None, CURTO)),
        ("img/ofertas/5412.webp", meta("image/webp", None, IMUTAVEL)),
        (
            "img/ofertas/5412_small.webp",
            meta("image/webp", None, IMUTAVEL),
        ),
        ("img/produtos/910.webp", meta("image/webp", None, IMUTAVEL)),
        (
            "img/placeholder/TECH.webp",
            meta("image/webp", None, IMUTAVEL),
        ),
        (
            "_app/immutable/entry/app.B1x2.js",
            meta("text/javascript; charset=utf-8", None, IMUTAVEL),
        ),
        (
            "_app/immutable/assets/0.C3d4.css",
            meta("text/css; charset=utf-8", None, IMUTAVEL),
        ),
        ("_app/version.json", meta(JSON, None, IMUTAVEL)),
        ("index.html", meta(HTML, None, CURTO)),
        ("sitemap.xml", meta("application/xml", None, CURTO)),
        ("sitemap-0.xml", meta("application/xml", None, CURTO)),
        ("robots.txt", meta("text/plain; charset=utf-8", None, CURTO)),
    ];
    for (chave, esperado) in casos {
        assert_eq!(meta_para(chave), esperado, "{chave}");
    }
}

#[test]
fn manifest_prev_tem_headers_do_manifest() {
    assert_eq!(meta_para("manifest.prev.json"), meta_para("manifest.json"));
    assert!(meta_para("manifest.prev.json").is_some());
}

#[test]
fn chave_fora_da_tabela_nao_tem_headers() {
    for chave in [
        "",
        "segredo.env",
        "data/outro/x.json",
        "oferta/5412/foto.jpg",
        "img/ofertas/5412.png",
        "_app/binario.exe",
        "manifest.json.bak",
    ] {
        assert_eq!(meta_para(chave), None, "{chave}");
    }
}

#[test]
fn gerar_grava_com_a_meta_da_tabela() {
    let mut p = PublicadorMemoria::new();
    let fonte = FakeFonte::new(vec![linha(5412), linha(7001)], vec![], AGORA);
    gerar(
        &fonte,
        &mapeamento(),
        &mut p,
        &mut RedirectsMemoria::new(),
        AGORA,
    )
    .unwrap();
    gerar(
        &fonte,
        &mapeamento(),
        &mut p,
        &mut RedirectsMemoria::new(),
        AGORA + 600,
    )
    .unwrap();
    let chaves = p.gravacoes().to_vec();
    assert!(
        chaves.iter().any(|c| c == "manifest.prev.json"),
        "{chaves:?}"
    );
    assert!(
        chaves.iter().any(|c| c.starts_with("data/chunks/")),
        "{chaves:?}"
    );
    for c in chaves {
        assert_eq!(p.meta(&c), meta_para(&c), "{c}");
        assert!(p.existe(&c).unwrap());
    }
}
