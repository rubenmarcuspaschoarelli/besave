//! TRV-01..04 (BSV-14): trava de arquivo do `--ciclo`. Todos os testes capturam o log: com
//! testes sem subscriber em paralelo, o cache de interesse do `tracing` pode descartar o evento.

use std::io::Write;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use worker::trava::Trava;

const AGORA: i64 = 1_790_000_000; // 2026-09-21T14:13:20Z

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

fn caminho(nome: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "besave-trava-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    // Pasta ainda não existe: `adquirir` cria (padrão `%LOCALAPPDATA%\besave\`).
    dir.join("sub").join("worker.lock")
}

/// TRV-01 e TRV-04: com a trava segura, a 2ª aquisição devolve `None`; solta, volta a dar `Some`.
#[test]
fn segunda_aquisicao_espera_a_primeira_soltar() {
    let p = caminho("dupla");
    com_log(|| {
        let primeira = Trava::adquirir(&p, AGORA).unwrap();
        assert!(primeira.is_some());
        assert!(Trava::adquirir(&p, AGORA).unwrap().is_none());
        drop(primeira);
        assert!(Trava::adquirir(&p, AGORA + 1).unwrap().is_some());
    });
}

/// TRV-02: o arquivo registra o PID e o horário de início (lido depois de soltar: no Windows a
/// trava bloqueia leitura por outro handle).
#[test]
fn arquivo_registra_pid_e_inicio() {
    let p = caminho("pid");
    com_log(|| drop(Trava::adquirir(&p, AGORA).unwrap()));
    let txt = std::fs::read_to_string(&p).unwrap();
    assert!(
        txt.contains(&format!("pid={}", std::process::id())),
        "{txt}"
    );
    assert!(txt.contains("inicio=2026-09-21T14:13:20Z"), "{txt}");
    assert!(txt.contains("fim="), "{txt}");
}

/// TRV-03: conteúdo de um processo que morreu sem soltar (sem `fim=`) é tomado com `WARN`
/// que cita o PID anterior.
#[test]
fn trava_orfa_e_tomada_com_warn() {
    let p = caminho("orfa");
    std::fs::create_dir_all(p.parent().unwrap()).unwrap();
    std::fs::write(&p, "pid=999999 inicio=2026-09-21T14:00:00Z\n").unwrap();
    let (t, log) = com_log(|| Trava::adquirir(&p, AGORA).unwrap());
    assert!(t.is_some());
    let warns: Vec<&str> = log.lines().filter(|l| l.contains("WARN")).collect();
    assert_eq!(warns.len(), 1, "{log}");
    assert!(warns[0].contains("pid=999999"), "{log}");
    drop(t);
    let txt = std::fs::read_to_string(&p).unwrap();
    assert!(!txt.contains("999999"), "{txt}");
}

/// TRV-03 × TRV-04: depois de uma liberação normal, a próxima aquisição não é órfã.
#[test]
fn liberacao_normal_nao_gera_warn() {
    let p = caminho("normal");
    com_log(|| drop(Trava::adquirir(&p, AGORA).unwrap()));
    let (t, log) = com_log(|| Trava::adquirir(&p, AGORA + 300).unwrap());
    assert!(t.is_some());
    assert!(!log.contains("WARN"), "{log}");
}
