//! FONTE-03..06: config da OracleFonte só por env, erro nomeando a variável ausente ou inválida.

use std::collections::HashMap;

use worker::fonte::ErroFonte;
use worker::oracle::{ConfigOracle, SQL_OFERTAS};

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

fn com(extra: &[(&'static str, &'static str)]) -> Vec<(&'static str, &'static str)> {
    let mut v = COMPLETO.to_vec();
    v.extend_from_slice(extra);
    v
}

#[test]
fn fuso_padrao_e_menos_tres_horas_em_segundos() {
    let c = ConfigOracle::de(env(&COMPLETO)).unwrap();
    assert_eq!(c.fuso_segundos, -3 * 3600);
}

#[test]
fn fuso_aceita_offsets_com_sinal() {
    for (tz, seg) in [
        ("-03:00", -10800),
        ("+05:30", 19800),
        ("+00:00", 0),
        ("-02:00", -7200),
    ] {
        let c = ConfigOracle::de(env(&com(&[("BESAVE_ORACLE_TZ", tz)]))).unwrap();
        assert_eq!(c.fuso_segundos, seg, "{tz}");
    }
}

#[test]
fn fuso_por_nome_de_regiao_ou_malformado_e_rejeitado_nomeando_a_variavel() {
    for tz in [
        "America/Sao_Paulo",
        "UTC",
        "-3:00",
        "03:00",
        "-03:60",
        "-15:00",
        "-03:0x",
    ] {
        match ConfigOracle::de(env(&com(&[("BESAVE_ORACLE_TZ", tz)]))) {
            Err(ErroFonte::ConfigInvalida(v, _)) => assert_eq!(v, "BESAVE_ORACLE_TZ", "{tz}"),
            Err(e) => panic!("{tz}: erro inesperado: {e}"),
            Ok(_) => panic!("aceitou fuso {tz}"),
        }
    }
}

#[test]
fn client_dir_e_opcional() {
    let sem = ConfigOracle::de(env(&COMPLETO)).unwrap();
    assert_eq!(sem.client_dir, None);
    let vazio = ConfigOracle::de(env(&com(&[("BESAVE_ORACLE_CLIENT_DIR", "")]))).unwrap();
    assert_eq!(vazio.client_dir, None);
    let dir = r"C:\oraclexe\app\instantclient_19_30";
    let c = ConfigOracle::de(env(&com(&[("BESAVE_ORACLE_CLIENT_DIR", dir)]))).unwrap();
    assert_eq!(c.client_dir.as_deref(), Some(dir));
}

/// ORA-01882 no XE 11.2 com Instant Client 19: a query não pode depender de região de fuso.
#[test]
fn sql_de_ofertas_nao_usa_funcoes_de_fuso() {
    let sql = SQL_OFERTAS.to_uppercase();
    for f in [
        "FROM_TZ",
        "SYS_EXTRACT_UTC",
        "AT TIME ZONE",
        "SESSIONTIMEZONE",
        "DBTIMEZONE",
    ] {
        assert!(!sql.contains(f), "SQL usa {f}");
    }
    assert!(sql.contains("ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7"));
}

/// URL-01: a KVS de redirects precisa da URL de afiliado.
#[test]
fn sql_de_ofertas_le_url_de_afiliado() {
    assert!(SQL_OFERTAS.contains("DS_URL_AFILIADO"));
}
