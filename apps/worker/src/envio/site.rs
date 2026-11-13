//! Imagens do envio pelo site (BSV-61): com `BESAVE_IMAGENS_URL` / `BESAVE_AVISOS_URL` a foto vem
//! por HTTPS da CDN do site, e a pasta local não é lida. Sem URL, a pasta; sem as duas, nada.

use std::fmt;
use std::path::Path;
use std::time::Duration;

use bytes::Bytes;
use http_body_util::{BodyExt, Full, LengthLimitError, Limited};
use tokio::runtime::Runtime;

use crate::telegram::{ClienteHttps, cliente_https};

/// Maior corpo aceito (inclusive).
pub const MAX_BYTES: usize = 5 * 1024 * 1024;
/// Pedido + corpo.
pub const TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ErroBaixa {
    #[error("status {0}")]
    Status(u16),
    #[error("timeout de {0} s")]
    Timeout(u64),
    #[error("corpo maior que {MAX_BYTES} bytes")]
    Grande,
    #[error("conexão: {0}")]
    Conexao(String),
}

/// `GET url` → `(status, corpo)`. O cliente real para de ler acima de `MAX_BYTES`.
pub trait BaixarHttps {
    fn baixar(&self, url: &str) -> Result<(u16, Vec<u8>), ErroBaixa>;
}

/// Leitura de arquivo local (a pasta do espelho ou dos avisos).
pub trait LerDisco {
    fn ler(&self, caminho: &Path) -> std::io::Result<Vec<u8>>;
}

pub struct Disco;

impl LerDisco for Disco {
    fn ler(&self, caminho: &Path) -> std::io::Result<Vec<u8>> {
        std::fs::read(caminho)
    }
}

/// Sem cliente HTTPS: toda busca falha (a foto cai no placeholder / aviso sem foto).
pub struct SemHttp;

impl BaixarHttps for SemHttp {
    fn baixar(&self, _: &str) -> Result<(u16, Vec<u8>), ErroBaixa> {
        Err(ErroBaixa::Conexao("cliente HTTPS indisponível".to_owned()))
    }
}

/// De onde vêm as imagens de um tipo (ofertas ou avisos). `url` vence `dir`.
#[derive(Clone, Copy)]
pub struct Imagens<'a> {
    pub url: Option<&'a str>,
    pub dir: Option<&'a Path>,
    pub http: &'a dyn BaixarHttps,
    pub disco: &'a dyn LerDisco,
}

impl fmt::Debug for Imagens<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Imagens")
            .field("url", &self.url)
            .field("dir", &self.dir)
            .finish_non_exhaustive()
    }
}

impl<'a> Imagens<'a> {
    /// Só a pasta (o comportamento anterior à BSV-61).
    pub fn pasta(dir: Option<&'a Path>) -> Self {
        Self {
            url: None,
            dir,
            http: &SemHttp,
            disco: &Disco,
        }
    }
}

/// `{base}/{arquivo}`, com ou sem `/` no fim da base.
pub fn url(base: &str, arquivo: &str) -> String {
    format!("{}/{arquivo}", base.trim_end_matches('/'))
}

/// Corpo de um `200` com até `MAX_BYTES`; senão o motivo.
pub fn baixar(http: &dyn BaixarHttps, url: &str) -> Result<Vec<u8>, ErroBaixa> {
    let (status, corpo) = http.baixar(url)?;
    if status != 200 {
        return Err(ErroBaixa::Status(status));
    }
    if corpo.len() > MAX_BYTES {
        return Err(ErroBaixa::Grande);
    }
    Ok(corpo)
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{var} inválida: {motivo} (use https://host/caminho/)")]
pub struct ErroBase {
    pub var: &'static str,
    pub motivo: &'static str,
}

/// Base validada: `https://`, host não vazio, sem `?`, `#`, `@`, `\` nem espaço. Termina em `/`.
pub fn base(var: &'static str, valor: &str) -> Result<String, ErroBase> {
    let erro = |motivo| ErroBase { var, motivo };
    let v = valor.trim();
    let resto = v
        .strip_prefix("https://")
        .ok_or_else(|| erro("não começa com https://"))?;
    if resto.split('/').next().is_none_or(str::is_empty) {
        return Err(erro("sem host"));
    }
    if v.contains(['?', '#', '@', '\\', ' ']) {
        return Err(erro("com ?, #, @, \\ ou espaço"));
    }
    Ok(format!("{}/", v.trim_end_matches('/')))
}

/// `var` do ambiente: ausente ou vazia → `None`; presente → validada.
pub fn base_do_env(
    var: &'static str,
    env: impl Fn(&str) -> Option<String>,
) -> Result<Option<String>, ErroBase> {
    env(var)
        .filter(|v| !v.trim().is_empty())
        .map(|v| base(var, &v))
        .transpose()
}

/// Cliente HTTPS (só HTTPS, HTTP/1.1) com runtime próprio, como o do Telegram.
pub struct SiteHttps {
    rt: Runtime,
    cliente: ClienteHttps,
}

impl fmt::Debug for SiteHttps {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("SiteHttps").finish_non_exhaustive()
    }
}

impl SiteHttps {
    pub fn new() -> Result<Self, String> {
        let (rt, cliente) = cliente_https()?;
        Ok(Self { rt, cliente })
    }
}

impl BaixarHttps for SiteHttps {
    fn baixar(&self, url: &str) -> Result<(u16, Vec<u8>), ErroBaixa> {
        let req = http::Request::get(url)
            .body(Full::new(Bytes::new()))
            .map_err(|e| ErroBaixa::Conexao(e.to_string()))?;
        self.rt.block_on(async {
            let pedido = async {
                let resp = self
                    .cliente
                    .request(req)
                    .await
                    .map_err(|e| ErroBaixa::Conexao(e.to_string()))?;
                let status = resp.status().as_u16();
                if status != 200 {
                    return Ok((status, Vec::new()));
                }
                let corpo = Limited::new(resp.into_body(), MAX_BYTES)
                    .collect()
                    .await
                    .map_err(|e| {
                        if e.is::<LengthLimitError>() {
                            ErroBaixa::Grande
                        } else {
                            ErroBaixa::Conexao(e.to_string())
                        }
                    })?
                    .to_bytes();
                Ok((status, corpo.to_vec()))
            };
            tokio::time::timeout(TIMEOUT, pedido)
                .await
                .map_err(|_| ErroBaixa::Timeout(TIMEOUT.as_secs()))?
        })
    }
}
