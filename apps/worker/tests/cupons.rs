//! SEP-01..05 (BSV-50): separação de `DS_CUPOM` em códigos. Casos reais do log de 20/10.

use std::io::Write;
use std::sync::{Arc, Mutex};

use worker::conversao::separar_cupons;

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
        .with_max_level(tracing::Level::WARN)
        .finish();
    let r = tracing::subscriber::with_default(sub, f);
    let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
    (r, log)
}

fn separar(bruto: &str) -> Vec<String> {
    separar_cupons(1, Some(bruto))
}

// SEP-01
#[test]
fn tres_codigos_do_log_real() {
    assert_eq!(
        separar("MELI26TODOSITE | SITEMELI26 | MELI26SITETODO"),
        ["MELI26TODOSITE", "SITEMELI26", "MELI26SITETODO"]
    );
}

#[test]
fn dois_codigos_do_log_real() {
    assert_eq!(
        separar("ISDIN15D | SMARTWATCHES10"),
        ["ISDIN15D", "SMARTWATCHES10"]
    );
}

#[test]
fn um_codigo_continua_igual() {
    assert_eq!(separar("BESAVE10"), ["BESAVE10"]);
}

#[test]
fn espacos_e_minusculas() {
    assert_eq!(
        separar("  besave10 |a_b-c  |\tx1 "),
        ["BESAVE10", "A_B-C", "X1"]
    );
}

#[test]
fn limite_de_30_caracteres_por_codigo() {
    let trinta = "A".repeat(30);
    let trinta_e_um = "B".repeat(31);
    assert_eq!(separar(&format!("{trinta}|{trinta_e_um}")), [trinta]);
}

// SEP-02
#[test]
fn duplicados_saem_mantendo_a_ordem() {
    assert_eq!(separar("B | A | b | C | A"), ["B", "A", "C"]);
}

// SEP-03
#[test]
fn no_maximo_cinco_o_resto_sai_com_warn() {
    let (v, log) = com_log(|| separar_cupons(777, Some("A|B|C|D|E|F|G")));
    assert_eq!(v, ["A", "B", "C", "D", "E"]);
    assert!(log.contains("777"), "{log}");
    assert!(log.contains("WARN"), "{log}");
}

#[test]
fn exatamente_cinco_nao_gera_warn() {
    let (v, log) = com_log(|| separar("A|B|C|D|E"));
    assert_eq!(v.len(), 5);
    assert!(log.is_empty(), "{log}");
}

#[test]
fn duplicado_nao_conta_para_o_limite() {
    assert_eq!(separar("A|A|B|C|D|E"), ["A", "B", "C", "D", "E"]);
}

// SEP-04
#[test]
fn parte_invalida_sai_com_warn_de_id_e_parte() {
    let (v, log) = com_log(|| separar_cupons(4242, Some("BOM10 | ruim cupom | OK-2 | R$5")));
    assert_eq!(v, ["BOM10", "OK-2"]);
    assert!(log.contains("4242"), "{log}");
    assert!(log.contains("RUIM CUPOM"), "{log}");
    assert!(log.contains("R$5"), "{log}");
}

#[test]
fn parte_vazia_entre_barras_nao_e_invalida() {
    let (v, log) = com_log(|| separar("A || B |"));
    assert_eq!(v, ["A", "B"]);
    assert!(log.is_empty(), "{log}");
}

// SEP-05
#[test]
fn so_invalidos_ou_vazio_ou_ausente_sem_cupom() {
    assert!(separar("ruim cupom | outro!").is_empty());
    assert!(separar("   ").is_empty());
    assert!(separar("|").is_empty());
    assert!(separar_cupons(1, None).is_empty());
}
