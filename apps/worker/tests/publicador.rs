//! PUB-01..05: `PublicadorLocal` (pasta temporária) e `PublicadorMemoria` com o mesmo contrato.

use std::path::PathBuf;

use worker::publicador::{
    META_CHUNK, META_MANIFEST, Publicador, PublicadorLocal, PublicadorMemoria,
};

fn pasta(nome: &str) -> PathBuf {
    let p = std::env::temp_dir().join(format!("besave-pub-{}-{nome}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    p
}

/// PUB-02..04 contra qualquer implementação.
fn contrato(p: &mut dyn Publicador) {
    assert!(!p.existe("data/chunks/1-a.json.br").unwrap());
    assert_eq!(p.ler("data/chunks/1-a.json.br").unwrap(), None);
    assert_eq!(p.listar("data/chunks/").unwrap(), Vec::<String>::new());

    p.gravar("data/chunks/1-a.json.br", b"um", &META_CHUNK)
        .unwrap();
    p.gravar("data/chunks/0-b.json.br", b"zero", &META_CHUNK)
        .unwrap();
    p.gravar("manifest.json", b"{}", &META_MANIFEST).unwrap();

    assert!(p.existe("data/chunks/1-a.json.br").unwrap());
    assert_eq!(
        p.ler("data/chunks/1-a.json.br").unwrap(),
        Some(b"um".to_vec())
    );
    assert_eq!(
        p.listar("data/chunks/").unwrap(),
        vec!["data/chunks/0-b.json.br", "data/chunks/1-a.json.br"]
    );
    assert_eq!(
        p.listar("data/chunks/1-").unwrap(),
        vec!["data/chunks/1-a.json.br"]
    );

    p.remover("data/chunks/1-a.json.br").unwrap();
    assert!(!p.existe("data/chunks/1-a.json.br").unwrap());
    assert_eq!(p.ler("data/chunks/1-a.json.br").unwrap(), None);
    assert_eq!(
        p.listar("data/chunks/").unwrap(),
        vec!["data/chunks/0-b.json.br"]
    );
    p.remover("nao/existe").unwrap();
}

#[test]
fn local_cumpre_o_contrato() {
    let raiz = pasta("contrato");
    contrato(&mut PublicadorLocal::new(&raiz));
}

#[test]
fn memoria_cumpre_o_contrato() {
    contrato(&mut PublicadorMemoria::new());
}

#[test]
fn local_grava_bytes_e_headers_ao_lado() {
    let raiz = pasta("meta");
    let mut p = PublicadorLocal::new(&raiz);
    p.gravar("data/chunks/5-abc.json.br", &[1, 2, 3], &META_CHUNK)
        .unwrap();
    p.gravar("manifest.json", b"{}", &META_MANIFEST).unwrap();

    assert_eq!(
        std::fs::read(raiz.join("data/chunks/5-abc.json.br")).unwrap(),
        vec![1, 2, 3]
    );
    let meta: serde_json::Value = serde_json::from_slice(
        &std::fs::read(raiz.join("data/chunks/5-abc.json.br.meta.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(
        meta,
        serde_json::json!({
            "content_type": "application/json",
            "content_encoding": "br",
            "cache_control": "public, max-age=31536000, immutable"
        })
    );
    let meta: serde_json::Value =
        serde_json::from_slice(&std::fs::read(raiz.join("manifest.json.meta.json")).unwrap())
            .unwrap();
    assert_eq!(
        meta,
        serde_json::json!({
            "content_type": "application/json",
            "content_encoding": null,
            "cache_control": "public, max-age=300, stale-while-revalidate=60"
        })
    );
}

#[test]
fn local_remover_apaga_o_sidecar() {
    let raiz = pasta("remover");
    let mut p = PublicadorLocal::new(&raiz);
    p.gravar("data/chunks/5-abc.json.br", b"x", &META_CHUNK)
        .unwrap();
    p.remover("data/chunks/5-abc.json.br").unwrap();
    assert!(!raiz.join("data/chunks/5-abc.json.br").exists());
    assert!(!raiz.join("data/chunks/5-abc.json.br.meta.json").exists());
}

#[test]
fn memoria_expoe_headers_por_chave() {
    let mut p = PublicadorMemoria::new();
    p.gravar("data/chunks/5-abc.json.br", b"x", &META_CHUNK)
        .unwrap();
    p.gravar("manifest.json", b"{}", &META_MANIFEST).unwrap();
    assert_eq!(p.meta("data/chunks/5-abc.json.br"), Some(META_CHUNK));
    assert_eq!(p.meta("manifest.json"), Some(META_MANIFEST));
    assert_eq!(p.meta("ausente"), None);
    assert_eq!(
        p.gravacoes(),
        ["data/chunks/5-abc.json.br", "manifest.json"]
    );
}
