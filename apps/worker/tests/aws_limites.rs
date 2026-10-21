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
