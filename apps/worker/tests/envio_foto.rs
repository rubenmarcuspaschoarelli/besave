//! BSV-40 FOT-01..02: foto 800×800 JPEG, centralizada em fundo branco; placeholder sem imagem.

use std::path::{Path, PathBuf};

use image::codecs::webp::WebPEncoder;
use image::{ImageEncoder, ImageFormat, Rgba, RgbaImage};
use worker::envio::foto::{OrigemFoto, foto};
use worker::modelo::Area;

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-foto-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// Grava `{dir}/{id}/{id}.webp` sólido vermelho `w × h`.
fn webp(dir: &Path, id: i64, w: u32, h: u32) {
    let img = RgbaImage::from_pixel(w, h, Rgba([220, 0, 0, 255]));
    let mut bytes = Vec::new();
    WebPEncoder::new_lossless(&mut bytes)
        .write_image(img.as_raw(), w, h, image::ExtendedColorType::Rgba8)
        .unwrap();
    let pasta = dir.join(id.to_string());
    std::fs::create_dir_all(&pasta).unwrap();
    std::fs::write(pasta.join(format!("{id}.webp")), bytes).unwrap();
}

fn decodificar(jpeg: &[u8]) -> image::RgbImage {
    assert_eq!(&jpeg[..2], &[0xFF, 0xD8], "não é JPEG");
    image::load_from_memory_with_format(jpeg, ImageFormat::Jpeg)
        .unwrap()
        .to_rgb8()
}

fn branco(p: &image::Rgb<u8>) -> bool {
    p.0.iter().all(|&c| c >= 245)
}

fn vermelho(p: &image::Rgb<u8>) -> bool {
    p.0[0] >= 180 && p.0[1] <= 50 && p.0[2] <= 50
}

/// FOT-01: 400×200 → 800×400 centralizado (linhas 200..600), bordas brancas.
#[test]
fn paisagem_centralizada() {
    let dir = dir_temp("paisagem");
    webp(&dir, 7, 400, 200);
    let (jpeg, origem) = foto(Some(&dir), 7, Area::Tech).unwrap();
    assert_eq!(origem, OrigemFoto::Oferta(dir.join("7").join("7.webp")));
    let img = decodificar(&jpeg);
    assert_eq!(img.dimensions(), (800, 800));
    for (x, y) in [
        (0, 0),
        (799, 0),
        (0, 799),
        (799, 799),
        (400, 100),
        (400, 700),
    ] {
        assert!(
            branco(img.get_pixel(x, y)),
            "({x},{y}) {:?}",
            img.get_pixel(x, y)
        );
    }
    for (x, y) in [(400, 400), (5, 400), (794, 400), (400, 205), (400, 594)] {
        assert!(
            vermelho(img.get_pixel(x, y)),
            "({x},{y}) {:?}",
            img.get_pixel(x, y)
        );
    }
    // Proporção 2:1 preservada: faixa vermelha de ~400 linhas.
    let linhas = (0..800)
        .filter(|&y| vermelho(img.get_pixel(400, y)))
        .count();
    assert!((396..=404).contains(&linhas), "{linhas}");
}

/// FOT-01: retrato 1000×4000 → 200×800 centralizado (colunas 300..500).
#[test]
fn retrato_centralizado() {
    let dir = dir_temp("retrato");
    webp(&dir, 8, 1000, 4000);
    let img = decodificar(&foto(Some(&dir), 8, Area::Elas).unwrap().0);
    assert_eq!(img.dimensions(), (800, 800));
    let colunas = (0..800)
        .filter(|&x| vermelho(img.get_pixel(x, 400)))
        .count();
    assert!((196..=204).contains(&colunas), "{colunas}");
    assert!(branco(img.get_pixel(290, 400)) && branco(img.get_pixel(510, 400)));
    assert!(vermelho(img.get_pixel(400, 0)) && vermelho(img.get_pixel(400, 799)));
}

/// Transparência vira branco, não preto.
#[test]
fn alfa_sobre_branco() {
    let dir = dir_temp("alfa");
    let img = RgbaImage::from_pixel(100, 100, Rgba([0, 0, 0, 0]));
    let mut bytes = Vec::new();
    WebPEncoder::new_lossless(&mut bytes)
        .write_image(img.as_raw(), 100, 100, image::ExtendedColorType::Rgba8)
        .unwrap();
    std::fs::create_dir_all(dir.join("9")).unwrap();
    std::fs::write(dir.join("9").join("9.webp"), bytes).unwrap();
    let out = decodificar(&foto(Some(&dir), 9, Area::Tech).unwrap().0);
    assert!(
        branco(out.get_pixel(400, 400)),
        "{:?}",
        out.get_pixel(400, 400)
    );
}

/// FOT-02: sem imagem (ou sem pasta, ou arquivo ilegível) → placeholder da área, 800×800.
#[test]
fn sem_imagem_usa_placeholder() {
    let dir = dir_temp("sem");
    for d in [Some(dir.as_path()), None] {
        let (jpeg, origem) = foto(d, 1, Area::Pets).unwrap();
        assert_eq!(origem, OrigemFoto::Placeholder(Area::Pets));
        assert_eq!(decodificar(&jpeg).dimensions(), (800, 800));
    }
    std::fs::create_dir_all(dir.join("2")).unwrap();
    std::fs::write(dir.join("2").join("2.webp"), b"lixo").unwrap();
    let (_, origem) = foto(Some(&dir), 2, Area::MeuLar).unwrap();
    assert_eq!(origem, OrigemFoto::Placeholder(Area::MeuLar));
}
