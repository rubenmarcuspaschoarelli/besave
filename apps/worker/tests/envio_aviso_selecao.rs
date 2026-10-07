//! BSV-41 ENV-05..07, ENV-14, LEG-01..02: aviso devido, legenda e foto do aviso.

use std::path::{Path, PathBuf};

use image::codecs::jpeg::JpegEncoder;
use image::{ImageEncoder, ImageFormat, Rgb, RgbImage};
use worker::avisos::modelo::LinhaAviso;
use worker::envio::aviso::{devido, foto_aviso, legenda_aviso};
use worker::envio::fonte::AvisoCanal;
use worker::envio::legenda::tamanho;

/// 2026-09-24 00:00 em Brasília (03:00Z).
const DIA0: i64 = 1_790_218_800;

fn hora(h: i64, m: i64) -> i64 {
    DIA0 + h * 3600 + m * 60
}

fn aviso(id: i64, ultimo: Option<i64>) -> AvisoCanal {
    AvisoCanal {
        aviso: LinhaAviso {
            id,
            titulo: format!("Aviso {id}"),
            texto: "Texto.".into(),
            ativo: true,
            dt_inicio: DIA0 - 86_400,
            dt_publicacao_site: Some(DIA0 - 3600),
            ..Default::default()
        },
        intervalo_min: 120,
        ativo: true,
        ultimo_envio: ultimo,
    }
}

fn id_devido(v: &[AvisoCanal], agora: i64) -> Option<i64> {
    devido(v, agora).map(|a| a.aviso.id)
}

/// Intervalo de 120 min: nunca enviado → devido; 115 min depois → não; 120 → sim.
#[test]
fn intervalo_do_aviso() {
    assert_eq!(id_devido(&[aviso(1, None)], hora(8, 0)), Some(1));
    let enviado = [aviso(1, Some(hora(8, 0)))];
    assert_eq!(id_devido(&enviado, hora(9, 55)), None);
    assert_eq!(id_devido(&enviado, hora(9, 59) + 59), None);
    assert_eq!(id_devido(&enviado, hora(10, 0)), Some(1));
}

/// ENV-05: dois vencidos → o mais atrasado; nunca enviado vence; empate → menor id.
#[test]
fn mais_atrasado_primeiro() {
    let v = [aviso(1, Some(hora(6, 0))), aviso(2, Some(hora(5, 0)))];
    assert_eq!(id_devido(&v, hora(10, 0)), Some(2));
    let v = [aviso(1, Some(hora(5, 0))), aviso(2, None)];
    assert_eq!(id_devido(&v, hora(10, 0)), Some(2));
    let v = [aviso(3, Some(hora(5, 0))), aviso(2, Some(hora(5, 0)))];
    assert_eq!(id_devido(&v, hora(10, 0)), Some(2));
    let v = [aviso(3, None), aviso(2, None)];
    assert_eq!(id_devido(&v, hora(10, 0)), Some(2));
}

/// ENV-06: `DT_PUBLICACAO_SITE` nula → não envia.
#[test]
fn sem_pagina_no_ar_nao_envia() {
    let mut a = aviso(1, None);
    a.aviso.dt_publicacao_site = None;
    assert_eq!(id_devido(&[a], hora(10, 0)), None);
}

/// ENV-07: aviso inativo, ligação inativa, fim vencido, início no futuro → não envia.
#[test]
fn inativo_ou_fora_da_vigencia_nao_envia() {
    let agora = hora(10, 0);
    let mut inativo = aviso(1, None);
    inativo.aviso.ativo = false;
    let mut ligacao = aviso(2, None);
    ligacao.ativo = false;
    let mut vencido = aviso(3, None);
    vencido.aviso.dt_fim = Some(agora);
    let mut futuro = aviso(4, None);
    futuro.aviso.dt_inicio = agora + 1;
    for a in [inativo, ligacao, vencido, futuro] {
        let id = a.aviso.id;
        assert_eq!(id_devido(&[a], agora), None, "aviso {id}");
    }
    let mut vigente = aviso(5, None);
    vigente.aviso.dt_fim = Some(agora + 1);
    assert_eq!(id_devido(&[vigente], agora), Some(5));
}

/// ENV-14: imagem `.png` → aviso ignorado (o outro devido segue).
#[test]
fn imagem_png_ignora_o_aviso() {
    let mut png = aviso(1, None);
    png.aviso.imagem = Some("aviso.png".into());
    let mut jpg = aviso(2, Some(hora(5, 0)));
    jpg.aviso.imagem = Some("aviso.jpg".into());
    assert_eq!(id_devido(&[png.clone()], hora(10, 0)), None);
    assert_eq!(id_devido(&[png, jpg], hora(10, 0)), Some(2));
}

/// LEG-01: formato exato, link com `utm_source=telegram`, escape.
#[test]
fn legenda_do_aviso() {
    let mut a = aviso(7, None);
    a.aviso.titulo = "Como o Besave funciona".into();
    a.aviso.texto = "Links de afiliado.\nSem custo extra.".into();
    assert_eq!(
        legenda_aviso(&a),
        "<b>Como o Besave funciona</b>\nLinks de afiliado.\nSem custo extra.\n\
         <a href=\"https://besave.com.br/avisos/7/?utm_source=telegram\">Saiba mais</a>"
    );
    a.aviso.titulo = "<script>T&C</script>".into();
    a.aviso.texto = "a < b & \"c\" > d".into();
    let l = legenda_aviso(&a);
    assert!(
        l.starts_with("<b>&lt;script&gt;T&amp;C&lt;/script&gt;</b>\n"),
        "{l}"
    );
    assert!(l.contains("\na &lt; b &amp; &quot;c&quot; &gt; d\n"), "{l}");
    assert!(!l.contains("<script>"), "{l}");
}

/// LEG-02: texto que estoura 1024 depois do escape → só o texto é cortado, com `…`.
#[test]
fn legenda_cabe_em_1024() {
    let mut a = aviso(8, None);
    a.aviso.titulo = "T".repeat(120);
    a.aviso.texto = "R&D ".repeat(200);
    let l = legenda_aviso(&a);
    assert!(tamanho(&l) <= 1024, "{}", tamanho(&l));
    assert!(tamanho(&l) > 1000, "cortou demais: {}", tamanho(&l));
    assert!(
        l.starts_with(&format!("<b>{}</b>\n", "T".repeat(120))),
        "{l}"
    );
    assert!(
        l.contains("…\n<a href=\"https://besave.com.br/avisos/8/?utm_source=telegram\">"),
        "{l}"
    );
}

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-foto-aviso-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn jpg(dir: &Path, nome: &str, w: u32, h: u32) {
    let img = RgbImage::from_pixel(w, h, Rgb([0, 0, 220]));
    let mut bytes = Vec::new();
    JpegEncoder::new(&mut bytes)
        .write_image(img.as_raw(), w, h, image::ExtendedColorType::Rgb8)
        .unwrap();
    std::fs::write(dir.join(nome), bytes).unwrap();
}

/// ENV-13 (foto): arquivo da pasta → JPEG 800×800 com bordas brancas.
#[test]
fn foto_do_aviso_800() {
    let dir = dir_temp("ok");
    jpg(&dir, "aviso.jpg", 400, 200);
    let j = foto_aviso(Some(&dir), 1, Some("aviso.jpg")).unwrap();
    let img = image::load_from_memory_with_format(&j, ImageFormat::Jpeg)
        .unwrap()
        .to_rgb8();
    assert_eq!(img.dimensions(), (800, 800));
    assert!(
        img.get_pixel(400, 50).0.iter().all(|&c| c >= 245),
        "borda não é branca"
    );
    let centro = img.get_pixel(400, 400).0;
    assert!(centro[2] >= 180 && centro[0] <= 50, "{centro:?}");
}

/// ENV-12 (foto): sem imagem, sem pasta ou arquivo ausente → `None` (vai `sendMessage`).
#[test]
fn sem_foto_do_aviso() {
    let dir = dir_temp("sem");
    jpg(&dir, "aviso.jpg", 10, 10);
    assert_eq!(foto_aviso(Some(&dir), 1, None), None);
    assert_eq!(foto_aviso(None, 1, Some("aviso.jpg")), None);
    assert_eq!(foto_aviso(Some(&dir), 1, Some("nao-existe.jpg")), None);
    std::fs::write(dir.join("quebrada.jpg"), b"nao e jpeg").unwrap();
    assert_eq!(foto_aviso(Some(&dir), 1, Some("quebrada.jpg")), None);
}
