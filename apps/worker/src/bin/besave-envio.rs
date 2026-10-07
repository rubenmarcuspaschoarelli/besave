//! `besave-envio [--env-file <arquivo>] [--sim]` (BSV-40): posta um lote de ofertas no canal do
//! Telegram e edita as expiradas. Sem janela de console (o Agendador roda a cada 5 min); só o log
//! em arquivo e o código de saída (0, 1, 2). `--sim` imprime no stdout (use `| Out-Host` no
//! PowerShell) e grava as fotos em `%TEMP%\besave-envio-sim\`.
#![windows_subsystem = "windows"]

use std::process::ExitCode;

use worker::ciclo::carregar_env_file;
use worker::envio::binario::{argumentos, executar};

fn main() -> ExitCode {
    // Antes de qualquer thread: `dotenvy` usa `set_var`.
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let (sim, previa) = match argumentos(&args) {
        Ok(a) => (a.sim, a.env_file.map(|p| carregar_env_file(&p))),
        Err(e) => (false, Some(Err(e))),
    };
    ExitCode::from(executar(sim, previa).valor())
}
