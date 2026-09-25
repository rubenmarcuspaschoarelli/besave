//! Cards → chunks por faixa de id, JSON compacto, hash e Brotli (MANIFEST §2, §3).

use std::collections::BTreeMap;

use brotli::enc::BrotliEncoderParams;
use sha2::{Digest, Sha256};

use crate::modelo::OfertaCard;

#[derive(Debug, thiserror::Error)]
pub enum ErroChunk {
    #[error("serializando chunk: {0}")]
    Json(#[from] serde_json::Error),
    #[error("comprimindo chunk: {0}")]
    Brotli(#[from] std::io::Error),
}

/// Ids por chunk: `n = id / 1000`.
pub const FAIXA: i64 = 1000;
const QUALIDADE_BROTLI: i32 = 9;
const JANELA_BROTLI: i32 = 22;

/// Agrupa por `n = id / 1000`, cada chunk ordenado por `id`. `id ≤ 0` cai em `n = 0`.
pub fn particionar(cards: Vec<OfertaCard>) -> BTreeMap<u64, Vec<OfertaCard>> {
    let mut chunks: BTreeMap<u64, Vec<OfertaCard>> = BTreeMap::new();
    for c in cards {
        let n = u64::try_from(c.id / FAIXA).unwrap_or(0);
        chunks.entry(n).or_default().push(c);
    }
    for cards in chunks.values_mut() {
        cards.sort_by_key(|c| c.id);
    }
    chunks
}

/// JSON compacto UTF-8 e os 16 primeiros hex do SHA-256 desse JSON.
// SPEC_DEVIATION: devolve Result em vez de tupla pura.
// Reason: serde_json::to_vec é falível e a regra 9 proíbe unwrap fora de teste.
pub fn serializar_chunk(cards: &[OfertaCard]) -> Result<(Vec<u8>, String), ErroChunk> {
    let json = serde_json::to_vec(cards)?;
    let hash = hex::encode(&Sha256::digest(&json)[..8]);
    Ok((json, hash))
}

/// Brotli nível 9.
// SPEC_DEVIATION: devolve Result em vez de Vec<u8>.
// Reason: BrotliCompress devolve io::Result; a regra 9 proíbe unwrap fora de teste.
pub fn comprimir_br(json: &[u8]) -> Result<Vec<u8>, ErroChunk> {
    let params = BrotliEncoderParams {
        quality: QUALIDADE_BROTLI,
        lgwin: JANELA_BROTLI,
        ..Default::default()
    };
    let mut saida = Vec::with_capacity(json.len() / 4);
    brotli::BrotliCompress(&mut &json[..], &mut saida, &params)?;
    Ok(saida)
}

/// `data/chunks/{n}-{hash}.json.br`
pub fn chave_chunk(n: u64, hash: &str) -> String {
    format!("data/chunks/{n}-{hash}.json.br")
}
