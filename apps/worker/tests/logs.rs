//! LOG-01, LOG-02 (BSV-14): arquivo do dia (data de Brasília) e retenção de 14 dias.

use std::path::{Path, PathBuf};

use worker::logs::{arquivo_do_dia, limpar_antigos};

/// 2026-10-01T03:00:00Z = 2026-10-01 00:00 em Brasília (-03:00).
const VIRADA: i64 = 1_790_823_600;

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-logs-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn nomes(dir: &Path) -> Vec<String> {
    let mut v: Vec<String> = std::fs::read_dir(dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    v.sort();
    v
}

/// LOG-01: um arquivo por dia de Brasília; vira às 03:00 UTC.
#[test]
fn arquivo_do_dia_usa_a_data_de_brasilia() {
    let dir = Path::new("logs");
    assert_eq!(
        arquivo_do_dia(dir, VIRADA - 1),
        dir.join("besave-worker.2026-09-30.log")
    );
    assert_eq!(
        arquivo_do_dia(dir, VIRADA),
        dir.join("besave-worker.2026-10-01.log")
    );
}

/// LOG-02: com hoje = 2026-10-01, 2026-09-17 (14 dias) fica e 2026-09-16 (15 dias) sai;
/// arquivos que não são log do worker ficam.
#[test]
fn remove_so_logs_com_mais_de_14_dias() {
    let dir = dir_temp("retencao");
    for n in [
        "besave-worker.2026-08-01.log",
        "besave-worker.2026-09-16.log",
        "besave-worker.2026-09-17.log",
        "besave-worker.2026-09-30.log",
        "besave-worker.2026-10-01.log",
        "besave-worker.lixo.log",
        "outro.2026-08-01.log",
        "notas.txt",
    ] {
        std::fs::write(dir.join(n), "x").unwrap();
    }
    let mut removidos = limpar_antigos(&dir, VIRADA + 3600).unwrap();
    removidos.sort();
    assert_eq!(
        removidos,
        vec![
            dir.join("besave-worker.2026-08-01.log"),
            dir.join("besave-worker.2026-09-16.log"),
        ]
    );
    assert_eq!(
        nomes(&dir),
        vec![
            "besave-worker.2026-09-17.log",
            "besave-worker.2026-09-30.log",
            "besave-worker.2026-10-01.log",
            "besave-worker.lixo.log",
            "notas.txt",
            "outro.2026-08-01.log",
        ]
    );
}

/// LOG-02: o limite segue o dia de Brasília. Às 23:59 de 30/09 (Brasília), 2026-09-16 tem 14 dias.
#[test]
fn retencao_conta_dias_de_brasilia() {
    let dir = dir_temp("fuso");
    std::fs::write(dir.join("besave-worker.2026-09-16.log"), "x").unwrap();
    assert!(limpar_antigos(&dir, VIRADA - 60).unwrap().is_empty());
    assert_eq!(nomes(&dir), vec!["besave-worker.2026-09-16.log"]);
}

/// LOG-05: carimbo `AAAA-MM-DDTHH:MM:SS.mmm-03:00`, Brasília com offset fixo; 01:30Z cai às
/// 22:30 do dia anterior.
#[test]
fn carimbo_em_brasilia_com_milissegundos() {
    use worker::logs::carimbo_brasilia;
    // 2026-10-02T14:45:00Z
    assert_eq!(
        carimbo_brasilia(1_790_952_300_000),
        "2026-10-02T11:45:00.000-03:00"
    );
    // 2026-10-02T01:30:00.123Z
    assert_eq!(
        carimbo_brasilia(1_790_904_600_123),
        "2026-10-01T22:30:00.123-03:00"
    );
}
