//! ALR-01..07 (BSV-14): mensagens, anti-spam e configuração do alerta no Telegram.
//! Todos os testes capturam o log (ver `tests/trava.rs`).

use std::cell::RefCell;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use worker::alerta::{Alertas, ConfigTelegram, ErroTelegram, Telegram, sanitizar_host};

/// 2026-09-21T14:13:20Z = 11:13 em Brasília.
const AGORA: i64 = 1_790_000_000;
const DUAS_HORAS: i64 = 7200;
const TOKEN: &str = "123456:ABCdefGHIjkl";

#[derive(Default)]
struct TelegramFake {
    enviados: RefCell<Vec<String>>,
    tentativas: RefCell<u32>,
    falhar: bool,
}

impl Telegram for TelegramFake {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        *self.tentativas.borrow_mut() += 1;
        if self.falhar {
            return Err(ErroTelegram::Http(502));
        }
        self.enviados.borrow_mut().push(texto.to_owned());
        Ok(())
    }
}

#[derive(Clone, Default)]
struct Buffer(Arc<Mutex<Vec<u8>>>);

impl Write for Buffer {
    fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(b);
        Ok(b.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

fn com_log<T>(f: impl FnOnce() -> T) -> (T, String) {
    let buf = Buffer::default();
    let saida = buf.clone();
    let sub = tracing_subscriber::fmt()
        .with_writer(move || saida.clone())
        .with_ansi(false)
        .with_max_level(tracing::Level::INFO)
        .finish();
    let r = tracing::subscriber::with_default(sub, f);
    let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
    (r, log)
}

fn estado(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-alerta-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    d.join("alerta.json")
}

fn alertas<'a>(t: &'a TelegramFake, estado: &Path) -> Alertas<'a> {
    Alertas::new(t, estado.to_path_buf(), "MAQUINA-1".to_owned())
}

/// ALR-01: falha → 1 mensagem com cabeçalho, variante, fase, horário de Brasília e host.
#[test]
fn falha_envia_mensagem_completa() {
    let t = TelegramFake::default();
    let e = estado("completa");
    com_log(|| alertas(&t, &e).falha("Redirects::Kvs", "redirects", AGORA));
    let enviados = t.enviados.borrow();
    assert_eq!(enviados.len(), 1);
    let m = &enviados[0];
    assert!(m.starts_with("⚠️ Besave worker: falha no ciclo"), "{m}");
    assert!(m.contains("erro: Redirects::Kvs"), "{m}");
    assert!(m.contains("fase: redirects"), "{m}");
    assert!(m.contains("21/09/2026 11:13 (-03:00)"), "{m}");
    assert!(m.contains("host: MAQUINA-1"), "{m}");
}

/// ALR-02: mesma variante em < 2 h não envia; com 2 h, envia de novo.
#[test]
fn mesma_variante_respeita_janela_de_duas_horas() {
    let t = TelegramFake::default();
    let e = estado("janela");
    com_log(|| {
        let a = alertas(&t, &e);
        a.falha("Fonte::Oracle", "leitura_fonte", AGORA);
        a.falha("Fonte::Oracle", "leitura_fonte", AGORA + 300);
        a.falha("Fonte::Oracle", "leitura_fonte", AGORA + DUAS_HORAS - 1);
        assert_eq!(t.enviados.borrow().len(), 1);
        a.falha("Fonte::Oracle", "leitura_fonte", AGORA + DUAS_HORAS);
        assert_eq!(t.enviados.borrow().len(), 2);
    });
}

/// Edge: variante diferente na mesma janela tem envio próprio.
#[test]
fn variante_diferente_envia_na_mesma_janela() {
    let t = TelegramFake::default();
    let e = estado("variantes");
    com_log(|| {
        let a = alertas(&t, &e);
        a.falha("Fonte::Oracle", "leitura_fonte", AGORA);
        a.falha("Redirects::Kvs", "redirects", AGORA + 300);
    });
    let enviados = t.enviados.borrow();
    assert_eq!(enviados.len(), 2);
    assert!(enviados[1].contains("erro: Redirects::Kvs"));
}

/// ALR-03: 1º sucesso depois de 3 falhas → "recuperado após 3 falhas (desde 11:13)"; o seguinte não envia.
#[test]
fn sucesso_apos_falhas_envia_recuperado_uma_vez() {
    let t = TelegramFake::default();
    let e = estado("recuperado");
    com_log(|| {
        let a = alertas(&t, &e);
        a.falha("Redirects::Kvs", "redirects", AGORA);
        a.falha("Redirects::Kvs", "redirects", AGORA + 300);
        a.falha("Redirects::Kvs", "redirects", AGORA + 600);
        a.sucesso(AGORA + 900);
        a.sucesso(AGORA + 1200);
    });
    let enviados = t.enviados.borrow();
    assert_eq!(enviados.len(), 2);
    assert_eq!(
        enviados[1],
        "✅ Besave worker: recuperado após 3 falhas (desde 11:13)"
    );
}

/// ALR-03: sucesso sem falha anterior não envia nada.
#[test]
fn sucesso_sem_falha_nao_envia() {
    let t = TelegramFake::default();
    let e = estado("limpo");
    com_log(|| alertas(&t, &e).sucesso(AGORA));
    assert_eq!(*t.tentativas.borrow(), 0);
}

/// ALR-03: depois do "recuperado", uma nova falha da mesma variante alerta de novo (estado zerado).
#[test]
fn recuperado_zera_a_janela() {
    let t = TelegramFake::default();
    let e = estado("zera");
    com_log(|| {
        let a = alertas(&t, &e);
        a.falha("Redirects::Kvs", "redirects", AGORA);
        a.sucesso(AGORA + 300);
        a.falha("Redirects::Kvs", "redirects", AGORA + 600);
    });
    assert_eq!(t.enviados.borrow().len(), 3);
}

/// ALR-04: nenhuma mensagem contém `http`, o token ou `C:\Users\`, mesmo com host vindo de um caminho.
#[test]
fn mensagens_nao_vazam_url_token_nem_caminho() {
    let t = TelegramFake::default();
    let e = estado("vazamento");
    let host = sanitizar_host(Some(r"C:\Users\ruben"));
    com_log(|| {
        let a = Alertas::new(&t, e.clone(), host);
        a.falha("Redirects::Kvs", "redirects", AGORA);
        a.sucesso(AGORA + 300);
    });
    let enviados = t.enviados.borrow();
    assert_eq!(enviados.len(), 2);
    for m in enviados.iter() {
        assert!(!m.to_lowercase().contains("http"), "{m}");
        assert!(!m.contains(TOKEN), "{m}");
        assert!(!m.contains(r"C:\Users\"), "{m}");
    }
}

/// ALR-04: host só com `[A-Za-z0-9._-]`, até 63 caracteres; vazio ou ausente vira `desconhecido`.
#[test]
fn host_e_sanitizado() {
    assert_eq!(sanitizar_host(Some("BESAVE-PC")), "BESAVE-PC");
    assert_eq!(sanitizar_host(Some(r"a\b/c:d e")), "abcde");
    assert_eq!(sanitizar_host(Some(&"x".repeat(80))).len(), 63);
    assert_eq!(sanitizar_host(Some("///")), "desconhecido");
    assert_eq!(sanitizar_host(None), "desconhecido");
}

/// ALR-05: envio que falha loga `WARN`, não registra o envio e a falha seguinte tenta de novo.
#[test]
fn envio_que_falha_loga_warn_e_tenta_de_novo() {
    let t = TelegramFake {
        falhar: true,
        ..Default::default()
    };
    let e = estado("envio-falho");
    let (_, log) = com_log(|| {
        let a = alertas(&t, &e);
        a.falha("Redirects::Kvs", "redirects", AGORA);
        a.falha("Redirects::Kvs", "redirects", AGORA + 300);
    });
    assert_eq!(*t.tentativas.borrow(), 2);
    assert!(
        log.lines()
            .any(|l| l.contains("WARN") && l.contains("Telegram")),
        "{log}"
    );
}

/// Edge: "recuperado" que falha mantém o estado; o próximo sucesso tenta com o mesmo N.
#[test]
fn recuperado_que_falha_fica_para_o_proximo_sucesso() {
    let e = estado("recuperado-falho");
    com_log(|| {
        let ok = TelegramFake::default();
        alertas(&ok, &e).falha("Redirects::Kvs", "redirects", AGORA);
        let ruim = TelegramFake {
            falhar: true,
            ..Default::default()
        };
        alertas(&ruim, &e).sucesso(AGORA + 300);
        assert_eq!(*ruim.tentativas.borrow(), 1);
        alertas(&ok, &e).sucesso(AGORA + 600);
        assert_eq!(
            ok.enviados.borrow().last().unwrap(),
            "✅ Besave worker: recuperado após 1 falhas (desde 11:13)"
        );
    });
}

/// Edge: `alerta.json` corrompido → `WARN` e estado vazio (a falha alerta).
#[test]
fn estado_corrompido_vira_estado_vazio() {
    let t = TelegramFake::default();
    let e = estado("corrompido");
    std::fs::create_dir_all(e.parent().unwrap()).unwrap();
    std::fs::write(&e, "{ isto não é json").unwrap();
    let (_, log) = com_log(|| alertas(&t, &e).falha("Redirects::Kvs", "redirects", AGORA));
    assert_eq!(t.enviados.borrow().len(), 1);
    assert!(log.lines().any(|l| l.contains("WARN")), "{log}");
}

/// ALR-06: sem as duas variáveis → desligado; com as duas → ligado; só uma → erro que nomeia a ausente.
#[test]
fn config_telegram_exige_as_duas_ou_nenhuma() {
    let env = |pares: &'static [(&'static str, &'static str)]| {
        move |k: &str| {
            pares
                .iter()
                .find(|(c, _)| *c == k)
                .map(|(_, v)| (*v).to_owned())
        }
    };
    assert!(ConfigTelegram::de(env(&[])).unwrap().is_none());
    assert!(
        ConfigTelegram::de(env(&[("TELEGRAM_BOT_TOKEN", ""), ("TELEGRAM_CHAT_ID", "")]))
            .unwrap()
            .is_none()
    );
    let c = ConfigTelegram::de(env(&[
        ("TELEGRAM_BOT_TOKEN", TOKEN),
        ("TELEGRAM_CHAT_ID", "-100123"),
    ]))
    .unwrap()
    .unwrap();
    assert_eq!(c.token(), TOKEN);
    assert_eq!(c.chat_id, "-100123");
    let erro = ConfigTelegram::de(env(&[("TELEGRAM_BOT_TOKEN", TOKEN)]))
        .unwrap_err()
        .to_string();
    assert!(erro.contains("TELEGRAM_CHAT_ID"), "{erro}");
    assert!(!erro.contains(TOKEN), "{erro}");
    let erro = ConfigTelegram::de(env(&[("TELEGRAM_CHAT_ID", "-100123")]))
        .unwrap_err()
        .to_string();
    assert!(erro.contains("TELEGRAM_BOT_TOKEN"), "{erro}");
}

/// ALR-07: `Debug` da configuração não mostra o token.
#[test]
fn debug_da_config_mascara_o_token() {
    let c = ConfigTelegram::de(|k| match k {
        "TELEGRAM_BOT_TOKEN" => Some(TOKEN.to_owned()),
        "TELEGRAM_CHAT_ID" => Some("-100123".to_owned()),
        _ => None,
    })
    .unwrap()
    .unwrap();
    let d = format!("{c:?}");
    assert!(!d.contains(TOKEN), "{d}");
    assert!(!d.contains("ABCdef"), "{d}");
}
