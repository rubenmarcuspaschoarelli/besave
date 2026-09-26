//! Imagens WebP do robô → S3 (BSV-13). O robô já entrega `{dir}/{id}/{id}[-small].webp`;
//! o worker copia com verificação de orçamento (MANIFEST §1, §6, §7).

use std::path::{Path, PathBuf};

use tracing::warn;

use crate::publicador::{self, META_IMAGEM, Publicador};

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

// SPEC_DEVIATION: recodificação real (crate `image`, qualidade descendente, redimensionar a
// 320 px) chega na tarefa T4; por ora devolve os bytes como vieram, só para não travar o
// restante do pipeline de `publicar_imagens` enquanto a dependência não está no Cargo.toml.
// Reason: manter `publicar_imagens` (T3) compilável e testável antes de T4 acrescentar `image`.
fn ajustar_small_provisorio(bytes: &[u8]) -> Vec<u8> {
    bytes.to_vec()
}

/// Copia as imagens de `ids` de `dir` para o destino, uma por uma (regras 2, 3-provisório, 4, 5).
/// Reaproveitamento (regra 4) e ausência de origem (regra 5) nunca retornam erro; falha de
/// assinatura WebP conta em `RelatorioImagens.falhas` e não interrompe o loop (regra 2).
pub fn publicar_imagens(
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
) -> publicador::Result<RelatorioImagens> {
    let mut rel = RelatorioImagens::default();
    for &id in ids {
        let chave_s = chave_small(id);
        let chave_g = chave_grande(id);
        if pub_.existe(&chave_s)? && pub_.existe(&chave_g)? {
            rel.reaproveitadas += 1;
            continue;
        }
        let (origem_s, origem_g) = origem(dir, id);
        let (Ok(bytes_s), Ok(bytes_g)) = (std::fs::read(&origem_s), std::fs::read(&origem_g))
        else {
            rel.sem_origem += 1;
            continue;
        };
        if !e_webp(&bytes_s) || !e_webp(&bytes_g) {
            rel.falhas.push((id, MotivoFalhaImagem::NaoWebp));
            continue;
        }
        let bytes_s = if bytes_s.len() > ORCAMENTO_SMALL {
            rel.reprocessadas += 1;
            warn!(
                id,
                bytes = bytes_s.len(),
                "small acima do orçamento; recodificando"
            );
            ajustar_small_provisorio(&bytes_s)
        } else {
            bytes_s
        };
        if bytes_g.len() > AVISO_GRANDE {
            warn!(
                id,
                bytes = bytes_g.len(),
                "imagem grande acima de 300 KB; publicando assim mesmo"
            );
        }
        pub_.gravar(&chave_s, &bytes_s, &META_IMAGEM)?;
        pub_.gravar(&chave_g, &bytes_g, &META_IMAGEM)?;
        rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;
        rel.maior_small = rel.maior_small.max(bytes_s.len() as u64);
        rel.maior_grande = rel.maior_grande.max(bytes_g.len() as u64);
        rel.publicadas += 1;
    }
    Ok(rel)
}
