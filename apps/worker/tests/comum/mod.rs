#![allow(dead_code)]

use std::path::PathBuf;

pub fn fixture(nome: &str) -> String {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../packages/contract/fixtures")
        .join(nome);
    std::fs::read_to_string(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))
}

pub fn caminho_mapeamento() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../packages/contract/mapeamento.json")
}

/// Remove espaços fora de strings: forma compacta da fixture, mesma ordem de chaves.
pub fn compactar(json: &str) -> String {
    let mut out = String::with_capacity(json.len());
    let (mut em_string, mut escape) = (false, false);
    for ch in json.chars() {
        if em_string {
            out.push(ch);
            if escape {
                escape = false;
            } else if ch == '\\' {
                escape = true;
            } else if ch == '"' {
                em_string = false;
            }
        } else if ch == '"' {
            em_string = true;
            out.push(ch);
        } else if !ch.is_whitespace() {
            out.push(ch);
        }
    }
    out
}
