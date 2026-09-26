//! CHV-01, CHV-02: chaves e origem das imagens de oferta (BSV-13).

use std::path::PathBuf;

use worker::imagens::{chave_grande, chave_small, e_webp, origem};
use worker::modelo::Area;

#[test]
fn chaves_do_bucket() {
    assert_eq!(chave_small(5412), "img/ofertas/5412-small.webp");
    assert_eq!(chave_grande(5412), "img/ofertas/5412.webp");
}

#[test]
fn origem_monta_os_dois_caminhos() {
    let dir = PathBuf::from("robos").join("imagens");
    let (small, grande) = origem(&dir, 5412);
    assert_eq!(
        small,
        dir.join("5412").join("5412-small.webp"),
        "{}",
        small.display()
    );
    assert_eq!(
        grande,
        dir.join("5412").join("5412.webp"),
        "{}",
        grande.display()
    );
}

#[test]
fn assinatura_webp_aceita_riff_webp() {
    let mut bytes = b"RIFF".to_vec();
    bytes.extend_from_slice(&[10, 0, 0, 0]); // tamanho do chunk RIFF, irrelevante aqui
    bytes.extend_from_slice(b"WEBPVP8 ");
    assert!(e_webp(&bytes));
}

#[test]
fn assinatura_webp_rejeita_vazio_riff_sem_webp_e_jpeg() {
    assert!(!e_webp(b""));
    let mut riff_sem_webp = b"RIFF".to_vec();
    riff_sem_webp.extend_from_slice(&[10, 0, 0, 0]);
    riff_sem_webp.extend_from_slice(b"JPEGxxxx");
    assert!(!e_webp(&riff_sem_webp));
    assert!(!e_webp(&[0xFF, 0xD8, 0xFF, 0xE0, 0, 0, 0, 0, 0, 0, 0, 0]));
}

/// `Area::chave_area` deve cobrir as 10 variantes, na mesma grafia do enum do contrato 1.3.
#[test]
fn chave_area_cobre_as_10_variantes_do_contrato() {
    let esperado = [
        "TECH",
        "PLAYERS",
        "MEU_LAR",
        "ELAS",
        "ELES",
        "CULTURA",
        "FAMILIA",
        "PETS",
        "ESPORTE_VIDA",
        "OUTROS",
    ];
    let obtido: Vec<&str> = Area::TODAS.iter().map(Area::chave_area).collect();
    assert_eq!(obtido, esperado);
}
