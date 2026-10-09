//! SMP-02..SMP-04, SMP-06: `sitemap-paginas.xml` (BSV-33) com contagens sintéticas.

use worker::modelo::{Area, Publico};
use worker::site::{
    AtivaPagina, MAX_PCT_SUBPAGINA, MIN_ATIVAS_AREA, MIN_ATIVAS_SUBPAGINA, sitemap_paginas,
};

const BASE: &str = "https://besave.com.br";
const DP: &str = "2026-10-08T15:00:00Z";

fn n(area: Area, publico: Publico, qtd: usize, dp: &'static str) -> Vec<AtivaPagina<'static>> {
    vec![AtivaPagina { area, publico, dp }; qtd]
}

/// `(loc, lastmod)` de cada `<url>`; o XML precisa fazer parse com o namespace 0.9.
fn urls(ativas: &[AtivaPagina]) -> Vec<(String, Option<String>)> {
    let bytes = sitemap_paginas(ativas, BASE);
    let xml = std::str::from_utf8(&bytes).unwrap();
    let doc = roxmltree::Document::parse(xml).unwrap_or_else(|e| panic!("XML inválido: {e}"));
    let raiz = doc.root_element();
    assert_eq!(raiz.tag_name().name(), "urlset");
    assert_eq!(
        raiz.tag_name().namespace(),
        Some("http://www.sitemaps.org/schemas/sitemap/0.9")
    );
    raiz.children()
        .filter(|u| u.has_tag_name("url"))
        .map(|u| {
            let filho = |t: &str| {
                u.children()
                    .find(|c| c.has_tag_name(t))
                    .map(|c| c.text().unwrap_or_default().to_owned())
            };
            (filho("loc").unwrap(), filho("lastmod"))
        })
        .collect()
}

fn locs(ativas: &[AtivaPagina]) -> Vec<String> {
    urls(ativas).into_iter().map(|(l, _)| l).collect()
}

/// SMP-06: limiares da spec como constantes nomeadas.
#[test]
fn limiares_sao_os_da_spec() {
    assert_eq!(MIN_ATIVAS_AREA, 10);
    assert_eq!(MIN_ATIVAS_SUBPAGINA, 20);
    assert_eq!(MAX_PCT_SUBPAGINA, 90);
}

/// SMP-02: sem nenhuma ativa, só a home (sem `lastmod`).
#[test]
fn sem_ativas_so_a_home() {
    assert_eq!(urls(&[]), [("https://besave.com.br/".to_owned(), None)]);
}

/// SMP-02: área com 10 entra; com 9 fica fora.
#[test]
fn area_com_dez_entra_e_com_nove_fica_fora() {
    let mut a = n(Area::Pets, Publico::Unissex, 5, DP);
    a.extend(n(Area::Pets, Publico::Feminino, 5, DP));
    a.extend(n(Area::Players, Publico::Unissex, 9, DP));
    assert_eq!(
        locs(&a),
        ["https://besave.com.br/", "https://besave.com.br/pets/"]
    );
}

/// SMP-03: 20 ativas e exatamente 90% da área entra; 19 fica fora mesmo abaixo de 90%.
#[test]
fn subpagina_com_vinte_e_noventa_por_cento_entra() {
    // ESPORTE_VIDA: 20 feminino (≈ 51%), 19 masculino (≈ 49%).
    let mut a = n(Area::EsporteVida, Publico::Feminino, 20, DP);
    a.extend(n(Area::EsporteVida, Publico::Masculino, 19, DP));
    // ELAS: 180 unissex de 200 = 90%.
    a.extend(n(Area::Elas, Publico::Unissex, 180, DP));
    a.extend(n(Area::Elas, Publico::Feminino, 20, DP));
    assert_eq!(
        locs(&a),
        [
            "https://besave.com.br/",
            "https://besave.com.br/elas/",
            "https://besave.com.br/elas/feminino/",
            "https://besave.com.br/elas/unissex/",
            "https://besave.com.br/esporte-vida/",
            "https://besave.com.br/esporte-vida/feminino/",
        ]
    );
}

/// SMP-03: 91% da área fica fora (quase repete a área); os 9% restantes ficam fora por volume.
#[test]
fn subpagina_com_noventa_e_um_por_cento_fica_fora() {
    let mut a = n(Area::MeuLar, Publico::Unissex, 91, DP);
    a.extend(n(Area::MeuLar, Publico::Feminino, 9, DP));
    assert_eq!(
        locs(&a),
        ["https://besave.com.br/", "https://besave.com.br/meu-lar/"]
    );
    // 910 de 1000: 91%, com volume de sobra, continua fora; 90 de 1000 entra.
    let mut b = n(Area::MeuLar, Publico::Unissex, 910, DP);
    b.extend(n(Area::MeuLar, Publico::Feminino, 90, DP));
    assert_eq!(
        locs(&b),
        [
            "https://besave.com.br/",
            "https://besave.com.br/meu-lar/",
            "https://besave.com.br/meu-lar/feminino/",
        ]
    );
}

/// SMP-03: os 90% são da área, não do total: com outra área grande, 91% de MEU_LAR (45% do total)
/// continua fora.
#[test]
fn noventa_por_cento_e_da_area_e_nao_do_total() {
    let mut a = n(Area::MeuLar, Publico::Unissex, 910, DP);
    a.extend(n(Area::MeuLar, Publico::Feminino, 90, DP));
    a.extend(n(Area::Elas, Publico::Feminino, 500, DP));
    a.extend(n(Area::Elas, Publico::Unissex, 500, DP));
    assert_eq!(
        locs(&a),
        [
            "https://besave.com.br/",
            "https://besave.com.br/meu-lar/",
            "https://besave.com.br/meu-lar/feminino/",
            "https://besave.com.br/elas/",
            "https://besave.com.br/elas/feminino/",
            "https://besave.com.br/elas/unissex/",
        ]
    );
}

/// SMP-03: path `/{slug}/{publico}/` com o público em minúsculas, na ordem do enum.
#[test]
fn todos_os_publicos_usam_o_slug_minusculo() {
    let mut a = n(Area::Familia, Publico::Infantil, 30, DP);
    a.extend(n(Area::Familia, Publico::Masculino, 30, DP));
    a.extend(n(Area::Familia, Publico::Unissex, 30, DP));
    assert_eq!(
        locs(&a),
        [
            "https://besave.com.br/",
            "https://besave.com.br/familia/",
            "https://besave.com.br/familia/masculino/",
            "https://besave.com.br/familia/unissex/",
            "https://besave.com.br/familia/infantil/",
        ]
    );
}

/// SMP-04: `lastmod` = data em Brasília do maior `dp` da página; 01:00Z ainda é o dia anterior.
#[test]
fn lastmod_e_a_data_em_brasilia_do_maior_dp() {
    let mut a = n(Area::Tech, Publico::Unissex, 9, "2026-10-01T12:00:00Z");
    // Maior `dp` de TECH (e de tudo): 9 de outubro 01:00Z = 8 de outubro 22:00 em Brasília.
    a.extend(n(Area::Tech, Publico::Unissex, 1, "2026-10-09T01:00:00Z"));
    a.extend(n(Area::Pets, Publico::Unissex, 10, "2026-10-05T03:00:00Z"));
    assert_eq!(
        urls(&a),
        [
            (
                "https://besave.com.br/".to_owned(),
                Some("2026-10-08".to_owned())
            ),
            (
                "https://besave.com.br/tech/".to_owned(),
                Some("2026-10-08".to_owned())
            ),
            (
                "https://besave.com.br/pets/".to_owned(),
                Some("2026-10-05".to_owned())
            ),
        ]
    );
}

/// SMP-04: `lastmod` da subpágina vem só das ativas dela, não da área.
#[test]
fn lastmod_da_subpagina_e_o_dela() {
    let mut a = n(Area::Elas, Publico::Feminino, 20, "2026-10-07T12:00:00Z");
    a.extend(n(Area::Elas, Publico::Unissex, 20, "2026-10-02T12:00:00Z"));
    let u = urls(&a);
    let de = |loc: &str| u.iter().find(|(l, _)| l == loc).unwrap().1.clone();
    assert_eq!(
        de("https://besave.com.br/elas/unissex/").as_deref(),
        Some("2026-10-02")
    );
    assert_eq!(
        de("https://besave.com.br/elas/feminino/").as_deref(),
        Some("2026-10-07")
    );
    assert_eq!(
        de("https://besave.com.br/elas/").as_deref(),
        Some("2026-10-07")
    );
}

/// Mesma entrada em outra ordem → mesmos bytes (o worker só regrava o que mudou, AD-041).
#[test]
fn deterministico_independente_da_ordem() {
    let mut a = n(Area::Elas, Publico::Feminino, 30, DP);
    a.extend(n(Area::Tech, Publico::Unissex, 30, "2026-10-01T00:00:00Z"));
    let mut b = a.clone();
    b.reverse();
    assert_eq!(sitemap_paginas(&a, BASE), sitemap_paginas(&b, BASE));
}
