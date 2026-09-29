//! Gera os 10 placeholders versionados em `assets/placeholder/{slug}.webp` (BSV-13, regra 5).
//! Chave de arquivo = slug de URL da área (CONTRATO §2.3; `Area::slug`), não o valor do enum —
//! BSV-20 já referencia `img/placeholder/{slug}.webp`. Roda uma vez, offline:
//! `cargo run --example gerar_placeholders`. Fundo sólido por área (só para diferenciar
//! visualmente) + rótulo em fonte de pixels 5×7 embutida (sem crate de fonte nova, regra 9: só
//! a dependência `image` já usada por `ajustar_small`).

use image::{ExtendedColorType, ImageEncoder, Rgba, RgbaImage, codecs::webp::WebPEncoder};
use worker::modelo::Area;

const LADO: u32 = 320;
/// Cada "pixel" da fonte 5×7 vira um bloco `ESCALA × ESCALA`; 4 cabe o rótulo mais longo
/// (`ESPORTE_VIDA`, 12 caracteres) dentro dos 320 px.
const ESCALA: u32 = 4;

/// Fonte de pixels 5×7, só os glifos usados pelo rótulo visual (slug em maiúsculas, hífen virando
/// `_`): `A C D E F H I L M N O P R S T U V Y _`. Cada linha é 5 bits (bit 4 = coluna 0).
fn glifo(c: char) -> [u8; 7] {
    match c {
        'A' => [14, 17, 17, 31, 17, 17, 17],
        'C' => [15, 16, 16, 16, 16, 16, 15],
        'D' => [30, 17, 17, 17, 17, 17, 30],
        'E' => [31, 16, 16, 30, 16, 16, 31],
        'F' => [31, 16, 16, 30, 16, 16, 16],
        'H' => [17, 17, 17, 31, 17, 17, 17],
        'I' => [31, 4, 4, 4, 4, 4, 31],
        'L' => [16, 16, 16, 16, 16, 16, 31],
        'M' => [17, 27, 21, 17, 17, 17, 17],
        'N' => [17, 25, 21, 19, 17, 17, 17],
        'O' => [14, 17, 17, 17, 17, 17, 14],
        'P' => [30, 17, 17, 30, 16, 16, 16],
        'R' => [30, 17, 17, 30, 20, 18, 17],
        'S' => [15, 16, 16, 14, 1, 1, 30],
        'T' => [31, 4, 4, 4, 4, 4, 4],
        'U' => [17, 17, 17, 17, 17, 17, 14],
        'V' => [17, 17, 17, 17, 17, 10, 4],
        'Y' => [17, 17, 10, 4, 4, 4, 4],
        '_' => [0, 0, 0, 0, 0, 0, 31],
        _ => [0; 7],
    }
}

/// Tom neutro (cinza) por área, só para diferenciar as 10 imagens a olho; nada de cor viva.
fn cor_de_fundo(area: Area) -> Rgba<u8> {
    let n = Area::TODAS.iter().position(|a| *a == area).unwrap_or(0) as u8;
    let base = 90 + n * 12;
    Rgba([base, base, base.saturating_add(6), 255])
}

fn desenhar_texto(img: &mut RgbaImage, texto: &str) {
    let cor = Rgba([255, 255, 255, 255]);
    let largura_glifo = 6 * ESCALA; // 5 colunas do glifo + 1 coluna de espaço
    let texto_px = texto.chars().count() as u32 * largura_glifo;
    let x0 = LADO.saturating_sub(texto_px) / 2;
    let y0 = LADO.saturating_sub(7 * ESCALA) / 2;
    for (i, c) in texto.chars().enumerate() {
        let linhas = glifo(c);
        let gx = x0 + i as u32 * largura_glifo;
        for (linha, bits) in linhas.iter().enumerate() {
            for coluna in 0..5u32 {
                if (bits >> (4 - coluna)) & 1 == 0 {
                    continue;
                }
                let px = gx + coluna * ESCALA;
                let py = y0 + linha as u32 * ESCALA;
                for dx in 0..ESCALA {
                    for dy in 0..ESCALA {
                        if px + dx < LADO && py + dy < LADO {
                            img.put_pixel(px + dx, py + dy, cor);
                        }
                    }
                }
            }
        }
    }
}

fn main() -> anyhow::Result<()> {
    let saida = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("assets/placeholder");
    std::fs::create_dir_all(&saida)?;
    for area in Area::TODAS {
        let mut img = RgbaImage::from_pixel(LADO, LADO, cor_de_fundo(area));
        // Rótulo visual: slug em maiúsculas com `_` no lugar de `-` (a fonte 5×7 não tem hífen).
        let rotulo = area.slug().to_uppercase().replace('-', "_");
        desenhar_texto(&mut img, &rotulo);
        let mut bytes = Vec::new();
        WebPEncoder::new_lossless(&mut bytes).write_image(
            img.as_raw(),
            LADO,
            LADO,
            ExtendedColorType::Rgba8,
        )?;
        let caminho = saida.join(format!("{}.webp", area.slug()));
        std::fs::write(&caminho, &bytes)?;
        println!("{}: {} bytes", caminho.display(), bytes.len());
    }
    Ok(())
}
