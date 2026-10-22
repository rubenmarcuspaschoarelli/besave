//! UNT-01..: as unidades systemd de `infra/vps/` (BSV-47): `OnFailure=`, `TimeoutStartSec=15min`
//! e a unidade de alerta sem segredo, lendo só o `.env`. `systemd-analyze verify` roda no
//! workflow `worker-arm64` (precisa de systemd); aqui se confere o conteúdo.

use std::fs;
use std::path::{Path, PathBuf};

fn vps() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../infra/vps")
}

fn ler(nome: &str) -> String {
    fs::read_to_string(vps().join(nome))
        .unwrap()
        .replace("\r\n", "\n")
}

/// Linhas sem comentário nem vazias.
fn ativas(texto: &str) -> Vec<&str> {
    texto
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .collect()
}

/// Valores de `chave=` na seção `secao`.
fn valores(texto: &str, secao: &str, chave: &str) -> Vec<String> {
    let mut dentro = false;
    let mut v = Vec::new();
    for l in ativas(texto) {
        if let Some(s) = l.strip_prefix('[').and_then(|r| r.strip_suffix(']')) {
            dentro = s == secao;
        } else if dentro && let Some(r) = l.strip_prefix(chave).and_then(|r| r.strip_prefix('=')) {
            v.push(r.to_owned());
        }
    }
    v
}

#[test]
fn ciclo_e_envio_disparam_o_alerta_e_tem_timeout_de_15_minutos() {
    for u in ["besave-ciclo.service", "besave-envio.service"] {
        let t = ler(u);
        assert_eq!(
            valores(&t, "Unit", "OnFailure"),
            ["besave-alerta@%n.service"],
            "{u}"
        );
        assert_eq!(valores(&t, "Service", "TimeoutStartSec"), ["15min"], "{u}");
    }
}

#[test]
fn unidade_de_alerta_roda_o_subcomando_e_le_so_o_env() {
    let t = ler("besave-alerta@.service");
    assert_eq!(valores(&t, "Service", "Type"), ["oneshot"]);
    assert_eq!(
        valores(&t, "Service", "EnvironmentFile"),
        ["/srv/besave/worker.env"]
    );
    assert_eq!(
        valores(&t, "Service", "ExecStart"),
        ["/srv/besave/bin/besave-worker --alerta-encerrado %i"]
    );
    // Nenhum segredo nem variável embutida na unidade.
    assert!(valores(&t, "Service", "Environment").is_empty());
    let corpo = ativas(&t).join("\n");
    for proibido in ["TOKEN", "CHAT_ID", "PASS", "SECRET", "KEY="] {
        assert!(!corpo.contains(proibido), "{proibido}");
    }
    // Roda como as outras, sem privilégio extra.
    assert_eq!(valores(&t, "Service", "User"), ["besave"]);
    assert_eq!(valores(&t, "Service", "NoNewPrivileges"), ["yes"]);
}

/// ENV-02: o modelo do `.env` traz as chaves da AWS no lugar do perfil, a região e a regra das aspas.
#[test]
fn modelo_do_env_traz_chaves_aws_regiao_e_aspas_simples() {
    let t = ler("worker.env.example");
    let chaves: Vec<&str> = ativas(&t)
        .into_iter()
        .filter_map(|l| l.split_once('=').map(|(k, _)| k))
        .collect();
    for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"] {
        assert!(chaves.contains(&k), "falta {k}: {chaves:?}");
    }
    assert!(!chaves.contains(&"AWS_PROFILE"), "{chaves:?}");
    assert!(
        t.contains("ASPAS SIMPLES"),
        "aspas simples não documentadas"
    );
    assert!(
        t.contains("BESAVE_ORACLE_PASS='"),
        "exemplo com aspas simples"
    );
}
