//! BSV-40 CIC-01..03: `DT_PUBLICACAO_SITE` gravada depois do manifest, uma vez por oferta, em
//! lotes de 1 000; falha não derruba o ciclo. (CIC-04 em `tests/cli_ciclo.rs`.)

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use worker::execucao::{Codigo, concluir, marcar_publicacao_site, rodar};
use worker::fonte::FakeFonte;
use worker::geracao::Relatorio;
use worker::oracle::sql_publicacao_site;
use worker::publicador::{Publicador, PublicadorMemoria};
use worker::redirects::RedirectsMemoria;
use worker::site::ConfigSite;

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

/// Um ciclo publicado (como o `besave-ciclo` faz) + a marcação.
fn ciclo(fonte: &FakeFonte, p: &mut PublicadorMemoria) -> Relatorio {
    let mut rel = rodar(
        fonte,
        &mapeamento(),
        p,
        &mut RedirectsMemoria::new(),
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        AGORA,
    )
    .unwrap();
    marcar_publicacao_site(fonte, &mut rel);
    rel
}

/// CIC-01: primeira execução grava a data nos publicados; a segunda não altera nenhuma linha.
#[test]
fn data_gravada_uma_vez() {
    let mut rejeitada = linha(4);
    rejeitada.preco_por = None;
    let fonte = FakeFonte::new(vec![linha(1), linha(2), linha(3), rejeitada], vec![], AGORA);
    let mut p = PublicadorMemoria::new();
    let rel = ciclo(&fonte, &mut p);
    assert_eq!(rel.publicacao_site_marcadas, 3);
    assert_eq!(rel.publicacao_site_falhas, 0);
    let datas = fonte.publicadas_site();
    assert_eq!(datas.keys().copied().collect::<Vec<_>>(), vec![1, 2, 3]);
    assert!(datas.values().all(|&d| d == AGORA));
    let rel2 = ciclo(&fonte, &mut p);
    assert_eq!(rel2.publicacao_site_marcadas, 0);
    assert_eq!(fonte.publicadas_site(), datas);
}

/// CIC-02: 2 500 ids → 3 statements.
#[test]
fn ids_em_lotes_de_1000() {
    let fonte = FakeFonte::new((1..=2500).map(linha).collect(), vec![], AGORA);
    let mut rel = Relatorio {
        ids_publicados: (1..=2500).collect(),
        ..Default::default()
    };
    marcar_publicacao_site(&fonte, &mut rel);
    assert_eq!(fonte.lotes_publicacao_site(), 3);
    assert_eq!(rel.publicacao_site_marcadas, 2500);
}

/// CIC-03: falha no UPDATE → WARN, `publicacao_site_falhas`, código 0, manifest publicado.
#[test]
fn falha_no_update_nao_derruba_o_ciclo() {
    let fonte = FakeFonte::new(vec![linha(1), linha(2)], vec![], AGORA).com_falha_publicacao_site();
    let mut p = PublicadorMemoria::new();
    let (cod, log) = com_log(|| {
        let rel = ciclo(&fonte, &mut p);
        concluir(Ok((rel, 10)), None, AGORA)
    });
    assert_eq!(cod, Codigo::Ok);
    assert!(
        log.lines()
            .any(|l| l.contains("WARN") && l.contains("DT_PUBLICACAO_SITE")),
        "{log}"
    );
    assert!(log.contains("publicacao_site_falhas=1"), "{log}");
    assert!(log.contains("publicacao_site_marcadas=0"), "{log}");
    assert!(p.ler("manifest.json").unwrap().is_some());
}

/// O UPDATE real só toca datas nulas e usa um bind por id.
#[test]
fn sql_so_atualiza_data_nula() {
    let sql = sql_publicacao_site(3);
    assert!(sql.contains("SET DT_PUBLICACAO_SITE = SYSDATE"), "{sql}");
    assert!(sql.contains("DT_PUBLICACAO_SITE IS NULL"), "{sql}");
    assert!(sql.contains("ID_OFERTA IN (:1, :2, :3)"), "{sql}");
}
