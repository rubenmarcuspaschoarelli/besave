//! BSV-45 REC-02: `WARN` do índice de imagens inválido. Binário separado, com um teste só
//! (mesmo motivo de `aviso_ciclo_log.rs`: callsites do `tracing` com testes em paralelo).

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::AGORA;
use worker::imagens::{CHAVE_INDICE, ConfigImagens, chave_grande, chave_small, publicar_imagens};
use worker::publicador::{META_ESTADO, META_IMAGEM, Publicador, PublicadorMemoria};

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

fn origem(nome: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-worker-teste-indice-log-{nome}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&d);
    let pasta = d.join("1");
    std::fs::create_dir_all(&pasta).unwrap();
    let mut webp = b"RIFF".to_vec();
    webp.extend_from_slice(&[0, 0, 0, 0]);
    webp.extend_from_slice(b"WEBPVP8 ");
    webp.resize(200, b'A');
    std::fs::write(pasta.join("1-small.webp"), &webp).unwrap();
    std::fs::write(pasta.join("1.webp"), &webp).unwrap();
    d
}

/// REC-02: índice com JSON inválido e com valor fora do formato → 1 `WARN` citando o índice,
/// reconstrução sem erro. Índice ausente reconstrói sem `WARN`.
#[test]
fn indice_invalido_loga_warn_e_ausente_nao() {
    let casos: [(&str, Option<&[u8]>, usize); 3] = [
        ("json", Some(&b"{nao e json"[..]), 1),
        ("valor", Some(&br#"{"1":"abc"}"#[..]), 1),
        ("ausente", None, 0),
    ];
    for (nome, conteudo, esperados) in casos {
        let dir = origem(nome);
        let mut p = PublicadorMemoria::new();
        for c in [chave_small(1), chave_grande(1)] {
            p.gravar(&c, b"x", &META_IMAGEM).unwrap();
        }
        if let Some(c) = conteudo {
            p.gravar(CHAVE_INDICE, c, &META_ESTADO).unwrap();
        }
        let w = warns_de(|| {
            publicar_imagens(&[1], &dir, &mut p, &ConfigImagens::default(), AGORA).unwrap();
        });
        let do_indice: Vec<_> = w.iter().filter(|l| l.contains("imagens.json")).collect();
        assert_eq!(do_indice.len(), esperados, "{nome}: {w:?}");
        assert!(
            p.ler(CHAVE_INDICE).unwrap().is_some(),
            "{nome}: reconstruído"
        );
    }
}
