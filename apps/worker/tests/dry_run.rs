//! DRY-01, DRY-02 (e FONTE-04 no binário): `--dry-run` com a fonte fake de demonstração.
//! A fake de demo tem 11 linhas: 3 válidas (as das fixtures), 1 por motivo de rejeição (7)
//! e 1 inativa há 8 dias, que a fonte não entrega.

use std::process::{Command, Output};

use worker::conversao::Rejeicao;

fn rodar(args: &[&str], fonte: &str) -> Output {
    Command::new(env!("CARGO_BIN_EXE_besave-worker"))
        .args(args)
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("BESAVE_FONTE", fonte)
        .env("RUST_LOG", "warn")
        .env_remove("BESAVE_ORACLE_DSN")
        .env_remove("BESAVE_ORACLE_USER")
        .env_remove("BESAVE_ORACLE_PASS")
        .output()
        .unwrap()
}

#[test]
fn dry_run_fake_imprime_contagens_por_motivo() {
    let out = rodar(&["--dry-run"], "fake");
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(stdout.contains("lidas: 10\n"), "{stdout}");
    assert!(stdout.contains("validas: 3\n"), "{stdout}");
    assert!(stdout.contains("rejeitadas: 7\n"), "{stdout}");
    for r in [
        Rejeicao::PrecoPorInvalido,
        Rejeicao::TituloVazio,
        Rejeicao::LojaSemMapeamento,
        Rejeicao::AreaSemMapeamento,
        Rejeicao::PublicoSemMapeamento,
        Rejeicao::DataNula,
        Rejeicao::IdProdutoAusente,
    ] {
        assert!(
            stdout.contains(&format!("  {r}: 1\n")),
            "falta {r}: {stdout}"
        );
    }
}

#[test]
fn rejeicao_e_logada_com_id_e_motivo() {
    let out = rodar(&["--dry-run"], "fake");
    let stderr = String::from_utf8(out.stderr).unwrap();
    assert!(
        stderr.contains("id=1003 motivo=loja sem mapeamento"),
        "{stderr}"
    );
}

#[test]
fn sem_dry_run_sai_com_erro() {
    let out = rodar(&[], "fake");
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
}

#[test]
fn oracle_sem_config_sai_com_erro_nomeando_a_variavel() {
    let out = rodar(&["--dry-run"], "oracle");
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
    assert!(String::from_utf8_lossy(&out.stderr).contains("BESAVE_ORACLE_DSN"));
}
