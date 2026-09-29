//! CHK-05, MAN-01..08: `gerar` com `FakeFonte` + `PublicadorMemoria`.

mod comum;

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

use comum::{
    AGORA, compactar, descomprimir, dir_imagens_vazio, fixture, linha, linhas_fixture, mapeamento,
    texto_aleatorio, validar_schema,
};
use worker::conversao::{LinhaOferta, Rejeicao};
use worker::fonte::FakeFonte;
use worker::geracao::{ErroGeracao, Relatorio, checar_orcamento, contar_paginas, gerar};
use worker::imagens::RelatorioImagens;
use worker::modelo::{Area, Manifest};
use worker::paginas::RelatorioPaginas;
use worker::publicador::{
    ErroPublicador, META_CHUNK, META_MANIFEST, Meta, Publicador, PublicadorMemoria,
};
use worker::redirects::{Redirects, RedirectsMemoria, RelatorioRedirects};
use worker::site::{ConfigSite, RelatorioSite};

fn rodar(linhas: Vec<LinhaOferta>, p: &mut dyn Publicador) -> Result<Relatorio, ErroGeracao> {
    rodar_com(linhas, p, &mut RedirectsMemoria::new())
}

fn rodar_com(
    linhas: Vec<LinhaOferta>,
    p: &mut dyn Publicador,
    kvs: &mut dyn Redirects,
) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas, vec![], AGORA),
        &mapeamento(),
        p,
        kvs,
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        AGORA,
    )
}

fn rodar_com_imagens(
    linhas: Vec<LinhaOferta>,
    p: &mut dyn Publicador,
    kvs: &mut dyn Redirects,
    dir_imagens: &std::path::Path,
    agora: i64,
) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas, vec![], agora),
        &mapeamento(),
        p,
        kvs,
        dir_imagens,
        &ConfigSite::default(),
        agora,
    )
}

fn manifest(p: &PublicadorMemoria) -> Manifest {
    serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap()
}

/// Fixture (chunk 5) + 1001 e 1500 (chunk 1) + 2 rejeitadas.
fn fonte_mista() -> Vec<LinhaOferta> {
    let mut v = linhas_fixture();
    v.push(linha(1500));
    v.push(linha(1001));
    v.push(LinhaOferta {
        preco_por: None,
        ..linha(1700)
    });
    v.push(LinhaOferta {
        id_produto: None,
        ..linha(1800)
    });
    v
}

#[test]
fn manifest_valida_contra_schema() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    validar_schema(
        "manifest.schema.json",
        &serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap(),
    );
}

#[test]
fn manifest_cabecalho() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    let pkg: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../packages/contract/package.json"),
        )
        .unwrap(),
    )
    .unwrap();
    assert_eq!(m.contrato, pkg["version"].as_str().unwrap());
    assert_eq!(m.versao, 20_260_924_124_000);
    assert_eq!(m.gerado_em, "2026-09-24T12:40:00Z");
    assert_eq!(m.busca, None);
}

#[test]
fn manifest_chunks_com_ids_reais_e_bytes_comprimidos() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(m.chunks.iter().map(|c| c.n).collect::<Vec<_>>(), vec![1, 5]);
    assert_eq!(m.chunks[0].ids, [1001, 1500]);
    assert_eq!(m.chunks[0].qtd, 2);
    assert_eq!(m.chunks[1].ids, [5412, 5420]);
    assert_eq!(m.chunks[1].qtd, 3);
    for c in &m.chunks {
        let br = p.ler(&c.arquivo).unwrap().unwrap();
        assert_eq!(c.bytes, br.len() as u64, "{}", c.arquivo);
        let cards: Vec<serde_json::Value> = serde_json::from_slice(&descomprimir(&br)).unwrap();
        assert_eq!(c.qtd, cards.len() as u64);
    }
}

#[test]
fn fixture_vira_um_chunk_com_hash_deterministico() {
    let mut p = PublicadorMemoria::new();
    rodar(linhas_fixture(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(m.chunks.len(), 1);
    assert_eq!(
        m.chunks[0].arquivo,
        "data/chunks/5-89590e56ef6361dc.json.br"
    );
    let bruto = descomprimir(&p.ler(&m.chunks[0].arquivo).unwrap().unwrap());
    assert_eq!(
        String::from_utf8(bruto.clone()).unwrap(),
        compactar(&fixture("chunk-ok.json"))
    );
    validar_schema(
        "chunk.schema.json",
        &serde_json::from_slice(&bruto).unwrap(),
    );
}

#[test]
fn areas_contam_so_ativas_e_total_conta_todas() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    // 5420 (PETS) está expirada: fora de `areas`, mas dentro do chunk e do total.
    assert_eq!(m.areas, BTreeMap::from([(Area::Tech, 3), (Area::Elas, 1)]));
    assert_eq!(m.total_ofertas, 5);
}

/// AREA-01, AREA-03: `Area::Outros` conta em `manifest.areas` e o manifest ainda valida contra o schema 1.3.
#[test]
fn area_outros_conta_no_manifest_e_valida_contra_schema() {
    let mut p = PublicadorMemoria::new();
    let l = LinhaOferta {
        area: Some("Outros".into()),
        ..linha(9000)
    };
    rodar(vec![l], &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(m.areas, BTreeMap::from([(Area::Outros, 1)]));
    validar_schema(
        "manifest.schema.json",
        &serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap(),
    );
}

#[test]
fn headers_e_manifest_por_ultimo() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(p.gravacoes().last().unwrap(), "manifest.json");
    assert_eq!(p.meta("manifest.json"), Some(META_MANIFEST));
    for c in &m.chunks {
        let re = format!("data/chunks/{}-", c.n);
        assert!(c.arquivo.starts_with(&re) && c.arquivo.ends_with(".json.br"));
        assert_eq!(c.arquivo.len(), re.len() + 16 + ".json.br".len());
        assert_eq!(p.meta(&c.arquivo), Some(META_CHUNK));
    }
}

/// Imagens (passo 1 de MANIFEST §6, incluindo os placeholders) já foram publicadas quando o
/// orçamento do chunk estoura — o passo seguinte é que aborta; só chunk/manifest ficam de fora.
#[test]
fn chunk_acima_do_orcamento_falha_sem_gravar_nada() {
    let linhas: Vec<_> = (1..1000)
        .map(|id| LinhaOferta {
            titulo: Some(texto_aleatorio(id as u64, 200)),
            ..linha(id)
        })
        .collect();
    let mut p = PublicadorMemoria::new();
    let erro = rodar(linhas, &mut p).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ChunkAcimaDoOrcamento { n: 0, bytes } if bytes > 61_440),
        "{erro:?}"
    );
    assert!(
        p.gravacoes()
            .iter()
            .all(|c| !c.starts_with("data/chunks/") && c != "manifest.json"),
        "{:?}",
        p.gravacoes()
    );
    assert!(!p.existe("manifest.json").unwrap());
}

#[test]
fn orcamento_aceita_61440_e_recusa_61441() {
    assert!(checar_orcamento(0, 61_440).is_ok());
    assert!(matches!(
        checar_orcamento(3, 61_441),
        Err(ErroGeracao::ChunkAcimaDoOrcamento {
            n: 3,
            bytes: 61_441
        })
    ));
}

/// Falha na 2ª gravação de chunk.
struct DiscoCheio {
    dentro: PublicadorMemoria,
    chunks: u32,
}

impl Publicador for DiscoCheio {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        if chave.starts_with("data/chunks/") {
            self.chunks += 1;
            if self.chunks == 2 {
                return Err(ErroPublicador::Io {
                    operacao: "gravando",
                    chave: chave.into(),
                    fonte: std::io::Error::other("disco cheio"),
                });
            }
        }
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.dentro.listar(prefixo)
    }
}

#[test]
fn falha_em_chunk_nao_grava_manifest() {
    let mut p = DiscoCheio {
        dentro: PublicadorMemoria::new(),
        chunks: 0,
    };
    let erro = rodar(fonte_mista(), &mut p).unwrap_err();
    assert!(matches!(erro, ErroGeracao::Publicador(_)), "{erro:?}");
    assert!(!p.dentro.existe("manifest.json").unwrap());
}

#[test]
fn relatorio_com_contagens() {
    let mut p = PublicadorMemoria::new();
    let rel = rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    let maior = m.chunks.iter().max_by_key(|c| c.bytes).unwrap();
    let maior_html = p
        .listar("oferta/")
        .unwrap()
        .iter()
        .map(|c| p.ler(c).unwrap().unwrap().len() as u64)
        .max()
        .unwrap();
    assert_eq!(
        rel,
        Relatorio {
            lidas: 7,
            validas: 5,
            rejeitadas: BTreeMap::from([
                (Rejeicao::PrecoPorInvalido, 1),
                (Rejeicao::IdProdutoAusente, 1),
            ]),
            chunks_escritos: 2,
            chunks_reaproveitados: 0,
            chunks_removidos: 0,
            bytes_totais: m.chunks.iter().map(|c| c.bytes).sum(),
            maior_chunk: Some((maior.n, maior.bytes)),
            versao: 20_260_924_124_000,
            redirects: RelatorioRedirects {
                puts: 5,
                dels: 0,
                total: 5,
            },
            imagens: RelatorioImagens {
                publicadas: 0,
                reaproveitadas: 0,
                sem_origem: 5,
                reprocessadas: 0,
                falhas: vec![],
                bytes: 0,
                maior_small: 0,
                maior_grande: 0,
            },
            site: RelatorioSite {
                paginas: RelatorioPaginas {
                    renderizadas: 5,
                    publicadas: 5,
                    inalteradas: 0,
                    removidas: 0,
                    falhas: vec![],
                    maior_html,
                    // Tempo de relógio: o único campo sem valor fixo.
                    tempo_render_ms: rel.site.paginas.tempo_render_ms,
                },
                css_publicado: true,
                sitemaps_publicados: 2,
                sitemaps_removidos: 0,
                robots_publicado: true,
                indice_gravado: true,
            },
        }
    );
}

#[test]
fn fonte_vazia_gera_manifest_vazio() {
    let mut p = PublicadorMemoria::new();
    rodar(vec![], &mut p).unwrap();
    let m = manifest(&p);
    assert!(m.chunks.is_empty());
    assert_eq!(m.total_ofertas, 0);
    assert!(m.areas.is_empty());
}

/// URL-03: card sem URL de afiliado não é publicado e conta como rejeição.
#[test]
fn sem_url_de_afiliado_nao_publica_o_card() {
    let mut p = PublicadorMemoria::new();
    let rel = rodar(
        vec![
            LinhaOferta {
                url_afiliado: " ".into(),
                ..linha(2000)
            },
            linha(2001),
        ],
        &mut p,
    )
    .unwrap();
    assert_eq!(
        rel.rejeitadas,
        BTreeMap::from([(Rejeicao::UrlAfiliadoAusente, 1)])
    );
    assert_eq!(rel.validas, 1);
    let m = manifest(&p);
    assert_eq!(m.total_ofertas, 1);
    assert_eq!(m.chunks[0].ids, [2001, 2001]);
}

/// ORD-01: KVS = todo card publicado (inclui expirado 5420), nenhum rejeitado (1700, 1800).
#[test]
fn kvs_recebe_url_de_todo_card_publicado() {
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar_com(fonte_mista(), &mut p, &mut kvs).unwrap();
    let esperado: BTreeMap<i64, String> = [1001, 1500, 5412, 5413, 5420]
        .into_iter()
        .map(|id| (id, format!("https://loja.example/{id}")))
        .collect();
    assert_eq!(kvs.listar().unwrap(), esperado);
}

type Tempo = Rc<RefCell<Vec<String>>>;

/// Registra gravações numa linha do tempo comum com a KVS.
struct PubComTempo(PublicadorMemoria, Tempo);

impl Publicador for PubComTempo {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.0.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.0.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        self.1.borrow_mut().push(chave.to_owned());
        self.0.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.0.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.0.listar(prefixo)
    }
}

struct KvsComTempo(RedirectsMemoria, Tempo);

impl Redirects for KvsComTempo {
    fn listar(&self) -> worker::redirects::Result<BTreeMap<i64, String>> {
        self.0.listar()
    }
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> worker::redirects::Result<()> {
        self.1.borrow_mut().push("KVS".into());
        self.0.aplicar(put, del)
    }
}

/// ORD-02: chunks → KVS → manifest.prev.json → manifest.json.
#[test]
fn kvs_entre_chunks_e_manifest() {
    let tempo: Tempo = Rc::default();
    let mut p = PubComTempo(PublicadorMemoria::new(), tempo.clone());
    let mut kvs = KvsComTempo(RedirectsMemoria::new(), tempo.clone());
    rodar_com(fonte_mista(), &mut p, &mut kvs).unwrap();
    // Segunda rodada com oferta nova: existe manifest.prev.json, chunk 1 muda e há diff na KVS.
    tempo.borrow_mut().clear();
    let mut linhas = fonte_mista();
    linhas.push(linha(1600));
    rodar_com(linhas, &mut p, &mut kvs).unwrap();
    let t = tempo.borrow().clone();
    let kvs_em = t.iter().position(|x| x == "KVS").unwrap();
    let ultimo_chunk = t
        .iter()
        .rposition(|x| x.starts_with("data/chunks/"))
        .unwrap();
    assert!(ultimo_chunk < kvs_em, "{t:?}");
    assert_eq!(&t[kvs_em..], ["KVS", "manifest.prev.json", "manifest.json"]);
}

/// ORD-03: falha na KVS → erro e manifest não gravado (o anterior continua).
#[test]
fn falha_na_kvs_nao_grava_manifest() {
    let mut p = PublicadorMemoria::new();
    let erro = rodar_com(
        fonte_mista(),
        &mut p,
        &mut RedirectsMemoria::new().falhando(),
    )
    .unwrap_err();
    assert!(matches!(erro, ErroGeracao::Redirects(_)), "{erro:?}");
    assert!(!p.existe("manifest.json").unwrap());
    // Tudo que vem antes da KVS (MANIFEST §6 passos 1–3) pode ter subido; manifest nunca.
    assert!(
        p.gravacoes().iter().all(|c| c.starts_with("data/chunks/")
            || c.starts_with("img/placeholder/")
            || c.starts_with("oferta/")
            || c.starts_with("sitemap")
            || c == "assets/besave.css"
            || c == "robots.txt"
            || c == "_estado/paginas.json"),
        "{:?}",
        p.gravacoes()
    );

    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar_com(fonte_mista(), &mut p, &mut kvs).unwrap();
    let antes = p.ler("manifest.json").unwrap();
    let marca = p.gravacoes().len();
    let mut linhas = fonte_mista();
    linhas.push(linha(1600));
    let mut kvs = RedirectsMemoria::com(kvs.listar().unwrap()).falhando();
    assert!(matches!(
        rodar_com(linhas, &mut p, &mut kvs),
        Err(ErroGeracao::Redirects(_))
    ));
    assert_eq!(p.ler("manifest.json").unwrap(), antes);
    let depois = &p.gravacoes()[marca..];
    assert!(!depois.is_empty());
    // Chunk 1, página nova e sitemap/índice que a citam; nada de manifest.
    assert!(
        depois.iter().any(|c| c.starts_with("data/chunks/1-")),
        "{depois:?}"
    );
    assert!(
        depois.iter().all(|c| c.starts_with("data/chunks/")
            || c == "oferta/1600/index.html"
            || c == "sitemap-1.xml"
            || c == "_estado/paginas.json"),
        "{depois:?}"
    );
}

fn bytes_webp_teste(tamanho: usize) -> Vec<u8> {
    let mut b = b"RIFF".to_vec();
    b.extend_from_slice(&[0, 0, 0, 0]);
    b.extend_from_slice(b"WEBPVP8 ");
    b.resize(tamanho.max(b.len()), b'A');
    b
}

fn escrever_origem_imagem(dir: &std::path::Path, id: i64) {
    let pasta = dir.join(id.to_string());
    std::fs::create_dir_all(&pasta).unwrap();
    std::fs::write(
        pasta.join(format!("{id}-small.webp")),
        bytes_webp_teste(1_000),
    )
    .unwrap();
    std::fs::write(pasta.join(format!("{id}.webp")), bytes_webp_teste(1_000)).unwrap();
}

fn dir_temp_geracao(nome: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-worker-geracao-{nome}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// GER-01: `publicar_imagens` roda antes de qualquer gravação de chunk (MANIFEST §6 passo 1).
#[test]
fn imagens_publicadas_antes_de_qualquer_chunk() {
    let dir = dir_temp_geracao("ordem");
    escrever_origem_imagem(&dir, 5412);
    let mut p = PublicadorMemoria::new();
    rodar_com_imagens(
        vec![linha(5412)],
        &mut p,
        &mut RedirectsMemoria::new(),
        &dir,
        AGORA,
    )
    .unwrap();
    let primeiro_chunk = p
        .gravacoes()
        .iter()
        .position(|c| c.starts_with("data/chunks/"))
        .unwrap();
    let imagem = p
        .gravacoes()
        .iter()
        .position(|c| c == "img/ofertas/5412-small.webp")
        .unwrap();
    assert!(imagem < primeiro_chunk, "{:?}", p.gravacoes());
}

/// GER-02: o `Relatorio` de `gerar` carrega as contagens de `RelatorioImagens`.
#[test]
fn relatorio_inclui_contagens_de_imagens() {
    let dir = dir_temp_geracao("contagens");
    escrever_origem_imagem(&dir, 5412);
    let mut p = PublicadorMemoria::new();
    let rel = rodar_com_imagens(
        vec![linha(5412)],
        &mut p,
        &mut RedirectsMemoria::new(),
        &dir,
        AGORA,
    )
    .unwrap();
    assert_eq!(rel.imagens.publicadas, 1);
    assert_eq!(rel.imagens.sem_origem, 0);
}

/// GER-03: id que sai do conjunto publicado tem as duas chaves de imagem removidas.
#[test]
fn expurgo_remove_as_duas_chaves_de_imagem() {
    let dir = dir_temp_geracao("expurgo");
    escrever_origem_imagem(&dir, 5412);
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar_com_imagens(vec![linha(5412)], &mut p, &mut kvs, &dir, AGORA).unwrap();
    assert!(p.existe("img/ofertas/5412-small.webp").unwrap());
    assert!(p.existe("img/ofertas/5412.webp").unwrap());
    assert!(p.existe("oferta/5412/index.html").unwrap());

    // 5412 sai do resultado da fonte (expurgo, CONTRATO §7).
    rodar_com_imagens(vec![linha(9999)], &mut p, &mut kvs, &dir, AGORA + 600).unwrap();
    assert!(!p.existe("img/ofertas/5412-small.webp").unwrap());
    assert!(!p.existe("img/ofertas/5412.webp").unwrap());
    // BSV-21 regra 5 (PAG-06): a página sai junto com as imagens.
    assert!(!p.existe("oferta/5412/index.html").unwrap());
    assert!(p.remocoes().contains(&"oferta/5412/index.html".to_owned()));
}

/// GER-04: ausência de origem de imagem não bloqueia a publicação da oferta.
#[test]
fn sem_origem_de_imagem_nao_bloqueia_a_oferta() {
    let dir = dir_temp_geracao("sem-origem-oferta");
    let mut p = PublicadorMemoria::new();
    let rel = rodar_com_imagens(
        vec![linha(5412)],
        &mut p,
        &mut RedirectsMemoria::new(),
        &dir,
        AGORA,
    )
    .unwrap();
    assert_eq!(rel.imagens.sem_origem, 1);
    assert_eq!(rel.validas, 1);
    let m = manifest(&p);
    assert_eq!(m.total_ofertas, 1);
}

// ---- BSV-21 ----

/// SIT-13: imagens → chunks → CSS → páginas → sitemaps → robots → índice → KVS → manifest.
#[test]
fn ordem_de_publicacao_do_site() {
    let tempo: Tempo = Rc::default();
    let mut p = PubComTempo(PublicadorMemoria::new(), tempo.clone());
    let mut kvs = KvsComTempo(RedirectsMemoria::new(), tempo.clone());
    rodar_com(fonte_mista(), &mut p, &mut kvs).unwrap();
    let t = tempo.borrow().clone();
    let pos = |pred: &dyn Fn(&str) -> bool| t.iter().position(|c| pred(c)).unwrap();
    let ultima = |pred: &dyn Fn(&str) -> bool| t.iter().rposition(|c| pred(c)).unwrap();
    let ordem = [
        ultima(&|c| c.starts_with("img/")),
        pos(&|c| c.starts_with("data/chunks/")),
        ultima(&|c| c.starts_with("data/chunks/")),
        pos(&|c| c == "assets/besave.css"),
        pos(&|c| c.starts_with("oferta/")),
        ultima(&|c| c.starts_with("oferta/")),
        pos(&|c| c == "sitemap-1.xml"),
        pos(&|c| c == "sitemap.xml"),
        pos(&|c| c == "robots.txt"),
        pos(&|c| c == "_estado/paginas.json"),
        pos(&|c| c == "KVS"),
        pos(&|c| c == "manifest.json"),
    ];
    assert!(ordem.windows(2).all(|w| w[0] < w[1]), "{ordem:?} {t:?}");
}

/// Falha só nas páginas de oferta.
struct PaginaFalha(PublicadorMemoria);

impl Publicador for PaginaFalha {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.0.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.0.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        if chave.starts_with("oferta/") {
            return Err(ErroPublicador::Aws {
                operacao: "PutObject",
                chave: chave.into(),
                fonte: "timeout".into(),
            });
        }
        self.0.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.0.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.0.listar(prefixo)
    }
}

/// SIT-14: falha de upload de página aborta antes do índice, da KVS e do manifest.
#[test]
fn falha_no_upload_de_pagina_nao_grava_manifest() {
    let mut p = PaginaFalha(PublicadorMemoria::new());
    let mut kvs = RedirectsMemoria::new();
    let erro = rodar_com(fonte_mista(), &mut p, &mut kvs).unwrap_err();
    assert!(
        matches!(
            &erro,
            ErroGeracao::Site(worker::site::ErroSite::Paginas(
                worker::paginas::ErroPaginas::Publicador(ErroPublicador::Aws { .. })
            ))
        ),
        "{erro:?}"
    );
    assert!(!p.0.existe("manifest.json").unwrap());
    assert!(!p.0.existe("_estado/paginas.json").unwrap());
    assert!(kvs.aplicados().is_empty());
}

/// PRD-02: 10 000 ofertas → ≤ 10 chamadas de `produtos` e nenhuma de `produto`; o produto
/// carregado em lote chega à página.
#[test]
fn produtos_em_lote_sem_n_mais_1() {
    let linhas: Vec<LinhaOferta> = (1..=10_000).map(linha).collect();
    let produtos = vec![worker::conversao::LinhaProduto {
        id_produto: 42,
        descricao: Some("Descrição carregada em lote.".into()),
        ..Default::default()
    }];
    let fonte = FakeFonte::new(linhas, produtos, AGORA);
    let mut p = PublicadorMemoria::new();
    let rel = gerar(
        &fonte,
        &mapeamento(),
        &mut p,
        &mut RedirectsMemoria::new(),
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        AGORA,
    )
    .unwrap();
    assert!(
        fonte.chamadas_produtos() <= 10,
        "{}",
        fonte.chamadas_produtos()
    );
    assert!(fonte.chamadas_produtos() >= 1);
    assert_eq!(fonte.chamadas_produto(), 0);
    assert_eq!(rel.site.paginas.publicadas, 10_000);
    let html = String::from_utf8(p.ler("oferta/42/index.html").unwrap().unwrap()).unwrap();
    assert!(html.contains("Descrição carregada em lote."));
}

/// PRD-04: o `--dry-run` converte para página com os produtos em lote (1 chamada, nenhuma unitária).
#[test]
fn dry_run_usa_produtos_em_lote() {
    let mut linhas = comum::linhas_fixture();
    linhas.push(LinhaOferta {
        id_produto: None,
        ..linha(7001)
    });
    let fonte = FakeFonte::new(linhas, vec![], AGORA);
    let (lidas, validas, rejeitadas) = contar_paginas(&fonte, &mapeamento()).unwrap();
    assert_eq!((lidas, validas), (4, 3));
    assert_eq!(
        rejeitadas,
        BTreeMap::from([(Rejeicao::IdProdutoAusente, 1)])
    );
    assert_eq!(fonte.chamadas_produtos(), 1);
    assert_eq!(fonte.chamadas_produto(), 0);
}
