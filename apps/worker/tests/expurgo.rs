//! EXP-01..: expurgo diferido e em lotes (BSV-47). Derivados do critério de aceite da spec:
//! nada é removido fora da janela, no máximo `ceil(chaves/1000)` chamadas por lote, retomada sem
//! repetir nem perder chave, manifest antes de qualquer remoção, órfãs entram na fila uma vez.

mod comum;

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::rc::Rc;

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use worker::conversao::LinhaOferta;
use worker::expurgo::{
    CHAVE_EXPURGO, ConfigExpurgo, FilaExpurgo, Janela, MAX_PADRAO, RelatorioExpurgo,
};
use worker::fonte::FakeFonte;
use worker::geracao::{Relatorio, gerar};
use worker::imagens::{IndiceImagens, chave_grande, chave_small};
use worker::paginas::chave_pagina;
use worker::publicador::{
    self, META_ESTADO, META_IMAGEM, META_PAGINA, Meta, Publicador, PublicadorMemoria,
};
use worker::redirects::{Redirects, RedirectsMemoria};
use worker::site::ConfigSite;

/// 2026-09-25T05:30:00Z = 02:30 em Brasília: dentro da janela padrão.
const NA_JANELA: i64 = AGORA + 16 * 3600 + 50 * 60;

fn site_padrao() -> ConfigSite {
    ConfigSite::default()
}

fn rodar(
    linhas: Vec<LinhaOferta>,
    p: &mut dyn Publicador,
    kvs: &mut RedirectsMemoria,
    agora: i64,
) -> Relatorio {
    gerar(
        &FakeFonte::new(linhas, vec![], agora),
        &mapeamento(),
        p,
        kvs,
        &dir_imagens_vazio(),
        &site_padrao(),
        agora,
    )
    .unwrap()
}

fn linhas_de(ids: impl IntoIterator<Item = i64>) -> Vec<LinhaOferta> {
    ids.into_iter()
        .map(|id| LinhaOferta {
            dt_publicacao_site: Some(AGORA - 1800),
            ..linha(id)
        })
        .collect()
}

fn chaves_do_id(id: i64) -> [String; 3] {
    [chave_pagina(id), chave_small(id), chave_grande(id)]
}

/// Bucket com página e as duas imagens de cada id, e a KVS com a chave deles.
fn bucket_com(ids: impl Iterator<Item = i64> + Clone) -> (PublicadorMemoria, RedirectsMemoria) {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    for id in ids {
        p.gravar(&chave_pagina(id), b"<html/>", &META_PAGINA)
            .unwrap();
        p.gravar(&chave_small(id), b"w", &META_IMAGEM).unwrap();
        p.gravar(&chave_grande(id), b"w", &META_IMAGEM).unwrap();
        kvs.inserir_bruto(&id.to_string(), "https://loja.example/x");
    }
    (p, kvs)
}

/// Páginas e imagens de oferta que ainda estão no bucket.
fn sobras(p: &PublicadorMemoria) -> Vec<String> {
    p.chaves()
        .into_iter()
        .filter(|c| c.starts_with("oferta/") || c.starts_with("img/ofertas/"))
        .collect()
}

fn fila_com(ids: impl IntoIterator<Item = i64>) -> FilaExpurgo {
    let mut f = FilaExpurgo::default();
    f.registrar(ids, AGORA);
    f
}

// ---- janela e configuração ----

#[test]
fn janela_e_em_brasilia_com_inicio_inclusivo_e_fim_exclusivo() {
    let j = Janela::analisar("02:00-05:00").unwrap();
    let dia = 1_790_208_000; // 2026-09-25T00:00:00Z
    let em = |h: i64, m: i64| dia + h * 3600 + m * 60;
    // 02:00 Brasília = 05:00Z; 05:00 Brasília = 08:00Z.
    assert!(!j.contem(em(4, 59)));
    assert!(j.contem(em(5, 0)));
    assert!(j.contem(em(7, 59)));
    assert!(!j.contem(em(8, 0)));
}

#[test]
fn janela_que_atravessa_a_meia_noite() {
    let j = Janela::analisar("22:00-02:00").unwrap();
    let dia = 1_790_208_000; // 00:00Z = 21:00 do dia anterior em Brasília
    let em = |h: i64| dia + h * 3600;
    assert!(!j.contem(em(0))); // 21:00
    assert!(j.contem(em(1))); // 22:00
    assert!(j.contem(em(4))); // 01:00
    assert!(!j.contem(em(5))); // 02:00
}

#[test]
fn janela_invalida_e_recusada() {
    for ruim in [
        "",
        "02:00",
        "2:00-5:00",
        "25:00-05:00",
        "02:60-05:00",
        "02:00-02:00",
        "a-b",
    ] {
        assert!(Janela::analisar(ruim).is_err(), "{ruim:?}");
    }
}

#[test]
fn config_padrao_e_do_env() {
    let d = ConfigExpurgo::default();
    assert_eq!(d.max, 3000);
    assert_eq!(d.max, MAX_PADRAO);
    assert_eq!(d.janela, Janela::analisar("02:00-05:00").unwrap());
    let c = ConfigExpurgo::de(|k| match k {
        "BESAVE_EXPURGO_JANELA" => Some("01:00-03:30".into()),
        "BESAVE_EXPURGO_MAX" => Some("500".into()),
        _ => None,
    })
    .unwrap();
    assert_eq!(c.max, 500);
    assert_eq!(c.janela, Janela::analisar("01:00-03:30").unwrap());
    assert_eq!(ConfigExpurgo::de(|_| None).unwrap(), d);
}

#[test]
fn config_ruim_nomeia_a_variavel() {
    for (var, valor) in [
        ("BESAVE_EXPURGO_JANELA", "madrugada"),
        ("BESAVE_EXPURGO_MAX", "0"),
        ("BESAVE_EXPURGO_MAX", "muitos"),
    ] {
        let e = ConfigExpurgo::de(|k| (k == var).then(|| valor.to_owned())).unwrap_err();
        assert_eq!(e.var, var);
        assert!(e.to_string().contains(var), "{e}");
    }
}

// ---- fila ----

/// EXP-01: 14.577 ids saindo, fora da janela → nenhuma chamada de remoção; a fila fica inteira.
#[test]
fn fora_da_janela_nada_e_apagado() {
    let ids = 1..=14_577;
    let (mut p, mut kvs) = bucket_com(ids.clone());
    let mut fila = fila_com(ids);
    let r = fila
        .executar(
            &ConfigExpurgo::default(),
            AGORA,
            &mut p,
            &mut kvs,
            &mut IndiceImagens::default(),
        )
        .unwrap();
    assert_eq!(p.remover_lote_chamadas(), 0);
    assert!(p.remocoes().is_empty());
    assert_eq!(kvs.aplicados().len(), 0);
    assert_eq!(
        r,
        RelatorioExpurgo {
            pendente: 14_577,
            ..Default::default()
        }
    );
}

/// EXP-02: na janela, no máximo `ceil(chaves/1000)` chamadas por ciclo e `MAX` ids por ciclo; a
/// fila esvazia em `ceil(14577/3000)` = 5 noites, cada chave apagada uma vez.
#[test]
fn na_janela_apaga_em_lotes_de_mil_chaves_ate_o_maximo() {
    let ids = 1..=14_577i64;
    let (mut p, mut kvs) = bucket_com(ids.clone());
    let mut fila = fila_com(ids.clone());
    let cfg = ConfigExpurgo::default();
    let mut chamadas_antes = 0;
    let mut pendentes = Vec::new();
    for noite in 0..5 {
        let r = fila
            .executar(
                &cfg,
                NA_JANELA + noite * 86_400,
                &mut p,
                &mut kvs,
                &mut IndiceImagens::default(),
            )
            .unwrap();
        let chamadas = p.remover_lote_chamadas() - chamadas_antes;
        chamadas_antes = p.remover_lote_chamadas();
        assert_eq!(chamadas, r.chaves.div_ceil(1000), "noite {noite}");
        assert!(r.removidos <= 3000, "{r:?}");
        pendentes.push(r.pendente);
    }
    assert_eq!(pendentes, [11_577, 8_577, 5_577, 2_577, 0]);
    // 14.577 ids × 3 chaves, cada uma uma vez.
    let remocoes = p.remocoes();
    assert_eq!(remocoes.len(), 14_577 * 3);
    assert_eq!(
        remocoes.iter().collect::<BTreeSet<_>>().len(),
        remocoes.len()
    );
    assert!(sobras(&p).is_empty(), "{}", sobras(&p).len());
    assert!(kvs.listar().unwrap().is_empty());
}

#[test]
fn lote_exato_usa_ceil_de_chaves_sobre_mil() {
    // 1000 ids = 3000 chaves = 3 chamadas; 1001 ids = 3003 chaves = 4 chamadas.
    for (n, esperado) in [(1000, 3), (1001, 4), (1, 1)] {
        let (mut p, mut kvs) = bucket_com(1..=n);
        let mut fila = fila_com(1..=n);
        fila.executar(
            &ConfigExpurgo::sempre(),
            AGORA,
            &mut p,
            &mut kvs,
            &mut IndiceImagens::default(),
        )
        .unwrap();
        assert_eq!(p.remover_lote_chamadas(), esperado, "{n} ids");
    }
}

/// EXP-03: chamada que falha no meio → erro; o estado gravado até ali vale; novo ciclo continua
/// sem repetir e sem perder chave.
#[test]
fn interrompido_no_meio_retoma_sem_repetir_e_sem_perder() {
    let ids = 1..=2000i64;
    let (mut p, mut kvs) = bucket_com(ids.clone());
    p = p.falhando_em_remover_lote_na(4);
    let mut fila = fila_com(ids.clone());
    fila.salvar(&mut p).unwrap();
    let cfg = ConfigExpurgo::sempre();
    fila.executar(&cfg, AGORA, &mut p, &mut kvs, &mut IndiceImagens::default())
        .unwrap_err();
    let apagadas_1 = p.remocoes().to_vec();
    assert_eq!(
        apagadas_1.len(),
        3000,
        "3 chamadas de 1000 chaves antes da falha"
    );

    // Outro processo: lê a fila gravada.
    let mut fila = FilaExpurgo::carregar(&p).unwrap();
    assert_eq!(fila.len(), 1000, "mil ids ficaram feitos e gravados");
    assert_eq!(fila.ids().next(), Some(1001));
    let r = fila
        .executar(
            &cfg,
            AGORA + 300,
            &mut p,
            &mut kvs,
            &mut IndiceImagens::default(),
        )
        .unwrap();
    assert_eq!((r.removidos, r.pendente), (1000, 0));

    let todas = p.remocoes();
    assert_eq!(todas.len(), 6000, "nada repetido: {}", todas.len());
    let esperadas: BTreeSet<String> = ids.flat_map(chaves_do_id).collect();
    assert_eq!(todas.iter().cloned().collect::<BTreeSet<_>>(), esperadas);
    assert!(kvs.listar().unwrap().is_empty());
}

/// Falha com um id cortado ao meio pela fronteira do lote: nenhuma chave se perde; no máximo as
/// duas que já tinham ido são reenviadas.
#[test]
fn interrupcao_no_meio_de_um_id_nao_perde_chave() {
    let ids = 1..=1000i64;
    let (mut p, mut kvs) = bucket_com(ids.clone());
    p = p.falhando_em_remover_lote_na(3);
    let mut fila = fila_com(ids.clone());
    let cfg = ConfigExpurgo::sempre();
    fila.executar(&cfg, AGORA, &mut p, &mut kvs, &mut IndiceImagens::default())
        .unwrap_err();
    let mut fila = FilaExpurgo::carregar(&p).unwrap();
    assert!(
        !fila.is_empty(),
        "a fila gravada depois da 1ª chamada ficou no bucket"
    );
    fila.executar(
        &cfg,
        AGORA + 300,
        &mut p,
        &mut kvs,
        &mut IndiceImagens::default(),
    )
    .unwrap();
    let todas = p.remocoes();
    let esperadas: BTreeSet<String> = ids.flat_map(chaves_do_id).collect();
    assert_eq!(todas.iter().cloned().collect::<BTreeSet<_>>(), esperadas);
    assert!(todas.len() <= esperadas.len() + 2, "{}", todas.len());
    assert!(sobras(&p).is_empty());
}

/// A KVS perde a chave do id apagado e o índice acompanha (próximo ciclo segue em modo índice).
#[test]
fn apagar_tira_a_chave_da_kvs_e_atualiza_o_indice() {
    let (mut p, mut kvs) = bucket_com(1..=5);
    // Ciclo que publica 1..=5 e cria o índice.
    let r = rodar(linhas_de(1..=5), &mut p, &mut kvs, AGORA);
    assert_eq!(r.expurgo.pendente, 0);
    // 4 e 5 saem; ainda fora da janela: ficam na KVS e na fila.
    let r = rodar(linhas_de(1..=3), &mut p, &mut kvs, AGORA + 600);
    assert_eq!(r.expurgo.enfileirados, 2);
    assert_eq!(r.expurgo.pendente, 2);
    assert_eq!(kvs.listar().unwrap().len(), 5);
    // Na janela: somem de verdade, e o ciclo seguinte não lista a KVS.
    let r = rodar(linhas_de(1..=3), &mut p, &mut kvs, NA_JANELA);
    assert_eq!((r.expurgo.removidos, r.expurgo.pendente), (2, 0));
    assert_eq!(
        kvs.listar().unwrap().into_keys().collect::<Vec<_>>(),
        [1, 2, 3]
    );
    let listar = kvs.listar_chamadas();
    let r = rodar(linhas_de(1..=3), &mut p, &mut kvs, NA_JANELA + 300);
    assert_eq!(kvs.listar_chamadas(), listar, "índice em dia");
    assert_eq!(r.redirects.modo, worker::redirects::ModoRedirects::Indice);
}

// ---- ciclo ----

/// Linha do tempo única de gravações e remoções.
#[derive(Default, Clone)]
struct Tempo(Rc<RefCell<Vec<String>>>);

struct PubComTempo(PublicadorMemoria, Tempo);

impl Publicador for PubComTempo {
    fn existe(&self, c: &str) -> publicador::Result<bool> {
        self.0.existe(c)
    }
    fn ler(&self, c: &str) -> publicador::Result<Option<Vec<u8>>> {
        self.0.ler(c)
    }
    fn gravar(&mut self, c: &str, b: &[u8], m: &Meta) -> publicador::Result<()> {
        self.1.0.borrow_mut().push(format!("gravar {c}"));
        self.0.gravar(c, b, m)
    }
    fn remover(&mut self, c: &str) -> publicador::Result<()> {
        self.1.0.borrow_mut().push(format!("remover {c}"));
        self.0.remover(c)
    }
    fn remover_lote(&mut self, cs: &[String]) -> publicador::Result<()> {
        for c in cs {
            self.1.0.borrow_mut().push(format!("remover {c}"));
        }
        self.0.remover_lote(cs)
    }
    fn listar(&self, p: &str) -> publicador::Result<Vec<String>> {
        self.0.listar(p)
    }
}

/// EXP-04: o id sai da lista no ciclo em que sai do conjunto; o arquivo só some na janela; o
/// manifest é gravado antes de qualquer remoção.
#[test]
fn desativacao_de_dia_sai_da_lista_e_o_arquivo_so_some_de_madrugada() {
    let tempo = Tempo::default();
    let mut p = PubComTempo(PublicadorMemoria::new(), tempo.clone());
    let mut kvs = RedirectsMemoria::new();
    rodar(linhas_de([5412, 5413, 5420]), &mut p, &mut kvs, AGORA);
    assert!(p.existe("oferta/5413/index.html").unwrap());

    // Dia: 5413 sai. Fora dos chunks e do sitemap já, arquivo ainda lá.
    tempo.0.borrow_mut().clear();
    let r = rodar(linhas_de([5412, 5420]), &mut p, &mut kvs, AGORA + 600);
    assert_eq!(
        (
            r.expurgo.enfileirados,
            r.expurgo.removidos,
            r.expurgo.pendente
        ),
        (1, 0, 1)
    );
    assert!(p.existe("oferta/5413/index.html").unwrap());
    assert!(p.existe("img/placeholder/tech.webp").unwrap());
    let manifest: worker::modelo::Manifest =
        serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap();
    assert_eq!(manifest.total_ofertas, 2);
    let sitemap = String::from_utf8(p.ler("sitemap-1.xml").unwrap().unwrap()).unwrap();
    assert!(!sitemap.contains("/oferta/5413/"), "{sitemap}");
    assert!(
        tempo.0.borrow().iter().all(|l| !l.starts_with("remover ")),
        "{:?}",
        tempo.0.borrow()
    );

    // Madrugada: some, e depois do manifest.
    tempo.0.borrow_mut().clear();
    let r = rodar(linhas_de([5412, 5420]), &mut p, &mut kvs, NA_JANELA);
    assert_eq!((r.expurgo.removidos, r.expurgo.pendente), (1, 0));
    assert!(!p.existe("oferta/5413/index.html").unwrap());
    let t = tempo.0.borrow();
    let manifest = t.iter().position(|l| l == "gravar manifest.json").unwrap();
    let primeira_remocao = t.iter().position(|l| l.starts_with("remover ")).unwrap();
    assert!(manifest < primeira_remocao, "{t:?}");
}

/// Regra 1 (AD-028): sem mudança no Oracle, nada além dos manifests; fila vazia fora da janela
/// não faz chamada de remoção e na janela também não.
#[test]
fn ciclo_sem_mudanca_com_fila_vazia_nao_altera_nada() {
    for agora in [AGORA, NA_JANELA] {
        let mut p = PublicadorMemoria::new();
        let mut kvs = RedirectsMemoria::new();
        rodar(linhas_de([5412, 5413]), &mut p, &mut kvs, agora);
        let marca = p.gravacoes().len();
        let r = rodar(linhas_de([5412, 5413]), &mut p, &mut kvs, agora + 300);
        assert_eq!(
            &p.gravacoes()[marca..],
            ["manifest.prev.json", "manifest.json"],
            "agora={agora}"
        );
        assert_eq!(p.remover_lote_chamadas(), 0);
        assert!(p.remocoes().is_empty());
        assert_eq!(r.expurgo, RelatorioExpurgo::default());
    }
}

/// Oferta que volta ao conjunto antes da janela sai da fila: nada dela é apagado.
#[test]
fn oferta_reativada_sai_da_fila_e_nao_e_apagada() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(linhas_de([5412, 5413]), &mut p, &mut kvs, AGORA);
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, AGORA + 300);
    assert_eq!(r.expurgo.pendente, 1);
    let r = rodar(linhas_de([5412, 5413]), &mut p, &mut kvs, AGORA + 600);
    assert_eq!(r.expurgo.pendente, 0);
    let r = rodar(linhas_de([5412, 5413]), &mut p, &mut kvs, NA_JANELA);
    assert_eq!(r.expurgo.removidos, 0);
    assert!(p.existe("oferta/5413/index.html").unwrap());
    let apagadas_do_site: Vec<_> = p
        .remocoes()
        .iter()
        .filter(|c| c.starts_with("oferta/") || c.starts_with("img/"))
        .collect();
    assert!(apagadas_do_site.is_empty(), "{apagadas_do_site:?}");
    assert!(kvs.listar().unwrap().contains_key(&5413));
}

// ---- reconciliação ----

/// EXP-05: imagem e página de id fora do conjunto e fora da fila entram na fila uma vez.
#[test]
fn orfas_entram_na_fila_uma_vez() {
    let mut p = PublicadorMemoria::new();
    // 777: só a página; 888: só uma imagem; 999: tudo. Nenhum está no conjunto publicado.
    p.gravar("oferta/777/index.html", b"x", &META_PAGINA)
        .unwrap();
    p.gravar(&chave_small(888), b"w", &META_IMAGEM).unwrap();
    p.gravar(&chave_pagina(999), b"x", &META_PAGINA).unwrap();
    p.gravar(&chave_grande(999), b"w", &META_IMAGEM).unwrap();
    let mut kvs = RedirectsMemoria::new();
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, AGORA);
    assert_eq!(r.expurgo.enfileirados, 3);
    assert_eq!(r.expurgo.pendente, 3);
    let fila: serde_json::Value =
        serde_json::from_slice(&p.ler(CHAVE_EXPURGO).unwrap().unwrap()).unwrap();
    assert_eq!(fila["reconciliado"], true);
    let ids: BTreeSet<&str> = fila["fila"]
        .as_object()
        .unwrap()
        .keys()
        .map(String::as_str)
        .collect();
    assert_eq!(ids, BTreeSet::from(["777", "888", "999"]));
    for data in fila["fila"].as_object().unwrap().values() {
        assert_eq!(data, "2026-09-24T12:40:00Z");
    }

    // Segunda vez: não reconcilia de novo, nem repete ids; o que o id publicado 5412 tem não entra.
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, AGORA + 300);
    assert_eq!(r.expurgo.enfileirados, 0);
    assert_eq!(r.expurgo.pendente, 3);
    // Órfã criada depois não é pega pela reconciliação (já feita): é problema do ciclo normal.
    p.gravar("oferta/4444/index.html", b"x", &META_PAGINA)
        .unwrap();
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, AGORA + 600);
    assert_eq!(r.expurgo.pendente, 3);

    // Na janela, as três saem (página + duas imagens de cada, inexistentes ou não).
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, NA_JANELA);
    assert_eq!((r.expurgo.removidos, r.expurgo.pendente), (3, 0));
    assert!(!p.existe("oferta/777/index.html").unwrap());
    assert!(!p.existe(&chave_small(888)).unwrap());
    assert!(!p.existe(&chave_pagina(999)).unwrap());
    assert!(p.existe(&chave_pagina(5412)).unwrap());
}

#[test]
fn fila_ilegivel_recomeca_e_reconcilia() {
    let mut p = PublicadorMemoria::new();
    p.gravar(CHAVE_EXPURGO, b"{nao e json", &META_ESTADO)
        .unwrap();
    p.gravar("oferta/777/index.html", b"x", &META_PAGINA)
        .unwrap();
    let f = FilaExpurgo::carregar(&p).unwrap();
    assert!(f.is_empty() && !f.reconciliado());
    let mut kvs = RedirectsMemoria::new();
    let r = rodar(linhas_de([5412]), &mut p, &mut kvs, AGORA);
    assert_eq!(r.expurgo.pendente, 1);
}

#[test]
fn fila_salva_so_quando_muda_e_sem_url() {
    let mut p = PublicadorMemoria::new();
    let mut f = fila_com([10, 11]);
    assert!(f.salvar(&mut p).unwrap());
    assert!(!f.salvar(&mut p).unwrap());
    let m = p.meta(CHAVE_EXPURGO).unwrap();
    assert_eq!(
        (m.cache_control, m.content_type),
        ("no-store", "application/json")
    );
    let texto = String::from_utf8(p.ler(CHAVE_EXPURGO).unwrap().unwrap()).unwrap();
    assert!(!texto.contains("http"), "{texto}");
    // Registrar de novo o que já está na fila não muda a data de entrada.
    f.registrar([10], AGORA + 999);
    assert!(!f.salvar(&mut p).unwrap());
    let por_id: BTreeMap<String, String> = serde_json::from_value(
        serde_json::from_str::<serde_json::Value>(&texto).unwrap()["fila"].clone(),
    )
    .unwrap();
    assert_eq!(por_id["10"], "2026-09-24T12:40:00Z");
}

/// Conferência do KVS no expurgo: id sem chave na KVS (órfã de página) não gera `UpdateKeys`.
#[test]
fn id_sem_chave_na_kvs_nao_chama_a_kvs() {
    let mut p = PublicadorMemoria::new();
    p.gravar(&chave_pagina(777), b"x", &META_PAGINA).unwrap();
    let mut kvs = RedirectsMemoria::new();
    let mut fila = fila_com([777]);
    fila.executar(
        &ConfigExpurgo::sempre(),
        AGORA,
        &mut p,
        &mut kvs,
        &mut IndiceImagens::default(),
    )
    .unwrap();
    assert_eq!(kvs.aplicados().len(), 0);
    assert!(fila.is_empty());
}

/// EXP-06 (lição 15): tempo do expurgo em memória com aquecimento e mediana. O gargalo real é a
/// rede (`DeleteObjects`); aqui só se garante que a contabilidade da fila (estado gravado a cada
/// lote) não é quadrática: 3000 ids de uma fila de 14.577 em menos de 5 s na mediana (build de teste).
#[test]
fn expurgo_de_um_ciclo_cabe_no_tempo_na_mediana() {
    let ids = 1..=14_577i64;
    let uma_rodada = || {
        let (mut p, mut kvs) = bucket_com(ids.clone());
        let mut fila = fila_com(ids.clone());
        let inicio = std::time::Instant::now();
        let r = fila
            .executar(
                &ConfigExpurgo::default(),
                NA_JANELA,
                &mut p,
                &mut kvs,
                &mut IndiceImagens::default(),
            )
            .unwrap();
        assert_eq!(r.removidos, 3000);
        inicio.elapsed()
    };
    uma_rodada(); // aquecimento
    let mut tempos: Vec<_> = (0..5).map(|_| uma_rodada()).collect();
    tempos.sort();
    assert!(
        tempos[2] < std::time::Duration::from_secs(5),
        "mediana {:?}",
        tempos[2]
    );
}

/// M49: `ConfigSite` lê `BESAVE_EXPURGO_JANELA` e `BESAVE_EXPURGO_MAX` do ambiente.
#[test]
fn config_do_site_le_a_janela_e_o_maximo_do_expurgo() {
    let env = |k: &str| match k {
        "BESAVE_EXPURGO_JANELA" => Some("22:00-23:30".to_owned()),
        "BESAVE_EXPURGO_MAX" => Some("17".to_owned()),
        _ => None,
    };
    let c = ConfigSite::de(env).unwrap();
    assert_eq!(c.expurgo.max, 17);
    assert_eq!(c.expurgo.janela, Janela::analisar("22:00-23:30").unwrap());
    // Sem as variáveis: os padrões.
    let padrao = ConfigSite::de(|_| None).unwrap();
    assert_eq!(padrao.expurgo, ConfigExpurgo::default());
}
