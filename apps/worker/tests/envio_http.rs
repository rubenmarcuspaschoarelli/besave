//! BSV-40: pedidos à Bot API (sem rede), leitura das respostas (429), token fora do `Debug`, `--sim`
//! (BIN-03) e argumentos do binário.

mod comum;

use std::ffi::OsString;
use std::path::PathBuf;

use comum::{AGORA, linha_canal, mapeamento};
use worker::envio::binario::{Argumentos, argumentos, texto_simulacao};
use worker::envio::canal::{ErroCanal, FakeCanal, RelogioFake};
use worker::envio::fonte::FakeEnvio;
use worker::envio::foto::foto;
use worker::envio::http::{ConfigCanal, interpretar, multipart, pedido_edicao, pedido_foto};
use worker::envio::modelo::Parametros;
use worker::envio::rodada::{Contexto, simular};

const TOKEN: &str = "123456:segredo";

fn cfg() -> ConfigCanal {
    ConfigCanal::de(|k| (k == "TELEGRAM_CANAL_BOT_TOKEN").then(|| format!(" {TOKEN} "))).unwrap()
}

#[test]
fn token_obrigatorio_e_fora_do_debug() {
    assert!(ConfigCanal::de(|_| None).is_err());
    assert!(ConfigCanal::de(|_| Some("  ".into())).is_err());
    let c = cfg();
    assert_eq!(c.token(), TOKEN);
    let d = format!("{c:?}");
    assert!(!d.contains("segredo"), "{d}");
}

/// `sendPhoto` multipart com chat, legenda HTML, silêncio e a foto.
#[test]
fn pedido_de_foto() {
    let jpeg = [0xFF, 0xD8, 0x01, 0x02];
    let r = pedido_foto(&cfg(), "@besaveofertas", &jpeg, "<b>Oi</b>\nlinha", true).unwrap();
    assert_eq!(r.method(), http::Method::POST);
    assert_eq!(
        r.uri().to_string(),
        format!("https://api.telegram.org/bot{TOKEN}/sendPhoto")
    );
    let ct = r.headers()[http::header::CONTENT_TYPE].to_str().unwrap();
    let fronteira = ct.strip_prefix("multipart/form-data; boundary=").unwrap();
    let corpo = r.body();
    let texto = String::from_utf8_lossy(corpo);
    for (nome, valor) in [
        ("chat_id", "@besaveofertas"),
        ("caption", "<b>Oi</b>\nlinha"),
        ("parse_mode", "HTML"),
        ("disable_notification", "true"),
    ] {
        let parte = format!(
            "--{fronteira}\r\nContent-Disposition: form-data; name=\"{nome}\"\r\n\r\n{valor}\r\n"
        );
        assert!(texto.contains(&parte), "{nome}: {texto}");
    }
    assert!(texto.contains("name=\"photo\"; filename=\"foto.jpg\"\r\nContent-Type: image/jpeg"));
    assert!(corpo.windows(4).any(|w| w == jpeg));
    assert!(texto.ends_with(&format!("\r\n--{fronteira}--\r\n")));
    let r = pedido_foto(&cfg(), "x", &jpeg, "y", false).unwrap();
    assert!(String::from_utf8_lossy(r.body()).contains("disable_notification\"\r\n\r\nfalse"));
}

#[test]
fn multipart_sem_campos_so_com_foto() {
    let b = multipart(&[], b"JPG");
    let t = String::from_utf8_lossy(&b);
    assert_eq!(t.matches("Content-Disposition").count(), 1);
}

#[test]
fn pedido_de_edicao() {
    let r = pedido_edicao(&cfg(), "@c", 42, "⛔ <b>Oferta encerrada</b>").unwrap();
    assert_eq!(
        r.uri().to_string(),
        format!("https://api.telegram.org/bot{TOKEN}/editMessageCaption")
    );
    let v: serde_json::Value = serde_json::from_slice(r.body()).unwrap();
    assert_eq!(v["chat_id"], "@c");
    assert_eq!(v["message_id"], 42);
    assert_eq!(v["caption"], "⛔ <b>Oferta encerrada</b>");
    assert_eq!(v["parse_mode"], "HTML");
}

/// LIM-01 na leitura da resposta: 429 → `Limite(retry_after)`.
#[test]
fn respostas_da_bot_api() {
    let ok = interpretar(200, br#"{"ok":true,"result":{"message_id":77}}"#).unwrap();
    assert_eq!(ok["message_id"], 77);
    assert_eq!(
        interpretar(
            429,
            br#"{"ok":false,"error_code":429,"description":"Too Many Requests: retry after 31","parameters":{"retry_after":31}}"#
        ),
        Err(ErroCanal::Limite(31))
    );
    assert_eq!(
        interpretar(
            400,
            br#"{"ok":false,"error_code":400,"description":"Bad Request: x"}"#
        ),
        Err(ErroCanal::Recusada {
            status: 400,
            descricao: "Bad Request: x".into()
        })
    );
    assert_eq!(interpretar(502, b"<html>"), Err(ErroCanal::Http(502)));
    assert!(interpretar(200, br#"{"ok":false}"#).is_err());
}

/// BIN-03: `--sim` não chama o Telegram nem grava no Oracle; mostra as próximas candidatas mesmo
/// fora da janela, com legenda e foto.
#[test]
fn simulacao_so_le() {
    let f = FakeEnvio::new(
        Parametros::default(),
        (1..=5)
            .map(|id| linha_canal(id, Some(200.0), 100.0))
            .collect(),
    );
    // 23:40 em Brasília: fora da janela.
    let r = RelogioFake::em(AGORA + 14 * 3600);
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    let ctx = Contexto {
        fonte: &f,
        telegram: &tg,
        relogio: &r,
        m: &m,
        dir_imagens: None,
        foto,
        canal: 1,
        pausa_ate: None,
    };
    let antes = f.envios();
    let sim = simular(&ctx).unwrap();
    assert!(tg.chamadas().is_empty());
    assert_eq!(f.envios(), antes);
    assert_eq!(sim.devido, 0);
    assert_eq!(sim.previas.len(), 2);
    assert!(sim.previas[0].legenda.contains("besave.io/"));
    assert_eq!(&sim.previas[0].jpeg[..2], &[0xFF, 0xD8]);
    let fotos = vec![PathBuf::from("a.jpg"), PathBuf::from("b.jpg")];
    let t = texto_simulacao(&sim, &fotos);
    assert!(t.contains("lote devido agora: 0"), "{t}");
    assert!(t.contains(&sim.previas[1].legenda), "{t}");
    assert!(t.contains("a.jpg") && t.contains("b.jpg"), "{t}");
}

#[test]
fn argumentos_do_binario() {
    let a = |v: &[&str]| argumentos(&v.iter().map(OsString::from).collect::<Vec<_>>());
    assert_eq!(a(&[]).unwrap(), Argumentos::default());
    assert_eq!(
        a(&["--sim", "--env-file", "x.env"]).unwrap(),
        Argumentos {
            sim: true,
            env_file: Some(PathBuf::from("x.env"))
        }
    );
    assert_eq!(
        a(&["--env-file=y.env", "--sim"]).unwrap().env_file,
        Some(PathBuf::from("y.env"))
    );
    assert!(a(&["--ciclo"]).is_err());
}
