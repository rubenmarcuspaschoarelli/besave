//! Imagens WebP do robô → S3 (BSV-13). O robô já entrega `{dir}/{id}/{id}[-small].webp`;
//! o worker copia com verificação de orçamento (MANIFEST §1, §6, §7).

use std::path::{Path, PathBuf};

/// Orçamento da imagem pequena (MANIFEST §7): acima disso, `ajustar_small` recodifica.
pub const ORCAMENTO_SMALL: usize = 25_600;
/// Acima disso a imagem grande só gera aviso; publica do mesmo jeito (regra 3).
pub const AVISO_GRANDE: usize = 300_000;

#[derive(Debug, thiserror::Error)]
pub enum ErroImagem {
    #[error("decodificando imagem de origem: {0}")]
    Decode(String),
    #[error("codificando WebP: {0}")]
    Encode(String),
}

/// Motivo de falha ao publicar a imagem de um id (regra 2).
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum MotivoFalhaImagem {
    #[error("nao_webp")]
    NaoWebp,
}

/// Contagens e amostras de uma execução de `publicar_imagens`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioImagens {
    pub publicadas: u64,
    pub reaproveitadas: u64,
    pub sem_origem: u64,
    pub reprocessadas: u64,
    pub falhas: Vec<(i64, MotivoFalhaImagem)>,
    /// Bytes efetivamente gravados nesta execução (soma das duas chaves de cada id publicado).
    pub bytes: u64,
    /// Maior `-small.webp` publicado nesta execução, em bytes (0 se nenhum).
    pub maior_small: u64,
    /// Maior `{id}.webp` publicado nesta execução, em bytes (0 se nenhum).
    pub maior_grande: u64,
}

/// `"img/ofertas/{id}-small.webp"` (CONTRATO §6).
pub fn chave_small(id: i64) -> String {
    format!("img/ofertas/{id}-small.webp")
}

/// `"img/ofertas/{id}.webp"` (CONTRATO §6).
pub fn chave_grande(id: i64) -> String {
    format!("img/ofertas/{id}.webp")
}

/// `({dir}/{id}/{id}-small.webp, {dir}/{id}/{id}.webp)`: caminhos que o robô já grava.
pub fn origem(dir: &Path, id: i64) -> (PathBuf, PathBuf) {
    let base = dir.join(id.to_string());
    (
        base.join(format!("{id}-small.webp")),
        base.join(format!("{id}.webp")),
    )
}

/// Contêiner RIFF/WebP: `RIFF` em 0..4, `WEBP` em 8..12 (regra 2). Não decodifica a imagem.
pub fn e_webp(bytes: &[u8]) -> bool {
    bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP"
}
