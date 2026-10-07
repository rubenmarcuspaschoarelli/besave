//! BSV-41 ENV-14: `WARN` do aviso com imagem em formato não aceito. Binário separado, com um teste
//! só (mesmo motivo de `indice_redirects_log.rs`).

use std::io::Write;
use std::sync::{Arc, Mutex};

use worker::avisos::modelo::LinhaAviso;
use worker::envio::aviso::devido;
use worker::envio::fonte::AvisoCanal;

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

fn aviso(id: i64, imagem: &str) -> AvisoCanal {
    AvisoCanal {
        aviso: LinhaAviso {
            id,
            titulo: format!("Aviso {id}"),
            texto: "Texto.".into(),
            imagem: Some(imagem.into()),
            ativo: true,
            dt_inicio: 0,
            dt_publicacao_site: Some(0),
            ..Default::default()
        },
        intervalo_min: 120,
        ativo: true,
        ultimo_envio: None,
    }
}

/// ENV-14: `.png` → aviso ignorado com `WARN` citando o id; `.jpg` não loga.
#[test]
fn png_loga_warn() {
    let avisos = [aviso(1, "aviso.png"), aviso(2, "aviso.jpg")];
    let mut escolhido = None;
    let w = warns_de(|| escolhido = devido(&avisos, 1_000_000).map(|a| a.aviso.id));
    assert_eq!(escolhido, Some(2));
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("id=1") && w[0].contains("ignorado"), "{w:?}");
}
