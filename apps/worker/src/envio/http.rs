//! Bot do canal na Bot API (`sendPhoto` multipart, `editMessageCaption`) sobre o mesmo `hyper`
//! do alerta (BSV-14). Nenhum erro, log ou `Debug` carrega o token.

use std::fmt;
use std::time::Duration;

use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use tokio::runtime::Runtime;

use crate::envio::canal::{CanalTelegram, ErroCanal};
use crate::telegram::{ClienteHttps, HOST, cliente_https};

/// Upload de foto: mais folga que o alerta.
const TIMEOUT: Duration = Duration::from_secs(30);
const VAR_TOKEN: &str = "TELEGRAM_CANAL_BOT_TOKEN";
const FRONTEIRA: &str = "besave-envio-7d3f9a2c1e";

#[derive(Debug, thiserror::Error)]
#[error("{VAR_TOKEN} ausente: o envio ao canal usa um bot próprio (≠ bot de alertas)")]
pub struct ErroConfigCanal;

/// `TELEGRAM_CANAL_BOT_TOKEN`. `Debug` manual: o token nunca aparece.
#[derive(Clone)]
pub struct ConfigCanal {
    token: String,
}

impl fmt::Debug for ConfigCanal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ConfigCanal")
            .field("token", &"***")
            .finish()
    }
}

impl ConfigCanal {
    pub fn do_env() -> Result<Self, ErroConfigCanal> {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroConfigCanal> {
        env(VAR_TOKEN)
            .map(|v| v.trim().to_owned())
            .filter(|v| !v.is_empty())
            .map(|token| Self { token })
            .ok_or(ErroConfigCanal)
    }

    pub fn token(&self) -> &str {
        &self.token
    }
}

/// Corpo `multipart/form-data` com campos de texto e a foto (`photo`, `foto.jpg`).
pub fn multipart(campos: &[(&str, &str)], jpeg: &[u8]) -> Vec<u8> {
    let mut b = Vec::with_capacity(jpeg.len() + 1024);
    for (nome, valor) in campos {
        b.extend_from_slice(
            format!(
                "--{FRONTEIRA}\r\nContent-Disposition: form-data; name=\"{nome}\"\r\n\r\n{valor}\r\n"
            )
            .as_bytes(),
        );
    }
    b.extend_from_slice(
        format!(
            "--{FRONTEIRA}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"foto.jpg\"\r\n\
             Content-Type: image/jpeg\r\n\r\n"
        )
        .as_bytes(),
    );
    b.extend_from_slice(jpeg);
    b.extend_from_slice(format!("\r\n--{FRONTEIRA}--\r\n").as_bytes());
    b
}

fn erro_pedido() -> ErroCanal {
    // O texto do erro do `http` pode citar a URI (com o token).
    ErroCanal::Conexao("pedido inválido".to_owned())
}

/// POST `.../sendPhoto` multipart com `parse_mode=HTML`.
pub fn pedido_foto(
    cfg: &ConfigCanal,
    chat_id: &str,
    jpeg: &[u8],
    legenda: &str,
    silencioso: bool,
) -> Result<http::Request<Vec<u8>>, ErroCanal> {
    let corpo = multipart(
        &[
            ("chat_id", chat_id),
            ("caption", legenda),
            ("parse_mode", "HTML"),
            (
                "disable_notification",
                if silencioso { "true" } else { "false" },
            ),
        ],
        jpeg,
    );
    http::Request::post(format!("https://{HOST}/bot{}/sendPhoto", cfg.token()))
        .header(
            http::header::CONTENT_TYPE,
            format!("multipart/form-data; boundary={FRONTEIRA}"),
        )
        .body(corpo)
        .map_err(|_| erro_pedido())
}

/// POST `.../editMessageCaption` (JSON) com `parse_mode=HTML`.
pub fn pedido_edicao(
    cfg: &ConfigCanal,
    chat_id: &str,
    message_id: i64,
    legenda: &str,
) -> Result<http::Request<Vec<u8>>, ErroCanal> {
    let corpo = serde_json::json!({
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": legenda,
        "parse_mode": "HTML",
    })
    .to_string();
    http::Request::post(format!(
        "https://{HOST}/bot{}/editMessageCaption",
        cfg.token()
    ))
    .header(http::header::CONTENT_TYPE, "application/json")
    .body(corpo.into_bytes())
    .map_err(|_| erro_pedido())
}

/// Resposta da Bot API → `result` ou o erro: 429 → `Limite(retry_after)`; com `description` →
/// `Recusada`; senão `Http`.
pub fn interpretar(status: u16, corpo: &[u8]) -> Result<serde_json::Value, ErroCanal> {
    let v: serde_json::Value = serde_json::from_slice(corpo).unwrap_or_default();
    if (200..300).contains(&status) && v["ok"] == true {
        return Ok(v["result"].clone());
    }
    if status == 429 || v["error_code"] == 429 {
        let s = v["parameters"]["retry_after"].as_u64().unwrap_or(60);
        return Err(ErroCanal::Limite(s));
    }
    match v["description"].as_str() {
        Some(d) => Err(ErroCanal::Recusada {
            status,
            descricao: d.to_owned(),
        }),
        None => Err(ErroCanal::Http(status)),
    }
}

pub struct CanalTelegramHttp {
    cfg: ConfigCanal,
    rt: Runtime,
    cliente: ClienteHttps,
}

impl fmt::Debug for CanalTelegramHttp {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CanalTelegramHttp")
            .field("cfg", &self.cfg)
            .finish_non_exhaustive()
    }
}

impl CanalTelegramHttp {
    pub fn new(cfg: ConfigCanal) -> Result<Self, ErroCanal> {
        let (rt, cliente) = cliente_https().map_err(ErroCanal::Conexao)?;
        Ok(Self { cfg, rt, cliente })
    }

    fn limpo(&self, e: impl fmt::Display) -> String {
        e.to_string().replace(self.cfg.token(), "***")
    }

    fn chamar(&self, req: http::Request<Vec<u8>>) -> Result<serde_json::Value, ErroCanal> {
        let req = req.map(|c| Full::new(Bytes::from(c)));
        self.rt.block_on(async {
            let segundos = TIMEOUT.as_secs();
            let resp = tokio::time::timeout(TIMEOUT, self.cliente.request(req))
                .await
                .map_err(|_| ErroCanal::Timeout(segundos))?
                .map_err(|e| ErroCanal::Conexao(self.limpo(&e)))?;
            let status = resp.status().as_u16();
            let corpo = tokio::time::timeout(TIMEOUT, resp.into_body().collect())
                .await
                .map_err(|_| ErroCanal::Timeout(segundos))?
                .map_err(|e| ErroCanal::Conexao(self.limpo(&e)))?
                .to_bytes();
            interpretar(status, &corpo).map_err(|e| match e {
                ErroCanal::Recusada { status, descricao } => ErroCanal::Recusada {
                    status,
                    descricao: self.limpo(descricao),
                },
                outro => outro,
            })
        })
    }
}

impl CanalTelegram for CanalTelegramHttp {
    fn enviar_foto(
        &self,
        chat_id: &str,
        jpeg: &[u8],
        legenda: &str,
        silencioso: bool,
    ) -> Result<i64, ErroCanal> {
        let r = self.chamar(pedido_foto(&self.cfg, chat_id, jpeg, legenda, silencioso)?)?;
        r["message_id"]
            .as_i64()
            .ok_or_else(|| ErroCanal::Conexao("resposta sem message_id".to_owned()))
    }

    fn editar_legenda(
        &self,
        chat_id: &str,
        message_id: i64,
        legenda: &str,
    ) -> Result<(), ErroCanal> {
        self.chamar(pedido_edicao(&self.cfg, chat_id, message_id, legenda)?)
            .map(|_| ())
    }
}
