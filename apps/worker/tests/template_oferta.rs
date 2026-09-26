//! BSV-20: página estática da oferta (docs/specs/BSV-20.md, .specs/features/BSV-20/spec.md).

mod comum;

use std::path::PathBuf;

use comum::fixture;
use serde_json::Value;
use worker::modelo::OfertaPagina;
use worker::pagina_html::{TABELA, TemplateOferta};

fn raiz() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn oferta_ok() -> OfertaPagina {
    serde_json::from_str(&fixture("oferta-pagina-ok.json")).unwrap()
}

fn render(o: &OfertaPagina) -> String {
    TemplateOferta::novo().unwrap().renderizar(o).unwrap()
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
