//! BSV-61 IMG-02: WARN com `id` e o status ou motivo quando a foto do site falha. Binário separado,
//! com um teste só (mesmo motivo de `envio_aviso_log.rs`).

use std::io::Write;
use std::sync::{Arc, Mutex};

use image::ImageEncoder;
use worker::envio::foto::foto_de;
use worker::envio::site::{BaixarHttps, Disco, ErroBaixa, Imagens, MAX_BYTES};
use worker::modelo::Area;

#[derive(Clone, Default)]
struct Buffer(Arc<Mutex<Vec<u8>>>);

impl Write for Buffer {
    fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(b);
        Ok(b.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

fn warns_de(f: impl FnOnce()) -> Vec<String> {
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .with_max_level(tracing::Level::WARN)
        .finish();
    tracing::subscriber::with_default(sub, f);
    String::from_utf8(buf.0.lock().unwrap().clone())
        .unwrap()
        .lines()
        .filter(|l| l.contains("WARN"))
        .map(str::to_owned)
        .collect()
}

struct Resposta(Result<(u16, Vec<u8>), ErroBaixa>);

impl BaixarHttps for Resposta {
    fn baixar(&self, _: &str) -> Result<(u16, Vec<u8>), ErroBaixa> {
        self.0.clone()
    }
}

/// IMG-02: cada falha loga um WARN com o id e o motivo; `200` válido não loga.
#[test]
fn warn_com_id_e_motivo() {
    let mut grande = Vec::new();
    image::codecs::webp::WebPEncoder::new_lossless(&mut grande)
        .write_image(
            &[220, 0, 0, 255].repeat(4),
            2,
            2,
            image::ExtendedColorType::Rgba8,
        )
        .unwrap();
    let valido = grande.clone();
    grande.resize(MAX_BYTES + 1, 0);
    let casos = [
        (Ok((404, vec![])), "status 404"),
        (Err(ErroBaixa::Timeout(15)), "timeout de 15 s"),
        (Ok((200, b"lixo".to_vec())), "não é imagem"),
        (Ok((200, grande)), "maior que 5242880 bytes"),
    ];
    for (r, motivo) in casos {
        let http = Resposta(r);
        let img = Imagens {
            url: Some("https://besave.com.br/img/ofertas/"),
            dir: None,
            http: &http,
            disco: &Disco,
        };
        let w = warns_de(|| {
            foto_de(&img, 7, Area::Tech).unwrap();
        });
        assert_eq!(w.len(), 1, "{motivo}: {w:?}");
        assert!(
            w[0].contains("id=7") && w[0].contains(motivo) && w[0].contains("placeholder"),
            "{motivo}: {w:?}"
        );
    }
    let http = Resposta(Ok((200, valido)));
    let img = Imagens {
        url: Some("https://besave.com.br/img/ofertas/"),
        dir: None,
        http: &http,
        disco: &Disco,
    };
    let w = warns_de(|| {
        foto_de(&img, 7, Area::Tech).unwrap();
    });
    assert!(w.is_empty(), "{w:?}");
}
