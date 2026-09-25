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

/// Descomprime Brotli.
pub fn descomprimir(br: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    brotli::BrotliDecompress(&mut &br[..], &mut out).unwrap();
    out
}

/// Valida `instancia` contra `packages/contract/schema/<nome>`, com os demais schemas
/// registrados pelo `$id` (resolve `$ref` relativos) e `format` checado.
pub fn validar_schema(nome: &str, instancia: &serde_json::Value) {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../packages/contract/schema");
    let mut schemas = Vec::new();
    for e in std::fs::read_dir(&dir).unwrap() {
        let p = e.unwrap().path();
        let v: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&p).unwrap()).unwrap();
        schemas.push((p.file_name().unwrap().to_string_lossy().into_owned(), v));
    }
    let registro = jsonschema::Registry::new()
        .extend(
            schemas
                .iter()
                .map(|(_, v)| (v["$id"].as_str().unwrap().to_owned(), v.clone())),
        )
        .unwrap()
        .prepare()
        .unwrap();
    let (_, alvo) = schemas.iter().find(|(n, _)| n == nome).unwrap();
    let v = jsonschema::options()
        .with_registry(&registro)
        .should_validate_formats(true)
        .build(alvo)
        .unwrap();
    let erros: Vec<String> = v.iter_errors(instancia).map(|e| e.to_string()).collect();
    assert!(erros.is_empty(), "{nome}: {erros:?}");
}
