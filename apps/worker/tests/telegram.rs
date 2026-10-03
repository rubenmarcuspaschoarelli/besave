//! ALR-04, ALR-07 no cliente real (BSV-14): montagem do pedido `sendMessage` e `Debug` sem
//! token. Sem rede: nenhum teste chama `enviar`.

use worker::alerta::ConfigTelegram;
use worker::telegram::{TelegramHttp, pedido};

const TOKEN: &str = "123456:ABCdefGHIjkl";

fn cfg() -> ConfigTelegram {
    ConfigTelegram::de(|k| match k {
        "TELEGRAM_BOT_TOKEN" => Some(TOKEN.to_owned()),
        "TELEGRAM_CHAT_ID" => Some("-100123".to_owned()),
        _ => None,
    })
    .unwrap()
    .unwrap()
}

/// Bot API: POST `https://api.telegram.org/bot{token}/sendMessage`, JSON com `chat_id` e `text`.
#[test]
fn pedido_send_message() {
    let r = pedido(&cfg(), "⚠️ Besave worker: falha no ciclo").unwrap();
    assert_eq!(r.method(), http::Method::POST);
    assert_eq!(
        r.uri().to_string(),
        format!("https://api.telegram.org/bot{TOKEN}/sendMessage")
    );
    assert_eq!(r.headers()["content-type"], "application/json");
    let corpo: serde_json::Value = serde_json::from_str(r.body()).unwrap();
    assert_eq!(
        corpo,
        serde_json::json!({ "chat_id": "-100123", "text": "⚠️ Besave worker: falha no ciclo" })
    );
}

/// ALR-07: `Debug` do cliente não mostra o token.
#[test]
fn debug_do_cliente_nao_mostra_o_token() {
    let c = TelegramHttp::new(cfg()).unwrap();
    let d = format!("{c:?}");
    assert!(!d.contains(TOKEN), "{d}");
    assert!(d.contains("-100123"), "{d}");
}
