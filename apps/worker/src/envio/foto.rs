//! Foto do post (BSV-40 regra 5): imagem da oferta (ou placeholder da área) centralizada num
//! quadrado 800×800 branco, em JPEG. Só memória: nada vai para o S3.

use std::path::{Path, PathBuf};

use image::codecs::jpeg::JpegEncoder;
use image::imageops::{self, FilterType};
use image::{DynamicImage, ImageEncoder, Rgba, RgbaImage};
use tracing::warn;

use crate::imagens::{ErroImagem, origem, placeholder};
use crate::modelo::Area;

pub const LADO: u32 = 800;
const QUALIDADE: u8 = 85;

/// De onde veio a imagem.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OrigemFoto {
    Oferta(PathBuf),
    Placeholder(Area),
}

/// JPEG 800×800 da oferta: `{dir}/{id}/{id}.webp` do robô (o mesmo arquivo de
/// `img/ofertas/{id}.webp`); sem pasta, ausente ou ilegível → placeholder da área.
pub fn foto(dir: Option<&Path>, id: i64, area: Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem> {
    if let Some(dir) = dir {
        let (_, grande) = origem(dir, id);
        match std::fs::read(&grande) {
            Ok(bytes) => match image::load_from_memory(&bytes) {
                Ok(img) => return Ok((quadrado_jpeg(&img)?, OrigemFoto::Oferta(grande))),
                Err(e) => warn!(id, erro = %e, "imagem da oferta ilegível; placeholder"),
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => warn!(id, erro = %e, "lendo imagem da oferta; placeholder"),
        }
    }
    let img = image::load_from_memory(placeholder(area))
        .map_err(|e| ErroImagem::Decode(e.to_string()))?;
    Ok((quadrado_jpeg(&img)?, OrigemFoto::Placeholder(area)))
}

/// Escala para caber em 800×800 (para cima ou para baixo, proporção preservada), centraliza sobre
/// branco (alfa composto sobre branco) e codifica em JPEG.
pub fn quadrado_jpeg(img: &DynamicImage) -> Result<Vec<u8>, ErroImagem> {
    let ajustada = img.resize(LADO, LADO, FilterType::Lanczos3).to_rgba8();
    let mut fundo = RgbaImage::from_pixel(LADO, LADO, Rgba([255, 255, 255, 255]));
    let x = (LADO - ajustada.width()) / 2;
    let y = (LADO - ajustada.height()) / 2;
    imageops::overlay(&mut fundo, &ajustada, i64::from(x), i64::from(y));
    let rgb = DynamicImage::ImageRgba8(fundo).to_rgb8();
    let mut out = Vec::new();
    JpegEncoder::new_with_quality(&mut out, QUALIDADE)
        .write_image(
            rgb.as_raw(),
            rgb.width(),
            rgb.height(),
            image::ExtendedColorType::Rgb8,
        )
        .map_err(|e| ErroImagem::Encode(e.to_string()))?;
    Ok(out)
}
