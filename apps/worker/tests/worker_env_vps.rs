//! ENV-01 (BSV-43): `infra/vps/worker.env.example` traz toda variável que o worker lê (ciclo e envio),
//! menos as opcionais listadas aqui com o motivo. Lê o código-fonte: variável nova em `src/` sem
//! entrada no modelo nem em `OPCIONAIS` reprova.

use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

/// Lidas pelo worker que ficam fora do `worker.env.example`, com o motivo.
const OPCIONAIS: &[(&str, &str)] = &[
    (
        "LOCALAPPDATA",
        "só Windows; na VPS as pastas vêm de BESAVE_LOG_DIR e das travas",
    ),
    (
        "COMPUTERNAME",
        "só Windows; na VPS o nome do alerta vem de HOSTNAME",
    ),
    (
        "BESAVE_ORACLE_CLIENT_DIR",
        "só Windows; no Linux o Instant Client vem do ldconfig",
    ),
    ("BESAVE_ORACLE_TZ", "padrão -03:00, o fuso do banco"),
    (
        "BESAVE_MAPEAMENTO",
        "sem ela, o mapeamento do contrato embutido no binário",
    ),
    (
        "BESAVE_DESTINO_LOCAL",
        "ensaio e testes: grava numa pasta em vez do S3",
    ),
    ("BESAVE_AGORA", "relógio fixo, só com BESAVE_DESTINO_LOCAL"),
    ("BESAVE_ALERTA_SEM_NOVAS_HORAS", "padrão 24 h"),
    ("BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS", "padrão 24 h"),
    ("BESAVE_CANAL_URL", "padrão https://t.me/besaveofertas"),
    (
        "BESAVE_ENVIO_CANAL",
        "padrão ID_CANAL 1 (@besaveofertas, sql/bsv-40.sql)",
    ),
];

/// Do modelo, mas lidas por bibliotecas (não aparecem em `src/`).
const EXTERNAS: &[(&str, &str)] = &[
    ("TNS_ADMIN", "Oracle Instant Client: pasta da wallet"),
    ("AWS_REGION", "aws-config"),
    ("AWS_PROFILE", "aws-config"),
];

fn raiz() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn arquivos_rs(dir: &Path, saida: &mut Vec<PathBuf>) {
    for e in fs::read_dir(dir).unwrap() {
        let p = e.unwrap().path();
        if p.is_dir() {
            arquivos_rs(&p, saida);
        } else if p.extension().is_some_and(|x| x == "rs") {
            saida.push(p);
        }
    }
}

fn eh_nome(s: &str) -> bool {
    !s.is_empty()
        && s.bytes()
            .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_')
        && s.as_bytes()[0].is_ascii_uppercase()
}

/// Literais de string do código, com a posição da aspa de abertura. Pula comentários, literais de
/// caractere (`'"'`) e strings brutas, e respeita `\"`: senão uma aspa solta desalinha o resto.
fn literais(codigo: &str) -> Vec<(usize, String)> {
    let b = codigo.as_bytes();
    let mut v = Vec::new();
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'/' if b.get(i + 1) == Some(&b'/') => {
                i = codigo[i..].find('\n').map_or(b.len(), |f| i + f);
            }
            b'/' if b.get(i + 1) == Some(&b'*') => {
                i = codigo[i + 2..]
                    .find("*/")
                    .map_or(b.len(), |f| i + 2 + f + 2);
            }
            b'r' if matches!(b.get(i + 1), Some(b'"' | b'#'))
                && (i == 0 || !(b[i - 1].is_ascii_alphanumeric() || b[i - 1] == b'_')) =>
            {
                let hashes = b[i + 1..].iter().take_while(|&&c| c == b'#').count();
                let abre = i + 1 + hashes;
                if b.get(abre) != Some(&b'"') {
                    i += 1;
                    continue;
                }
                let fecho = format!("\"{}", "#".repeat(hashes));
                let f = codigo[abre + 1..].find(&fecho).unwrap();
                v.push((abre, codigo[abre + 1..abre + 1 + f].to_owned()));
                i = abre + 1 + f + fecho.len();
            }
            b'\'' => {
                // Literal de caractere ('x', '\n', 'ç') ou lifetime ('a): só o primeiro é pulado.
                if b.get(i + 1) == Some(&b'\\') {
                    i += 2 + codigo[i + 2..].find('\'').unwrap() + 1;
                } else {
                    let c = codigo[i + 1..].chars().next().map_or(1, char::len_utf8);
                    i += if b.get(i + 1 + c) == Some(&b'\'') {
                        c + 2
                    } else {
                        1
                    };
                }
            }
            b'"' => {
                let mut j = i + 1;
                while b[j] != b'"' {
                    j += if b[j] == b'\\' { 2 } else { 1 };
                }
                v.push((i, codigo[i + 1..j].to_owned()));
                i = j + 1;
            }
            _ => i += 1,
        }
    }
    v
}

/// Nomes de variável lidos em `src/`: literal `BESAVE_*`/`TELEGRAM_*` (inclui as passadas por
/// constante ou closure, `env("BESAVE_…")`) ou literal direto em `var(`, `var_os(` e `env = `.
fn lidas_no_codigo() -> BTreeSet<String> {
    let mut arquivos = Vec::new();
    arquivos_rs(&raiz().join("src"), &mut arquivos);
    let mut nomes = BTreeSet::new();
    for a in arquivos {
        let codigo = fs::read_to_string(&a).unwrap();
        for (i, s) in literais(&codigo) {
            if !eh_nome(&s) {
                continue;
            }
            let antes = codigo[..i].trim_end();
            let chamada = ["var(", "var_os(", "env ="]
                .iter()
                .any(|c| antes.ends_with(c));
            if s.starts_with("BESAVE_") || s.starts_with("TELEGRAM_") || chamada {
                nomes.insert(s);
            }
        }
    }
    nomes
}

fn chaves_do_modelo() -> BTreeSet<String> {
    let texto = fs::read_to_string(raiz().join("../../infra/vps/worker.env.example")).unwrap();
    texto
        .lines()
        .filter(|l| !l.trim_start().starts_with('#'))
        .filter_map(|l| l.split_once('='))
        .map(|(k, _)| k.trim().to_owned())
        .collect()
}

fn nomes(lista: &[(&str, &str)]) -> BTreeSet<String> {
    lista.iter().map(|(k, _)| (*k).to_owned()).collect()
}

#[test]
fn varredura_acha_as_leituras_conhecidas() {
    // Sem isso, um leitor que não acha nada passaria o teste abaixo vazio.
    let lidas = lidas_no_codigo();
    for k in [
        "BESAVE_BUCKET",
        "BESAVE_INDEXAVEL",
        "BESAVE_AVISOS_DIR",
        "BESAVE_ALERTA_SEM_NOVAS_HORAS", // por constante
        "TELEGRAM_CANAL_BOT_TOKEN",
        "LOCALAPPDATA", // var_os("…")
        "HOSTNAME",     // var("…") sem prefixo
    ] {
        assert!(lidas.contains(k), "varredura não achou {k}: {lidas:?}");
    }
}

#[test]
fn modelo_da_vps_traz_toda_variavel_lida() {
    let lidas = lidas_no_codigo();
    let modelo = chaves_do_modelo();
    let opcionais = nomes(OPCIONAIS);
    let externas = nomes(EXTERNAS);

    let faltam: Vec<_> = lidas
        .iter()
        .filter(|k| !modelo.contains(*k) && !opcionais.contains(*k))
        .collect();
    assert!(
        faltam.is_empty(),
        "lidas pelo worker e ausentes do worker.env.example (incluir ou listar em OPCIONAIS com o motivo): {faltam:?}"
    );

    let nas_duas: Vec<_> = opcionais.intersection(&modelo).collect();
    assert!(
        nas_duas.is_empty(),
        "em OPCIONAIS e no modelo ao mesmo tempo: {nas_duas:?}"
    );

    let obsoletas: Vec<_> = opcionais.difference(&lidas).collect();
    assert!(
        obsoletas.is_empty(),
        "em OPCIONAIS mas o worker não lê mais: {obsoletas:?}"
    );

    // Erro de digitação no modelo (BESAVE_INDEXAVL) seria uma variável que ninguém lê.
    let ninguem_le: Vec<_> = modelo
        .iter()
        .filter(|k| !lidas.contains(*k) && !externas.contains(*k))
        .collect();
    assert!(
        ninguem_le.is_empty(),
        "no modelo mas ninguém lê: {ninguem_le:?}"
    );
}
