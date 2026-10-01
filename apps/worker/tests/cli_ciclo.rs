//! CIC-02..04, TRV-01, ALR-06 (BSV-14) no binário: `--ciclo --env-file`. Sem rede: todos os
//! cenários param antes do Oracle e da AWS (configuração ou trava).

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use worker::trava::Trava;

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-cli-ciclo-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// `.env` com a configuração mínima do `--publicar` (sem `BESAVE_FONTE`). Caminhos entre aspas
/// simples: sem aspas, o `dotenvy` lê `\` como escape.
fn env_file(dir: &Path, extra: &str) -> PathBuf {
    let mapeamento =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../packages/contract/mapeamento.json");
    let p = dir.join("worker.env");
    std::fs::write(
        &p,
        format!(
            "BESAVE_MAPEAMENTO='{}'\nBESAVE_BUCKET=bucket-do-env-file\nBESAVE_KVS_ARN=arn:aws:cloudfront::1:key-value-store/x\nBESAVE_IMAGENS_DIR='{}'\n{extra}",
            mapeamento.display(),
            dir.join("imagens").display()
        ),
    )
    .unwrap();
    p
}

/// Ambiente limpo das variáveis do worker; `LOCALAPPDATA` aponta para `local`.
fn comando(local: &Path) -> Command {
    let mut c = Command::new(env!("CARGO_BIN_EXE_besave-worker"));
    c.current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("LOCALAPPDATA", local)
        .env("RUST_LOG", "info");
    for k in [
        "BESAVE_FONTE",
        "BESAVE_MAPEAMENTO",
        "BESAVE_BUCKET",
        "BESAVE_KVS_ARN",
        "BESAVE_IMAGENS_DIR",
        "BESAVE_LOCK",
        "BESAVE_LOG_DIR",
        "BESAVE_ORACLE_DSN",
        "BESAVE_ORACLE_USER",
        "BESAVE_ORACLE_PASS",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ] {
        c.env_remove(k);
    }
    c
}

/// Conteúdo de todos os logs em `{local}/besave/logs`.
fn logs(local: &Path) -> String {
    let dir = local.join("besave").join("logs");
    let mut s = String::new();
    for e in std::fs::read_dir(&dir).unwrap_or_else(|e| panic!("{}: {e}", dir.display())) {
        s.push_str(&std::fs::read_to_string(e.unwrap().path()).unwrap());
    }
    s
}

fn texto(o: &Output) -> String {
    format!(
        "status={:?}\nstdout={}\nstderr={}",
        o.status.code(),
        String::from_utf8_lossy(&o.stdout),
        String::from_utf8_lossy(&o.stderr)
    )
}

/// CIC-02: `--env-file` inexistente → código 2 e mensagem que nomeia a opção e o arquivo.
#[test]
fn env_file_inexistente_sai_com_2() {
    let local = dir_temp("sem-env");
    let falta = local.join("nao-existe.env");
    let out = comando(&local)
        .args(["--ciclo", "--env-file"])
        .arg(&falta)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("--env-file"), "{}", texto(&out));
    assert!(stderr.contains("nao-existe.env"), "{}", texto(&out));
}

/// CIC-03 + CIC-04 + ALR-06: o `.env` é lido (bucket, ARN e mapeamento vêm dele), mas
/// `BESAVE_FONTE` do ambiente vence a do `.env`; valor inválido → código 2. Sem `TELEGRAM_*`,
/// o alerta fica desligado com `INFO` no log do dia.
#[test]
fn ambiente_vence_o_env_file() {
    let local = dir_temp("precedencia");
    let env = env_file(&local, "BESAVE_FONTE=fake\n");
    let out = comando(&local)
        .env("BESAVE_FONTE", "do_ambiente")
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let log = logs(&local);
    assert!(log.contains("do_ambiente"), "{log}");
    assert!(
        log.lines()
            .any(|l| l.contains("INFO") && l.contains("alerta desligado")),
        "{log}"
    );
    assert!(
        log.lines()
            .any(|l| l.contains("ERROR") && l.contains("fase=config")),
        "{log}"
    );
}

/// TRV-01: com a trava segura por outro processo, o ciclo sai com 0 e loga
/// "ciclo anterior em andamento".
#[test]
fn trava_ocupada_sai_com_0() {
    let local = dir_temp("trava");
    let env = env_file(&local, "BESAVE_FONTE=fake\n");
    let _t = Trava::adquirir(&local.join("besave").join("worker.lock"), 0)
        .unwrap()
        .unwrap();
    let out = comando(&local)
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(0), "{}", texto(&out));
    let log = logs(&local);
    assert!(
        log.lines()
            .any(|l| l.contains("INFO") && l.contains("ciclo anterior em andamento")),
        "{log}"
    );
}

/// ALR-06: só uma das `TELEGRAM_*` → código 2 nomeando a ausente.
#[test]
fn telegram_pela_metade_sai_com_2() {
    let local = dir_temp("telegram");
    let env = env_file(&local, "BESAVE_FONTE=fake\nTELEGRAM_BOT_TOKEN=123:abc\n");
    let out = comando(&local)
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let log = logs(&local);
    assert!(log.contains("TELEGRAM_CHAT_ID"), "{log}");
    assert!(!log.contains("123:abc"), "{log}");
}

/// CIC-04: sem `LOCALAPPDATA` e sem `BESAVE_LOCK`/`BESAVE_LOG_DIR` não há onde travar → código 2.
#[test]
fn sem_pasta_local_sai_com_2() {
    let local = dir_temp("sem-local");
    let env = env_file(&local, "BESAVE_FONTE=fake\n");
    let out = comando(&local)
        .env_remove("LOCALAPPDATA")
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("LOCALAPPDATA"),
        "{}",
        texto(&out)
    );
}

/// CIC-04: `BESAVE_LOCK` e `BESAVE_LOG_DIR` substituem os padrões.
#[test]
fn lock_e_logs_configuraveis() {
    let local = dir_temp("vars");
    let env = env_file(&local, "BESAVE_FONTE=do_env_file_invalida\n");
    let logs_dir = local.join("meus-logs");
    let out = comando(&local)
        .env_remove("LOCALAPPDATA")
        .env("BESAVE_LOCK", local.join("trava").join("w.lock"))
        .env("BESAVE_LOG_DIR", &logs_dir)
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    assert!(local.join("trava").join("w.lock").exists());
    let n = std::fs::read_dir(&logs_dir).unwrap().count();
    assert_eq!(n, 1);
}
