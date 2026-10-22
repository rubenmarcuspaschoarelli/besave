//! LIM-01..: limites de tempo das chamadas AWS e falha clara sem credenciais (BSV-47).
//! Um servidor local aceita a conexão e nunca responde: a chamada tem de falhar dentro do limite.

use std::net::TcpListener;
use std::time::{Duration, Instant};

use aws_config::SdkConfig;
use aws_sdk_s3::config::{Credentials, SharedCredentialsProvider};
use worker::aws::{ContextoAws, ErroAws, LimitesTempo, PublicadorS3, exigir_credenciais};
use worker::publicador::Publicador;

/// Aceita conexões e as segura abertas, sem ler nem responder, até o fim do teste.
fn servidor_mudo() -> (
    String,
    std::thread::JoinHandle<()>,
    std::sync::mpsc::Sender<()>,
) {
    let l = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}", l.local_addr().unwrap());
    l.set_nonblocking(true).unwrap();
    let (fim, recebe) = std::sync::mpsc::channel::<()>();
    let t = std::thread::spawn(move || {
        let mut presas = Vec::new();
        while recebe.try_recv().is_err() {
            if let Ok((s, _)) = l.accept() {
                presas.push(s);
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    });
    (url, t, fim)
}

fn rt() -> tokio::runtime::Runtime {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap()
}

fn limites_curtos() -> LimitesTempo {
    LimitesTempo {
        conexao: Duration::from_secs(1),
        leitura: Duration::from_secs(1),
        tentativa: Duration::from_secs(1),
        operacao: Duration::from_secs(2),
    }
}

/// LIM-01: servidor que aceita e não responde → erro dentro do limite, com a operação e a chave.
#[test]
fn servidor_mudo_vira_erro_dentro_do_limite_de_operacao() {
    let (url, t, fim) = servidor_mudo();
    let ctx = ContextoAws::com_endpoint(&url, &limites_curtos()).unwrap();
    let p = PublicadorS3::new(&ctx, "bucket-de-ensaio");
    let inicio = Instant::now();
    let erro = p.existe("oferta/1/index.html").unwrap_err().to_string();
    let gasto = inicio.elapsed();
    fim.send(()).unwrap();
    t.join().unwrap();
    assert!(gasto < Duration::from_secs(6), "levou {gasto:?}: {erro}");
    assert!(erro.contains("HeadObject"), "{erro}");
    assert!(erro.contains("oferta/1/index.html"), "{erro}");
}

/// LIM-02: o mesmo vale para a escrita e a remoção em lote.
#[test]
fn escrita_e_remocao_em_lote_tambem_respeitam_o_limite() {
    let (url, t, fim) = servidor_mudo();
    let ctx = ContextoAws::com_endpoint(&url, &limites_curtos()).unwrap();
    let mut p = PublicadorS3::new(&ctx, "bucket-de-ensaio");
    let chaves = vec![
        "oferta/1/index.html".to_owned(),
        "img/ofertas/1.webp".to_owned(),
    ];
    let inicio = Instant::now();
    let erro = p.remover_lote(&chaves).unwrap_err().to_string();
    let gasto = inicio.elapsed();
    fim.send(()).unwrap();
    t.join().unwrap();
    assert!(gasto < Duration::from_secs(6), "levou {gasto:?}: {erro}");
    assert!(erro.contains("DeleteObjects"), "{erro}");
    assert!(erro.contains("oferta/1/index.html"), "{erro}");
}

/// LIM-03: configuração conferida inteira.
#[test]
fn limites_padrao_e_timeout_config_completos() {
    let l = LimitesTempo::default();
    assert_eq!(
        (l.conexao, l.leitura, l.tentativa, l.operacao),
        (
            Duration::from_secs(10),
            Duration::from_secs(30),
            Duration::from_secs(60),
            Duration::from_secs(180)
        )
    );
    let c = l.timeout_config();
    assert_eq!(c.connect_timeout(), Some(l.conexao));
    assert_eq!(c.read_timeout(), Some(l.leitura));
    assert_eq!(c.operation_attempt_timeout(), Some(l.tentativa));
    assert_eq!(c.operation_timeout(), Some(l.operacao));
    // Tentativa dentro da operação, e conexão dentro da tentativa.
    assert!(l.conexao < l.tentativa && l.tentativa < l.operacao);
}

/// CRED-01: sem provedor de credenciais, a falha é clara e imediata (nada de perguntar ao
/// serviço de metadados de instância).
#[test]
fn sem_credenciais_a_falha_diz_credenciais_aws_ausentes() {
    let sdk = SdkConfig::builder().build();
    let inicio = Instant::now();
    let erro = rt()
        .block_on(exigir_credenciais(&sdk, Duration::from_secs(5)))
        .unwrap_err();
    assert!(matches!(erro, ErroAws::CredenciaisAusentes), "{erro:?}");
    assert!(
        erro.to_string().contains("credenciais AWS ausentes"),
        "{erro}"
    );
    assert!(inicio.elapsed() < Duration::from_secs(1));
}

/// CRED-02: com credenciais (as do `.env`) a verificação passa.
#[test]
fn com_credenciais_a_verificacao_passa() {
    let sdk = SdkConfig::builder()
        .credentials_provider(SharedCredentialsProvider::new(Credentials::new(
            "id", "segredo", None, None, "teste",
        )))
        .build();
    rt().block_on(exigir_credenciais(&sdk, Duration::from_secs(5)))
        .unwrap();
}

// ---- M44/M45: a carga aplica os limites e exige credenciais ----

/// M44: a configuração que `ContextoAws::carregar` usa já traz os limites padrão.
#[test]
fn config_padrao_do_carregar_traz_os_limites_de_tempo() {
    let sdk = rt().block_on(
        worker::aws::config_padrao()
            .region(aws_config::Region::new("us-east-1"))
            .credentials_provider(Credentials::new("id", "s", None, None, "teste"))
            .load(),
    );
    let c = sdk.timeout_config().expect("sem TimeoutConfig");
    let esperado = LimitesTempo::default();
    assert_eq!(c.connect_timeout(), Some(esperado.conexao));
    assert_eq!(c.read_timeout(), Some(esperado.leitura));
    assert_eq!(c.operation_attempt_timeout(), Some(esperado.tentativa));
    assert_eq!(c.operation_timeout(), Some(esperado.operacao));
}

/// M45: a carga do contexto falha por região ausente e por credenciais ausentes.
#[test]
fn contexto_sem_regiao_ou_sem_credenciais_nao_carrega() {
    let sem_credenciais = SdkConfig::builder()
        .region(aws_config::Region::new("us-east-1"))
        .build();
    assert!(matches!(
        ContextoAws::com_sdk(sem_credenciais),
        Err(ErroAws::CredenciaisAusentes)
    ));
    let sem_regiao = SdkConfig::builder()
        .credentials_provider(SharedCredentialsProvider::new(Credentials::new(
            "id", "s", None, None, "teste",
        )))
        .build();
    assert!(matches!(
        ContextoAws::com_sdk(sem_regiao),
        Err(ErroAws::RegiaoAusente)
    ));
    let completo = SdkConfig::builder()
        .region(aws_config::Region::new("us-east-1"))
        .credentials_provider(SharedCredentialsProvider::new(Credentials::new(
            "id", "s", None, None, "teste",
        )))
        .build();
    assert!(ContextoAws::com_sdk(completo).is_ok());
}

// ---- M46: DeleteObjects com falha parcial ----

/// Servidor que responde 200 a qualquer requisição com o corpo `xml` (como o S3 faz no
/// `DeleteObjects` com `Errors`), depois de ler a requisição.
fn servidor_s3_com_corpo(xml: &'static str) -> (String, std::thread::JoinHandle<()>) {
    use std::io::{Read, Write};
    let l = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}", l.local_addr().unwrap());
    let t = std::thread::spawn(move || {
        let (mut s, _) = l.accept().unwrap();
        s.set_read_timeout(Some(Duration::from_millis(400)))
            .unwrap();
        let mut buf = [0u8; 8192];
        while let Ok(n) = s.read(&mut buf) {
            if n == 0 {
                break;
            }
        }
        let resposta = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/xml\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{xml}",
            xml.len()
        );
        s.write_all(resposta.as_bytes()).unwrap();
    });
    (url, t)
}

const DELETE_RESULT_PARCIAL: &str = r#"<?xml version="1.0" encoding="UTF-8"?><DeleteResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Error><Key>oferta/2/index.html</Key><Code>AccessDenied</Code><Message>Access Denied</Message></Error><Error><Key>img/ofertas/3-small.webp</Key><Code>InternalError</Code><Message>We encountered an internal error</Message></Error></DeleteResult>"#;

#[derive(Clone, Default)]
struct Buffer(std::sync::Arc<std::sync::Mutex<Vec<u8>>>);

impl std::io::Write for Buffer {
    fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(b);
        Ok(b.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

/// M46: o S3 responde 200 com `Errors` → erro do lote com a contagem e as chaves com falha, e as
/// chaves aparecem no log (WARN). O expurgo as mantém na fila porque `remover_lote` devolve erro.
#[test]
fn delete_objects_com_erros_parciais_vira_erro_com_as_chaves_e_vai_ao_log() {
    let (url, t) = servidor_s3_com_corpo(DELETE_RESULT_PARCIAL);
    let ctx = ContextoAws::com_endpoint(&url, &LimitesTempo::default()).unwrap();
    let mut p = PublicadorS3::new(&ctx, "bucket-de-ensaio");
    let chaves = vec![
        "oferta/1/index.html".to_owned(),
        "oferta/2/index.html".to_owned(),
        "img/ofertas/3-small.webp".to_owned(),
    ];
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .with_max_level(tracing::Level::WARN)
        .finish();
    let erro = tracing::subscriber::with_default(sub, || p.remover_lote(&chaves))
        .expect_err("falha parcial do S3 tem de ser erro")
        .to_string();
    t.join().unwrap();
    assert!(erro.contains("DeleteObjects"), "{erro}");
    assert!(erro.contains("2 erro(s) no lote"), "{erro}");
    assert!(erro.contains("oferta/2/index.html"), "{erro}");
    assert!(erro.contains("img/ofertas/3-small.webp"), "{erro}");
    assert!(!erro.contains("oferta/1/index.html"), "{erro}");
    let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
    assert!(log.contains("oferta/2/index.html"), "{log}");
    assert!(log.contains("img/ofertas/3-small.webp"), "{log}");
}

/// Lote sem `Errors` (resposta vazia do modo quieto) é sucesso.
#[test]
fn delete_objects_sem_erros_e_sucesso() {
    let (url, t) = servidor_s3_com_corpo(
        r#"<?xml version="1.0" encoding="UTF-8"?><DeleteResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"></DeleteResult>"#,
    );
    let ctx = ContextoAws::com_endpoint(&url, &LimitesTempo::default()).unwrap();
    let mut p = PublicadorS3::new(&ctx, "bucket-de-ensaio");
    p.remover_lote(&["oferta/1/index.html".to_owned()]).unwrap();
    t.join().unwrap();
}
