//! BSV-41 PAG-06, PAG-07, PAG-08: `WARN` do ciclo de avisos. Binário separado, com um teste só
//! (mesmo motivo de `indice_redirects_log.rs`: callsites do `tracing` com testes em paralelo).

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::AGORA;
use worker::avisos::modelo::LinhaAviso;
use worker::avisos::publicacao::{ConfigAvisos, publicar_avisos};
use worker::fonte::FakeFonte;
use worker::publicador::PublicadorMemoria;

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

fn aviso(id: i64, imagem: Option<&str>, link: Option<&str>) -> LinhaAviso {
    LinhaAviso {
        id,
        titulo: format!("Aviso {id}"),
        texto: "Texto.".into(),
        imagem: imagem.map(str::to_owned),
        link_interno: link.map(str::to_owned),
        ativo: true,
        dt_inicio: AGORA - 3600,
        ..Default::default()
    }
}

/// PAG-06: link externo → WARN com o id; PAG-07: `.png` → WARN; PAG-08: arquivo ausente → WARN;
/// aviso válido não loga.
#[test]
fn warns_do_ciclo_de_avisos() {
    let fonte = FakeFonte::new(vec![], vec![], AGORA).com_avisos(vec![
        aviso(1, None, Some("https://loja.com")),
        aviso(2, Some("foto.png"), Some("/")),
        aviso(3, Some("nao-existe.jpg"), Some("/")),
        aviso(4, None, Some("/elas/")),
    ]);
    let cfg = ConfigAvisos {
        dir: Some(std::env::temp_dir().join("besave-avisos-log-vazio")),
        ..ConfigAvisos::default()
    };
    let mut p = PublicadorMemoria::new();
    let w = warns_de(|| {
        publicar_avisos(&fonte, &mut p, &cfg, AGORA, true).unwrap();
    });
    assert_eq!(w.len(), 3, "{w:?}");
    assert!(
        w[0].contains("id=1") && w[0].contains("DS_LINK_INTERNO"),
        "{w:?}"
    );
    assert!(w[1].contains("id=2") && w[1].contains("ignorado"), "{w:?}");
    assert!(
        w[2].contains("id=3") && w[2].contains("sem imagem"),
        "{w:?}"
    );
}
