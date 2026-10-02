//! Bot API do Telegram (`sendMessage`) sobre `hyper` + `hyper-rustls`, as mesmas crates do SDK
//! AWS (BSV-14). Síncrono, com runtime `current_thread` próprio, como `aws.rs`. Nenhum erro
//! carrega a URL: ela contém o token.

use std::fmt;
use std::time::Duration;

use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper_rustls::HttpsConnector;
use hyper_util::client::legacy::Client;
use hyper_util::client::legacy::connect::HttpConnector;
use hyper_util::rt::TokioExecutor;
use tokio::runtime::Runtime;

use crate::alerta::{ConfigTelegram, ErroTelegram, Telegram};

const HOST: &str = "api.telegram.org";
const TIMEOUT: Duration = Duration::from_secs(10);

/// POST `https://api.telegram.org/bot{token}/sendMessage` com `{"chat_id", "text"}`.
pub fn pedido(cfg: &ConfigTelegram, texto: &str) -> Result<http::Request<String>, ErroTelegram> {
    let corpo = serde_json::json!({ "chat_id": cfg.chat_id, "text": texto }).to_string();
    http::Request::post(format!("https://{HOST}/bot{}/sendMessage", cfg.token()))
        .header(http::header::CONTENT_TYPE, "application/json")
        .body(corpo)
        // O texto do erro do `http` pode citar a URI.
        .map_err(|_| ErroTelegram::Conexao("pedido inválido".to_owned()))
}

pub struct TelegramHttp {
    cfg: ConfigTelegram,
    rt: Runtime,
    cliente: Client<HttpsConnector<HttpConnector>, Full<Bytes>>,
}

impl fmt::Debug for TelegramHttp {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("TelegramHttp")
            .field("cfg", &self.cfg)
            .finish_non_exhaustive()
    }
}

impl TelegramHttp {
    /// Raízes de certificado do sistema (no Windows, o repositório do usuário/máquina).
    pub fn new(cfg: ConfigTelegram) -> Result<Self, ErroTelegram> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| ErroTelegram::Conexao(format!("runtime: {e}")))?;
        let https = hyper_rustls::HttpsConnectorBuilder::new()
            .with_native_roots()
            .map_err(|e| ErroTelegram::Conexao(format!("certificados do sistema: {e}")))?
            .https_only()
            .enable_http1()
            .build();
        let cliente = Client::builder(TokioExecutor::new()).build(https);
        Ok(Self { cfg, rt, cliente })
    }

    /// Texto de erro de terceiros sem o token (defesa: hoje nenhum deles cita a URI).
    fn limpo(&self, e: impl fmt::Display) -> String {
        e.to_string().replace(self.cfg.token(), "***")
    }
}

impl Telegram for TelegramHttp {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        let req = pedido(&self.cfg, texto)?.map(|c| Full::new(Bytes::from(c)));
        self.rt.block_on(async {
            let segundos = TIMEOUT.as_secs();
            let resp = tokio::time::timeout(TIMEOUT, self.cliente.request(req))
                .await
                .map_err(|_| ErroTelegram::Timeout(segundos))?
                .map_err(|e| ErroTelegram::Conexao(self.limpo(&e)))?;
            let status = resp.status();
            let corpo = tokio::time::timeout(TIMEOUT, resp.into_body().collect())
                .await
                .map_err(|_| ErroTelegram::Timeout(segundos))?
                .map_err(|e| ErroTelegram::Conexao(self.limpo(&e)))?
                .to_bytes();
            let v: serde_json::Value = serde_json::from_slice(&corpo).unwrap_or_default();
            if status.is_success() && v["ok"] == true {
                return Ok(());
            }
            match v["description"].as_str() {
                Some(d) => Err(ErroTelegram::Recusada(format!(
                    "HTTP {}: {}",
                    status.as_u16(),
                    self.limpo(d)
                ))),
                None => Err(ErroTelegram::Http(status.as_u16())),
            }
        })
    }
}
