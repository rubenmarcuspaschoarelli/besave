//! CIC-04, LOG-03, LOG-04, ALR-01..03, ALR-05 (BSV-14): ciclo com falha injetada pela fonte,
//! classificação da falha, linha de relatório e código de saída. Todos os testes capturam o
//! log (ver `tests/trava.rs`).

mod comum;

use std::cell::RefCell;
use std::collections::HashMap;
use std::io::Write;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use worker::alerta::{Alertas, ErroTelegram, Telegram};
use worker::conversao::{LinhaOferta, LinhaProduto};
use worker::execucao::{Codigo, Falha, concluir, rodar, variante_de};
use worker::fonte::{ErroFonte, FakeFonte, FonteOfertas};
use worker::geracao::{ErroGeracao, Relatorio};
use worker::publicador::{ErroPublicador, Publicador, PublicadorMemoria};
use worker::redirects::{ErroRedirects, Redirects, RedirectsMemoria};
use worker::site::ConfigSite;

/// Fonte que sempre erra (falha injetada).
struct FonteQueErra;

impl FonteOfertas for FonteQueErra {
    fn ofertas(&self) -> Result<Vec<LinhaOferta>, ErroFonte> {
        Err(ErroFonte::ConfigInvalida(
            "BESAVE_ORACLE_DSN",
            "fake".into(),
        ))
    }
    fn produto(&self, _: i64) -> Result<Option<LinhaProduto>, ErroFonte> {
        Ok(None)
    }
    fn produtos(&self, _: &[i64]) -> Result<HashMap<i64, LinhaProduto>, ErroFonte> {
        Ok(HashMap::new())
    }
}

#[derive(Default)]
struct TelegramFake {
    enviados: RefCell<Vec<String>>,
    falhar: bool,
}

impl Telegram for TelegramFake {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        if self.falhar {
            return Err(ErroTelegram::Timeout(10));
        }
        self.enviados.borrow_mut().push(texto.to_owned());
        Ok(())
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

fn com_log<T>(f: impl FnOnce() -> T) -> (T, String) {
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .with_max_level(tracing::Level::INFO)
        .finish();
    let r = tracing::subscriber::with_default(sub, f);
    let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
    (r, log)
}

fn estado(nome: &str) -> PathBuf {
    std::env::temp_dir()
        .join(format!(
            "besave-execucao-{nome}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
        .join("alerta.json")
}

/// `rodar` no destino em memória; o relatório segue com `tempo_ms`.
fn rodar_em(
    fonte: &dyn FonteOfertas,
    p: &mut PublicadorMemoria,
    agora: i64,
    tempo_ms: u64,
) -> Result<(Relatorio, u64), Falha> {
    rodar(
        fonte,
        &mapeamento(),
        p,
        &mut RedirectsMemoria::new(),
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        agora,
    )
    .map(|rel| (rel, tempo_ms))
}

/// Falha injetada → código 1, `ERROR` com fase e variante, 1 envio; mesma falha em < 2 h → 0
/// envios; sucesso seguinte → 1 envio "recuperado" e código 0.
#[test]
fn falha_injetada_alerta_uma_vez_e_recupera() {
    let t = TelegramFake::default();
    let e = estado("injetada");
    let a = Alertas::new(&t, e, "MAQUINA-1".to_owned());
    let mut p = PublicadorMemoria::new();

    let (cod, log) =
        com_log(|| concluir(rodar_em(&FonteQueErra, &mut p, AGORA, 10), Some(&a), AGORA));
    assert_eq!(cod, Codigo::Falha);
    assert_eq!(cod.valor(), 1);
    let erros: Vec<&str> = log.lines().filter(|l| l.contains("ERROR")).collect();
    assert_eq!(erros.len(), 1, "{log}");
    assert!(erros[0].contains("fase=leitura_fonte"), "{log}");
    assert!(erros[0].contains("variante=Fonte::ConfigInvalida"), "{log}");
    assert_eq!(t.enviados.borrow().len(), 1);
    assert!(t.enviados.borrow()[0].contains("fase: leitura_fonte"));

    let (cod, _) = com_log(|| {
        concluir(
            rodar_em(&FonteQueErra, &mut p, AGORA + 300, 10),
            Some(&a),
            AGORA + 300,
        )
    });
    assert_eq!(cod, Codigo::Falha);
    assert_eq!(t.enviados.borrow().len(), 1);

    let fonte = FakeFonte::new(vec![linha(1), linha(2)], vec![], AGORA + 600);
    let (cod, log) = com_log(|| {
        concluir(
            rodar_em(&fonte, &mut p, AGORA + 600, 10),
            Some(&a),
            AGORA + 600,
        )
    });
    assert_eq!(cod, Codigo::Ok);
    assert_eq!(cod.valor(), 0);
    let enviados = t.enviados.borrow();
    assert_eq!(enviados.len(), 2);
    assert!(
        enviados[1].starts_with("✅ Besave worker: recuperado após 2 falhas (desde "),
        "{}",
        enviados[1]
    );
    assert!(log.contains("relatorio "), "{log}");
}

/// LOG-03: sucesso → uma linha `relatorio` com os campos em `chave=valor`.
#[test]
fn sucesso_loga_relatorio_em_chave_valor() {
    let fonte = FakeFonte::new(vec![linha(1), linha(2), linha(3)], vec![], AGORA);
    let mut p = PublicadorMemoria::new();
    let (cod, log) = com_log(|| concluir(rodar_em(&fonte, &mut p, AGORA, 1234), None, AGORA));
    assert_eq!(cod, Codigo::Ok);
    let linhas: Vec<&str> = log.lines().filter(|l| l.contains("relatorio ")).collect();
    assert_eq!(linhas.len(), 1, "{log}");
    let l = linhas[0];
    for campo in [
        "lidas=3",
        "validas=3",
        "rejeitadas=0",
        "chunks_escritos=1",
        "redirects_put=3",
        "redirects_modo=reconstrucao",
        "paginas_publicadas=3",
        "tempo_ms=1234",
    ] {
        assert!(l.contains(campo), "{campo} ausente em {l}");
    }
    // Pares `chave=valor` separados por espaço, sem `: ` do relatório do stdout.
    let pares = l.split_once("relatorio ").unwrap().1;
    assert!(
        pares.split(' ').all(|p| p
            .split_once('=')
            .is_some_and(|(k, v)| !k.is_empty() && !v.is_empty())),
        "{pares}"
    );
}

/// ALR-05: Telegram falhando → mesmo código de saída (1) e `WARN`.
#[test]
fn telegram_falhando_nao_muda_o_codigo() {
    let t = TelegramFake {
        falhar: true,
        ..Default::default()
    };
    let a = Alertas::new(&t, estado("telegram-falho"), "MAQUINA-1".to_owned());
    let mut p = PublicadorMemoria::new();
    let (cod, log) =
        com_log(|| concluir(rodar_em(&FonteQueErra, &mut p, AGORA, 1), Some(&a), AGORA));
    assert_eq!(cod, Codigo::Falha);
    assert!(
        log.lines()
            .any(|l| l.contains("WARN") && l.contains("Telegram")),
        "{log}"
    );
    // Sucesso com o Telegram falhando também segue 0.
    let fonte = FakeFonte::new(vec![linha(1)], vec![], AGORA + 300);
    let (cod, _) = com_log(|| {
        concluir(
            rodar_em(&fonte, &mut p, AGORA + 300, 1),
            Some(&a),
            AGORA + 300,
        )
    });
    assert_eq!(cod, Codigo::Ok);
}

/// CIC-04: falha de configuração sai com 2; de execução, com 1.
#[test]
fn codigos_de_saida() {
    let (cod, _) = com_log(|| {
        concluir(
            Err(Falha::config(
                "config",
                &ErroFonte::ConfigAusente("BESAVE_ORACLE_DSN"),
            )),
            None,
            AGORA,
        )
    });
    assert_eq!(cod.valor(), 2);
    let (cod, log) = com_log(|| {
        concluir(
            Err(Falha::execucao(
                "conexao_oracle",
                &ErroFonte::ConfigInvalida("x", "y".into()),
            )),
            None,
            AGORA,
        )
    });
    assert_eq!(cod.valor(), 1);
    assert!(log.contains("fase=conexao_oracle"), "{log}");
}

/// ALR-01: fase e variante a partir do erro de `gerar()`.
#[test]
fn fase_e_variante_dos_erros_de_geracao() {
    let s3 = || ErroPublicador::Aws {
        operacao: "GetObject",
        chave: "manifest.json".into(),
        fonte: "https://loja.example/x AccessDenied".into(),
    };
    let casos = [
        (
            ErroGeracao::Fonte(ErroFonte::ConfigAusente("X")),
            "leitura_fonte",
            "Fonte::ConfigAusente",
        ),
        (
            ErroGeracao::Redirects(ErroRedirects::Kvs {
                operacao: "DescribeKeyValueStore",
                fonte: "ResourceNotFound".into(),
            }),
            "redirects",
            "Redirects::Kvs",
        ),
        (
            ErroGeracao::ChunkAcimaDoOrcamento { n: 1, bytes: 2 },
            "chunks",
            "ChunkAcimaDoOrcamento",
        ),
        (ErroGeracao::VersaoContrato, "manifest", "VersaoContrato"),
        (ErroGeracao::Publicador(s3()), "s3", "Publicador::Aws"),
        (
            ErroGeracao::Imagens(worker::imagens::ErroImagens::Publicador(s3())),
            "imagens",
            "Imagens::Publicador",
        ),
        (
            ErroGeracao::Site(worker::site::ErroSite::Publicador(s3())),
            "paginas",
            "Site::Publicador",
        ),
    ];
    for (erro, fase, variante) in casos {
        let f = Falha::de_geracao(&erro);
        assert_eq!(f.fase, fase, "{erro:?}");
        assert_eq!(f.variante, variante, "{erro:?}");
        assert_eq!(f.codigo, Codigo::Falha);
        assert!(!f.variante.contains("http"));
    }
}

/// ALR-04: a variante só tem identificadores, nunca dado do erro.
#[test]
fn variante_so_tem_identificadores() {
    let e = ErroRedirects::Concorrencia {
        etag: "e1".into(),
        fonte: r"C:\Users\ruben https://x".into(),
    };
    assert_eq!(variante_de(&e), "Concorrencia");
    assert_eq!(variante_de(&"texto solto"), "Desconhecido");
}

/// CIC-01: o ciclo é o `--publicar --sim`: escreve no destino (manifest no bucket, ids na KVS).
#[test]
fn rodar_escreve_no_destino_como_publicar_sim() {
    let fonte = FakeFonte::new(vec![linha(1), linha(2)], vec![], AGORA);
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    let (r, _) = com_log(|| {
        rodar(
            &fonte,
            &mapeamento(),
            &mut p,
            &mut kvs,
            &dir_imagens_vazio(),
            &ConfigSite::default(),
            AGORA,
        )
    });
    let rel = r.unwrap();
    assert_eq!(rel.validas, 2);
    assert!(p.ler("manifest.json").unwrap().is_some());
    assert_eq!(
        kvs.listar().unwrap().keys().copied().collect::<Vec<_>>(),
        vec![1, 2]
    );
}
