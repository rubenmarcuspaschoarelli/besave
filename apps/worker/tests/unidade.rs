//! UNI-01..: alerta de unidade encerrada pelo systemd (BSV-47): mesmo bot e mesma regra de
//! repetição do alerta do worker; subcomando `besave-worker --alerta-encerrado`.

use std::cell::RefCell;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::Command;

use worker::alerta::{ErroTelegram, TITULO_CICLO, TITULO_ENVIO, Telegram};
use worker::unidade::{ErroUnidade, FASE, VARIANTE, alertar, arquivo_de_estado};

#[derive(Default)]
struct TelegramFake {
    enviados: RefCell<Vec<String>>,
}

impl Telegram for TelegramFake {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        self.enviados.borrow_mut().push(texto.to_owned());
        Ok(())
    }
}

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-unidade-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// 2026-09-24T12:40:00Z = 09:40 em Brasília.
const AGORA: i64 = 1_790_253_600;

/// UNI-01: a mensagem do ciclo traz título, variante, fase, horário e host.
#[test]
fn ciclo_encerrado_avisa_com_titulo_variante_fase_e_host() {
    let d = dir_temp("msg");
    let tg = TelegramFake::default();
    alertar(
        "besave-ciclo.service",
        d.join("alerta.json"),
        &tg,
        "vps-1".into(),
        AGORA,
    )
    .unwrap();
    let msgs = tg.enviados.borrow();
    assert_eq!(msgs.len(), 1);
    let m = &msgs[0];
    assert!(m.contains(TITULO_CICLO), "{m}");
    assert!(m.contains(&format!("erro: {VARIANTE}")), "{m}");
    assert!(m.contains(&format!("fase: {FASE}")), "{m}");
    assert!(m.contains("24/09/2026 09:40"), "{m}");
    assert!(m.contains("host: vps-1"), "{m}");
}

/// UNI-02: a mesma regra de repetição do alerta do worker: 1 envio por variante a cada 2 h.
#[test]
fn repete_so_depois_de_duas_horas() {
    let d = dir_temp("repete");
    let tg = TelegramFake::default();
    let estado = d.join("alerta.json");
    let alerta = |t| alertar("besave-ciclo.service", estado.clone(), &tg, "h".into(), t).unwrap();
    alerta(AGORA);
    alerta(AGORA + 300);
    alerta(AGORA + 2 * 3600 - 1);
    assert_eq!(tg.enviados.borrow().len(), 1);
    alerta(AGORA + 2 * 3600);
    assert_eq!(tg.enviados.borrow().len(), 2);
}

/// UNI-03: o envio tem título e arquivo de estado próprios (como o `besave-envio`).
#[test]
fn envio_tem_titulo_e_estado_proprios() {
    let d = dir_temp("envio");
    let tg = TelegramFake::default();
    alertar(
        "besave-ciclo.service",
        d.join("alerta.json"),
        &tg,
        "h".into(),
        AGORA,
    )
    .unwrap();
    alertar(
        "besave-envio.service",
        d.join("alerta-envio.json"),
        &tg,
        "h".into(),
        AGORA,
    )
    .unwrap();
    let msgs = tg.enviados.borrow();
    assert_eq!(msgs.len(), 2, "estados separados: um não cala o outro");
    assert!(msgs[0].contains(TITULO_CICLO) && !msgs[0].contains(TITULO_ENVIO));
    assert!(msgs[1].contains(TITULO_ENVIO));
}

/// UNI-04: o estado fica ao lado da trava, no mesmo arquivo que o worker usa.
#[test]
fn estado_fica_ao_lado_da_trava() {
    let env = |k: &str| match k {
        "BESAVE_LOCK" => Some(OsString::from("/srv/besave/estado/worker.lock")),
        "BESAVE_ENVIO_LOCK" => Some(OsString::from("/srv/besave/estado/envio.lock")),
        _ => None,
    };
    assert_eq!(
        arquivo_de_estado("besave-ciclo.service", env).unwrap(),
        Path::new("/srv/besave/estado/alerta.json")
    );
    assert_eq!(
        arquivo_de_estado("besave-envio.service", env).unwrap(),
        Path::new("/srv/besave/estado/alerta-envio.json")
    );
}

#[test]
fn unidade_desconhecida_ou_sem_pasta_e_erro_claro() {
    assert!(matches!(
        arquivo_de_estado("sshd.service", |_| Some("/x".into())),
        Err(ErroUnidade::Desconhecida(_))
    ));
    assert!(matches!(
        arquivo_de_estado("besave-ciclo.service", |_| None),
        Err(ErroUnidade::PastaAusente("BESAVE_LOCK"))
    ));
    let tg = TelegramFake::default();
    assert!(alertar("outra.service", PathBuf::from("x"), &tg, "h".into(), AGORA).is_err());
    assert!(tg.enviados.borrow().is_empty());
}

fn worker() -> Command {
    let mut c = Command::new(env!("CARGO_BIN_EXE_besave-worker"));
    for k in [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "BESAVE_LOCK",
        "BESAVE_ENVIO_LOCK",
        "LOCALAPPDATA",
    ] {
        c.env_remove(k);
    }
    c.current_dir(env!("CARGO_MANIFEST_DIR"));
    c
}

/// UNI-05: o subcomando existe (`--help`).
#[test]
fn subcomando_aparece_na_ajuda() {
    let o = worker().arg("--help").output().unwrap();
    let ajuda = String::from_utf8_lossy(&o.stdout);
    assert!(ajuda.contains("--alerta-encerrado"), "{ajuda}");
}

/// UNI-06: sem Telegram configurado, sai com 2 e diz por quê.
#[test]
fn subcomando_sem_telegram_sai_com_2() {
    let d = dir_temp("cli");
    let o = worker()
        .args(["--alerta-encerrado", "besave-ciclo.service"])
        .env("BESAVE_LOCK", d.join("worker.lock"))
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(2), "{o:?}");
    let saida = format!(
        "{}{}",
        String::from_utf8_lossy(&o.stdout),
        String::from_utf8_lossy(&o.stderr)
    );
    assert!(saida.contains("TELEGRAM_BOT_TOKEN"), "{saida}");
    assert!(!d.join("alerta.json").exists());
}

#[test]
fn subcomando_com_unidade_desconhecida_sai_com_2() {
    let o = worker()
        .args(["--alerta-encerrado", "sshd.service"])
        .env("BESAVE_LOCK", "x/worker.lock")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(2));
}
