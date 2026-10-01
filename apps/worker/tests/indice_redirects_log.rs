//! REC-05 (BSV-12c): `WARN` da reconstrução do índice da KVS. Binário separado, com um teste
//! só: com outros testes rodando `gerar` em paralelo sem subscriber, o cache de interesse dos
//! callsites do `tracing` às vezes descarta o evento antes de chegar ao subscriber de captura.

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use worker::fonte::FakeFonte;
use worker::geracao::gerar;
use worker::publicador::PublicadorMemoria;
use worker::redirects::RedirectsMemoria;
use worker::site::ConfigSite;

fn rodar(ids: &[i64], p: &mut PublicadorMemoria, kvs: &mut RedirectsMemoria) {
    gerar(
        &FakeFonte::new(ids.iter().map(|&id| linha(id)).collect(), vec![], AGORA),
        &mapeamento(),
        p,
        kvs,
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        AGORA,
    )
    .unwrap();
}

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
        .filter(|l| l.contains("WARN") && l.contains("redirects"))
        .map(str::to_owned)
        .collect()
}

/// REC-05: reconstrução loga `WARN` com o motivo; modo indice não loga.
#[test]
fn reconstrucao_loga_warn_com_o_motivo() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    let w = warns_de(|| {
        rodar(&[1001], &mut p, &mut kvs);
    });
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("indice_ausente"), "{w:?}");

    let w = warns_de(|| {
        rodar(&[1001], &mut p, &mut kvs);
    });
    assert!(w.is_empty(), "{w:?}");

    kvs.inserir_bruto("7", "x");
    let w = warns_de(|| {
        rodar(&[1001], &mut p, &mut kvs);
    });
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("etag_divergente"), "{w:?}");
}
