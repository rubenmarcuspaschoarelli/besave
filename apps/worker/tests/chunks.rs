//! CHK-01..04: partição por faixa, ordem por id, hash da fixture e round-trip Brotli + schema.

mod comum;

use comum::{compactar, descomprimir, fixture, validar_schema};
use worker::chunks::{comprimir_br, particionar, serializar_chunk};
use worker::modelo::OfertaCard;

fn cards_fixture() -> Vec<OfertaCard> {
    serde_json::from_str(&fixture("chunk-ok.json")).unwrap()
}

fn card(id: i64) -> OfertaCard {
    OfertaCard {
        id,
        ..cards_fixture().remove(0)
    }
}

fn ids(cards: &[OfertaCard]) -> Vec<i64> {
    cards.iter().map(|c| c.id).collect()
}

#[test]
fn particao_por_faixa_de_mil() {
    let chunks = particionar(vec![card(2000), card(999), card(1999), card(1000)]);
    assert_eq!(chunks.keys().copied().collect::<Vec<_>>(), vec![0, 1, 2]);
    assert_eq!(ids(&chunks[&0]), vec![999]);
    assert_eq!(ids(&chunks[&1]), vec![1000, 1999]);
    assert_eq!(ids(&chunks[&2]), vec![2000]);
}

#[test]
fn chunk_ordenado_por_id() {
    let mut embaralhados = cards_fixture();
    embaralhados.reverse();
    let chunks = particionar(embaralhados);
    assert_eq!(chunks.len(), 1);
    assert_eq!(ids(&chunks[&5]), vec![5412, 5413, 5420]);
}

#[test]
fn fixture_chunk_ok_tem_json_e_hash_deterministicos() {
    let (json, hash) = serializar_chunk(&cards_fixture()).unwrap();
    assert_eq!(
        String::from_utf8(json).unwrap(),
        compactar(&fixture("chunk-ok.json"))
    );
    assert_eq!(hash, "89590e56ef6361dc");
}

#[test]
fn brotli_round_trip_valida_contra_schema() {
    let (json, _) = serializar_chunk(&cards_fixture()).unwrap();
    let br = comprimir_br(&json).unwrap();
    assert_ne!(br, json);
    let bruto = descomprimir(&br);
    assert_eq!(bruto, json);
    validar_schema(
        "chunk.schema.json",
        &serde_json::from_slice(&bruto).unwrap(),
    );
}
