//! BSV-41 PAG-01..02, PAG-07..08, REM-01..06, DTP-01..02: avisos no ciclo com fakes.

mod comum;

use std::path::{Path, PathBuf};

use comum::AGORA;
use worker::avisos::modelo::LinhaAviso;
use worker::avisos::publicacao::{
    CHAVE_ESTADO_AVISOS, ConfigAvisos, IndiceAvisos, RelatorioAvisos, publicar_avisos,
};
use worker::fonte::FakeFonte;
use worker::publicador::{META_ESTADO, Publicador, PublicadorMemoria, meta_para};

const HORA: i64 = 3600;

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-avisos-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn arquivo(dir: &Path, nome: &str, bytes: &[u8]) {
    std::fs::write(dir.join(nome), bytes).unwrap();
}

fn aviso(id: i64, imagem: Option<&str>) -> LinhaAviso {
    LinhaAviso {
        id,
        titulo: format!("Aviso {id}"),
        texto: format!("Texto do aviso {id}."),
        imagem: imagem.map(str::to_owned),
        link_interno: Some("/".into()),
        ativo: true,
        dt_inicio: AGORA - 24 * HORA,
        ..Default::default()
    }
}

struct Cenario {
    fonte: FakeFonte,
    p: PublicadorMemoria,
    cfg: ConfigAvisos,
    dir: PathBuf,
}

impl Cenario {
    /// Avisos 1 (`a1.jpg`) e 2 (`a2.webp`), ativos e vigentes, imagens na pasta.
    fn novo(nome: &str) -> Self {
        let dir = dir_temp(nome);
        arquivo(&dir, "a1.jpg", b"jpg-do-aviso-1");
        arquivo(&dir, "a2.webp", b"webp-do-aviso-2");
        Self::com(
            dir,
            vec![aviso(1, Some("a1.jpg")), aviso(2, Some("a2.webp"))],
        )
    }

    fn com(dir: PathBuf, avisos: Vec<LinhaAviso>) -> Self {
        Self {
            fonte: FakeFonte::new(vec![], vec![], AGORA).com_avisos(avisos),
            p: PublicadorMemoria::new(),
            cfg: ConfigAvisos {
                dir: Some(dir.clone()),
                ..ConfigAvisos::default()
            },
            dir,
        }
    }

    fn rodar(&mut self) -> RelatorioAvisos {
        self.rodar_em(AGORA)
    }

    fn rodar_em(&mut self, agora: i64) -> RelatorioAvisos {
        publicar_avisos(&self.fonte, &mut self.p, &self.cfg, agora, true).unwrap()
    }

    fn texto(&self, chave: &str) -> String {
        String::from_utf8(self.p.ler(chave).unwrap().unwrap_or_default()).unwrap()
    }

    fn indice(&self) -> IndiceAvisos {
        serde_json::from_slice(&self.p.ler(CHAVE_ESTADO_AVISOS).unwrap().unwrap()).unwrap()
    }

    fn existe(&self, chave: &str) -> bool {
        self.p.existe(chave).unwrap()
    }

    fn alterar(&self, id: i64, f: impl FnOnce(&mut LinhaAviso)) {
        let mut v = self.fonte.avisos_atuais();
        if let Some(a) = v.iter_mut().find(|a| a.id == id) {
            f(a);
        }
        self.fonte.definir_avisos(v);
    }
}

/// PAG-01, PAG-09: 2 avisos → 2 páginas + 2 imagens + índice, com os headers da tabela.
#[test]
fn dois_avisos_publicados() {
    let mut c = Cenario::novo("dois");
    let rel = c.rodar();
    assert_eq!(rel.publicados, 2);
    assert_eq!(rel.imagens_publicadas, 2);
    assert_eq!(rel.no_ar, 2);
    for chave in [
        "avisos/1/index.html",
        "avisos/2/index.html",
        "img/avisos/1.jpg",
        "img/avisos/2.webp",
    ] {
        assert!(c.existe(chave), "{chave}");
        assert_eq!(c.p.meta(chave), meta_para(chave), "{chave}");
    }
    assert_eq!(
        c.p.ler("img/avisos/1.jpg").unwrap().unwrap(),
        b"jpg-do-aviso-1"
    );
    assert_eq!(
        c.p.ler("img/avisos/2.webp").unwrap().unwrap(),
        b"webp-do-aviso-2"
    );
    assert!(
        c.texto("avisos/1/index.html")
            .contains("src=\"/img/avisos/1.jpg\"")
    );
    assert!(
        c.texto("avisos/2/index.html")
            .contains("src=\"/img/avisos/2.webp\"")
    );
    let idx = c.indice();
    assert_eq!(idx.keys().copied().collect::<Vec<_>>(), vec![1, 2]);
    assert_eq!(idx[&1].imagem.as_deref(), Some("img/avisos/1.jpg"));
    assert_eq!(c.p.meta(CHAVE_ESTADO_AVISOS), Some(META_ESTADO));
}

/// PAG-02: segunda execução sem mudança → nenhum objeto gravado nem removido.
#[test]
fn segunda_execucao_sem_uploads() {
    let mut c = Cenario::novo("idempotente");
    c.rodar();
    let (g, r) = (c.p.gravacoes().len(), c.p.remocoes().len());
    let rel = c.rodar();
    assert_eq!(c.p.gravacoes().len(), g, "{:?}", &c.p.gravacoes()[g..]);
    assert_eq!(c.p.remocoes().len(), r, "{:?}", &c.p.remocoes()[r..]);
    assert_eq!(
        (rel.publicados, rel.imagens_publicadas, rel.removidos),
        (0, 0, 0)
    );
}

/// Imagem trocada no mesmo nome: sobe só a imagem nova e a página fica.
#[test]
fn imagem_trocada_no_mesmo_nome() {
    let mut c = Cenario::novo("troca");
    c.rodar();
    let g = c.p.gravacoes().len();
    arquivo(&c.dir, "a1.jpg", b"jpg-novo");
    let rel = c.rodar();
    assert_eq!(
        c.p.gravacoes()[g..],
        [
            "img/avisos/1.jpg".to_owned(),
            CHAVE_ESTADO_AVISOS.to_owned()
        ]
    );
    assert_eq!(rel.imagens_publicadas, 1);
    assert_eq!(c.p.ler("img/avisos/1.jpg").unwrap().unwrap(), b"jpg-novo");
}

/// REM-01, DTP-02: desativado → página e imagem removidas, fora do índice, data anulada.
#[test]
fn desativado_sai_do_ar() {
    let mut c = Cenario::novo("desativado");
    c.rodar();
    c.alterar(1, |a| a.ativo = false);
    let rel = c.rodar();
    assert_eq!(rel.removidos, 1);
    assert!(!c.existe("avisos/1/index.html"));
    assert!(!c.existe("img/avisos/1.jpg"));
    assert!(c.existe("avisos/2/index.html"));
    assert!(!c.indice().contains_key(&1));
    let datas: Vec<_> = c
        .fonte
        .avisos_atuais()
        .iter()
        .map(|a| (a.id, a.dt_publicacao_site))
        .collect();
    assert_eq!(datas, vec![(1, None), (2, Some(AGORA))]);
    assert_eq!(rel.datas_anuladas, 1);
}

/// REM-02: `DT_FIM` no passado (ou igual a agora: fim exclusivo) → removido.
#[test]
fn dt_fim_vencido_sai_do_ar() {
    let mut c = Cenario::novo("fim");
    c.rodar();
    c.alterar(1, |a| a.dt_fim = Some(AGORA - HORA));
    c.alterar(2, |a| a.dt_fim = Some(AGORA));
    let rel = c.rodar();
    assert_eq!(rel.removidos, 2);
    assert!(!c.existe("avisos/1/index.html") && !c.existe("img/avisos/1.jpg"));
    assert!(!c.existe("avisos/2/index.html") && !c.existe("img/avisos/2.webp"));
    // `DT_FIM` no futuro continua no ar.
    let mut d = Cenario::novo("fim-futuro");
    d.alterar(1, |a| a.dt_fim = Some(AGORA + 1));
    d.rodar();
    assert!(d.existe("avisos/1/index.html"));
}

/// REM-03: id do índice que sumiu do Oracle → removido.
#[test]
fn apagado_sai_do_ar() {
    let mut c = Cenario::novo("apagado");
    c.rodar();
    c.fonte.definir_avisos(vec![aviso(2, Some("a2.webp"))]);
    let rel = c.rodar();
    assert_eq!(rel.removidos, 1);
    assert!(!c.existe("avisos/1/index.html") && !c.existe("img/avisos/1.jpg"));
    assert!(c.existe("avisos/2/index.html"));
}

/// REM-04: `DT_INICIO` no futuro → não publica; no instante exato → publica.
#[test]
fn inicio_no_futuro_nao_publica() {
    let dir = dir_temp("inicio");
    let mut c = Cenario::com(
        dir,
        vec![
            LinhaAviso {
                dt_inicio: AGORA + 1,
                ..aviso(1, None)
            },
            LinhaAviso {
                dt_inicio: AGORA,
                ..aviso(2, None)
            },
        ],
    );
    c.rodar();
    assert!(!c.existe("avisos/1/index.html"));
    assert!(c.existe("avisos/2/index.html"));
    assert_eq!(c.fonte.avisos_atuais()[0].dt_publicacao_site, None);
}

/// PAG-04 (no ciclo): texto com `<script>` sai escapado na página publicada.
#[test]
fn script_escapado_na_pagina_publicada() {
    let dir = dir_temp("script");
    let mut c = Cenario::com(
        dir,
        vec![LinhaAviso {
            texto: "<script>alert(1)</script>".into(),
            ..aviso(3, None)
        }],
    );
    c.rodar();
    let h = c.texto("avisos/3/index.html");
    assert!(h.contains("&lt;script&gt;alert(1)&lt;/script&gt;"), "{h}");
    assert!(!h.contains("<script>"), "{h}");
}

/// PAG-06 (no ciclo): link externo → página sem botão, contado como inválido.
#[test]
fn link_externo_sem_botao() {
    let dir = dir_temp("link");
    let mut c = Cenario::com(
        dir,
        vec![LinhaAviso {
            link_interno: Some("https://loja.com".into()),
            ..aviso(4, None)
        }],
    );
    let rel = c.rodar();
    assert_eq!(rel.links_invalidos, 1);
    let h = c.texto("avisos/4/index.html");
    assert!(!h.contains("class=\"cta\""), "{h}");
    assert!(!h.contains("loja.com"), "{h}");
}

/// PAG-07: `.png` (ou nome com caminho) → aviso ignorado; se estava no ar, sai e a data é anulada.
#[test]
fn imagem_png_ignora_o_aviso() {
    let mut c = Cenario::novo("png");
    arquivo(&c.dir, "a1.png", b"png");
    c.rodar();
    c.alterar(1, |a| a.imagem = Some("a1.png".into()));
    c.fonte.definir_avisos(
        c.fonte
            .avisos_atuais()
            .into_iter()
            .chain([aviso(5, Some("../a1.jpg")), aviso(6, Some("x\\a1.jpg"))])
            .collect(),
    );
    let rel = c.rodar();
    assert_eq!(rel.ignorados, 3);
    assert_eq!(rel.removidos, 1);
    for chave in [
        "avisos/1/index.html",
        "img/avisos/1.jpg",
        "img/avisos/1.png",
        "avisos/5/index.html",
        "avisos/6/index.html",
    ] {
        assert!(!c.existe(chave), "{chave}");
    }
    assert!(c.existe("avisos/2/index.html"));
    let a1 = c
        .fonte
        .avisos_atuais()
        .into_iter()
        .find(|a| a.id == 1)
        .unwrap();
    assert_eq!(a1.dt_publicacao_site, None);
}

/// Extensão em maiúsculas é aceita.
#[test]
fn extensao_em_maiusculas() {
    let dir = dir_temp("maiusculas");
    arquivo(&dir, "A.JPG", b"x");
    let mut c = Cenario::com(dir, vec![aviso(7, Some("A.JPG"))]);
    c.rodar();
    assert!(c.existe("img/avisos/7.jpg"));
}

/// PAG-08: imagem acima de 1 MB, ausente ou sem pasta → página sem imagem; exatamente 1 MB → com.
#[test]
fn imagem_grande_ou_ausente_pagina_sem_imagem() {
    let dir = dir_temp("grande");
    arquivo(&dir, "grande.jpg", &vec![0u8; 1_048_577]);
    arquivo(&dir, "limite.jpg", &vec![0u8; 1_048_576]);
    let mut c = Cenario::com(
        dir,
        vec![
            aviso(1, Some("grande.jpg")),
            aviso(2, Some("limite.jpg")),
            aviso(3, Some("nao-existe.webp")),
        ],
    );
    let rel = c.rodar();
    assert_eq!(rel.sem_imagem, 2);
    assert!(c.existe("avisos/1/index.html") && !c.existe("img/avisos/1.jpg"));
    assert!(!c.texto("avisos/1/index.html").contains("<img"));
    assert!(c.existe("img/avisos/2.jpg"));
    assert!(
        c.texto("avisos/2/index.html")
            .contains("src=\"/img/avisos/2.jpg\"")
    );
    assert!(c.existe("avisos/3/index.html") && !c.existe("img/avisos/3.webp"));
    assert!(!c.texto("avisos/3/index.html").contains("<img"));

    let mut sem_pasta = Cenario::novo("sem-pasta");
    sem_pasta.cfg.dir = None;
    let rel = sem_pasta.rodar();
    assert_eq!(rel.sem_imagem, 2);
    assert!(sem_pasta.existe("avisos/1/index.html"));
    assert!(!sem_pasta.existe("img/avisos/1.jpg"));
}

/// REM-06: extensão trocada → chave antiga removida; imagem retirada → chave removida.
#[test]
fn chave_antiga_da_imagem_removida() {
    let mut c = Cenario::novo("extensao");
    c.rodar();
    arquivo(&c.dir, "a1.webp", b"agora-webp");
    c.alterar(1, |a| a.imagem = Some("a1.webp".into()));
    c.alterar(2, |a| a.imagem = None);
    c.rodar();
    assert!(!c.existe("img/avisos/1.jpg"));
    assert!(c.existe("img/avisos/1.webp"));
    assert!(
        c.texto("avisos/1/index.html")
            .contains("src=\"/img/avisos/1.webp\"")
    );
    assert!(!c.existe("img/avisos/2.webp"));
    assert!(c.existe("avisos/2/index.html"));
    assert!(!c.texto("avisos/2/index.html").contains("<img"));
}

/// REM-05: sem índice (ou ilegível), o que está no bucket e saiu do conjunto é removido.
#[test]
fn indice_ausente_ou_ilegivel_reconstroi_pelo_bucket() {
    for ilegivel in [false, true] {
        let mut c = Cenario::novo("reconstrucao");
        let meta = meta_para("img/avisos/9.jpg").unwrap();
        c.p.gravar("img/avisos/9.jpg", b"velha", &meta).unwrap();
        c.p.gravar(
            "avisos/9/index.html",
            b"velha",
            &meta_para("avisos/9/index.html").unwrap(),
        )
        .unwrap();
        c.p.gravar(
            "img/avisos/8.webp",
            b"so-imagem",
            &meta_para("img/avisos/8.webp").unwrap(),
        )
        .unwrap();
        if ilegivel {
            c.p.gravar(CHAVE_ESTADO_AVISOS, b"{nao json", &META_ESTADO)
                .unwrap();
        }
        let rel = c.rodar();
        assert_eq!(rel.removidos, 2, "ilegivel={ilegivel}");
        assert!(!c.existe("avisos/9/index.html"));
        assert!(!c.existe("img/avisos/9.jpg"));
        assert!(!c.existe("img/avisos/8.webp"));
        assert!(c.existe("avisos/1/index.html") && c.existe("img/avisos/1.jpg"));
        assert_eq!(c.indice().keys().copied().collect::<Vec<_>>(), vec![1, 2]);
    }
}

/// DTP-01: página no ar → data gravada uma vez; não regrava nas execuções seguintes.
#[test]
fn data_de_publicacao_gravada_uma_vez() {
    let mut c = Cenario::novo("data");
    let rel = c.rodar();
    assert_eq!(rel.datas_gravadas, 2);
    assert!(
        c.fonte
            .avisos_atuais()
            .iter()
            .all(|a| a.dt_publicacao_site == Some(AGORA))
    );
    let rel = c.rodar_em(AGORA + 600);
    assert_eq!((rel.datas_gravadas, rel.datas_anuladas), (0, 0));
}

/// DTP-03 (unidade): `marcar = false` não toca as datas.
#[test]
fn sem_marcar_nao_toca_as_datas() {
    let mut c = Cenario::novo("sem-marcar");
    publicar_avisos(&c.fonte, &mut c.p, &c.cfg, AGORA, false).unwrap();
    assert!(c.existe("avisos/1/index.html"));
    assert!(
        c.fonte
            .avisos_atuais()
            .iter()
            .all(|a| a.dt_publicacao_site.is_none())
    );
}

/// Falha do Oracle na leitura → erro, nada gravado.
#[test]
fn falha_do_oracle_e_erro() {
    let fonte = FakeFonte::new(vec![], vec![], AGORA)
        .com_avisos(vec![aviso(1, None)])
        .com_falha_avisos();
    let mut p = PublicadorMemoria::new();
    let r = publicar_avisos(&fonte, &mut p, &ConfigAvisos::default(), AGORA, true);
    assert!(r.is_err());
    assert!(p.gravacoes().is_empty());
}
