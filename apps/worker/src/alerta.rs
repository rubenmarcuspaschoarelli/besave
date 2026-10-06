//! Alerta de falha do `--ciclo` no Telegram (BSV-14): mensagens curtas, sem URL, token ou
//! caminho; no máximo 1 envio por variante de erro a cada 2 h; "recuperado" no 1º sucesso.
//! BSV-14b: aviso de "nenhuma oferta nova" (limiar, lembrete e mensagem de volta), com estado
//! próprio em `alerta.json`.

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

/// `dd/mm HH:MM` de Brasília.
fn dia_hora(t: i64) -> String {
    let s = iso_brasilia(t);
    format!("{}/{} {}", &s[8..10], &s[5..7], &s[11..16])
}

/// Horas inteiras (para baixo) entre `dt` e `agora`; `None` se o conjunto é vazio.
pub fn horas_sem_novas(dt: Option<i64>, agora: i64) -> Option<i64> {
    dt.map(|d| (agora - d).max(0) / 3600)
}

fn mensagem_sem_novas(dt: Option<i64>, publicadas: u64, agora: i64, host: &str) -> String {
    let titulo = match horas_sem_novas(dt, agora) {
        Some(h) => format!("nenhuma oferta nova há {h} h"),
        None => "nenhuma oferta nova".to_owned(),
    };
    let ultima = dt.map_or_else(|| "—".to_owned(), |d| format!("{} (-03:00)", dia_hora(d)));
    format!("⚠️ Besave: {titulo}\núltima: {ultima}\npublicadas: {publicadas}\nhost: {host}")
}

fn mensagem_com_novas(desde: Option<i64>) -> String {
    let desde = desde.map_or_else(|| "—".to_owned(), dia_hora);
    format!("✅ Besave: ofertas novas de novo (paradas desde {desde})")
}

pub fn mensagem_recuperado(falhas: u64, desde: i64) -> String {
    format!(
        "✅ Besave worker: recuperado após {falhas} falhas (desde {})",
        hora(desde)
    )
}

const VAR_LIMIAR: &str = "BESAVE_ALERTA_SEM_NOVAS_HORAS";
const VAR_LEMBRETE: &str = "BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS";

#[derive(Debug, thiserror::Error)]
#[error("{var} inválida: use um inteiro ≥ 0 (horas)")]
pub struct ErroConfigSemNovas {
    var: &'static str,
}

/// Limiar e lembrete do aviso de "nenhuma oferta nova", em horas; `0` desliga (limiar) ou
/// dispensa o lembrete.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConfigSemNovas {
    pub limiar_horas: u64,
    pub lembrete_horas: u64,
}

impl Default for ConfigSemNovas {
    fn default() -> Self {
        Self {
            limiar_horas: 24,
            lembrete_horas: 24,
        }
    }
}

impl ConfigSemNovas {
    pub fn do_env() -> Result<Self, ErroConfigSemNovas> {
        Self::de(|k| std::env::var(k).ok())
    }

    /// Ausente ou vazio → padrão (24 h); inteiro ≥ 0 ou erro que nomeia a variável.
    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroConfigSemNovas> {
        let ler = |var: &'static str, padrao: u64| -> Result<u64, ErroConfigSemNovas> {
            match env(var)
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty())
            {
                None => Ok(padrao),
                Some(v) => v.parse().map_err(|_| ErroConfigSemNovas { var }),
            }
        };
        let padrao = Self::default();
        Ok(Self {
            limiar_horas: ler(VAR_LIMIAR, padrao.limiar_horas)?,
            lembrete_horas: ler(VAR_LEMBRETE, padrao.lembrete_horas)?,
        })
    }
}

/// Bloco `sem_novas` do `alerta.json`. `desde`: `dt` da última oferta quando o último aviso foi
/// entregue; `ultimo_envio`: instante dessa entrega (aviso ou lembrete). `None` = nenhum aviso ativo.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EstadoSemNovas {
    pub desde: Option<i64>,
    pub ultimo_envio: Option<i64>,
}

/// `alerta.json`: ciclos falhos seguidos, início da sequência e último envio entregue por variante.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EstadoAlerta {
    pub falhas: u64,
    pub desde: Option<i64>,
    pub envios: BTreeMap<String, i64>,
    /// Independente do estado de falha; ausente em arquivos da BSV-14.
    #[serde(default)]
    pub sem_novas: EstadoSemNovas,
}

pub struct Alertas<'a> {
    telegram: &'a dyn Telegram,
    estado: PathBuf,
    host: String,
    sem_novas: ConfigSemNovas,
}

impl<'a> Alertas<'a> {
    pub fn new(telegram: &'a dyn Telegram, estado: PathBuf, host: String) -> Self {
        Self {
            telegram,
            estado,
            host,
            // Desligado até `com_sem_novas`: quem não configura não ganha aviso novo.
            sem_novas: ConfigSemNovas {
                limiar_horas: 0,
                ..ConfigSemNovas::default()
            },
        }
    }

    /// Liga o aviso de "nenhuma oferta nova" com este limiar e lembrete.
    #[must_use]
    pub fn com_sem_novas(mut self, cfg: ConfigSemNovas) -> Self {
        self.sem_novas = cfg;
        self
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
                // `sem_novas` não é do estado de falha: sobrevive à recuperação.
                self.salvar(&EstadoAlerta {
                    sem_novas: e.sem_novas,
                    ..EstadoAlerta::default()
                });
            }
            Err(err) => warn!(erro = %err, "falha ao enviar recuperação ao Telegram"),
        }
    }

    /// Ciclo ok: compara o `dt` mais recente publicado com o limiar e chama `sem_novas` ou
    /// `com_novas`. Limiar 0 = desligado. Conjunto vazio (`None`) conta como "sem novas".
    pub fn avaliar_novas(&self, dt_mais_recente: Option<i64>, publicadas: u64, agora: i64) {
        let limiar = self.sem_novas.limiar_horas;
        if limiar == 0 {
            return;
        }
        let limite = i64::try_from(limiar)
            .unwrap_or(i64::MAX)
            .saturating_mul(3600);
        if dt_mais_recente.is_none_or(|d| agora - d > limite) {
            self.sem_novas(dt_mais_recente, publicadas, agora);
        } else {
            self.com_novas(agora);
        }
    }

    /// Aviso no 1º ciclo parado; lembrete a cada `lembrete_horas` do último envio entregue.
    /// Envio que falha → WARN e o estado não avança.
    pub fn sem_novas(&self, dt_mais_recente: Option<i64>, publicadas: u64, agora: i64) {
        let mut e = self.carregar();
        let lembrete = i64::try_from(self.sem_novas.lembrete_horas)
            .unwrap_or(i64::MAX)
            .saturating_mul(3600);
        let devido = match e.sem_novas.ultimo_envio {
            None => true,
            Some(t) => lembrete > 0 && agora - t >= lembrete,
        };
        if !devido {
            return;
        }
        let texto = mensagem_sem_novas(dt_mais_recente, publicadas, agora, &self.host);
        match self.telegram.enviar(&texto) {
            Ok(()) => {
                info!("alerta de ofertas paradas enviado ao Telegram");
                e.sem_novas = EstadoSemNovas {
                    desde: dt_mais_recente,
                    ultimo_envio: Some(agora),
                };
                self.salvar(&e);
            }
            Err(err) => warn!(erro = %err, "falha ao enviar alerta de ofertas paradas ao Telegram"),
        }
    }

    /// Chegou oferta dentro do limiar: "de novo", só se um aviso foi entregue.
    pub fn com_novas(&self, _agora: i64) {
        let mut e = self.carregar();
        if e.sem_novas.ultimo_envio.is_none() {
            return;
        }
        match self.telegram.enviar(&mensagem_com_novas(e.sem_novas.desde)) {
            Ok(()) => {
                info!("retomada de ofertas enviada ao Telegram");
                e.sem_novas = EstadoSemNovas::default();
                self.salvar(&e);
            }
            Err(err) => warn!(erro = %err, "falha ao enviar retomada de ofertas ao Telegram"),
        }
    }
}
