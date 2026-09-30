//! IDX/REC/REL (BSV-12c): índice `_estado/redirects.json` da KVS em ciclos de `gerar`.

mod comum;

use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;
use std::sync::{Arc, Mutex};

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use sha2::{Digest, Sha256};
use worker::conversao::LinhaOferta;
use worker::fonte::FakeFonte;
use worker::geracao::{ErroGeracao, Relatorio, gerar};
use worker::imagens::{chave_grande, chave_small};
use worker::publicador::{self, Meta, Publicador, PublicadorMemoria};
use worker::redirects::{
    ErroRedirects, ModoRedirects, MotivoReconstrucao, Redirects, RedirectsMemoria,
};
use worker::site::ConfigSite;

const INDICE: &str = "_estado/redirects.json";

fn rodar(
    linhas: &[LinhaOferta],
    p: &mut dyn Publicador,
    kvs: &mut RedirectsMemoria,
) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas.to_vec(), vec![], AGORA),
        &mapeamento(),
        p,
        kvs,
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        AGORA,
    )
}

fn linhas(ids: impl IntoIterator<Item = i64>) -> Vec<LinhaOferta> {
    ids.into_iter().map(linha).collect()
}

fn com_url(id: i64, url: &str) -> LinhaOferta {
    LinhaOferta {
        url_afiliado: url.into(),
        ..linha(id)
    }
}

/// hash16 da spec: SHA-256, 8 primeiros bytes em hex.
fn h16(url: &str) -> String {
    hex::encode(&Sha256::digest(url.as_bytes())[..8])
}

fn indice(p: &PublicadorMemoria) -> serde_json::Value {
    serde_json::from_slice(&p.ler(INDICE).unwrap().expect("índice ausente")).unwrap()
}

fn gravadas(p: &PublicadorMemoria, desde: usize) -> Vec<String> {
    p.gravacoes()[desde..].to_vec()
}

/// IDX-01, IDX-04: índice válido e nada mudou → 0 `listar`, 1 `descrever`, 0 `aplicar`, modo
/// `indice`, e o índice não é regravado.
#[test]
fn indice_valido_sem_mudanca_nao_lista_nem_aplica_nem_regrava() {
    let l = linhas(1001..=1005);
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&l, &mut p, &mut kvs).unwrap();
    let (listar, descrever, aplicados) = (
        kvs.listar_chamadas(),
        kvs.descrever_chamadas(),
        kvs.aplicados().len(),
    );
    let marca = p.gravacoes().len();

    let r = rodar(&l, &mut p, &mut kvs).unwrap();
    assert_eq!(kvs.listar_chamadas() - listar, 0, "listar no modo indice");
    assert_eq!(kvs.descrever_chamadas() - descrever, 1);
    assert_eq!(kvs.aplicados().len() - aplicados, 0, "UpdateKeys sem diff");
    assert_eq!(r.redirects.modo, ModoRedirects::Indice);
    assert_eq!(r.redirects.motivo, None);
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 0));
    assert!(
        !gravadas(&p, marca).contains(&INDICE.to_owned()),
        "{:?}",
        gravadas(&p, marca)
    );
}

/// IDX-02, IDX-03: 3 novas, 1 alterada, 2 removidas → um `aplicar` só com esses 6; índice com o
/// `ETag`/`ItemCount` pós-escrita e um hash16 por id publicado.
#[test]
fn diff_de_seis_chaves_so_aplica_elas_e_atualiza_o_indice() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&linhas(1001..=1006), &mut p, &mut kvs).unwrap();
    let listar = kvs.listar_chamadas();
    let aplicados = kvs.aplicados().len();

    let mut l = linhas([1002, 1003, 1004, 1007, 1008, 1009]);
    l.push(com_url(1001, "https://loja.example/1001-nova"));
    let r = rodar(&l, &mut p, &mut kvs).unwrap();

    assert_eq!(kvs.listar_chamadas(), listar, "listar no modo indice");
    assert_eq!(kvs.aplicados().len(), aplicados + 1);
    let (put, del) = kvs.aplicados().last().unwrap().clone();
    assert_eq!(
        put,
        [
            (1001, "https://loja.example/1001-nova".to_owned()),
            (1007, "https://loja.example/1007".to_owned()),
            (1008, "https://loja.example/1008".to_owned()),
            (1009, "https://loja.example/1009".to_owned()),
        ]
    );
    assert_eq!(del, [1005, 1006]);
    assert_eq!(r.redirects.modo, ModoRedirects::Indice);
    assert_eq!(
        (r.redirects.puts, r.redirects.dels, r.redirects.total),
        (4, 2, 7)
    );

    let depois = kvs.descrever().unwrap();
    let i = indice(&p);
    assert_eq!(i["kvs_etag"], depois.etag.as_str());
    assert_eq!(i["kvs_item_count"], 7);
    assert_eq!(depois.item_count, 7);
    let urls: BTreeMap<String, String> = serde_json::from_value(i["urls"].clone()).unwrap();
    let esperado: BTreeMap<String, String> = [1002, 1003, 1004, 1007, 1008, 1009]
        .into_iter()
        .map(|id| (id.to_string(), h16(&format!("https://loja.example/{id}"))))
        .chain([("1001".to_owned(), h16("https://loja.example/1001-nova"))])
        .collect();
    assert_eq!(urls, esperado);
}

/// Edge: conjunto publicado vazio em modo indice → todos os ids do índice viram delete.
#[test]
fn conjunto_vazio_em_modo_indice_apaga_tudo() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    let r = rodar(&[], &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.modo, ModoRedirects::Indice);
    assert_eq!(
        kvs.aplicados().last().unwrap(),
        &(vec![], vec![1001, 1002, 1003])
    );
    assert!(kvs.listar().unwrap().is_empty());
}

/// IDX-05: headers do índice.
#[test]
fn indice_e_json_sem_cache() {
    let mut p = PublicadorMemoria::new();
    rodar(&linhas([1001]), &mut p, &mut RedirectsMemoria::new()).unwrap();
    let m = p.meta(INDICE).expect("índice não gravado");
    assert_eq!(m.content_type, "application/json");
    assert_eq!(m.cache_control, "no-store");
    assert_eq!(m.content_encoding, None);
}

/// IDX-06: nenhuma URL em claro no índice.
#[test]
fn indice_nao_tem_url_em_claro() {
    let mut p = PublicadorMemoria::new();
    let mut l = linhas(1001..=1003);
    l.push(com_url(1004, "http://amzn.to/abc?tag=besave-20"));
    rodar(&l, &mut p, &mut RedirectsMemoria::new()).unwrap();
    let texto = String::from_utf8(p.ler(INDICE).unwrap().unwrap()).unwrap();
    assert!(!texto.contains("http"), "{texto}");
    assert!(!texto.contains("amzn"), "{texto}");
    assert_eq!(indice(&p)["urls"].as_object().unwrap().len(), 4);
}

/// IDX-07 (exigência do dono): em modo indice, o expurgo de imagens usa os ids do índice e o
/// ciclo inteiro faz 0 `listar`.
#[test]
fn expurgo_em_modo_indice_vem_do_indice_sem_listar() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    let listar = kvs.listar_chamadas();
    let remocoes = p.remocoes().len();

    let r = rodar(&linhas(1001..=1002), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.modo, ModoRedirects::Indice);
    assert_eq!(
        kvs.listar_chamadas(),
        listar,
        "listar em algum ponto do ciclo"
    );
    let removidas = &p.remocoes()[remocoes..];
    for chave in [chave_small(1003), chave_grande(1003)] {
        assert!(
            removidas.contains(&chave),
            "{chave} não expurgada: {removidas:?}"
        );
    }
    for id in [1001, 1002] {
        assert!(!removidas.contains(&chave_small(id)), "{removidas:?}");
    }
}

/// REC-01: sem índice → 1 `listar`, `reconstrucao`/`indice_ausente`, índice criado; ciclo
/// seguinte → `indice`.
#[test]
fn indice_ausente_reconstroi_uma_vez_e_depois_usa_o_indice() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(kvs.listar_chamadas(), 1);
    assert_eq!(r.redirects.modo, ModoRedirects::Reconstrucao);
    assert_eq!(r.redirects.motivo, Some(MotivoReconstrucao::IndiceAusente));
    assert!(p.existe(INDICE).unwrap());

    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.modo, ModoRedirects::Indice);
    assert_eq!(kvs.listar_chamadas(), 1);
}

/// REC-01 no caso real da 1ª execução: KVS já populada (BSV-12) e sem índice → a listagem é a
/// base do diff, então nada é reenviado.
#[test]
fn indice_ausente_com_kvs_populada_nao_reenvia_nada() {
    let mut kvs = RedirectsMemoria::com(
        (1001..=1003)
            .map(|id| (id, format!("https://loja.example/{id}")))
            .collect(),
    );
    let mut p = PublicadorMemoria::new();
    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.motivo, Some(MotivoReconstrucao::IndiceAusente));
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 0));
    assert!(kvs.aplicados().is_empty());
    assert_eq!(
        indice(&p)["kvs_etag"],
        kvs.descrever().unwrap().etag.as_str()
    );
}

/// REC-02: KVS alterada por fora → `etag_divergente`, e a KVS volta a espelhar o publicado.
#[test]
fn kvs_alterada_por_fora_reconstroi_com_etag_divergente() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    kvs.inserir_bruto("1002", "https://intruso.example/x");
    let listar = kvs.listar_chamadas();

    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.modo, ModoRedirects::Reconstrucao);
    assert_eq!(r.redirects.motivo, Some(MotivoReconstrucao::EtagDivergente));
    assert_eq!(kvs.listar_chamadas(), listar + 1);
    assert_eq!((r.redirects.puts, r.redirects.dels), (1, 0));
    assert_eq!(
        kvs.listar().unwrap(),
        (1001..=1003)
            .map(|id| (id, format!("https://loja.example/{id}")))
            .collect::<BTreeMap<_, _>>()
    );
    assert_eq!(
        indice(&p)["kvs_etag"],
        kvs.descrever().unwrap().etag.as_str()
    );
}

/// REC-03: `ETag` igual e `ItemCount` diferente → `item_count_divergente`.
#[test]
fn item_count_diferente_reconstroi() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    let etag = kvs.descrever().unwrap().etag;
    kvs.inserir_bruto("9999", "https://loja.example/9999");
    kvs.definir_etag(&etag);

    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.modo, ModoRedirects::Reconstrucao);
    assert_eq!(
        r.redirects.motivo,
        Some(MotivoReconstrucao::ItemCountDivergente)
    );
    assert_eq!(kvs.aplicados().last().unwrap(), &(vec![], vec![9999]));
}

/// REC-04: índice corrompido (não é JSON, ou JSON sem os campos) → `indice_ilegivel`, sem abortar,
/// e índice regravado legível.
#[test]
fn indice_corrompido_reconstroi_sem_abortar() {
    for lixo in [&b"{nao e json"[..], br#"{"urls":{}}"#, b"[]"] {
        let mut p = PublicadorMemoria::new();
        let mut kvs = RedirectsMemoria::new();
        rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
        p.gravar(INDICE, lixo, &publicador::META_ESTADO).unwrap();

        let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
        let ctx = String::from_utf8_lossy(lixo);
        assert_eq!(r.redirects.modo, ModoRedirects::Reconstrucao, "{ctx}");
        assert_eq!(
            r.redirects.motivo,
            Some(MotivoReconstrucao::IndiceIlegivel),
            "{ctx}"
        );
        assert!(p.existe("manifest.json").unwrap());
        assert_eq!(indice(&p)["kvs_item_count"], 3, "{ctx}");
    }
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
        rodar(&linhas([1001]), &mut p, &mut kvs).unwrap();
    });
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("indice_ausente"), "{w:?}");

    let w = warns_de(|| {
        rodar(&linhas([1001]), &mut p, &mut kvs).unwrap();
    });
    assert!(w.is_empty(), "{w:?}");

    kvs.inserir_bruto("7", "x");
    let w = warns_de(|| {
        rodar(&linhas([1001]), &mut p, &mut kvs).unwrap();
    });
    assert_eq!(w.len(), 1, "{w:?}");
    assert!(w[0].contains("etag_divergente"), "{w:?}");
}

/// Publicador cuja gravação do índice falha.
struct IndiceQuebrado(PublicadorMemoria);

impl Publicador for IndiceQuebrado {
    fn existe(&self, chave: &str) -> publicador::Result<bool> {
        self.0.existe(chave)
    }
    fn ler(&self, chave: &str) -> publicador::Result<Option<Vec<u8>>> {
        self.0.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> publicador::Result<()> {
        if chave == INDICE {
            return Err(publicador::ErroPublicador::Aws {
                operacao: "PutObject",
                chave: chave.to_owned(),
                fonte: "falha injetada".into(),
            });
        }
        self.0.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> publicador::Result<()> {
        self.0.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> publicador::Result<Vec<String>> {
        self.0.listar(prefixo)
    }
}

/// REC-06: falha ao gravar o índice → erro nomeado e nenhum manifest; o ciclo seguinte (com o
/// índice gravável) reconstrói.
#[test]
fn falha_ao_gravar_indice_aborta_antes_do_manifest() {
    let mut p = IndiceQuebrado(PublicadorMemoria::new());
    let mut kvs = RedirectsMemoria::new();
    let erro = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::Redirects(ErroRedirects::Indice(_))),
        "{erro:?}"
    );
    assert!(erro.to_string().contains(INDICE), "{erro}");
    assert!(!p.0.existe("manifest.json").unwrap());
    assert!(!p.0.existe(INDICE).unwrap());

    let mut p = p.0;
    let r = rodar(&linhas(1001..=1003), &mut p, &mut kvs).unwrap();
    assert_eq!(r.redirects.motivo, Some(MotivoReconstrucao::IndiceAusente));
    assert!(p.existe("manifest.json").unwrap());
}

/// Edge: falha na KVS → nem índice nem manifest.
#[test]
fn falha_na_kvs_nao_grava_indice() {
    let mut p = PublicadorMemoria::new();
    let erro = rodar(
        &linhas([1001]),
        &mut p,
        &mut RedirectsMemoria::new().falhando(),
    )
    .unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::Redirects(ErroRedirects::Kvs { .. })),
        "{erro:?}"
    );
    assert!(!p.existe(INDICE).unwrap());
    assert!(!p.existe("manifest.json").unwrap());
}

/// REL-01: textos exatos do relatório.
#[test]
fn modo_e_motivo_tem_os_textos_da_spec() {
    assert_eq!(ModoRedirects::Indice.to_string(), "indice");
    assert_eq!(ModoRedirects::Reconstrucao.to_string(), "reconstrucao");
    let motivos: BTreeSet<String> = [
        MotivoReconstrucao::IndiceAusente,
        MotivoReconstrucao::IndiceIlegivel,
        MotivoReconstrucao::EtagDivergente,
        MotivoReconstrucao::ItemCountDivergente,
    ]
    .iter()
    .map(ToString::to_string)
    .collect();
    assert_eq!(
        motivos,
        BTreeSet::from(
            [
                "indice_ausente",
                "indice_ilegivel",
                "etag_divergente",
                "item_count_divergente"
            ]
            .map(String::from)
        )
    );
}
