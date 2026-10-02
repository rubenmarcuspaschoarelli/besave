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
        // Só usada por `--gerar`; `--dry-run` ignora, e o valor nunca precisa existir no disco
        // (regra 5: pasta ausente vira `sem_origem`, nunca bloqueia).
        .env(
            "BESAVE_IMAGENS_DIR",
            std::env::temp_dir().join("besave-worker-cli-testes-sem-imagens"),
        )
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

/// Fix 4 (validation.md): `--gerar` sem `BESAVE_IMAGENS_DIR` sai com erro nomeando a variável,
/// sem panic (mesmo padrão de `publicar_sem_bucket_nomeia_a_variavel`).
#[test]
fn gerar_sem_imagens_dir_nomeia_a_variavel() {
    let dir = saida("sem-imagens-dir");
    let out = Command::new(env!("CARGO_BIN_EXE_besave-worker"))
        .args(["--gerar", "--saida", dir.to_str().unwrap()])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("BESAVE_FONTE", "fake")
        .env("RUST_LOG", "warn")
        .env_remove("BESAVE_IMAGENS_DIR")
        .env_remove("BESAVE_ORACLE_DSN")
        .env_remove("BESAVE_ORACLE_USER")
        .env_remove("BESAVE_ORACLE_PASS")
        .output()
        .unwrap();
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("BESAVE_IMAGENS_DIR"),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(!dir.join("manifest.json").exists());
}

// AWS-03, AWS-04 (BSV-12): `--publicar` valida a config antes de qualquer acesso à rede.

fn publicar(args: &[&str], env: &[(&str, &str)]) -> Output {
    let mut c = Command::new(env!("CARGO_BIN_EXE_besave-worker"));
    c.args(args)
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("BESAVE_FONTE", "fake")
        .env("RUST_LOG", "warn");
    for v in [
        "BESAVE_BUCKET",
        "BESAVE_KVS_ARN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "AWS_REGION",
    ] {
        c.env_remove(v);
    }
    c.envs(env.iter().copied()).output().unwrap()
}

fn falha_sem_panic(out: &Output) -> String {
    assert!(!out.status.success(), "{:?}", out.status);
    assert_ne!(out.status.code(), Some(101), "panic");
    String::from_utf8_lossy(&out.stderr).into_owned()
}

#[test]
fn publicar_sem_bucket_nomeia_a_variavel() {
    let stderr = falha_sem_panic(&publicar(&["--publicar"], &[]));
    assert!(stderr.contains("BESAVE_BUCKET"), "{stderr}");
}

#[test]
fn publicar_sem_arn_da_kvs_nomeia_a_variavel() {
    let stderr = falha_sem_panic(&publicar(
        &["--publicar", "--sim"],
        &[("BESAVE_BUCKET", "besave-site")],
    ));
    assert!(stderr.contains("BESAVE_KVS_ARN"), "{stderr}");
    assert!(!stderr.contains("BESAVE_BUCKET"), "{stderr}");
}

#[test]
fn sim_sem_publicar_sai_com_erro() {
    let stderr = falha_sem_panic(&publicar(&["--sim"], &[]));
    assert!(stderr.contains("--publicar"), "{stderr}");
    let stderr = falha_sem_panic(&publicar(&["--dry-run", "--sim"], &[]));
    assert!(stderr.contains("--publicar"), "{stderr}");
}

#[test]
fn publicar_e_gerar_juntos_saem_com_erro() {
    let dir = saida("publicar-gerar");
    falha_sem_panic(&publicar(
        &["--publicar", "--gerar", "--saida", dir.to_str().unwrap()],
        &[],
    ));
    assert!(!dir.join("manifest.json").exists());
}

// BSV-21: páginas, CSS, sitemap e robots no `--gerar`; config do site por env.

fn gerar_com(nome: &str, env: &[(&str, &str)]) -> (std::path::PathBuf, Output) {
    let dir = saida(nome);
    let mut c = Command::new(env!("CARGO_BIN_EXE_besave-worker"));
    c.args(["--gerar", "--saida", dir.to_str().unwrap()])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .env("BESAVE_FONTE", "fake")
        .env(
            "BESAVE_IMAGENS_DIR",
            std::env::temp_dir().join("besave-worker-cli-testes-sem-imagens"),
        )
        .env("RUST_LOG", "warn")
        .env_remove("BESAVE_BASE_URL")
        .env_remove("BESAVE_INDEXAVEL");
    for (k, v) in env {
        c.env(k, v);
    }
    (dir, c.output().unwrap())
}

/// SIT-01 no binário + relatório de páginas.
#[test]
fn gerar_fake_publica_paginas_e_imprime_relatorio_do_site() {
    let (dir, out) = gerar_com("site", &[]);
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    for id in [5412, 5413, 5420] {
        assert!(
            dir.join(format!("oferta/{id}/index.html")).is_file(),
            "{id}"
        );
    }
    assert!(dir.join("assets/besave.css").is_file());
    assert!(dir.join("sitemap.xml").is_file());
    assert!(dir.join("_estado/paginas.json").is_file());
    assert_eq!(
        std::fs::read_to_string(dir.join("robots.txt")).unwrap(),
        "User-agent: *\nDisallow: /\n"
    );
    for linha in [
        "paginas_renderizadas: 3\n",
        "paginas_publicadas: 3\n",
        "paginas_inalteradas: 0\n",
        "paginas_removidas: 0\n",
        "paginas_falhas: 0\n",
        "css_publicado: true\n",
        "sitemaps_publicados: 2\n",
        "robots_publicado: true\n",
    ] {
        assert!(stdout.contains(linha), "falta {linha:?}: {stdout}");
    }
    for chave in ["maior_html: ", "tempo_render_ms: "] {
        assert!(stdout.contains(chave), "falta {chave:?}: {stdout}");
    }
}

/// SIT-09/SIT-15 no binário: `BESAVE_INDEXAVEL=true` + `BESAVE_BASE_URL` chegam ao robots e ao sitemap.
#[test]
fn gerar_indexavel_usa_a_base_do_env() {
    let (dir, out) = gerar_com(
        "indexavel",
        &[
            ("BESAVE_INDEXAVEL", "true"),
            ("BESAVE_BASE_URL", "https://d1.cloudfront.net"),
        ],
    );
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let robots = std::fs::read_to_string(dir.join("robots.txt")).unwrap();
    assert!(
        robots.contains("Sitemap: https://d1.cloudfront.net/sitemap.xml"),
        "{robots}"
    );
    let sitemap = std::fs::read_to_string(dir.join("sitemap-1.xml")).unwrap();
    assert!(
        sitemap.contains("<loc>https://d1.cloudfront.net/oferta/5412/</loc>"),
        "{sitemap}"
    );
}

/// SIT-15 no binário: valor inválido falha nomeando a variável, sem panic e sem gerar nada.
#[test]
fn gerar_com_indexavel_invalida_nomeia_a_variavel() {
    let (dir, out) = gerar_com("indexavel-invalida", &[("BESAVE_INDEXAVEL", "talvez")]);
    assert!(!out.status.success());
    assert_ne!(out.status.code(), Some(101), "panic");
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("BESAVE_INDEXAVEL"), "{stderr}");
    assert!(!dir.join("manifest.json").exists());
}

/// REL-02 (BSV-12c): o relatório impresso traz o modo da sincronização da KVS e o motivo da
/// reconstrução. No `--gerar` a KVS é sempre uma `RedirectsMemoria` nova e a saída não tem índice.
#[test]
fn gerar_fake_imprime_modo_e_motivo_dos_redirects() {
    let dir = saida("redirects-modo");
    let out = rodar(&["--gerar", "--saida", dir.to_str().unwrap()], "fake");
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(
        stdout.contains(
            "
redirects_modo: reconstrucao
"
        ),
        "{stdout}"
    );
    assert!(
        stdout.contains(
            "
redirects_motivo_reconstrucao: indice_ausente
"
        ),
        "{stdout}"
    );
    assert!(dir.join("_estado/redirects.json").exists());
}

/// TMP-02 (BSV-13b): `--gerar` imprime uma linha `t_<fase>: <n> ms` por medida e a contagem de
/// chaves estranhas de imagem. Confere presença e formato, não valores.
#[test]
fn gerar_fake_imprime_tempo_por_fase() {
    let dir = saida("tempos");
    let out = rodar(&["--gerar", "--saida", dir.to_str().unwrap()], "fake");
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    for medida in [
        "t_leitura_fonte",
        "t_imagens",
        "t_imagens_listagem",
        "t_chunks",
        "t_paginas",
        "t_redirects",
        "t_redirects_listagem",
        "t_manifest",
        "t_orfaos",
    ] {
        let prefixo = format!("{medida}: ");
        let linha = stdout
            .lines()
            .find(|l| l.starts_with(&prefixo))
            .unwrap_or_else(|| panic!("falta {medida}: {stdout}"));
        let valor = linha[prefixo.len()..]
            .strip_suffix(" ms")
            .unwrap_or_else(|| panic!("{linha:?} sem unidade ms"));
        assert!(valor.parse::<u64>().is_ok(), "{linha:?}");
    }
    assert!(stdout.contains("imagens_chaves_estranhas: 0\n"), "{stdout}");
}

/// BSV-14 CIC-08: o modo manual também usa o mapeamento embutido; pasta de trabalho fora do
/// repo e sem `BESAVE_MAPEAMENTO` funciona.
#[test]
fn dry_run_fora_do_repo_usa_mapeamento_embutido() {
    let fora = std::env::temp_dir().join(format!("besave-dry-run-fora-{}", std::process::id()));
    std::fs::create_dir_all(&fora).unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_besave-worker"))
        .arg("--dry-run")
        .current_dir(&fora)
        .env("BESAVE_FONTE", "fake")
        .env("RUST_LOG", "warn")
        .env_remove("BESAVE_MAPEAMENTO")
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("validas: 3\n"), "{stdout}");
    assert!(stdout.contains("rejeitadas: 7\n"), "{stdout}");
}
