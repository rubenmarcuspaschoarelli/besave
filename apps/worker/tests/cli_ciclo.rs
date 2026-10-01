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

/// `besave-worker` com o ambiente de `comando_de`.
fn comando(local: &Path) -> Command {
    comando_de(env!("CARGO_BIN_EXE_besave-worker"), local)
}

/// Ambiente limpo das variáveis do worker; `LOCALAPPDATA` aponta para `local`.
fn comando_de(exe: &str, local: &Path) -> Command {
    let mut c = Command::new(exe);
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
        "BESAVE_DESTINO_LOCAL",
        "BESAVE_AGORA",
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
    // Ciclo que falha não imprime relatório no stdout.
    assert!(out.stdout.is_empty(), "{}", texto(&out));
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

/// CIC-02 (ilegível) + CIC-05: `.env` malformado → código 2, e nem o log nem o stderr ecoam a
/// linha (que pode ter token ou senha).
#[test]
fn env_file_malformado_sai_com_2_sem_ecoar_a_linha() {
    let local = dir_temp("malformado");
    let env = local.join("ruim.env");
    std::fs::write(&env, "TELEGRAM_BOT_TOKEN=123:SEGREDO\\q x y\n").unwrap();
    let out = comando(&local)
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("--env-file"), "{}", texto(&out));
    assert!(!stderr.contains("SEGREDO"), "{}", texto(&out));
    let log = logs(&local);
    assert!(log.contains("fase=env_file"), "{log}");
    assert!(!log.contains("SEGREDO"), "{log}");
}

/// Linha `relatorio` do log, sem as medições de tempo (`t_*`, `tempo_ms`).
fn relatorio_estavel(local: &Path) -> String {
    let log = logs(local);
    let linhas: Vec<&str> = log.lines().filter(|l| l.contains(" relatorio ")).collect();
    assert_eq!(linhas.len(), 1, "{log}");
    let pares = linhas[0].split_once(" relatorio ").unwrap().1;
    pares
        .split(' ')
        .filter(|p| !p.starts_with("t_") && !p.starts_with("tempo_ms="))
        .collect::<Vec<_>>()
        .join(" ")
}

/// CIC-06: `besave-ciclo` e `besave-worker --ciclo` dão a mesma linha de relatório para a mesma
/// fonte fake; o `besave-ciclo` não escreve nada em stdout nem stderr. Destino local
/// (`BESAVE_DESTINO_LOCAL`, CIC-07): sem AWS; `BESAVE_AGORA` fixa o relógio da fonte fake.
#[test]
fn besave_ciclo_e_ciclo_dao_o_mesmo_relatorio() {
    let rodar = |exe: &str, args: &[&str], nome: &str| {
        let local = dir_temp(nome);
        let extra = format!(
            "BESAVE_FONTE=fake\nBESAVE_DESTINO_LOCAL='{}'\nBESAVE_AGORA=1790000000\n",
            local.join("saida").display()
        );
        let env = env_file(&local, &extra);
        let out = comando_de(exe, &local)
            .args(args)
            .arg("--env-file")
            .arg(&env)
            .output()
            .unwrap();
        (local, out)
    };
    let (local_w, out_w) = rodar(
        env!("CARGO_BIN_EXE_besave-worker"),
        &["--ciclo"],
        "rel-worker",
    );
    let (local_c, out_c) = rodar(env!("CARGO_BIN_EXE_besave-ciclo"), &[], "rel-ciclo");
    assert_eq!(out_w.status.code(), Some(0), "{}", texto(&out_w));
    assert_eq!(out_c.status.code(), Some(0), "{}", texto(&out_c));
    assert!(out_c.stdout.is_empty(), "{}", texto(&out_c));
    assert!(out_c.stderr.is_empty(), "{}", texto(&out_c));
    // `--ciclo` à mão mantém o relatório no stdout ("além da saída atual").
    let stdout_w = String::from_utf8_lossy(&out_w.stdout);
    assert!(stdout_w.contains("lidas: 10\n"), "{}", texto(&out_w));
    assert!(stdout_w.contains("validas: 3\n"), "{}", texto(&out_w));
    // Destino local nunca passa calado: `WARN` no log.
    let log_c = logs(&local_c);
    assert!(
        log_c
            .lines()
            .any(|l| l.contains("WARN") && l.contains("BESAVE_DESTINO_LOCAL")),
        "{log_c}"
    );
    let rel_w = relatorio_estavel(&local_w);
    assert!(rel_w.contains("lidas=10 validas=3 rejeitadas=7"), "{rel_w}");
    assert_eq!(relatorio_estavel(&local_c), rel_w);
    assert!(local_c.join("saida").join("manifest.json").exists());
}

/// CIC-06: argumento desconhecido no `besave-ciclo` → código 2, registrado só no log. Vale
/// para um argumento solto e para sobra depois de `--env-file <arq>`.
#[test]
fn besave_ciclo_argumento_invalido_sai_com_2() {
    for (nome, args) in [
        ("ciclo-arg", vec!["--publicar".to_owned()]),
        (
            "ciclo-arg-sobra",
            vec![
                "--env-file".to_owned(),
                "x.env".to_owned(),
                "--sim".to_owned(),
            ],
        ),
        (
            "ciclo-arg-igual",
            vec!["--env-file=x.env".to_owned(), "--sim".to_owned()],
        ),
        (
            "ciclo-arg-antes",
            vec!["--sim".to_owned(), "--env-file=x.env".to_owned()],
        ),
    ] {
        let local = dir_temp(nome);
        let out = comando_de(env!("CARGO_BIN_EXE_besave-ciclo"), &local)
            .args(&args)
            .output()
            .unwrap();
        assert_eq!(out.status.code(), Some(2), "{args:?}: {}", texto(&out));
        assert!(out.stdout.is_empty(), "{}", texto(&out));
        assert!(out.stderr.is_empty(), "{}", texto(&out));
        let log = logs(&local);
        assert!(
            log.lines()
                .any(|l| l.contains("ERROR") && l.contains("variante=Argumento")),
            "{args:?}: {log}"
        );
    }
}

/// CIC-07: `BESAVE_AGORA` só vale com `BESAVE_DESTINO_LOCAL`; sem ele, o relógio é o do
/// sistema (o arquivo de log não é o de 2026-09-21).
#[test]
fn agora_fixo_ignorado_sem_destino_local() {
    let local = dir_temp("agora-ignorado");
    let env = env_file(&local, "BESAVE_FONTE=invalida\nBESAVE_AGORA=1790000000\n");
    let out = comando(&local)
        .args(["--ciclo", "--env-file"])
        .arg(&env)
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2), "{}", texto(&out));
    let nomes: Vec<String> = std::fs::read_dir(local.join("besave").join("logs"))
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    assert_eq!(nomes.len(), 1);
    assert_ne!(nomes[0], "besave-worker.2026-09-21.log");
}
