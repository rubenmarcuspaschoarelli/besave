//! `besave-ciclo --env-file <arquivo>` (BSV-14): o mesmo caminho do `besave-worker --ciclo`, sem
//! console. No Windows é um executável sem janela (o Agendador não abre console a cada 5 min).
//! Nada em stdout/stderr: só o log em arquivo e o código de saída (0, 1, 2).
#![windows_subsystem = "windows"]

use std::path::PathBuf;
use std::process::ExitCode;

use worker::ciclo::{self, ErroCiclo, Opcoes};

fn main() -> ExitCode {
    // Antes de qualquer thread: `dotenvy` usa `set_var`.
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    // Só: nada, `--env-file <arq>` ou `--env-file=<arq>`. Qualquer outra coisa → código 2.
    let env_file = match args.as_slice() {
        [] => Ok(None),
        [opcao, arq] if opcao == "--env-file" => Ok(Some(PathBuf::from(arq))),
        [a] => a
            .to_str()
            .and_then(|s| s.strip_prefix("--env-file="))
            .map(|arq| Some(PathBuf::from(arq)))
            .ok_or_else(|| argumento(&args)),
        _ => Err(argumento(&args)),
    };
    let previa = match env_file {
        Ok(None) => None,
        Ok(Some(p)) => Some(ciclo::carregar_env_file(&p)),
        Err(e) => Some(Err(e)),
    };
    ExitCode::from(ciclo::executar(&Opcoes::do_env(), previa).valor())
}

fn argumento(args: &[std::ffi::OsString]) -> ErroCiclo {
    let texto: Vec<_> = args.iter().map(|a| a.to_string_lossy()).collect();
    ErroCiclo::Argumento(texto.join(" "))
}
