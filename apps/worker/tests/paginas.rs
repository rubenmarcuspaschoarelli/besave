//! PAG-01..11: páginas de oferta em massa (BSV-21 regras 2–5, 9, 10).

mod comum;

use std::time::{Duration, Instant};

use comum::fixture;
use worker::modelo::{OfertaPagina, Status};
use worker::pagina_html::TemplateOferta;
use worker::paginas::{
    ErroPaginas, IndicePaginas, ORCAMENTO_HTML, RelatorioPaginas, chave_pagina,
    checar_orcamento_html, publicar_paginas,
};
use worker::publicador::{Meta, Publicador, PublicadorMemoria};

const HTML: &str = "text/html; charset=utf-8";
const CACHE: &str = "public, max-age=600, stale-while-revalidate=300";

fn oferta(id: i64) -> OfertaPagina {
    let base: OfertaPagina = serde_json::from_str(&fixture("oferta-pagina-ok.json")).unwrap();
    OfertaPagina {
        id,
        titulo: format!("{} #{id}", base.titulo),
        ..base
    }
}

fn tres() -> Vec<OfertaPagina> {
    vec![oferta(5412), oferta(5413), oferta(5420)]
}

fn t() -> TemplateOferta {
    TemplateOferta::novo().unwrap()
}

fn publicar(
    paginas: &[OfertaPagina],
    p: &mut dyn Publicador,
    anterior: &IndicePaginas,
) -> (IndicePaginas, RelatorioPaginas) {
    publicar_paginas(paginas, &t(), p, anterior).unwrap()
}

fn hex16(s: &str) -> bool {
    s.len() == 16
        && s.bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

/// PAG-01.
#[test]
fn chave_da_pagina() {
    assert_eq!(chave_pagina(5412), "oferta/5412/index.html");
}

/// PAG-02, PAG-09 (headers), PAG-10: sem índice anterior sobe tudo, com o HTML do template.
#[test]
fn sem_indice_anterior_publica_todas() {
    let mut p = PublicadorMemoria::new();
    let (indice, rel) = publicar(&tres(), &mut p, &IndicePaginas::default());

    assert_eq!(
        p.gravacoes(),
        [
            "oferta/5412/index.html",
            "oferta/5413/index.html",
            "oferta/5420/index.html"
        ]
    );
    assert_eq!(
        indice.0.keys().copied().collect::<Vec<_>>(),
        [5412, 5413, 5420]
    );
    assert!(indice.0.values().all(|h| hex16(h)), "{indice:?}");
    let mut maior = 0;
    for o in tres() {
        let chave = chave_pagina(o.id);
        let html = t().renderizar(&o).unwrap();
        assert_eq!(p.ler(&chave).unwrap().unwrap(), html.as_bytes());
        assert_eq!(
            p.meta(&chave),
            Some(Meta {
                content_type: HTML,
                content_encoding: None,
                cache_control: CACHE,
            })
        );
        maior = maior.max(html.len() as u64);
    }
    assert_eq!(rel.renderizadas, 3);
    assert_eq!(rel.publicadas, 3);
    assert_eq!(rel.inalteradas, 0);
    assert_eq!(rel.removidas, 0);
    assert!(rel.falhas.is_empty());
    assert_eq!(rel.maior_html, maior);
}

/// PAG-03: mesmo hash do índice → nada sobe; o índice novo é igual ao anterior.
#[test]
fn hash_igual_ao_indice_nao_sobe() {
    let mut p = PublicadorMemoria::new();
    let (indice, _) = publicar(&tres(), &mut p, &IndicePaginas::default());
    let marca = p.gravacoes().len();
    let (indice2, rel) = publicar(&tres(), &mut p, &indice);
    assert_eq!(p.gravacoes().len(), marca, "{:?}", &p.gravacoes()[marca..]);
    assert_eq!(indice2, indice);
    assert_eq!(
        (rel.renderizadas, rel.publicadas, rel.inalteradas),
        (3, 0, 3)
    );
}

/// PAG-04: render determinístico.
#[test]
fn render_deterministico() {
    let o = oferta(5412);
    let t = t();
    assert_eq!(t.renderizar(&o).unwrap(), t.renderizar(&o).unwrap());
    assert_eq!(
        t.renderizar(&o).unwrap(),
        TemplateOferta::novo().unwrap().renderizar(&o).unwrap()
    );
}

/// PAG-05: ATIVA → ENCERRADA muda o hash e só aquela página sobe.
#[test]
fn oferta_encerrada_reenvia_so_ela() {
    let mut p = PublicadorMemoria::new();
    let (indice, _) = publicar(&tres(), &mut p, &IndicePaginas::default());
    let marca = p.gravacoes().len();
    let mut paginas = tres();
    paginas[1].status = Status::Encerrada;
    let (indice2, rel) = publicar(&paginas, &mut p, &indice);
    assert_eq!(&p.gravacoes()[marca..], ["oferta/5413/index.html"]);
    assert_ne!(indice2.0[&5413], indice.0[&5413]);
    assert_eq!(indice2.0[&5412], indice.0[&5412]);
    assert_eq!((rel.publicadas, rel.inalteradas), (1, 2));
    let html = String::from_utf8(p.ler("oferta/5413/index.html").unwrap().unwrap()).unwrap();
    assert!(html.contains("noindex"), "página encerrada sem noindex");
}

/// PAG-06: id do índice anterior fora do conjunto → removido do bucket e do índice.
#[test]
fn expurgo_remove_pagina_e_tira_do_indice() {
    let mut p = PublicadorMemoria::new();
    let (indice, _) = publicar(&tres(), &mut p, &IndicePaginas::default());
    let (indice2, rel) = publicar(&tres()[..2], &mut p, &indice);
    assert_eq!(p.remocoes(), ["oferta/5420/index.html"]);
    assert!(!p.existe("oferta/5420/index.html").unwrap());
    assert!(!indice2.0.contains_key(&5420));
    assert_eq!(indice2.0.len(), 2);
    assert_eq!(rel.removidas, 1);
}

/// PAG-07: acima de 30 KB → erro nomeado com id e bytes; nada daquela página sobe.
#[test]
fn pagina_acima_do_orcamento_falha_com_erro_nomeado() {
    let mut grande = oferta(7001);
    grande.titulo = "x".repeat(40_000);
    let mut p = PublicadorMemoria::new();
    let erro = publicar_paginas(&[grande], &t(), &mut p, &IndicePaginas::default()).unwrap_err();
    assert!(
        matches!(erro, ErroPaginas::PaginaAcimaDoOrcamento { id: 7001, bytes } if bytes > 30_720),
        "{erro:?}"
    );
    assert!(erro.to_string().contains("7001"), "{erro}");
    assert!(!p.existe("oferta/7001/index.html").unwrap());
}

/// PAG-07 borda: 30 720 passa, 30 721 não.
#[test]
fn orcamento_aceita_30720_e_recusa_30721() {
    assert_eq!(ORCAMENTO_HTML, 30_720);
    assert!(checar_orcamento_html(1, 30_720).is_ok());
    assert!(matches!(
        checar_orcamento_html(1, 30_721),
        Err(ErroPaginas::PaginaAcimaDoOrcamento {
            id: 1,
            bytes: 30_721
        })
    ));
}

/// PAG-08: erro de render conta, não publica aquela página e segue; se já estava publicada,
/// mantém o hash anterior (não vira expurgo).
#[test]
fn falha_de_render_conta_e_segue() {
    let mut p = PublicadorMemoria::new();
    let (indice, _) = publicar(&tres(), &mut p, &IndicePaginas::default());
    let marca = p.gravacoes().len();

    let mut paginas = tres();
    paginas[0].dt_oferta = "data invalida".into();
    paginas[2].titulo = "Novo título".into();
    paginas.push(OfertaPagina {
        dt_oferta: "invalida".into(),
        ..oferta(9001)
    });
    let (indice2, rel) = publicar(&paginas, &mut p, &indice);

    assert_eq!(rel.falhas, [5412, 9001]);
    assert_eq!(rel.renderizadas, 2);
    assert_eq!(&p.gravacoes()[marca..], ["oferta/5420/index.html"]);
    assert!(p.remocoes().is_empty());
    assert_eq!(indice2.0[&5412], indice.0[&5412]);
    assert!(!indice2.0.contains_key(&9001));
}

/// Conta as chamadas de `gravar_lote` e o tamanho de cada uma.
#[derive(Default)]
struct Lotes {
    dentro: PublicadorMemoria,
    lotes: Vec<usize>,
}

impl Publicador for Lotes {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.dentro.listar(prefixo)
    }
    fn gravar_lote(&mut self, itens: &[(String, Vec<u8>, Meta)]) -> worker::publicador::Result<()> {
        self.lotes.push(itens.len());
        for (c, b, m) in itens {
            self.dentro.gravar(c, b, m)?;
        }
        Ok(())
    }
}

/// PAG-09: upload via `gravar_lote` em blocos de no máximo 64.
#[test]
fn upload_em_lotes_de_64() {
    let paginas: Vec<OfertaPagina> = (1..=130).map(oferta).collect();
    let mut p = Lotes::default();
    let (_, rel) = publicar(&paginas, &mut p, &IndicePaginas::default());
    assert_eq!(p.lotes, [64, 64, 2]);
    assert_eq!(rel.publicadas, 130);
    assert_eq!(p.dentro.gravacoes().len(), 130);
}

/// PAG-10: `tempo_render_ms` mede só o render, então nunca passa do tempo total da chamada.
#[test]
fn tempo_de_render_cabe_no_tempo_da_chamada() {
    let paginas: Vec<OfertaPagina> = (1..=300).map(oferta).collect();
    let inicio = Instant::now();
    let (_, rel) = publicar(
        &paginas,
        &mut PublicadorMemoria::new(),
        &IndicePaginas::default(),
    );
    assert!(u128::from(rel.tempo_render_ms) <= inicio.elapsed().as_millis());
    // 300 renders não cabem em menos de 1 ms: o campo mede de verdade.
    assert!(rel.tempo_render_ms > 0);
}

/// PAG-11: 30 000 páginas renderizadas em ≤ 60 s (release). Instável sob carga no CI.
#[test]
#[ignore = "desempenho; rodar com cargo test --release -- --ignored"]
fn trinta_mil_paginas_em_ate_60_segundos() {
    let paginas: Vec<OfertaPagina> = (1..=30_000).map(oferta).collect();
    let inicio = Instant::now();
    let (indice, rel) = publicar(
        &paginas,
        &mut PublicadorMemoria::new(),
        &IndicePaginas::default(),
    );
    let tempo = inicio.elapsed();
    assert_eq!(indice.0.len(), 30_000);
    assert_eq!(rel.renderizadas, 30_000);
    assert!(tempo <= Duration::from_secs(60), "{tempo:?}");
}
