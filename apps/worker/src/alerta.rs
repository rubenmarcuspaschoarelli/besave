//! Alerta de falha do `--ciclo` no Telegram (BSV-14): mensagens curtas, sem URL, token ou
//! caminho; no máximo 1 envio por variante de erro a cada 2 h; "recuperado" no 1º sucesso.

use std::collections::BTreeMap;
use std::fmt;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::logs::iso_brasilia;

/// Mesma variante: no máximo 1 mensagem por janela.
pub const JANELA_SEGUNDOS: i64 = 2 * 3600;
const HOST_MAX: usize = 63;

/// Erros sem a URL do pedido (ela contém o token).
#[derive(Debug, thiserror::Error)]
pub enum ErroTelegram {
    #[error("Telegram respondeu HTTP {0}")]
    Http(u16),
    #[error("Telegram recusou a mensagem: {0}")]
    Recusada(String),
    #[error("Telegram sem resposta em {0} s")]
    Timeout(u64),
    #[error("Telegram: {0}")]
    Conexao(String),
}

/// Envio de uma mensagem de texto ao chat configurado.
pub trait Telegram {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram>;
}

#[derive(Debug, thiserror::Error)]
#[error("{presente} definida sem {ausente}: defina as duas ou nenhuma")]
pub struct ErroConfigTelegram {
    presente: &'static str,
    ausente: &'static str,
}

/// `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. `Debug` manual: o token nunca aparece.
#[derive(Clone)]
pub struct ConfigTelegram {
    token: String,
    pub chat_id: String,
}

impl fmt::Debug for ConfigTelegram {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ConfigTelegram")
            .field("token", &"***")
            .field("chat_id", &self.chat_id)
            .finish()
    }
}

impl ConfigTelegram {
    /// `None`: nenhuma das duas definida (alerta desligado).
    pub fn do_env() -> Result<Option<Self>, ErroConfigTelegram> {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Option<Self>, ErroConfigTelegram> {
        const TOKEN: &str = "TELEGRAM_BOT_TOKEN";
        const CHAT: &str = "TELEGRAM_CHAT_ID";
        let ler = |k| {
            env(k)
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty())
        };
        match (ler(TOKEN), ler(CHAT)) {
            (None, None) => Ok(None),
            (Some(token), Some(chat_id)) => Ok(Some(Self { token, chat_id })),
            (Some(_), None) => Err(ErroConfigTelegram {
                presente: TOKEN,
                ausente: CHAT,
            }),
            (None, Some(_)) => Err(ErroConfigTelegram {
                presente: CHAT,
                ausente: TOKEN,
            }),
        }
    }

    pub fn token(&self) -> &str {
        &self.token
    }
}

/// Só `[A-Za-z0-9._-]`, até 63 caracteres; vazio ou ausente → `desconhecido`.
pub fn sanitizar_host(bruto: Option<&str>) -> String {
    let h: String = bruto
        .unwrap_or_default()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
        .take(HOST_MAX)
        .collect();
    if h.is_empty() {
        "desconhecido".to_owned()
    } else {
        h
    }
}

/// `COMPUTERNAME` (Windows) ou `HOSTNAME`, sanitizado.
pub fn host_do_env() -> String {
    let h = std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .ok();
    sanitizar_host(h.as_deref())
}

/// `dd/mm/aaaa HH:MM` de Brasília.
fn data_hora(agora: i64) -> String {
    let s = iso_brasilia(agora);
    format!("{}/{}/{} {}", &s[8..10], &s[5..7], &s[..4], &s[11..16])
}

fn hora(agora: i64) -> String {
    iso_brasilia(agora)[11..16].to_owned()
}

pub fn mensagem_falha(variante: &str, fase: &str, agora: i64, host: &str) -> String {
    format!(
        "⚠️ Besave worker: falha no ciclo\nerro: {variante}\nfase: {fase}\nhorário: {} (-03:00)\nhost: {host}",
        data_hora(agora)
    )
}

pub fn mensagem_recuperado(falhas: u64, desde: i64) -> String {
    format!(
        "✅ Besave worker: recuperado após {falhas} falhas (desde {})",
        hora(desde)
    )
}

/// `alerta.json`: ciclos falhos seguidos, início da sequência e último envio entregue por variante.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EstadoAlerta {
    pub falhas: u64,
    pub desde: Option<i64>,
    pub envios: BTreeMap<String, i64>,
}

pub struct Alertas<'a> {
    telegram: &'a dyn Telegram,
    estado: PathBuf,
    host: String,
}

impl<'a> Alertas<'a> {
    pub fn new(telegram: &'a dyn Telegram, estado: PathBuf, host: String) -> Self {
        Self {
            telegram,
            estado,
            host,
        }
    }

    fn carregar(&self) -> EstadoAlerta {
        match std::fs::read(&self.estado) {
            Ok(b) => serde_json::from_slice(&b).unwrap_or_else(|e| {
                warn!(erro = %e, "alerta.json ilegível; recomeçando o estado do alerta");
                EstadoAlerta::default()
            }),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => EstadoAlerta::default(),
            Err(e) => {
                warn!(erro = %e, "lendo alerta.json; recomeçando o estado do alerta");
                EstadoAlerta::default()
            }
        }
    }

    fn salvar(&self, e: &EstadoAlerta) {
        let r = self
            .estado
            .parent()
            .map_or(Ok(()), std::fs::create_dir_all)
            .and_then(|()| {
                let json = serde_json::to_vec_pretty(e).map_err(std::io::Error::other)?;
                std::fs::write(&self.estado, json)
            });
        if let Err(e) = r {
            warn!(erro = %e, "gravando alerta.json");
        }
    }

    /// Ciclo falho: conta a falha e envia se a variante não foi alertada na janela.
    pub fn falha(&self, variante: &str, fase: &str, agora: i64) {
        let mut e = self.carregar();
        e.falhas += 1;
        e.desde.get_or_insert(agora);
        let na_janela = e
            .envios
            .get(variante)
            .is_some_and(|&t| agora - t < JANELA_SEGUNDOS);
        if na_janela {
            info!(variante, "alerta já enviado nas últimas 2 h; não reenviado");
        } else {
            match self
                .telegram
                .enviar(&mensagem_falha(variante, fase, agora, &self.host))
            {
                Ok(()) => {
                    e.envios.insert(variante.to_owned(), agora);
                    info!(variante, "alerta de falha enviado ao Telegram");
                }
                Err(err) => warn!(erro = %err, "falha ao enviar alerta ao Telegram"),
            }
        }
        self.salvar(&e);
    }

    /// Ciclo ok: depois de falhas, envia "recuperado" e zera o estado (só se entregou).
    pub fn sucesso(&self, agora: i64) {
        let e = self.carregar();
        if e.falhas == 0 {
            return;
        }
        let desde = e.desde.unwrap_or(agora);
        match self.telegram.enviar(&mensagem_recuperado(e.falhas, desde)) {
            Ok(()) => {
                info!(falhas = e.falhas, "recuperação enviada ao Telegram");
                self.salvar(&EstadoAlerta::default());
            }
            Err(err) => warn!(erro = %err, "falha ao enviar recuperação ao Telegram"),
        }
    }
}
