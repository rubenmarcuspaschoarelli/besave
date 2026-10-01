//! `besave-ciclo --env-file <arquivo>` (BSV-14): o mesmo caminho do `besave-worker --ciclo`, sem
//! console. No Windows é um executável sem janela (o Agendador não abre console a cada 5 min).
//! Nada em stdout/stderr: só o log em arquivo e o código de saída (0, 1, 2).
#![windows_subsystem = "windows"]

use std::process::ExitCode;

use worker::ciclo::{self, ErroCiclo, Opcoes};

fn main() -> ExitCode {
    // Antes de qualquer thread: `dotenvy` usa `set_var`.
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let previa = match args.as_slice() {
        [] => None,
        [_, _] | [_] => ciclo::env_file_dos_args(args.iter().cloned())
            .map(|p| ciclo::carregar_env_file(&p))
            .or_else(|| Some(Err(argumento(&args)))),
        _ => Some(Err(argumento(&args))),
    };
    ExitCode::from(ciclo::executar(&Opcoes::do_env(), previa).valor())
}

fn argumento(args: &[std::ffi::OsString]) -> ErroCiclo {
    let texto: Vec<_> = args.iter().map(|a| a.to_string_lossy()).collect();
    ErroCiclo::Argumento(texto.join(" "))
}
