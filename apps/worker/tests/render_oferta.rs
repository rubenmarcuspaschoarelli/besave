//! BIN-01, BIN-02 (BSV-20): binário de desenvolvimento `render-oferta`.

use std::path::PathBuf;
use std::process::{Command, Output};

use worker::modelo::OfertaPagina;
use worker::pagina_html::TemplateOferta;

fn rodar(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_render-oferta"))
        .args(args)
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .unwrap()
}

fn caminho_fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../packages/contract/fixtures/oferta-pagina-ok.json")
}

// BIN-01
#[test]
fn imprime_o_mesmo_html_do_template() {
    let caminho = caminho_fixture();
    let out = rodar(&[caminho.to_str().unwrap()]);
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let oferta: OfertaPagina =
        serde_json::from_str(&std::fs::read_to_string(&caminho).unwrap()).unwrap();
    let esperado = TemplateOferta::novo().unwrap().renderizar(&oferta).unwrap();
    assert_eq!(String::from_utf8(out.stdout).unwrap(), esperado);
}

// BIN-02
#[test]
fn entrada_invalida_sai_com_erro() {
    let sem_arquivo = rodar(&["nao-existe.json"]);
    assert!(!sem_arquivo.status.success());
    assert!(sem_arquivo.stdout.is_empty());
    assert!(String::from_utf8_lossy(&sem_arquivo.stderr).contains("nao-existe.json"));

    let chunk = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../packages/contract/fixtures/chunk-ok.json");
    let nao_pagina = rodar(&[chunk.to_str().unwrap()]);
    assert!(!nao_pagina.status.success());
    assert!(nao_pagina.stdout.is_empty());
    assert!(String::from_utf8_lossy(&nao_pagina.stderr).contains("não é OfertaPagina"));

    let sem_argumento = rodar(&[]);
    assert!(!sem_argumento.status.success());
    assert!(String::from_utf8_lossy(&sem_argumento.stderr).contains("uso: render-oferta"));
}

// PAG-16: o fuso do sistema não muda a saída.
#[test]
fn saida_nao_depende_do_fuso_do_sistema() {
    let caminho = caminho_fixture();
    let saidas: Vec<Vec<u8>> = ["UTC", "America/New_York", "Asia/Tokyo", "America/Sao_Paulo"]
        .iter()
        .map(|tz| {
            let out = Command::new(env!("CARGO_BIN_EXE_render-oferta"))
                .arg(&caminho)
                .env("TZ", tz)
                .output()
                .unwrap();
            assert!(out.status.success());
            out.stdout
        })
        .collect();
    assert!(saidas.windows(2).all(|par| par[0] == par[1]));
    let html = String::from_utf8(saidas[0].clone()).unwrap();
    assert!(html.contains(">24/09/2026 às 09:40</time>"));
}
