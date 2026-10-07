//! BSV-41 DTP-03, REL-01..02: fase de avisos no ciclo agendado e no relatório.

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::AGORA;
use worker::avisos::modelo::LinhaAviso;
use worker::avisos::publicacao::ConfigAvisos;
use worker::execucao::{Codigo, concluir, linha_relatorio, publicar_avisos_ciclo};
use worker::fonte::FakeFonte;
use worker::geracao::Relatorio;
use worker::publicador::{Publicador, PublicadorMemoria};

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

fn com_log<T>(f: impl FnOnce() -> T) -> (T, String) {
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .finish();
    let r = tracing::subscriber::with_default(sub, f);
    let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
    (r, log)
}

fn aviso(id: i64) -> LinhaAviso {
    LinhaAviso {
        id,
        titulo: format!("Aviso {id}"),
        texto: "Texto.".into(),
        ativo: true,
        dt_inicio: AGORA - 3600,
        ..Default::default()
    }
}

fn par<'a>(linha: &'a str, chave: &str) -> &'a str {
    linha
        .split(' ')
        .find_map(|p| p.strip_prefix(&format!("{chave}=")))
        .unwrap_or_else(|| panic!("falta {chave}: {linha}"))
}

/// REL-01: a linha `relatorio` traz publicados, removidos, falhas e o tempo da fase.
#[test]
fn relatorio_com_a_fase_de_avisos() {
    let fonte = FakeFonte::new(vec![], vec![], AGORA).com_avisos(vec![aviso(1), aviso(2)]);
    let mut p = PublicadorMemoria::new();
    let mut rel = Relatorio::default();
    publicar_avisos_ciclo(
        &fonte,
        &mut p,
        &ConfigAvisos::default(),
        AGORA,
        true,
        &mut rel,
    );
    let l = linha_relatorio(&rel, 10, AGORA);
    assert_eq!(par(&l, "avisos_publicados"), "2");
    assert_eq!(par(&l, "avisos_removidos"), "0");
    assert_eq!(par(&l, "avisos_falhas"), "0");
    assert_eq!(par(&l, "avisos_datas_gravadas"), "2");
    assert!(par(&l, "t_avisos").parse::<u64>().is_ok(), "{l}");

    fonte.definir_avisos(vec![aviso(2)]);
    let mut rel = Relatorio::default();
    publicar_avisos_ciclo(
        &fonte,
        &mut p,
        &ConfigAvisos::default(),
        AGORA,
        true,
        &mut rel,
    );
    let l = linha_relatorio(&rel, 10, AGORA);
    assert_eq!(par(&l, "avisos_publicados"), "0");
    assert_eq!(par(&l, "avisos_removidos"), "1");
}

/// REL-02: falha do Oracle na fase → WARN, `avisos_falhas=1`, código 0.
#[test]
fn falha_na_fase_nao_derruba_o_ciclo() {
    let fonte = FakeFonte::new(vec![], vec![], AGORA)
        .com_avisos(vec![aviso(1)])
        .com_falha_avisos();
    let mut p = PublicadorMemoria::new();
    let (cod, log) = com_log(|| {
        let mut rel = Relatorio::default();
        publicar_avisos_ciclo(
            &fonte,
            &mut p,
            &ConfigAvisos::default(),
            AGORA,
            true,
            &mut rel,
        );
        concluir(Ok((rel, 10)), None, AGORA)
    });
    assert_eq!(cod, Codigo::Ok);
    assert!(
        log.lines()
            .any(|l| l.contains("WARN") && l.contains("fase de avisos falhou")),
        "{log}"
    );
    assert!(log.contains("avisos_falhas=1"), "{log}");
    assert!(p.ler("avisos/1/index.html").unwrap().is_none());
}

/// DTP-03: com `marcar = false` (destino local) a página sobe e a data não é gravada.
#[test]
fn destino_local_nao_grava_a_data() {
    let fonte = FakeFonte::new(vec![], vec![], AGORA).com_avisos(vec![aviso(1)]);
    let mut p = PublicadorMemoria::new();
    let mut rel = Relatorio::default();
    publicar_avisos_ciclo(
        &fonte,
        &mut p,
        &ConfigAvisos::default(),
        AGORA,
        false,
        &mut rel,
    );
    assert!(p.ler("avisos/1/index.html").unwrap().is_some());
    assert_eq!(fonte.avisos_atuais()[0].dt_publicacao_site, None);
}

/// `BESAVE_AVISOS_DIR` e `BESAVE_CANAL_URL` (padrão: canal 1).
#[test]
fn config_do_env() {
    let c = ConfigAvisos::de(|_| None);
    assert_eq!(c.dir, None);
    assert_eq!(c.canal, "https://t.me/besaveofertas");
    let c = ConfigAvisos::de(|k| match k {
        "BESAVE_AVISOS_DIR" => Some("C:\\besave\\avisos".into()),
        "BESAVE_CANAL_URL" => Some("https://t.me/outro".into()),
        _ => None,
    });
    assert_eq!(
        c.dir.as_deref(),
        Some(std::path::Path::new("C:\\besave\\avisos"))
    );
    assert_eq!(c.canal, "https://t.me/outro");
}
