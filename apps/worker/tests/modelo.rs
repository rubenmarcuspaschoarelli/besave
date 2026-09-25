//! CONV-12: round-trip serde das fixtures do contrato, byte a byte.

mod comum;

use comum::{compactar, fixture};
use worker::modelo::{Manifest, OfertaCard, OfertaPagina};

#[test]
fn chunk_ok_round_trip_identico() {
    let txt = fixture("chunk-ok.json");
    let cards: Vec<OfertaCard> = serde_json::from_str(&txt).unwrap();
    assert_eq!(cards.len(), 3);
    assert_eq!(serde_json::to_string(&cards).unwrap(), compactar(&txt));
}

#[test]
fn oferta_pagina_ok_round_trip_identico() {
    let txt = fixture("oferta-pagina-ok.json");
    let p: OfertaPagina = serde_json::from_str(&txt).unwrap();
    assert_eq!(serde_json::to_string(&p).unwrap(), compactar(&txt));
}

#[test]
fn manifest_ok_round_trip_identico() {
    let txt = fixture("manifest-ok.json");
    let m: Manifest = serde_json::from_str(&txt).unwrap();
    assert_eq!(serde_json::to_string(&m).unwrap(), compactar(&txt));
}
