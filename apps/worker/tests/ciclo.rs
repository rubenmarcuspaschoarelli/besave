//! CIC-01..06: execuções sucessivas de `gerar` sobre o mesmo `PublicadorMemoria`.

mod comum;

use std::time::{Duration, Instant};

use comum::{AGORA, DIA, linha, linhas_fixture, mapeamento};
use worker::conversao::LinhaOferta;
use worker::fonte::FakeFonte;
use worker::geracao::{ErroGeracao, Relatorio, gerar};
use worker::mapeamento::Mapeamento;
use worker::modelo::Manifest;
use worker::publicador::{Publicador, PublicadorMemoria};
use worker::redirects::{Redirects, RedirectsMemoria};

fn rodar(
    linhas: &[LinhaOferta],
    p: &mut PublicadorMemoria,
    m: &Mapeamento,
    agora: i64,
) -> Result<Relatorio, ErroGeracao> {
    rodar_com(linhas, p, &mut RedirectsMemoria::new(), m, agora)
}

fn rodar_com(
    linhas: &[LinhaOferta],
    p: &mut PublicadorMemoria,
    kvs: &mut RedirectsMemoria,
    m: &Mapeamento,
    agora: i64,
) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas.to_vec(), vec![], agora),
        m,
        p,
        kvs,
        agora,
    )
}

fn manifest(p: &PublicadorMemoria) -> Manifest {
    serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap()
}

fn arquivo(m: &Manifest, n: u64) -> String {
    m.chunks.iter().find(|c| c.n == n).unwrap().arquivo.clone()
}

/// Chunks 1, 5 (fixture) e 7.
fn fonte() -> Vec<LinhaOferta> {
    let mut v = linhas_fixture();
    v.extend([linha(1001), linha(7001)]);
    v
}

/// Chaves gravadas a partir do índice `desde` do histórico.
fn gravadas(p: &PublicadorMemoria, desde: usize) -> Vec<String> {
    p.gravacoes()[desde..].to_vec()
}

#[test]
fn segunda_execucao_sem_mudanca_nao_grava_nem_remove_chunk() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    let r1 = rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    assert_eq!(r1.chunks_escritos, 3);
    let marca = p.gravacoes().len();

    let r2 = rodar(&fonte(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r2.chunks_escritos, 0);
    assert_eq!(r2.chunks_removidos, 0);
    assert_eq!(r2.chunks_reaproveitados, 3);
    assert_eq!(
        gravadas(&p, marca),
        vec!["manifest.prev.json", "manifest.json"]
    );
    assert_eq!(p.listar("data/chunks/").unwrap().len(), 3);
}

#[test]
fn mudanca_no_chunk_5_regrava_so_ele_e_antigo_sai_na_terceira() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    let m1 = manifest(&p);
    let antigo_5 = arquivo(&m1, 5);

    let mut alterada = fonte();
    alterada[1].preco_por = Some(79.90); // 5413
    let marca = p.gravacoes().len();
    let r2 = rodar(&alterada, &mut p, &m, AGORA + 600).unwrap();
    let m2 = manifest(&p);
    let novo_5 = arquivo(&m2, 5);

    assert_ne!(novo_5, antigo_5);
    assert_eq!(r2.chunks_escritos, 1);
    assert_eq!(
        gravadas(&p, marca),
        vec![
            novo_5.clone(),
            "manifest.prev.json".into(),
            "manifest.json".into()
        ]
    );
    assert_eq!(arquivo(&m2, 1), arquivo(&m1, 1));
    assert_eq!(arquivo(&m2, 7), arquivo(&m1, 7));
    // O manifest anterior ainda aponta para o antigo: fica mais um ciclo.
    assert_eq!(r2.chunks_removidos, 0);
    assert!(p.existe(&antigo_5).unwrap());

    let r3 = rodar(&alterada, &mut p, &m, AGORA + 1200).unwrap();
    assert_eq!(r3.chunks_removidos, 1);
    assert_eq!(r3.chunks_escritos, 0);
    assert!(!p.existe(&antigo_5).unwrap());
    assert!(p.existe(&novo_5).unwrap());
    assert_eq!(p.listar("data/chunks/").unwrap(), {
        let mut v: Vec<String> = m2.chunks.iter().map(|c| c.arquivo.clone()).collect();
        v.sort();
        v
    });
}

#[test]
fn manifest_prev_e_copia_do_anterior() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    assert!(!p.existe("manifest.prev.json").unwrap());
    let primeiro = p.ler("manifest.json").unwrap().unwrap();

    rodar(&fonte(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(p.ler("manifest.prev.json").unwrap().unwrap(), primeiro);
    assert_ne!(p.ler("manifest.json").unwrap().unwrap(), primeiro);
}

#[test]
fn expurgo_muda_hash_e_faixa_vazia_some() {
    let m = mapeamento();
    let desativada_ha_6_dias = |l: LinhaOferta| LinhaOferta {
        ativo: false,
        dt_desativacao: Some(AGORA - 6 * DIA),
        ..l
    };
    let mut linhas = fonte();
    linhas[2] = desativada_ha_6_dias(linhas[2].clone()); // 5420
    linhas.push(desativada_ha_6_dias(linha(9001))); // sozinha no chunk 9
    let mut p = PublicadorMemoria::new();
    rodar(&linhas, &mut p, &m, AGORA).unwrap();
    let m1 = manifest(&p);
    assert!(m1.chunks.iter().any(|c| c.n == 9));

    // 2 dias depois as duas passam de 7 dias desativadas e saem da fonte.
    rodar(&linhas, &mut p, &m, AGORA + 2 * DIA).unwrap();
    let m2 = manifest(&p);
    let c5 = m2.chunks.iter().find(|c| c.n == 5).unwrap();
    assert_ne!(c5.arquivo, arquivo(&m1, 5));
    assert_eq!(c5.ids, [5412, 5413]);
    assert!(m2.chunks.iter().all(|c| c.n != 9));
}

#[test]
fn manifest_anterior_invalido_falha_sem_gravar() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    p.gravar(
        "manifest.json",
        b"{nao e json",
        &worker::publicador::META_MANIFEST,
    )
    .unwrap();
    let erro = rodar(&fonte(), &mut p, &m, AGORA).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ManifestAnteriorInvalido(_)),
        "{erro:?}"
    );
    assert_eq!(p.gravacoes(), ["manifest.json"]);
}

#[test]
fn trinta_mil_cards_em_ate_10_segundos() {
    let m = mapeamento();
    let linhas: Vec<_> = (1..=30_000)
        .map(|id| LinhaOferta {
            titulo: Some(format!(
                "Produto {id} linha {} modelo {} com garantia",
                id % 97,
                id % 13
            )),
            preco_por: Some(10.0 + (id % 500) as f64),
            ..linha(id)
        })
        .collect();
    let mut p = PublicadorMemoria::new();
    let inicio = Instant::now();
    let rel = rodar(&linhas, &mut p, &m, AGORA).unwrap();
    let tempo = inicio.elapsed();
    assert_eq!(rel.validas, 30_000);
    assert_eq!(manifest(&p).chunks.len(), 31);
    assert!(tempo <= Duration::from_secs(10), "{tempo:?}");
}

#[test]
fn manifest_anterior_json_sem_forma_de_manifest_falha_sem_gravar() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    p.gravar(
        "manifest.json",
        br#"{"versao":1}"#,
        &worker::publicador::META_MANIFEST,
    )
    .unwrap();
    let erro = rodar(&fonte(), &mut p, &m, AGORA).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ManifestAnteriorInvalido(_)),
        "{erro:?}"
    );
    assert_eq!(p.gravacoes(), ["manifest.json"]);
}

/// ORD-05: oferta expurgada perde a chave na KVS; segunda execução sem mudança não escreve.
#[test]
fn expurgo_apaga_a_chave_na_kvs() {
    let m = mapeamento();
    let mut linhas = fonte();
    linhas[2] = LinhaOferta {
        ativo: false,
        dt_desativacao: Some(AGORA - 6 * DIA),
        ..linhas[2].clone()
    }; // 5420
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA).unwrap();
    assert!(kvs.listar().unwrap().contains_key(&5420));

    let r = rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA + 600).unwrap();
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 0));

    let r = rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA + 2 * DIA).unwrap();
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 1));
    assert_eq!(
        kvs.listar().unwrap().into_keys().collect::<Vec<_>>(),
        [1001, 5412, 5413, 7001]
    );
}
