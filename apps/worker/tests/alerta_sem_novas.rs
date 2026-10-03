//! SN-01..11 (BSV-14b): alerta de "nenhuma oferta nova" — limiar, lembrete, volta, estado e config.

use std::cell::RefCell;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use worker::alerta::{Alertas, ConfigSemNovas, ErroTelegram, Telegram};

const H: i64 = 3600;
/// 2026-09-24T12:40:00Z = 09:40 em Brasília.
const DT: i64 = 1_790_253_600;
const TOKEN: &str = "123456:ABCdefGHIjkl";

#[derive(Default)]
struct TelegramFake {
    enviados: RefCell<Vec<String>>,
    tentativas: RefCell<u32>,
    falhar: RefCell<bool>,
}

impl Telegram for TelegramFake {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        *self.tentativas.borrow_mut() += 1;
        if *self.falhar.borrow() {
            return Err(ErroTelegram::Http(502));
        }
        self.enviados.borrow_mut().push(texto.to_owned());
        Ok(())
    }
}

impl TelegramFake {
    fn n(&self) -> usize {
        self.enviados.borrow().len()
    }
    fn ultima(&self) -> String {
        self.enviados.borrow().last().cloned().unwrap_or_default()
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
    std::env::temp_dir()
        .join(format!(
            "besave-sn-{nome}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
        .join("alerta.json")
}

fn alertas<'a>(t: &'a TelegramFake, e: &Path, limiar: u64, lembrete: u64) -> Alertas<'a> {
    Alertas::new(t, e.to_path_buf(), "MAQUINA-1".to_owned()).com_sem_novas(ConfigSemNovas {
        limiar_horas: limiar,
        lembrete_horas: lembrete,
    })
}

/// SN-01/02/03: 23 h → 0; 25 h → aviso; até 23h55 depois → 0; 24 h depois → lembrete; 48 h → mais 1;
/// oferta recente → "de novo" com o horário certo; ciclo seguinte → 0.
#[test]
fn aviso_lembretes_e_volta() {
    let t = TelegramFake::default();
    let e = estado("fluxo");
    com_log(|| {
        let a = alertas(&t, &e, 24, 24);
        a.avaliar_novas(Some(DT), 17326, DT + 23 * H);
        assert_eq!(t.n(), 0, "23 h não alerta");

        let aviso = DT + 25 * H;
        a.avaliar_novas(Some(DT), 17326, aviso);
        assert_eq!(t.n(), 1);
        let m = t.ultima();
        assert!(
            m.starts_with("⚠️ Besave: nenhuma oferta nova há 25 h"),
            "{m}"
        );
        assert!(m.contains("última: 24/09 09:40"), "{m}");
        assert!(m.contains("publicadas: 17326"), "{m}");
        assert!(m.contains("host: MAQUINA-1"), "{m}");

        for min in (5..=(24 * 60 - 5)).step_by(5) {
            a.avaliar_novas(Some(DT), 17326, aviso + min * 60);
        }
        assert_eq!(t.n(), 1, "nada até 23h55 depois do aviso");

        a.avaliar_novas(Some(DT), 17326, aviso + 24 * H);
        assert_eq!(t.n(), 2, "lembrete 24 h depois");
        assert!(t.ultima().contains("há 49 h"), "{}", t.ultima());
        a.avaliar_novas(Some(DT), 17326, aviso + 48 * H);
        assert_eq!(t.n(), 3);
        assert!(t.ultima().contains("há 73 h"), "{}", t.ultima());

        let agora = aviso + 50 * H;
        a.avaliar_novas(Some(agora - 600), 17327, agora);
        assert_eq!(t.n(), 4);
        assert_eq!(
            t.ultima(),
            "✅ Besave: ofertas novas de novo (paradas desde 24/09 09:40)"
        );
        a.avaliar_novas(Some(agora - 600), 17327, agora + 300);
        assert_eq!(t.n(), 4, "ciclo seguinte não repete");
    });
}

/// SN-04: lembrete 0 → só aviso e volta, nenhum lembrete em 72 h parado.
#[test]
fn lembrete_zero_so_avisa_e_volta() {
    let t = TelegramFake::default();
    let e = estado("lembrete0");
    com_log(|| {
        let a = alertas(&t, &e, 24, 0);
        let primeiro = DT + 25 * H;
        for h in 0..=72 {
            a.avaliar_novas(Some(DT), 10, primeiro + h * H);
        }
        assert_eq!(t.n(), 1);
        let agora = primeiro + 73 * H;
        a.avaliar_novas(Some(agora - 60), 11, agora);
        assert_eq!(t.n(), 2);
        assert!(t.ultima().starts_with("✅"), "{}", t.ultima());
    });
}

/// SN-04: lembrete 6 → a cada 6 h.
#[test]
fn lembrete_de_seis_horas() {
    let t = TelegramFake::default();
    let e = estado("lembrete6");
    com_log(|| {
        let a = alertas(&t, &e, 24, 6);
        let primeiro = DT + 25 * H;
        for h in 0..=18 {
            a.avaliar_novas(Some(DT), 10, primeiro + h * H);
        }
        // 0, 6, 12, 18 h
        assert_eq!(t.n(), 4);
    });
}

/// SN-05: aviso que falha → WARN, próximo ciclo tenta de novo; lembrete conta do envio entregue.
#[test]
fn aviso_que_falha_tenta_de_novo_e_lembrete_conta_do_entregue() {
    let t = TelegramFake::default();
    let e = estado("falho");
    let (_, log) = com_log(|| {
        let a = alertas(&t, &e, 24, 24);
        let t0 = DT + 25 * H;
        *t.falhar.borrow_mut() = true;
        a.avaliar_novas(Some(DT), 10, t0);
        a.avaliar_novas(Some(DT), 10, t0 + 300);
        assert_eq!(*t.tentativas.borrow(), 2);
        *t.falhar.borrow_mut() = false;
        let entregue = t0 + 600;
        a.avaliar_novas(Some(DT), 10, entregue);
        assert_eq!(t.n(), 1);
        a.avaliar_novas(Some(DT), 10, entregue + 24 * H - 1);
        assert_eq!(t.n(), 1);
        a.avaliar_novas(Some(DT), 10, entregue + 24 * H);
        assert_eq!(t.n(), 2);
    });
    assert!(
        log.lines()
            .any(|l| l.contains("WARN") && l.contains("Telegram")),
        "{log}"
    );
}

/// SN-05: "de novo" que falha não avança o estado; o próximo ciclo tenta de novo.
#[test]
fn volta_que_falha_tenta_no_proximo_ciclo() {
    let t = TelegramFake::default();
    let e = estado("volta-falha");
    com_log(|| {
        let a = alertas(&t, &e, 24, 24);
        a.avaliar_novas(Some(DT), 10, DT + 25 * H);
        assert_eq!(t.n(), 1);
        let agora = DT + 26 * H;
        *t.falhar.borrow_mut() = true;
        a.avaliar_novas(Some(agora - 60), 11, agora);
        *t.falhar.borrow_mut() = false;
        a.avaliar_novas(Some(agora - 60), 11, agora + 300);
        assert_eq!(t.n(), 2);
        assert!(t.ultima().starts_with("✅"));
    });
}

/// SN-06: limiar 0 → nunca avalia.
#[test]
fn limiar_zero_desliga() {
    let t = TelegramFake::default();
    let e = estado("limiar0");
    com_log(|| {
        let a = alertas(&t, &e, 0, 24);
        a.avaliar_novas(Some(DT), 10, DT + 1000 * H);
        a.avaliar_novas(None, 0, DT + 1000 * H);
    });
    assert_eq!(*t.tentativas.borrow(), 0);
}

/// SN-07: valores inválidos → erro que nomeia a variável; ausente → 24/24; `0` vale.
#[test]
fn config_do_env() {
    let env = |pares: &'static [(&'static str, &'static str)]| {
        move |k: &str| {
            pares
                .iter()
                .find(|(c, _)| *c == k)
                .map(|(_, v)| (*v).to_owned())
        }
    };
    let c = ConfigSemNovas::de(env(&[])).unwrap();
    assert_eq!((c.limiar_horas, c.lembrete_horas), (24, 24));
    let c = ConfigSemNovas::de(env(&[
        ("BESAVE_ALERTA_SEM_NOVAS_HORAS", "0"),
        ("BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS", "6"),
    ]))
    .unwrap();
    assert_eq!((c.limiar_horas, c.lembrete_horas), (0, 6));
    for (var, v) in [
        ("BESAVE_ALERTA_SEM_NOVAS_HORAS", "abc"),
        ("BESAVE_ALERTA_SEM_NOVAS_HORAS", "-1"),
        ("BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS", "abc"),
        ("BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS", "-1"),
    ] {
        let erro = ConfigSemNovas::de(move |k| (k == var).then(|| v.to_owned()))
            .unwrap_err()
            .to_string();
        assert!(erro.contains(var), "{erro}");
    }
}

/// SN-08: `alerta.json` da BSV-14 (sem `sem_novas`) carrega e `falhas`/`envios` sobrevivem.
#[test]
fn arquivo_antigo_preserva_falhas_e_envios() {
    let t = TelegramFake::default();
    let e = estado("antigo");
    std::fs::create_dir_all(e.parent().unwrap()).unwrap();
    std::fs::write(
        &e,
        r#"{"falhas":2,"desde":1790000000,"envios":{"Redirects::Kvs":1790000100}}"#,
    )
    .unwrap();
    com_log(|| alertas(&t, &e, 24, 24).avaliar_novas(Some(DT), 10, DT + 25 * H));
    assert_eq!(t.n(), 1);
    let v: serde_json::Value = serde_json::from_slice(&std::fs::read(&e).unwrap()).unwrap();
    assert_eq!(v["falhas"], 2);
    assert_eq!(v["desde"], 1_790_000_000);
    assert_eq!(v["envios"]["Redirects::Kvs"], 1_790_000_100);
    assert!(v["sem_novas"]["ultimo_envio"].is_i64(), "{v}");
}

/// SN-09: falha de ciclo durante um "sem novas" ativo → alerta de falha normal, `sem_novas` intacto;
/// recuperação ainda parada → só "recuperado" (sem "de novo").
#[test]
fn falha_de_ciclo_nao_mexe_em_sem_novas() {
    let t = TelegramFake::default();
    let e = estado("falha-no-meio");
    com_log(|| {
        let a = alertas(&t, &e, 24, 24);
        let t0 = DT + 25 * H;
        a.avaliar_novas(Some(DT), 10, t0);
        assert_eq!(t.n(), 1);
        let antes = std::fs::read_to_string(&e).unwrap();
        let sn_antes: serde_json::Value = serde_json::from_str(&antes).unwrap();

        a.falha("Redirects::Kvs", "redirects", t0 + 300);
        assert_eq!(t.n(), 2);
        assert!(t.ultima().contains("falha no ciclo"), "{}", t.ultima());

        a.sucesso(t0 + 600);
        assert_eq!(t.n(), 3);
        assert!(t.ultima().contains("recuperado"), "{}", t.ultima());
        a.avaliar_novas(Some(DT), 10, t0 + 600);
        assert_eq!(t.n(), 3, "ainda parada: nem de novo, nem novo aviso");

        let v: serde_json::Value = serde_json::from_slice(&std::fs::read(&e).unwrap()).unwrap();
        assert_eq!(v["sem_novas"], sn_antes["sem_novas"]);
    });
}

/// SN-10: sem `http`, token ou `C:\Users\`; com `-03:00`.
#[test]
fn mensagens_limpas() {
    let t = TelegramFake::default();
    let e = estado("limpas");
    let host = worker::alerta::sanitizar_host(Some(r"C:\Users\ruben"));
    com_log(|| {
        let a = Alertas::new(&t, e.clone(), host).com_sem_novas(ConfigSemNovas {
            limiar_horas: 24,
            lembrete_horas: 24,
        });
        a.avaliar_novas(Some(DT), 10, DT + 25 * H);
        a.avaliar_novas(Some(DT + 26 * H - 60), 11, DT + 26 * H);
    });
    assert_eq!(t.n(), 2);
    for m in t.enviados.borrow().iter() {
        assert!(!m.to_lowercase().contains("http"), "{m}");
        assert!(!m.contains(TOKEN), "{m}");
        assert!(!m.contains(r"C:\Users\"), "{m}");
    }
    assert!(t.enviados.borrow()[0].contains("-03:00"));
}

/// SN-11: conjunto vazio conta como "sem novas", com `última: —`.
#[test]
fn conjunto_vazio_alerta_com_traco() {
    let t = TelegramFake::default();
    let e = estado("vazio");
    com_log(|| alertas(&t, &e, 24, 24).avaliar_novas(None, 0, DT));
    assert_eq!(t.n(), 1);
    let m = t.ultima();
    assert!(m.contains("última: —"), "{m}");
    assert!(m.contains("publicadas: 0"), "{m}");
}

/// Sem aviso entregue, oferta nova não manda "de novo".
#[test]
fn volta_sem_aviso_previo_nao_envia() {
    let t = TelegramFake::default();
    let e = estado("sem-aviso");
    com_log(|| alertas(&t, &e, 24, 24).avaliar_novas(Some(DT), 10, DT + H));
    assert_eq!(*t.tentativas.borrow(), 0);
}

const MIN: i64 = 60;

/// Fronteira do limiar (estrito, "mais velho que"): 24 h − 1 min → 0; 24 h + 1 min → 1 aviso.
#[test]
fn limiar_estrito_em_torno_de_24_h() {
    let antes = TelegramFake::default();
    com_log(|| {
        alertas(&antes, &estado("lim-antes"), 24, 24).avaliar_novas(Some(DT), 10, DT + 24 * H - MIN)
    });
    assert_eq!(antes.n(), 0);

    let exato = TelegramFake::default();
    com_log(|| {
        alertas(&exato, &estado("lim-exato"), 24, 24).avaliar_novas(Some(DT), 10, DT + 24 * H)
    });
    assert_eq!(
        exato.n(),
        0,
        "exatamente 24 h ainda não é mais velho que o limiar"
    );

    let depois = TelegramFake::default();
    com_log(|| {
        alertas(&depois, &estado("lim-depois"), 24, 24).avaliar_novas(
            Some(DT),
            10,
            DT + 24 * H + MIN,
        )
    });
    assert_eq!(depois.n(), 1);
}

/// Fronteira do lembrete de 24 h (`>=`): 23h59 depois do aviso entregue → 0; 24h00 → 1.
#[test]
fn lembrete_de_24_h_na_fronteira() {
    let t = TelegramFake::default();
    let e = estado("lemb24");
    com_log(|| {
        let a = alertas(&t, &e, 24, 24);
        let aviso = DT + 25 * H;
        a.avaliar_novas(Some(DT), 10, aviso);
        assert_eq!(t.n(), 1);
        a.avaliar_novas(Some(DT), 10, aviso + 24 * H - MIN);
        assert_eq!(t.n(), 1, "23h59 depois");
        a.avaliar_novas(Some(DT), 10, aviso + 24 * H);
        assert_eq!(t.n(), 2, "24h00 depois");
    });
}

/// Fronteira do lembrete de 6 h: 5h59 → 0; 6h00 → 1.
#[test]
fn lembrete_de_6_h_na_fronteira() {
    let t = TelegramFake::default();
    let e = estado("lemb6");
    com_log(|| {
        let a = alertas(&t, &e, 24, 6);
        let aviso = DT + 25 * H;
        a.avaliar_novas(Some(DT), 10, aviso);
        a.avaliar_novas(Some(DT), 10, aviso + 6 * H - MIN);
        assert_eq!(t.n(), 1, "5h59 depois");
        a.avaliar_novas(Some(DT), 10, aviso + 6 * H);
        assert_eq!(t.n(), 2, "6h00 depois");
    });
}

/// `Alertas::new` sem `com_sem_novas` nasce desligado: nunca avalia.
#[test]
fn sem_configurar_nunca_avalia() {
    let t = TelegramFake::default();
    let e = estado("nao-configurado");
    com_log(|| {
        let a = Alertas::new(&t, e.clone(), "MAQUINA-1".to_owned());
        a.avaliar_novas(Some(DT), 10, DT + 1000 * H);
        a.avaliar_novas(None, 0, DT + 1000 * H);
    });
    assert_eq!(*t.tentativas.borrow(), 0);
}
