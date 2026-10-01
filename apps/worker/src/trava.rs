//! Trava de arquivo do `--ciclo` (BSV-14): um ciclo por vez. `File::try_lock` da std; o SO solta
//! a trava quando o processo morre, então conteúdo sem `fim=` com a trava livre é um órfão.

use std::fs::{File, OpenOptions, TryLockError};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::Path;

use tracing::warn;

use crate::conversao::iso_utc;

#[derive(Debug, thiserror::Error)]
#[error("trava {caminho}: {fonte}")]
pub struct ErroTrava {
    caminho: String,
    fonte: std::io::Error,
}

/// Solta (e grava `fim=`) no `Drop`.
#[derive(Debug)]
pub struct Trava {
    arquivo: File,
    conteudo: String,
}

impl Trava {
    /// `None`: outro processo segura a trava. Cria a pasta se preciso. `agora` em segundos Unix.
    pub fn adquirir(caminho: &Path, agora: i64) -> Result<Option<Self>, ErroTrava> {
        let erro = |fonte| ErroTrava {
            caminho: caminho.display().to_string(),
            fonte,
        };
        if let Some(dir) = caminho.parent() {
            std::fs::create_dir_all(dir).map_err(erro)?;
        }
        let mut arquivo = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(caminho)
            .map_err(erro)?;
        match arquivo.try_lock() {
            Ok(()) => {}
            Err(TryLockError::WouldBlock) => return Ok(None),
            Err(TryLockError::Error(e)) => return Err(erro(e)),
        }
        let mut bytes = Vec::new();
        arquivo.read_to_end(&mut bytes).map_err(erro)?;
        let anterior = String::from_utf8_lossy(&bytes);
        let anterior = anterior.trim();
        if !anterior.is_empty() && !anterior.contains("fim=") {
            warn!(
                anterior,
                "trava órfã tomada: o ciclo anterior terminou sem soltar"
            );
        }
        let conteudo = format!("pid={} inicio={}", std::process::id(), iso_utc(agora));
        let mut t = Self { arquivo, conteudo };
        t.gravar("").map_err(erro)?;
        Ok(Some(t))
    }

    fn gravar(&mut self, sufixo: &str) -> std::io::Result<()> {
        self.arquivo.set_len(0)?;
        self.arquivo.seek(SeekFrom::Start(0))?;
        writeln!(self.arquivo, "{}{sufixo}", self.conteudo)?;
        self.arquivo.flush()
    }
}

impl Drop for Trava {
    fn drop(&mut self) {
        let fim = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| i64::try_from(d.as_secs()).unwrap_or(i64::MAX));
        // Falha aqui só faz o próximo ciclo logar um órfão.
        let _ = self.gravar(&format!(" fim={}", iso_utc(fim)));
        let _ = self.arquivo.unlock();
    }
}
