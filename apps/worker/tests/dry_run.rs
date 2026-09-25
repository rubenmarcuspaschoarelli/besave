//! DRY-01, DRY-02 (e FONTE-04 no binário): `--dry-run` com a fonte fake de demonstração.
//! A fake de demo tem 11 linhas: 3 válidas (as das fixtures), 1 por motivo de rejeição (7)
//! e 1 inativa há 8 dias, que a fonte não entrega.
//! CLI-01..03 (BSV-11): `--gerar --saida` com a mesma fake.

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

fn saida(nome: &str) -> std::path::PathBuf {
    let p = std::env::temp_dir().join(format!("besave-cli-{}-{nome}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    p
}

#[test]
fn gerar_fake_cria_arvore_e_imprime_relatorio() {
    let dir = saida("gerar");
    let out = rodar(&["--gerar", "--saida", dir.to_str().unwrap()], "fake");
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(dir.join("manifest.json").is_file());
    assert!(dir.join("manifest.json.meta.json").is_file());
    let chunks: Vec<_> = std::fs::read_dir(dir.join("data/chunks"))
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    assert!(chunks.iter().any(|c| c.ends_with(".json.br")), "{chunks:?}");
    for linha in [
        "lidas: 10
",
        "validas: 3
",
        "rejeitadas: 7
",
        "chunks_escritos: 1
",
        "chunks_reaproveitados: 0
",
        "chunks_removidos: 0
",
    ] {
        assert!(stdout.contains(linha), "falta {linha:?}: {stdout}");
    }
    for chave in [
        "bytes_totais: ",
        "maior_chunk: n=5 bytes=",
        "versao: ",
        "tempo: ",
    ] {
        assert!(stdout.contains(chave), "falta {chave:?}: {stdout}");
    }
}

#[test]
fn gerar_e_dry_run_juntos_saem_com_erro() {
    let dir = saida("conflito");
    let out = rodar(
        &["--gerar", "--dry-run", "--saida", dir.to_str().unwrap()],
        "fake",
    );
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
    assert!(!dir.join("manifest.json").exists());
}

#[test]
fn gerar_sem_saida_sai_com_erro() {
    let out = rodar(&["--gerar"], "fake");
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
    assert!(String::from_utf8_lossy(&out.stderr).contains("--saida"));
}
