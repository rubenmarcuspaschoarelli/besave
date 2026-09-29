//! SIT-03, SIT-06, SIT-08, SIT-09, SIT-15: sitemaps, robots.txt e config do site (BSV-21).

use std::collections::HashMap;

use worker::site::{ConfigSite, ErroConfigSite, MAX_URLS_SITEMAP, robots, sitemaps};

const BASE: &str = "https://besave.com.br";

fn env(pares: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
    let m: HashMap<String, String> = pares
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
    move |k| m.get(k).cloned()
}

fn ativas(n: i64) -> Vec<(i64, String)> {
    (1..=n)
        .map(|id| (id, "2026-09-24T12:40:00Z".to_owned()))
        .collect()
}

fn gerar(ativas: &[(i64, String)]) -> Vec<(String, Vec<u8>)> {
    let refs: Vec<(i64, &str)> = ativas.iter().map(|(id, dt)| (*id, dt.as_str())).collect();
    sitemaps(&refs, BASE)
}

fn arquivo<'a>(arquivos: &'a [(String, Vec<u8>)], chave: &str) -> &'a str {
    let (_, b) = arquivos
        .iter()
        .find(|(c, _)| c == chave)
        .unwrap_or_else(|| panic!("sem {chave}"));
    std::str::from_utf8(b).unwrap()
}

/// `(tag raiz, textos de <loc>, textos de <lastmod>)` de um XML que precisa fazer parse.
fn ler_xml(xml: &str) -> (String, Vec<String>, Vec<String>) {
    let doc = roxmltree::Document::parse(xml).unwrap_or_else(|e| panic!("XML inválido: {e}"));
    let raiz = doc.root_element();
    assert_eq!(
        raiz.tag_name().namespace(),
        Some("http://www.sitemaps.org/schemas/sitemap/0.9")
    );
    let textos = |tag: &str| -> Vec<String> {
        raiz.descendants()
            .filter(|n| n.has_tag_name(tag))
            .map(|n| n.text().unwrap_or_default().to_owned())
            .collect()
    };
    (
        raiz.tag_name().name().to_owned(),
        textos("loc"),
        textos("lastmod"),
    )
}

/// SIT-06: 46 000 ativas → sitemap-1 (45 000) + sitemap-2 (1 000) + index; parse e ≤ 50 MB.
#[test]
fn quarenta_e_seis_mil_ativas_viram_dois_sitemaps_e_um_index() {
    assert_eq!(MAX_URLS_SITEMAP, 45_000);
    let arquivos = gerar(&ativas(46_000));
    let mut chaves: Vec<&str> = arquivos.iter().map(|(c, _)| c.as_str()).collect();
    chaves.sort();
    assert_eq!(chaves, ["sitemap-1.xml", "sitemap-2.xml", "sitemap.xml"]);
    for (c, b) in &arquivos {
        assert!(b.len() <= 50 * 1024 * 1024, "{c}: {} B", b.len());
    }

    let (raiz, locs, _) = ler_xml(arquivo(&arquivos, "sitemap-1.xml"));
    assert_eq!(raiz, "urlset");
    assert_eq!(locs.len(), 45_000);
    assert_eq!(locs[0], "https://besave.com.br/oferta/1/");
    assert_eq!(locs[44_999], "https://besave.com.br/oferta/45000/");

    let (_, locs, _) = ler_xml(arquivo(&arquivos, "sitemap-2.xml"));
    assert_eq!(locs.len(), 1_000);
    assert_eq!(locs[0], "https://besave.com.br/oferta/45001/");
    assert_eq!(locs[999], "https://besave.com.br/oferta/46000/");

    let (raiz, locs, _) = ler_xml(arquivo(&arquivos, "sitemap.xml"));
    assert_eq!(raiz, "sitemapindex");
    assert_eq!(
        locs,
        [
            "https://besave.com.br/sitemap-1.xml",
            "https://besave.com.br/sitemap-2.xml"
        ]
    );
}

/// SIT-06 borda: exatamente 45 000 cabe num arquivo só.
#[test]
fn quarenta_e_cinco_mil_ativas_cabem_num_sitemap() {
    let arquivos = gerar(&ativas(45_000));
    let mut chaves: Vec<&str> = arquivos.iter().map(|(c, _)| c.as_str()).collect();
    chaves.sort();
    assert_eq!(chaves, ["sitemap-1.xml", "sitemap.xml"]);
    let (_, locs, _) = ler_xml(arquivo(&arquivos, "sitemap-1.xml"));
    assert_eq!(locs.len(), 45_000);
}

/// SIT-06 borda: sem ativas, o index aponta para um `sitemap-1.xml` com `urlset` vazio.
#[test]
fn sem_ativas_o_index_aponta_para_urlset_vazio() {
    let arquivos = gerar(&[]);
    let (raiz, locs, _) = ler_xml(arquivo(&arquivos, "sitemap-1.xml"));
    assert_eq!((raiz.as_str(), locs.len()), ("urlset", 0));
    let (_, locs, _) = ler_xml(arquivo(&arquivos, "sitemap.xml"));
    assert_eq!(locs, ["https://besave.com.br/sitemap-1.xml"]);
}

/// SIT-03: `<loc>` = `{base}/oferta/{id}/`, `<lastmod>` = AAAA-MM-DD de `dt_oferta`, id crescente.
#[test]
fn loc_e_lastmod_de_cada_oferta() {
    let arquivos = gerar(&[
        (5413, "2026-09-24T12:41:00Z".to_owned()),
        (5412, "2026-09-23T23:59:59Z".to_owned()),
    ]);
    let (_, locs, lastmods) = ler_xml(arquivo(&arquivos, "sitemap-1.xml"));
    assert_eq!(
        locs,
        [
            "https://besave.com.br/oferta/5412/",
            "https://besave.com.br/oferta/5413/"
        ]
    );
    assert_eq!(lastmods, ["2026-09-23", "2026-09-24"]);
}

/// Mesma entrada → mesmos bytes (o worker só regrava sitemap que mudou).
#[test]
fn sitemaps_sao_deterministicos() {
    assert_eq!(gerar(&ativas(10)), gerar(&ativas(10)));
}

/// SIT-08.
#[test]
fn robots_nao_indexavel_bloqueia_tudo() {
    assert_eq!(robots(false, BASE), "User-agent: *\nDisallow: /\n");
}

/// SIT-09.
#[test]
fn robots_indexavel_libera_e_aponta_o_sitemap() {
    let r = robots(true, BASE);
    assert!(r.starts_with("User-agent: *\nAllow: /\n"), "{r}");
    assert!(
        r.contains("Sitemap: https://besave.com.br/sitemap.xml\n"),
        "{r}"
    );
    assert!(!r.contains("Disallow"), "{r}");
}

/// SIT-15: sem variáveis → base padrão e não indexável.
#[test]
fn config_padrao() {
    let c = ConfigSite::de(env(&[])).unwrap();
    assert_eq!(c.base, "https://besave.com.br");
    assert!(!c.indexavel);
    assert_eq!(robots(c.indexavel, &c.base), "User-agent: *\nDisallow: /\n");
}

/// SIT-09 pelo env: `BESAVE_INDEXAVEL=true` → `Sitemap:` com a base configurada.
#[test]
fn config_indexavel_com_base_do_env() {
    let c = ConfigSite::de(env(&[
        ("BESAVE_INDEXAVEL", "true"),
        ("BESAVE_BASE_URL", "https://d1.cloudfront.net/"),
    ]))
    .unwrap();
    assert!(c.indexavel);
    assert_eq!(c.base, "https://d1.cloudfront.net");
    assert!(
        robots(c.indexavel, &c.base).contains("Sitemap: https://d1.cloudfront.net/sitemap.xml\n")
    );
}

#[test]
fn indexavel_aceita_1_0_false_e_vazio() {
    for (v, esperado) in [("1", true), ("0", false), ("false", false), ("", false)] {
        let c = ConfigSite::de(env(&[("BESAVE_INDEXAVEL", v)])).unwrap();
        assert_eq!(c.indexavel, esperado, "{v:?}");
    }
}

/// SIT-15: valor fora de true/false/1/0 falha nomeando a variável.
#[test]
fn indexavel_invalida_nomeia_a_variavel() {
    let erro = ConfigSite::de(env(&[("BESAVE_INDEXAVEL", "talvez")])).unwrap_err();
    assert!(
        matches!(erro, ErroConfigSite::Invalida("BESAVE_INDEXAVEL", _)),
        "{erro:?}"
    );
    assert!(erro.to_string().contains("BESAVE_INDEXAVEL"), "{erro}");
}

/// Base relativa geraria `<loc>` inválido.
#[test]
fn base_sem_esquema_http_nomeia_a_variavel() {
    let erro = ConfigSite::de(env(&[("BESAVE_BASE_URL", "besave.com.br")])).unwrap_err();
    assert!(
        matches!(erro, ErroConfigSite::Invalida("BESAVE_BASE_URL", _)),
        "{erro:?}"
    );
}

/// Borda: `/` final removida da base, sem `//oferta`.
#[test]
fn base_com_barra_final_nao_duplica_a_barra() {
    let c = ConfigSite::de(env(&[("BESAVE_BASE_URL", "https://besave.com.br/")])).unwrap();
    let refs = [(1, "2026-09-24T12:40:00Z")];
    let arquivos = sitemaps(&refs, &c.base);
    let (_, locs, _) = ler_xml(arquivo(&arquivos, "sitemap-1.xml"));
    assert_eq!(locs, ["https://besave.com.br/oferta/1/"]);
}
