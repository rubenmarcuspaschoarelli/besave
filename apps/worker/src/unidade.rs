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

/// `Result` da unidade (`systemctl show -p Result`) que o worker não avisou sozinho: o sistema
/// matou o processo. `exit-code` o próprio worker já alertou (erro com nome e fase); outros
/// valores (`success`, `resources`…) não são fim anormal por tempo ou sinal.
pub fn encerrado_pelo_sistema(result: &str) -> bool {
    matches!(
        result.trim(),
        "timeout" | "signal" | "core-dump" | "watchdog"
    )
}

/// `systemctl show -p Result --value <unidade>`.
pub fn ler_result(unidade: &str) -> std::io::Result<String> {
    let saida = std::process::Command::new("systemctl")
        .args(["show", "-p", "Result", "--value", unidade])
        .output()?;
    if !saida.status.success() {
        return Err(std::io::Error::other(format!(
            "systemctl show saiu com {}",
            saida.status
        )));
    }
    Ok(String::from_utf8_lossy(&saida.stdout).trim().to_owned())
}

/// Consulta o motivo do fim da unidade com `ler` e avisa só se foi o sistema que a encerrou.
/// Sem conseguir ler o motivo, avisa (melhor um alerta a mais que silêncio). Devolve se avisou.
pub fn alertar_se_encerrada(
    unidade: &str,
    estado: PathBuf,
    telegram: &dyn Telegram,
    host: String,
    agora: i64,
    ler: impl Fn(&str) -> std::io::Result<String>,
) -> Result<bool, ErroUnidade> {
    match ler(unidade) {
        Ok(result) if !encerrado_pelo_sistema(&result) => {
            info!(
                unidade,
                result, "unidade falhou por exit-code; o worker já avisou"
            );
            return Ok(false);
        }
        Ok(_) => {}
        Err(e) => warn!(unidade, erro = %e, "motivo do fim da unidade ilegível; avisando"),
    }
    alertar(unidade, estado, telegram, host, agora)?;
    Ok(true)
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
        alertar_se_encerrada(unidade, estado, &tg, host_do_env(), agora, ler_result).map(|_| ())
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
