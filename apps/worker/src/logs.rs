//! Log em arquivo do `--ciclo` (BSV-14): um arquivo por dia de Brasília, retenção de 14 dias.
//! Cada execução dura minutos, então o arquivo é escolhido no início (sem rotação em processo).

use std::path::{Path, PathBuf};

use crate::conversao::iso_utc;

/// Brasília, offset fixo (CLAUDE.md regra 5).
pub const FUSO_BRASILIA: i64 = -3 * 3600;
pub const RETENCAO_DIAS: i64 = 14;
const PREFIXO: &str = "besave-worker.";
const SUFIXO: &str = ".log";

/// `AAAA-MM-DDTHH:MM:SS` no horário de Brasília.
pub fn iso_brasilia(agora: i64) -> String {
    let mut s = iso_utc(agora + FUSO_BRASILIA);
    s.pop(); // `Z`
    s
}

fn data_brasilia(agora: i64) -> String {
    iso_brasilia(agora)[..10].to_owned()
}

/// `{dir}/besave-worker.AAAA-MM-DD.log` do dia de Brasília.
pub fn arquivo_do_dia(dir: &Path, agora: i64) -> PathBuf {
    dir.join(format!("{PREFIXO}{}{SUFIXO}", data_brasilia(agora)))
}

/// `AAAA-MM-DD` do nome de um log do worker; `None` para outros arquivos.
fn data_do_nome(nome: &str) -> Option<&str> {
    let d = nome.strip_prefix(PREFIXO)?.strip_suffix(SUFIXO)?;
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
    let limite = data_brasilia(agora - RETENCAO_DIAS * 86_400);
    let mut removidos = Vec::new();
    for e in std::fs::read_dir(dir)? {
        let e = e?;
        let nome = e.file_name();
        let Some(data) = nome.to_str().and_then(data_do_nome) else {
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
