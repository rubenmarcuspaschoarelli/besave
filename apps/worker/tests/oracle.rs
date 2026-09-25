//! FONTE-03, FONTE-04: config da OracleFonte só por env, erro nomeando a variável ausente.

use std::collections::HashMap;

use worker::fonte::ErroFonte;
use worker::oracle::ConfigOracle;

fn env(pares: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
    let m: HashMap<String, String> = pares
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
    move |k| m.get(k).cloned()
}

const COMPLETO: [(&str, &str); 3] = [
    ("BESAVE_ORACLE_DSN", "localhost/XE"),
    ("BESAVE_ORACLE_USER", "besave"),
    ("BESAVE_ORACLE_PASS", "segredo"),
];

#[test]
fn cada_variavel_ausente_e_nomeada() {
    for faltando in [
        "BESAVE_ORACLE_DSN",
        "BESAVE_ORACLE_USER",
        "BESAVE_ORACLE_PASS",
    ] {
        let pares: Vec<_> = COMPLETO
            .iter()
            .copied()
            .filter(|(k, _)| *k != faltando)
            .collect();
        match ConfigOracle::de(env(&pares)) {
            Err(ErroFonte::ConfigAusente(v)) => assert_eq!(v, faltando),
            Err(e) => panic!("erro inesperado: {e}"),
            Ok(_) => panic!("aceitou sem {faltando}"),
        }
    }
}

#[test]
fn variavel_vazia_conta_como_ausente() {
    let mut pares = COMPLETO.to_vec();
    pares[2] = ("BESAVE_ORACLE_PASS", "");
    assert!(matches!(
        ConfigOracle::de(env(&pares)),
        Err(ErroFonte::ConfigAusente("BESAVE_ORACLE_PASS"))
    ));
}

#[test]
fn config_completa_le_as_tres_variaveis_e_fuso_padrao() {
    let c = ConfigOracle::de(env(&COMPLETO)).unwrap();
    assert_eq!(c.dsn, "localhost/XE");
    assert_eq!(c.usuario, "besave");
    assert_eq!(c.fuso, "-03:00");
}
