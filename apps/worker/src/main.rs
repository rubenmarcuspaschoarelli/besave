use std::collections::BTreeMap;
use std::io::IsTerminal;
use std::path::PathBuf;
use std::process::ExitCode;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use clap::{ArgGroup, Parser};
use worker::alerta::horas_sem_novas;
use worker::aws::{ConfigAws, ContextoAws, PublicadorS3, RedirectsKvs};
use worker::ciclo;
use worker::conversao::Rejeicao;
use worker::execucao::dt_max_texto;
use worker::fonte::{FonteOfertas, fake_demo};
use worker::geracao::{Relatorio, contar_paginas_dt, gerar};
use worker::logs::HoraBrasilia;
use worker::mapeamento::Mapeamento;
use worker::oracle::{ConfigOracle, OracleFonte};
use worker::plano::publicar;
use worker::publicador::PublicadorLocal;
use worker::redirects::RedirectsMemoria;
use worker::site::ConfigSite;

/// Worker Besave. Fonte por `BESAVE_FONTE` (`oracle` | `fake`).
#[derive(Parser)]
#[command(version)]
#[command(group(ArgGroup::new("modo").required(true).args(["dry_run", "gerar", "publicar", "ciclo"])))]
struct Args {
    /// Lê a fonte, converte e imprime contagens; não gera nem publica nada.
    #[arg(long)]
    dry_run: bool,
    /// Gera chunks e manifest.json em `--saida`, no layout do bucket.
    #[arg(long, requires = "saida")]
    gerar: bool,
    /// Pasta de saída do `--gerar` (criada se não existir).
    #[arg(long, requires = "gerar")]
    saida: Option<PathBuf>,
    /// Publica no bucket (`BESAVE_BUCKET`) e sincroniza a KVS (`BESAVE_KVS_ARN`). Sem `--sim`,
    /// só imprime o plano.
    #[arg(long)]
    publicar: bool,
    /// Executa o `--publicar` (sem ele, nada é escrito).
    #[arg(long)]
    sim: bool,
    /// Override do mapeamento.json; sem ele, o mapeamento do contrato embutido no binário.
    #[arg(long, env = "BESAVE_MAPEAMENTO")]
    mapeamento: Option<PathBuf>,
    /// Raiz das imagens do robô: `{dir}/{id}/{id}[-small].webp`. Obrigatória com `--gerar` e
    /// `--publicar` (BSV-13); `--dry-run` não publica nada e não precisa dela.
    #[arg(long, env = "BESAVE_IMAGENS_DIR")]
    imagens_dir: Option<PathBuf>,
    /// Execução agendada (BSV-14): `--publicar --sim` com trava, log em arquivo e alerta no
    /// Telegram. Sai com 0 (ok ou ciclo anterior em andamento), 1 (falha) ou 2 (configuração).
    #[arg(long)]
    ciclo: bool,
    /// `.env` fora do repo, lido antes de tudo; variável já definida no ambiente vence.
    #[arg(long)]
    env_file: Option<PathBuf>,
}

fn main() -> ExitCode {
    // Antes de qualquer thread: `dotenvy` usa `set_var`. `.env` antes do `clap`, que lê os
    // `env =`; não sobrescreve o que já está definido.
    let previa =
        ciclo::env_file_dos_args(std::env::args_os().skip(1)).map(|p| ciclo::carregar_env_file(&p));
    let args = Args::parse();
    if args.ciclo {
        let op = ciclo::Opcoes {
            mapeamento: args.mapeamento,
            imagens_dir: args.imagens_dir,
            stderr: true,
            ao_publicar: Some(&imprimir_publicacao),
        };
        return ExitCode::from(ciclo::executar(&op, previa).valor());
    }
    tracing_subscriber::fmt()
        .with_timer(HoraBrasilia::default())
        .with_env_filter(ciclo::filtro())
        .with_writer(std::io::stderr)
        .with_ansi(std::io::stderr().is_terminal())
        .init();
    let r = match previa {
        Some(Err(e)) => Err(e.into()),
        _ => executar(args),
    };
    match r {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("Error: {e:?}");
            ExitCode::FAILURE
        }
    }
}

fn executar(args: Args) -> Result<()> {
    // `requires` do clap não pega flag booleana (o padrão `false` conta como presente).
    if args.sim && !args.publicar {
        bail!("--sim só vale junto com --publicar");
    }
    let m = Mapeamento::carregar_ou_embutido(args.mapeamento.as_deref())?;
    let agora = agora()?;
    // Config do destino antes de abrir o Oracle: erro de env não gasta conexão.
    let aws = if args.publicar {
        Some(ConfigAws::do_env()?)
    } else {
        None
    };
    if (args.gerar || args.publicar) && args.imagens_dir.is_none() {
        bail!("BESAVE_IMAGENS_DIR (ou --imagens-dir) é obrigatória com --gerar ou --publicar");
    }
    // `BESAVE_BASE_URL`/`BESAVE_INDEXAVEL`: também antes do Oracle.
    let site = if args.gerar || args.publicar {
        ConfigSite::do_env()?
    } else {
        ConfigSite::default()
    };
    let fonte: Box<dyn FonteOfertas> = match std::env::var("BESAVE_FONTE").as_deref() {
        Ok("fake") => Box::new(fake_demo(agora)),
        Ok("oracle") | Err(_) => Box::new(
            OracleFonte::conectar(&ConfigOracle::do_env()?).context("conectando ao Oracle")?,
        ),
        Ok(outra) => bail!("BESAVE_FONTE inválida: {outra} (use oracle ou fake)"),
    };
    match (args.saida, aws) {
        (Some(saida), _) if args.gerar => {
            let dir_imagens = args
                .imagens_dir
                .ok_or_else(|| anyhow::anyhow!("BESAVE_IMAGENS_DIR ausente"))?;
            gerar_em(fonte.as_ref(), &m, saida, &dir_imagens, &site, agora)
        }
        (_, Some(cfg)) => {
            let dir_imagens = args
                .imagens_dir
                .ok_or_else(|| anyhow::anyhow!("BESAVE_IMAGENS_DIR ausente"))?;
            publicar_aws(
                fonte.as_ref(),
                &m,
                &cfg,
                &dir_imagens,
                &site,
                agora,
                args.sim,
            )
        }
        _ => dry_run(fonte.as_ref(), &m),
    }
}

fn publicar_aws(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    cfg: &ConfigAws,
    dir_imagens: &std::path::Path,
    site: &ConfigSite,
    agora: i64,
    sim: bool,
) -> Result<()> {
    let inicio = Instant::now();
    let ctx = ContextoAws::carregar()?;
    let mut pub_ = PublicadorS3::new(&ctx, &cfg.bucket);
    let mut kvs = RedirectsKvs::new(&ctx, &cfg.kvs_arn);
    let pb = publicar(fonte, m, &mut pub_, &mut kvs, dir_imagens, site, agora, sim)
        .with_context(|| format!("publicando em s3://{}", cfg.bucket))?;
    if !sim {
        println!("PLANO: nada foi escrito. Rode com --sim para executar.");
        println!("bucket: {}", cfg.bucket);
        println!("kvs: {}", cfg.kvs_arn);
        for linha in pb.plano.linhas() {
            println!("{linha}");
        }
    }
    imprimir_publicacao(&pb.relatorio, inicio.elapsed());
    Ok(())
}

fn imprimir_publicacao(rel: &Relatorio, tempo: Duration) {
    imprimir_relatorio(rel);
    println!("redirects_put: {}", rel.redirects.puts);
    println!("redirects_del: {}", rel.redirects.dels);
    println!("redirects_total: {}", rel.redirects.total);
    println!("tempo: {:.2}s", tempo.as_secs_f64());
}

fn gerar_em(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    saida: PathBuf,
    dir_imagens: &std::path::Path,
    site: &ConfigSite,
    agora: i64,
) -> Result<()> {
    let inicio = Instant::now();
    let mut pub_ = PublicadorLocal::new(&saida);
    // Espelho local não tem KVS: os redirects só existem no `--publicar`.
    let rel = gerar(
        fonte,
        m,
        &mut pub_,
        &mut RedirectsMemoria::new(),
        dir_imagens,
        site,
        agora,
    )
    .with_context(|| format!("gerando em {}", saida.display()))?;
    imprimir_relatorio(&rel);
    println!("tempo: {:.2}s", inicio.elapsed().as_secs_f64());
    Ok(())
}

fn imprimir_relatorio(rel: &Relatorio) {
    imprimir_contagens(rel.lidas, rel.validas, &rel.rejeitadas);
    println!("chunks_escritos: {}", rel.chunks_escritos);
    println!("chunks_reaproveitados: {}", rel.chunks_reaproveitados);
    println!("chunks_removidos: {}", rel.chunks_removidos);
    println!("bytes_totais: {}", rel.bytes_totais);
    match rel.maior_chunk {
        Some((n, bytes)) => println!("maior_chunk: n={n} bytes={bytes}"),
        None => println!("maior_chunk: -"),
    }
    println!("versao: {}", rel.versao);
    imprimir_dt_max(rel.dt_mais_recente);
    println!("redirects_modo: {}", rel.redirects.modo);
    println!(
        "redirects_motivo_reconstrucao: {}",
        rel.redirects.motivo_texto()
    );
    let img = &rel.imagens;
    println!("imagens_publicadas: {}", img.publicadas);
    println!("imagens_reaproveitadas: {}", img.reaproveitadas);
    println!("imagens_sem_origem: {}", img.sem_origem);
    println!("imagens_reprocessadas: {}", img.reprocessadas);
    println!("imagens_falhas: {}", img.falhas.len());
    for (id, motivo) in &img.falhas {
        println!("  {id}: {motivo}");
    }
    println!("imagens_maior_small: {}", img.maior_small);
    println!("imagens_maior_grande: {}", img.maior_grande);
    println!("imagens_chaves_estranhas: {}", img.chaves_estranhas);
    let site = &rel.site;
    let pag = &site.paginas;
    println!("paginas_renderizadas: {}", pag.renderizadas);
    println!("paginas_publicadas: {}", pag.publicadas);
    println!("paginas_inalteradas: {}", pag.inalteradas);
    println!("paginas_removidas: {}", pag.removidas);
    println!("paginas_falhas: {}", pag.falhas.len());
    for id in &pag.falhas {
        println!("  {id}");
    }
    println!("maior_html: {}", pag.maior_html);
    println!("tempo_render_ms: {}", pag.tempo_render_ms);
    println!("css_publicado: {}", site.css_publicado);
    println!("sitemaps_publicados: {}", site.sitemaps_publicados);
    println!("sitemaps_removidos: {}", site.sitemaps_removidos);
    println!("robots_publicado: {}", site.robots_publicado);
    let t = &rel.tempos;
    for (nome, v) in [
        ("t_leitura_fonte", t.leitura_fonte),
        ("t_imagens", t.imagens),
        ("t_imagens_listagem", t.imagens_listagem),
        ("t_chunks", t.chunks),
        ("t_paginas", t.paginas),
        ("t_redirects", t.redirects),
        ("t_redirects_listagem", t.redirects_listagem),
        ("t_manifest", t.manifest),
        ("t_orfaos", t.orfaos),
    ] {
        println!("{nome}: {v} ms");
    }
}

fn dry_run(fonte: &dyn FonteOfertas, m: &Mapeamento) -> Result<()> {
    let (lidas, validas, rejeitadas, dt_max) = contar_paginas_dt(fonte, m)?;
    imprimir_contagens(lidas, validas, &rejeitadas);
    imprimir_dt_max(dt_max);
    Ok(())
}

fn imprimir_dt_max(dt: Option<i64>) {
    println!("dt_max: {}", dt_max_texto(dt));
    match horas_sem_novas(dt, agora().unwrap_or_default()) {
        Some(h) => println!("horas_sem_novas: {h}"),
        None => println!("horas_sem_novas: -"),
    }
}

fn imprimir_contagens(lidas: u64, validas: u64, rejeitadas: &BTreeMap<Rejeicao, u64>) {
    println!("lidas: {lidas}");
    println!("validas: {validas}");
    println!("rejeitadas: {}", rejeitadas.values().sum::<u64>());
    for (r, n) in rejeitadas {
        println!("  {r}: {n}");
    }
}

fn agora() -> Result<i64> {
    let s = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    Ok(i64::try_from(s)?)
}
