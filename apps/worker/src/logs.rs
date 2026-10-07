//! Log em arquivo do `--ciclo` (BSV-14): um arquivo por dia de Brasília, retenção de 14 dias.
//! Cada execução dura minutos, então o arquivo é escolhido no início (sem rotação em processo).

use std::fmt;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use tracing_subscriber::fmt::format::Writer;
use tracing_subscriber::fmt::time::FormatTime;

use crate::conversao::iso_utc;
use crate::pagina_html::OFFSET_BRASILIA_MIN;

/// Brasília, offset fixo (CLAUDE.md regra 5), em segundos.
pub const FUSO_BRASILIA: i64 = OFFSET_BRASILIA_MIN * 60;
pub const RETENCAO_DIAS: i64 = 14;
const PREFIXO: &str = "besave-worker.";
/// Log do `besave-envio` (BSV-40).
pub const PREFIXO_ENVIO: &str = "besave-envio.";
const SUFIXO: &str = ".log";

/// `AAAA-MM-DDTHH:MM:SS` no horário de Brasília.
pub fn iso_brasilia(agora: i64) -> String {
    let mut s = iso_utc(agora + FUSO_BRASILIA);
    s.pop(); // `Z`
    s
}

/// `AAAA-MM-DDTHH:MM:SS.mmm-03:00` de um instante em milissegundos Unix.
pub fn carimbo_brasilia(ms: i64) -> String {
    let min = OFFSET_BRASILIA_MIN.abs();
    let sinal = if OFFSET_BRASILIA_MIN < 0 { '-' } else { '+' };
    format!(
        "{}.{:03}{sinal}{:02}:{:02}",
        iso_brasilia(ms.div_euclid(1000)),
        ms.rem_euclid(1000),
        min / 60,
        min % 60
    )
}

/// Timer do `tracing-subscriber` em Brasília, offset fixo (nunca o fuso do sistema). `fixo`:
/// relógio de ensaio/teste em ms (`BESAVE_AGORA`).
#[derive(Debug, Clone, Copy, Default)]
pub struct HoraBrasilia {
    fixo: Option<i64>,
}

impl HoraBrasilia {
    pub fn fixa(ms: i64) -> Self {
        Self { fixo: Some(ms) }
    }
}

impl FormatTime for HoraBrasilia {
    fn format_time(&self, w: &mut Writer<'_>) -> fmt::Result {
        let ms = self.fixo.unwrap_or_else(|| {
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_or(0, |d| i64::try_from(d.as_millis()).unwrap_or(i64::MAX))
        });
        w.write_str(&carimbo_brasilia(ms))
    }
}

fn data_brasilia(agora: i64) -> String {
    iso_brasilia(agora)[..10].to_owned()
}

/// `{dir}/besave-worker.AAAA-MM-DD.log` do dia de Brasília.
pub fn arquivo_do_dia(dir: &Path, agora: i64) -> PathBuf {
    arquivo_do_dia_de(dir, PREFIXO, agora)
}

/// `{dir}/{prefixo}AAAA-MM-DD.log` do dia de Brasília.
pub fn arquivo_do_dia_de(dir: &Path, prefixo: &str, agora: i64) -> PathBuf {
    dir.join(format!("{prefixo}{}{SUFIXO}", data_brasilia(agora)))
}

/// `AAAA-MM-DD` do nome de um log com `prefixo`; `None` para outros arquivos.
fn data_do_nome<'a>(nome: &'a str, prefixo: &str) -> Option<&'a str> {
    let d = nome.strip_prefix(prefixo)?.strip_suffix(SUFIXO)?;
    let b = d.as_bytes();
    let formato = b.len() == 10
        && b.iter().enumerate().all(|(i, c)| {
            if i == 4 || i == 7 {
                *c == b'-'
            } else {
                c.is_ascii_digit()
            }
        });
    formato.then_some(d)
}

/// Remove os logs do worker com mais de `RETENCAO_DIAS` dias (data do nome < hoje − 14, em
/// Brasília) e devolve os caminhos removidos.
pub fn limpar_antigos(dir: &Path, agora: i64) -> std::io::Result<Vec<PathBuf>> {
    limpar_antigos_de(dir, PREFIXO, agora)
}

/// Como `limpar_antigos`, para os logs com `prefixo` (os outros não são tocados).
pub fn limpar_antigos_de(dir: &Path, prefixo: &str, agora: i64) -> std::io::Result<Vec<PathBuf>> {
    let limite = data_brasilia(agora - RETENCAO_DIAS * 86_400);
    let mut removidos = Vec::new();
    for e in std::fs::read_dir(dir)? {
        let e = e?;
        let nome = e.file_name();
        let Some(data) = nome.to_str().and_then(|n| data_do_nome(n, prefixo)) else {
            continue;
        };
        // `AAAA-MM-DD` ordena como data.
        if data < limite.as_str() {
            std::fs::remove_file(e.path())?;
            removidos.push(e.path());
        }
    }
    Ok(removidos)
}
