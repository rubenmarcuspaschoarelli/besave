//! KVS-01..07: `sincronizar_redirects` com `RedirectsMemoria`.

use std::collections::BTreeMap;
use std::io::Write;
use std::sync::{Arc, Mutex};

use worker::redirects::{
    AVISO_ENTRADAS, ErroRedirects, LIMITE_KVS_BYTES, LIMITE_VALOR_BYTES, Redirects,
    RedirectsMemoria, sincronizar_redirects,
};

fn ativos(v: &[(i64, &str)]) -> Vec<(i64, String)> {
    v.iter().map(|&(id, u)| (id, u.to_owned())).collect()
}

fn estado(v: &[(i64, &str)]) -> BTreeMap<i64, String> {
    ativos(v).into_iter().collect()
}

#[test]
fn diff_put_e_del_so_do_que_mudou() {
    let mut kvs = RedirectsMemoria::com(estado(&[(1, "a"), (2, "b")]));

    let r = sincronizar_redirects(&ativos(&[(1, "a"), (2, "c"), (3, "d")]), &mut kvs).unwrap();
    assert_eq!(kvs.aplicados(), [(ativos(&[(2, "c"), (3, "d")]), vec![])]);
    assert_eq!((r.puts, r.dels, r.total), (2, 0, 3));
    assert_eq!(
        kvs.listar().unwrap(),
        estado(&[(1, "a"), (2, "c"), (3, "d")])
    );

    let r = sincronizar_redirects(&ativos(&[(1, "a")]), &mut kvs).unwrap();
    assert_eq!(kvs.aplicados()[1], (vec![], vec![2, 3]));
    assert_eq!((r.puts, r.dels, r.total), (0, 2, 1));
    assert_eq!(kvs.listar().unwrap(), estado(&[(1, "a")]));
}

#[test]
fn mesma_entrada_duas_vezes_segunda_e_noop() {
    let mut kvs = RedirectsMemoria::new();
    let a = ativos(&[(1, "a"), (2, "b")]);
    sincronizar_redirects(&a, &mut kvs).unwrap();
    let r = sincronizar_redirects(&a, &mut kvs).unwrap();
    assert_eq!((r.puts, r.dels), (0, 0));
    assert_eq!(kvs.aplicados().len(), 1, "segunda rodada chamou aplicar");
}

#[test]
fn chave_e_id_decimal_e_valor_e_a_url() {
    let mut kvs = RedirectsMemoria::new();
    sincronizar_redirects(&ativos(&[(5412, "https://amzn.to/x")]), &mut kvs).unwrap();
    assert_eq!(
        kvs.chaves(),
        BTreeMap::from([("5412".to_owned(), "https://amzn.to/x".to_owned())])
    );
}

#[test]
fn url_e_trimada() {
    let mut kvs = RedirectsMemoria::com(estado(&[(1, "https://a")]));
    let r = sincronizar_redirects(&ativos(&[(1, "  https://a \n")]), &mut kvs).unwrap();
    assert_eq!((r.puts, r.dels), (0, 0));
    assert_eq!(kvs.listar().unwrap(), estado(&[(1, "https://a")]));
}

#[test]
fn valor_acima_de_1024_bytes_e_erro_nomeado() {
    let mut kvs = RedirectsMemoria::new();
    let ok = "h".repeat(LIMITE_VALOR_BYTES);
    sincronizar_redirects(&[(1, ok)], &mut kvs).unwrap();

    let longa = "h".repeat(LIMITE_VALOR_BYTES + 1);
    let erro = sincronizar_redirects(&[(1, "a".into()), (7, longa)], &mut kvs).unwrap_err();
    assert!(
        matches!(
            erro,
            ErroRedirects::ValorGrandeDemais { id: 7, bytes: 1025 }
        ),
        "{erro:?}"
    );
    assert_eq!(kvs.aplicados().len(), 1, "aplicar chamado após erro");
    assert_eq!(LIMITE_VALOR_BYTES, 1024);
}

#[test]
fn total_acima_de_5_mb_e_erro_nomeado() {
    assert_eq!(LIMITE_KVS_BYTES, 5 * 1024 * 1024);
    // 6 000 × (4 B de chave + 1 000 B de valor) = 6 024 000 B > 5 MiB.
    let url = "u".repeat(1000);
    let muitos: Vec<(i64, String)> = (1000..7000).map(|id| (id, url.clone())).collect();
    let mut kvs = RedirectsMemoria::new();
    let erro = sincronizar_redirects(&muitos, &mut kvs).unwrap_err();
    assert!(
        matches!(erro, ErroRedirects::KvsAcimaDoLimite { bytes: 6_024_000 }),
        "{erro:?}"
    );
    assert!(kvs.aplicados().is_empty());

    // 5 000 × 1 004 B = 5 020 000 B ≤ 5 MiB.
    let cabem: Vec<(i64, String)> = (1000..6000).map(|id| (id, url.clone())).collect();
    sincronizar_redirects(&cabem, &mut kvs).unwrap();
}

#[test]
fn chave_nao_numerica_e_preservada() {
    let mut kvs = RedirectsMemoria::new();
    kvs.inserir_bruto("config", "x");
    kvs.inserir_bruto("1", "a");
    assert_eq!(kvs.listar().unwrap(), estado(&[(1, "a")]));
    sincronizar_redirects(&[], &mut kvs).unwrap();
    assert_eq!(
        kvs.chaves(),
        BTreeMap::from([("config".to_owned(), "x".to_owned())])
    );
}

#[test]
fn falha_injetada_vira_erro() {
    let mut kvs = RedirectsMemoria::new().falhando();
    let erro = sincronizar_redirects(&ativos(&[(1, "a")]), &mut kvs).unwrap_err();
    assert!(matches!(erro, ErroRedirects::Kvs { .. }), "{erro:?}");
    assert!(kvs.listar().unwrap().is_empty());
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

fn logs_de(f: impl FnOnce()) -> String {
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .with_max_level(tracing::Level::WARN)
        .finish();
    tracing::subscriber::with_default(sub, f);
    String::from_utf8(buf.0.lock().unwrap().clone()).unwrap()
}

#[test]
fn acima_de_40_mil_entradas_avisa_e_sincroniza() {
    assert_eq!(AVISO_ENTRADAS, 40_000);
    let v: Vec<(i64, String)> = (1..=40_001).map(|id| (id, "u".into())).collect();
    let mut kvs = RedirectsMemoria::new();
    let logs = logs_de(|| {
        sincronizar_redirects(&v, &mut kvs).unwrap();
    });
    assert!(logs.contains("WARN"), "{logs}");
    assert!(logs.contains("40001"), "{logs}");
    assert_eq!(kvs.listar().unwrap().len(), 40_001);

    let v: Vec<(i64, String)> = (1..=40_000).map(|id| (id, "u".into())).collect();
    let logs = logs_de(|| {
        sincronizar_redirects(&v, &mut RedirectsMemoria::new()).unwrap();
    });
    assert!(!logs.contains("WARN"), "{logs}");
}

/// KVS-08: valor vazio nunca chega à KVS.
#[test]
fn valor_vazio_e_erro_nomeado_sem_aplicar() {
    for url in ["", "  "] {
        let mut kvs = RedirectsMemoria::com(estado(&[(1, "a")]));
        let erro =
            sincronizar_redirects(&[(1, "a".into()), (9, url.into())], &mut kvs).unwrap_err();
        assert!(
            matches!(erro, ErroRedirects::ValorVazio { id: 9 }),
            "{url:?}: {erro:?}"
        );
        assert!(kvs.aplicados().is_empty());
        assert_eq!(kvs.listar().unwrap(), estado(&[(1, "a")]));
    }
}
