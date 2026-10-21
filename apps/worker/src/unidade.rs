//! Alerta de unidade encerrada pelo systemd (BSV-47). `OnFailure=besave-alerta@%n.service` chama
//! `besave-worker --alerta-encerrado <unidade>`: processo morto por `TimeoutStartSec` ou sinal não
//! avisa sozinho. Mesmo bot e mesma regra de repetição do alerta do worker (`Alertas::falha`);
//! as credenciais vêm só do `.env` da unidade.

use std::ffi::OsString;
use std::path::PathBuf;

use tracing::{info, warn};

use crate::alerta::{
    Alertas, ConfigTelegram, ErroConfigTelegram, TITULO_CICLO, TITULO_ENVIO, Telegram, host_do_env,
};
use crate::telegram::TelegramHttp;

/// Variante do alerta: sem dado do erro, só que o sistema encerrou a unidade.
pub const VARIANTE: &str = "EncerradoPeloSistema";
/// Fase do alerta.
pub const FASE: &str = "systemd";

#[derive(Debug, thiserror::Error)]
pub enum ErroUnidade {
    #[error("unidade desconhecida: {0:?} (esperado besave-ciclo.service ou besave-envio.service)")]
    Desconhecida(String),
    #[error("{0} ausente: defina a variável no .env da unidade")]
    PastaAusente(&'static str),
    #[error(transparent)]
    Telegram(#[from] ErroConfigTelegram),
    #[error("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID ausentes: sem como avisar")]
    SemTelegram,
    #[error("cliente do Telegram não iniciou: {0}")]
    Cliente(String),
}

/// Onde cada unidade guarda o estado do alerta (o mesmo arquivo que o próprio worker usa).
struct Destino {
    titulo: &'static str,
    arquivo: &'static str,
    var_trava: &'static str,
}

fn destino(unidade: &str) -> Result<Destino, ErroUnidade> {
    match unidade {
        "besave-ciclo.service" | "besave-ciclo" => Ok(Destino {
            titulo: TITULO_CICLO,
            arquivo: "alerta.json",
            var_trava: "BESAVE_LOCK",
        }),
        "besave-envio.service" | "besave-envio" => Ok(Destino {
            titulo: TITULO_ENVIO,
            arquivo: "alerta-envio.json",
            var_trava: "BESAVE_ENVIO_LOCK",
        }),
        outra => Err(ErroUnidade::Desconhecida(outra.to_owned())),
    }
}

/// Arquivo de estado do alerta da unidade: ao lado da trava (`BESAVE_LOCK`/`BESAVE_ENVIO_LOCK`).
pub fn arquivo_de_estado(
    unidade: &str,
    env: impl Fn(&str) -> Option<OsString>,
) -> Result<PathBuf, ErroUnidade> {
    let d = destino(unidade)?;
    let trava = env(d.var_trava)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .ok_or(ErroUnidade::PastaAusente(d.var_trava))?;
    Ok(trava.with_file_name(d.arquivo))
}

/// Avisa que `unidade` foi encerrada pelo sistema. Repetição: no máximo uma mensagem por 2 h.
pub fn alertar(
    unidade: &str,
    estado: PathBuf,
    telegram: &dyn Telegram,
    host: String,
    agora: i64,
) -> Result<(), ErroUnidade> {
    let d = destino(unidade)?;
    Alertas::new(telegram, estado, host)
        .com_titulo(d.titulo)
        .falha(VARIANTE, FASE, agora);
    Ok(())
}

/// Ponto de entrada do subcomando: lê o ambiente (`.env` da unidade) e avisa. Devolve o código de
/// saída (0 avisou ou já tinha avisado; 2 configuração).
pub fn executar(unidade: &str, agora: i64) -> u8 {
    let r = (|| {
        let estado = arquivo_de_estado(unidade, |k| std::env::var_os(k))?;
        let cfg = ConfigTelegram::do_env()?.ok_or(ErroUnidade::SemTelegram)?;
        let tg = TelegramHttp::new(cfg).map_err(|e| ErroUnidade::Cliente(e.to_string()))?;
        alertar(unidade, estado, &tg, host_do_env(), agora)
    })();
    match r {
        Ok(()) => {
            info!(unidade, "alerta de unidade encerrada tratado");
            0
        }
        Err(e) => {
            warn!(erro = %e, "alerta de unidade encerrada não enviado");
            2
        }
    }
}
