//! Imagens WebP do robô → S3 (BSV-13). O robô já entrega `{dir}/{id}/{id}[-small].webp`;
//! o worker copia com verificação de orçamento (MANIFEST §1, §6, §7).

use std::path::{Path, PathBuf};

use image::{
    DynamicImage, ImageEncoder, ImageFormat, codecs::webp::WebPEncoder, imageops::FilterType,
};
use tracing::warn;

use crate::modelo::Area;
use crate::publicador::{self, META_IMAGEM, Publicador};

/// Orçamento da imagem pequena (MANIFEST §7): acima disso, `ajustar_small` recodifica.
pub const ORCAMENTO_SMALL: usize = 25_600;
/// Acima disso a imagem grande só gera aviso; publica do mesmo jeito (regra 3).
pub const AVISO_GRANDE: usize = 300_000;
/// Lado maior de `-small.webp` após `ajustar_small` (regra 3).
pub const LADO_SMALL: u32 = 320;
/// Piso do redimensionamento iterativo: evita loop indefinido numa imagem que não cabe.
const LADO_MINIMO: u32 = 32;

#[derive(Debug, thiserror::Error)]
pub enum ErroImagem {
    #[error("decodificando imagem de origem: {0}")]
    Decode(String),
    #[error("codificando WebP: {0}")]
    Encode(String),
}

/// Motivo de falha ao publicar a imagem de um id (regra 2, regra 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum MotivoFalhaImagem {
    #[error("nao_webp")]
    NaoWebp,
    #[error("falha_recodificacao")]
    FalhaRecodificacao,
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

// SPEC_DEVIATION: a spec do ticket pede "qualidade descendo de 80 até 40"; o encoder WebP da
// crate `image` (via `image-webp`, checado em docs.rs) só faz VP8L (sem-perdas) — não existe
// parâmetro de qualidade. Um encoder com qualidade lossy real (crate `webp`) embute libwebp via
// `libwebp-sys`, exigindo toolchain C no build, e a regra 9 só permite a dependência `image`.
// Reason: reduzir a resolução progressivamente (320 → 3/4 a cada volta, piso 32 px) e recodificar
// sem perdas cumpre o mesmo critério de aceite (≤ 25 600 B, WebP válido, lado ≤ 320 px) com uma
// única dependência pura-Rust, sem trocar o encoder por um com dependência nativa.
/// Decodifica, redimensiona o lado maior a `alvo` e recodifica sem perdas; repete reduzindo o
/// lado até caber no orçamento ou atingir `LADO_MINIMO` (regra 3).
pub fn ajustar_small(bytes: &[u8]) -> Result<Vec<u8>, ErroImagem> {
    let original = image::load_from_memory_with_format(bytes, ImageFormat::WebP)
        .map_err(|e| ErroImagem::Decode(e.to_string()))?;
    let mut alvo = LADO_SMALL;
    loop {
        let redimensionada = redimensionar(&original, alvo);
        let codificada = codificar_webp_sem_perdas(&redimensionada)?;
        if codificada.len() <= ORCAMENTO_SMALL || alvo <= LADO_MINIMO {
            return Ok(codificada);
        }
        alvo = (alvo * 3 / 4).max(LADO_MINIMO);
    }
}

/// Redimensiona só quando o lado maior excede `alvo`; nunca aumenta a imagem. `resize` já encaixa
/// a imagem numa caixa `alvo × alvo` preservando a proporção (lado maior = `alvo`).
fn redimensionar(img: &DynamicImage, alvo: u32) -> DynamicImage {
    if img.width().max(img.height()) <= alvo {
        img.clone()
    } else {
        img.resize(alvo, alvo, FilterType::Lanczos3)
    }
}

fn codificar_webp_sem_perdas(img: &DynamicImage) -> Result<Vec<u8>, ErroImagem> {
    let rgba = img.to_rgba8();
    let mut saida = Vec::new();
    WebPEncoder::new_lossless(&mut saida)
        .write_image(
            rgba.as_raw(),
            rgba.width(),
            rgba.height(),
            image::ExtendedColorType::Rgba8,
        )
        .map_err(|e| ErroImagem::Encode(e.to_string()))?;
    Ok(saida)
}

/// `"img/placeholder/{area}.webp"` (CONTRATO §6), mesma chave de arquivo de `Area::chave_area`.
pub fn chave_placeholder(area: Area) -> String {
    format!("img/placeholder/{}.webp", area.chave_area())
}

/// Os 10 placeholders versionados, embutidos no binário (regra 5): nenhuma dependência de
/// arquivo em disco em tempo de execução, e o worker nunca falha por placeholder ausente.
fn placeholders() -> [(Area, &'static [u8]); 10] {
    [
        (
            Area::Tech,
            include_bytes!("../assets/placeholder/TECH.webp"),
        ),
        (
            Area::Players,
            include_bytes!("../assets/placeholder/PLAYERS.webp"),
        ),
        (
            Area::MeuLar,
            include_bytes!("../assets/placeholder/MEU_LAR.webp"),
        ),
        (
            Area::Elas,
            include_bytes!("../assets/placeholder/ELAS.webp"),
        ),
        (
            Area::Eles,
            include_bytes!("../assets/placeholder/ELES.webp"),
        ),
        (
            Area::Cultura,
            include_bytes!("../assets/placeholder/CULTURA.webp"),
        ),
        (
            Area::Familia,
            include_bytes!("../assets/placeholder/FAMILIA.webp"),
        ),
        (
            Area::Pets,
            include_bytes!("../assets/placeholder/PETS.webp"),
        ),
        (
            Area::EsporteVida,
            include_bytes!("../assets/placeholder/ESPORTE_VIDA.webp"),
        ),
        (
            Area::Outros,
            include_bytes!("../assets/placeholder/OUTROS.webp"),
        ),
    ]
}

/// Publica os 10 placeholders que ainda não existem no destino; reaproveita os demais (regra 5).
fn publicar_placeholders(pub_: &mut dyn Publicador) -> publicador::Result<()> {
    for (area, bytes) in placeholders() {
        let chave = chave_placeholder(area);
        if !pub_.existe(&chave)? {
            pub_.gravar(&chave, bytes, &META_IMAGEM)?;
        }
    }
    Ok(())
}

/// Copia as imagens de `ids` de `dir` para o destino, uma por uma (regras 2, 3, 4, 5), e garante
/// os 10 placeholders de área (regra 5). Reaproveitamento (regra 4) e ausência de origem
/// (regra 5) nunca retornam erro; falha de assinatura WebP conta em `RelatorioImagens.falhas` e
/// não interrompe o loop (regra 2).
pub fn publicar_imagens(
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
) -> publicador::Result<RelatorioImagens> {
    publicar_placeholders(pub_)?;
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
            match ajustar_small(&bytes_s) {
                Ok(b) => b,
                Err(e) => {
                    warn!(id, erro = %e, "falha ao recodificar small; oferta sem imagem");
                    rel.falhas.push((id, MotivoFalhaImagem::FalhaRecodificacao));
                    continue;
                }
            }
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
