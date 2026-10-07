//! BSV-40 BIN-01, BIN-02 no binário `besave-envio`. Sem rede: todos os cenários param antes do
//! Oracle e do Telegram (argumento, configuração ou trava).

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use worker::trava::Trava;

const TOKEN: &str = "123456:segredo-do-canal-que-nao-pode-vazar";

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-cli-envio-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// Ambiente limpo; `LOCALAPPDATA` aponta para `local`.
fn comando(local: &Path) -> Command {
    let mut c = Command::new(env!("CARGO_BIN_EXE_besave-envio"));
    c.current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("LOCALAPPDATA", local)
        .env("RUST_LOG", "info");
    for k in [
        "BESAVE_MAPEAMENTO",
        "BESAVE_IMAGENS_DIR",
        "BESAVE_LOG_DIR",
        "BESAVE_ENVIO_LOCK",
        "BESAVE_ENVIO_CANAL",
        "BESAVE_ORACLE_DSN",
        "BESAVE_ORACLE_USER",
        "BESAVE_ORACLE_PASS",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_CANAL_BOT_TOKEN",
    ] {
        c.env_remove(k);
    }
    c
}

fn logs(local: &Path) -> (Vec<String>, String) {
    let dir = local.join("besave").join("logs");
    let mut nomes = Vec::new();
    let mut s = String::new();
    for e in std::fs::read_dir(&dir).unwrap_or_else(|e| panic!("{}: {e}", dir.display())) {
        let e = e.unwrap();
        nomes.push(e.file_name().to_string_lossy().into_owned());
        s.push_str(&std::fs::read_to_string(e.path()).unwrap());
    }
    (nomes, s)
}

fn texto(o: &Output) -> String {
    format!(
        "status={:?}\nstdout={}\nstderr={}",
        o.status.code(),
        String::from_utf8_lossy(&o.stdout),
        String::from_utf8_lossy(&o.stderr)
    )
}

/// BIN-01: argumento desconhecido → código 2, só no log próprio `besave-envio.AAAA-MM-DD.log`.
#[test]
fn argumento_invalido_sai_com_2() {
    for args in [
        vec!["--publicar"],
        vec!["--sim", "--sim"],
        vec!["--env-file"],
        vec!["--env-file=a.env", "--env-file=b.env"],
    ] {
        let local = dir_temp("arg");
        let out = comando(&local).args(&args).output().unwrap();
        assert_eq!(out.status.code(), Some(2), "{args:?}: {}", texto(&out));
        assert!(
            out.stdout.is_empty() && out.stderr.is_empty(),
            "{}",
            texto(&out)
        );
        let (nomes, log) = logs(&local);
        assert_eq!(nomes.len(), 1, "{nomes:?}");
        assert!(
            nomes[0].starts_with("besave-envio.") && nomes[0].ends_with(".log"),
            "{nomes:?}"
        );
        assert!(
            log.lines()
                .any(|l| l.contains("ERROR") && l.contains("variante=Argumento")),
            "{args:?}: {log}"
        );
    }
}

/// BIN-02: sem `TELEGRAM_CANAL_BOT_TOKEN` (e sem `--sim`) → código 2 nomeando a variável.
#[test]
fn sem_token_do_canal_sai_com_2() {
    let local = dir_temp("token");
    let out = comando(&local).output().unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let (_, log) = logs(&local);
    assert!(
        log.lines()
            .any(|l| l.contains("ERROR") && l.contains("TELEGRAM_CANAL_BOT_TOKEN")),
        "{log}"
    );
}

/// BIN-02: o token do canal nunca vai para o log, mesmo quando a execução falha depois dele.
#[test]
fn token_nao_aparece_no_log() {
    let local = dir_temp("vazamento");
    let env = local.join("envio.env");
    std::fs::write(&env, format!("TELEGRAM_CANAL_BOT_TOKEN={TOKEN}\n")).unwrap();
    let out = comando(&local)
        .arg("--env-file")
        .arg(&env)
        .output()
        .unwrap();
    // Sem Oracle configurado: configuração ausente.
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let (_, log) = logs(&local);
    assert!(log.contains("BESAVE_ORACLE_DSN"), "{log}");
    assert!(!log.contains(TOKEN) && !log.contains("segredo"), "{log}");
}

/// BIN-01: trava própria (`envio.lock`): ocupada → código 0 e "pulado"; a do ciclo não bloqueia.
#[test]
fn trava_propria() {
    let local = dir_temp("trava");
    let _t = Trava::adquirir(&local.join("besave").join("envio.lock"), 0)
        .unwrap()
        .unwrap();
    let out = comando(&local).output().unwrap();
    assert_eq!(out.status.code(), Some(0), "{}", texto(&out));
    let (_, log) = logs(&local);
    assert!(log.contains("envio anterior em andamento"), "{log}");

    let local = dir_temp("trava-ciclo");
    let _c = Trava::adquirir(&local.join("besave").join("worker.lock"), 0)
        .unwrap()
        .unwrap();
    let out = comando(&local).output().unwrap();
    // Passa da trava e para na configuração (token ausente).
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
}
