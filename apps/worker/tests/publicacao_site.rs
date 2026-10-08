//! BSV-40 CIC-01..03: `DT_PUBLICACAO_SITE` gravada depois do manifest, uma vez por oferta, em
//! lotes de 1 000; falha não derruba o ciclo. (CIC-04 em `tests/cli_ciclo.rs`.)
//! BSV-36 GRV-01..02, IDE-01: o valor gravado é o instante do ciclo, o mesmo `dp` dos cards.

mod comum;

use std::io::Write;
use std::sync::{Arc, Mutex};

use std::collections::BTreeMap;

use comum::{AGORA, AGORA_DP, descomprimir, dir_imagens_vazio, linha, mapeamento};
use worker::conversao::{LinhaOferta, iso_utc};
use worker::execucao::{Codigo, concluir, marcar_publicacao_site, rodar};
use worker::fonte::{FakeFonte, FonteOfertas};
use worker::geracao::Relatorio;
use worker::modelo::{Manifest, OfertaCard};
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

/// BSV-36 GRV-02 (substitui o `SYSDATE` da BSV-40): o UPDATE real grava o instante ligado em `:1`,
/// só toca data nula ou fora da faixa `[:2, :3]` e usa um bind por id.
#[test]
fn sql_grava_instante_do_ciclo_so_em_data_nula_ou_fora_da_faixa() {
    let sql = sql_publicacao_site(3);
    assert!(!sql.contains("SYSDATE"), "{sql}");
    assert!(
        sql.contains("SET DT_PUBLICACAO_SITE = DATE '1970-01-01' + :1 / 86400"),
        "{sql}"
    );
    assert!(sql.contains("DT_PUBLICACAO_SITE IS NULL"), "{sql}");
    assert!(
        sql.contains("DT_PUBLICACAO_SITE < DATE '1970-01-01' + :2 / 86400"),
        "{sql}"
    );
    assert!(
        sql.contains("DT_PUBLICACAO_SITE > DATE '1970-01-01' + :3 / 86400"),
        "{sql}"
    );
    assert!(sql.contains("ID_OFERTA IN (:4, :5, :6)"), "{sql}");
}

// BSV-36 GRV-01, IDE-01: o `UPDATE` grava o mesmo instante do `dp` publicado; o segundo ciclo
// mantém o `dp` e não escreve chunk.

/// 2026-10-07T12:00:37Z; instante do ciclo = 12:00:00Z.
const AGORA_REAL: i64 = AGORA_DP + 37;
const ANTES_DO_LIMITE: i64 = 1_791_244_800 - 60; // 2026-10-05T23:59:00Z
const NO_AR: i64 = 1_791_298_920; // 2026-10-06T15:02:00Z

fn ciclo_em(fonte: &FakeFonte, p: &mut PublicadorMemoria, agora: i64) -> Relatorio {
    let mut rel = rodar(
        fonte,
        &mapeamento(),
        p,
        &mut RedirectsMemoria::new(),
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        agora,
    )
    .unwrap();
    marcar_publicacao_site(fonte, &mut rel);
    rel
}

/// `dp` de cada card publicado, por id.
fn dps(p: &PublicadorMemoria) -> BTreeMap<i64, String> {
    let m: Manifest = serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap();
    let mut out = BTreeMap::new();
    for c in &m.chunks {
        let cards: Vec<OfertaCard> =
            serde_json::from_slice(&descomprimir(&p.ler(&c.arquivo).unwrap().unwrap())).unwrap();
        out.extend(cards.into_iter().map(|c| (c.id, c.dt_publicacao)));
    }
    out
}

/// 1 nula, 2 no ar, 3 no futuro, 4 antes de 2026-10-06.
fn fonte_dp() -> FakeFonte {
    let com = |id, d| LinhaOferta {
        dt_publicacao_site: d,
        ..linha(id)
    };
    FakeFonte::new(
        vec![
            com(1, None),
            com(2, Some(NO_AR)),
            com(3, Some(AGORA_DP + 3600)),
            com(4, Some(ANTES_DO_LIMITE)),
        ],
        vec![],
        AGORA_REAL,
    )
}

#[test]
fn grv_01_update_grava_o_mesmo_instante_do_dp_publicado() {
    let fonte = fonte_dp();
    let mut p = PublicadorMemoria::new();
    let rel = ciclo_em(&fonte, &mut p, AGORA_REAL);
    let publicados = dps(&p);
    assert_eq!(publicados[&1], "2026-10-07T12:00:00Z");
    assert_eq!(publicados[&2], "2026-10-06T15:02:00Z");
    assert_eq!(publicados[&3], "2026-10-07T12:00:00Z");
    assert_eq!(publicados[&4], "2026-10-07T12:00:00Z");
    // Nula e fora da faixa recebem o instante; a que está no ar não é tocada.
    assert_eq!(rel.publicacao_site_marcadas, 3);
    let gravadas = fonte.publicadas_site();
    assert_eq!(
        gravadas,
        BTreeMap::from([(1, AGORA_DP), (3, AGORA_DP), (4, AGORA_DP)])
    );
    for (id, d) in &gravadas {
        assert_eq!(iso_utc(*d), publicados[id], "id {id}");
    }
    assert_eq!(fonte.ofertas().unwrap()[1].dt_publicacao_site, Some(NO_AR));
}

#[test]
fn ide_01_segundo_ciclo_mantem_dp_e_nao_escreve_chunk() {
    let fonte = fonte_dp();
    let mut p = PublicadorMemoria::new();
    ciclo_em(&fonte, &mut p, AGORA_REAL);
    let primeiro = dps(&p);
    let marca = p.gravacoes().len();
    let rel2 = ciclo_em(&fonte, &mut p, AGORA_REAL + 600);
    assert_eq!(dps(&p), primeiro);
    assert_eq!(rel2.chunks_escritos, 0);
    assert_eq!(rel2.publicacao_site_marcadas, 0);
    assert_eq!(
        p.gravacoes()[marca..].to_vec(),
        vec!["manifest.prev.json", "manifest.json"]
    );
}
