//! BSV-62 FRA-04/05: WARN quando `BESAVE_FRASES_CANAL` é inválido e quando uma frase é descartada.
//! Binário separado, com um teste só (o subscriber de log é por thread).

use std::io::Write;
use std::sync::{Arc, Mutex};

use worker::envio::frases::Frases;

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

#[test]
fn warn_no_arquivo_invalido_e_na_frase_descartada() {
    let d = std::env::temp_dir().join(format!("besave-frases-log-{}", std::process::id()));
    std::fs::create_dir_all(&d).unwrap();
    let invalido = d.join("invalido.json");
    std::fs::write(&invalido, r#"{"icones": [], "frases": ["a"]}"#).unwrap();
    let valido = d.join("valido.json");
    std::fs::write(&valido, r#"{"icones": ["🚨"], "frases": ["Ok."]}"#).unwrap();

    let w = warns_de(|| {
        Frases::carregar_ou_embutidas(Some(&invalido)).unwrap();
    });
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("BESAVE_FRASES_CANAL"), "{w:?}");
    assert!(w[0].contains("invalido.json"), "{w:?}");

    let w = warns_de(|| {
        Frases::carregar_ou_embutidas(Some(&valido)).unwrap();
        Frases::carregar_ou_embutidas(None).unwrap();
    });
    assert!(w.is_empty(), "arquivo válido e embutido não avisam: {w:?}");

    let longa = "x".repeat(121);
    let w = warns_de(|| {
        Frases::de_json(&format!(
            r#"{{"icones": ["🚨"], "frases": ["", "{longa}", "Ok."]}}"#
        ))
        .unwrap();
    });
    assert_eq!(w.len(), 2, "uma por frase descartada: {w:?}");
}
