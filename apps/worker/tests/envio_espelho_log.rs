//! BSV-62 ESP-03: falha ao inserir na fila do WhatsApp → WARN com `id` e o motivo; duplicata não
//! avisa. Binário separado, com um teste só (o subscriber de log é por thread).

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::{linha_canal, mapeamento};
use worker::envio::binario::espelho_do_env;
use worker::envio::canal::{FakeCanal, RelogioFake};
use worker::envio::fonte::{FakeEnvio, FilaWhatsapp, FonteEnvio};
use worker::envio::foto::OrigemFoto;
use worker::envio::frases::Frases;
use worker::envio::modelo::{LinhaCanal, Parametros};
use worker::envio::rodada::{Contexto, rodar};
use worker::envio::site::Imagens;
use worker::imagens::ErroImagem;
use worker::modelo::Area;

const DIA0: i64 = 1_790_218_800;

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

fn oferta(id: i64) -> LinhaCanal {
    let mut l = linha_canal(id, Some(200.0), 100.0);
    l.oferta.dt_oferta = Some(DIA0 + 7 * 3600);
    l.dt_publicacao_site = Some(DIA0 + 7 * 3600);
    l
}

fn foto_rapida(_: &Imagens, id: i64, area: Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem> {
    Ok((vec![0xFF, 0xD8, id as u8], OrigemFoto::Placeholder(area)))
}

fn rodar_com(f: &FakeEnvio) {
    let r = RelogioFake::em(DIA0 + 10 * 3600);
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    rodar(&Contexto {
        fonte: f,
        telegram: &tg,
        relogio: &r,
        m: &m,
        imagens: Imagens::pasta(None),
        avisos: Imagens::pasta(None),
        foto: foto_rapida,
        frases: &Frases::embutidas().unwrap(),
        espelho_whatsapp: Some(2),
        canal: 1,
        pausa_ate: None,
    })
    .unwrap();
}

#[test]
fn warn_na_falha_e_silencio_na_duplicata() {
    let f = FakeEnvio::new(Parametros::default(), vec![oferta(41)]);
    f.falhar_fila(true);
    let w = warns_de(|| rodar_com(&f));
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("id=41"), "{w:?}");
    assert!(w[0].contains("falha injetada em ENVIO_WHATSAPP"), "{w:?}");

    // Duplicata: a oferta já está na fila; nenhum WARN.
    let f = FakeEnvio::new(Parametros::default(), vec![oferta(42)]);
    f.enfileirar_whatsapp(&FilaWhatsapp {
        canal: 2,
        id_oferta: 42,
        id_envio_telegram: 1,
        legenda: "x".into(),
        area_slug: "tech".into(),
        dt_fila: DIA0,
    })
    .unwrap();
    let w = warns_de(|| rodar_com(&f));
    assert!(w.is_empty(), "{w:?}");

    // Variável inválida: WARN e espelho desligado.
    let w = warns_de(|| assert_eq!(espelho_do_env(Some("dois")), None));
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("BESAVE_ENVIO_ESPELHO_WHATSAPP"), "{w:?}");
}
