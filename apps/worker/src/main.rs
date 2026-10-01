use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs::File;
use std::io::IsTerminal;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Mutex;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use clap::{ArgGroup, Parser};
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use worker::alerta::{Alertas, ConfigTelegram, host_do_env};
use worker::aws::{ConfigAws, ContextoAws, ErroAws, PublicadorS3, RedirectsKvs};
use worker::conversao::{LinhaOferta, LinhaProduto, Rejeicao};
use worker::execucao::{Codigo, Falha, concluir, rodar};
use worker::fonte::{FakeFonte, FonteOfertas};
use worker::geracao::{Relatorio, contar_paginas, gerar};
use worker::logs::{arquivo_do_dia, limpar_antigos};
use worker::mapeamento::Mapeamento;
use worker::oracle::{ConfigOracle, OracleFonte};
use worker::plano::publicar;
use worker::publicador::PublicadorLocal;
use worker::redirects::RedirectsMemoria;
use worker::site::ConfigSite;
use worker::telegram::TelegramHttp;
use worker::trava::Trava;

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
    /// Caminho do mapeamento.json do contrato.
    #[arg(
        long,
        env = "BESAVE_MAPEAMENTO",
        default_value = "../../packages/contract/mapeamento.json"
    )]
    mapeamento: PathBuf,
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

/// Erros do `--ciclo` fora de `gerar()`; o nome da variante vai para o alerta.
#[derive(Debug, thiserror::Error)]
enum ErroCiclo {
    #[error("--env-file {caminho}: {erro}")]
    EnvFile { caminho: String, erro: String },
    #[error("{0} ausente: defina LOCALAPPDATA ou {0}")]
    PastaAusente(&'static str),
    #[error("BESAVE_IMAGENS_DIR (ou --imagens-dir) é obrigatória com --ciclo")]
    ImagensAusente,
    #[error("BESAVE_FONTE inválida: {0} (use oracle ou fake)")]
    FonteInvalida(String),
}

/// `--env-file` direto do `argv`: precisa estar no ambiente antes do `clap` ler os `env =`.
fn env_file_do_argv() -> Option<PathBuf> {
    let mut args = std::env::args_os().skip(1);
    while let Some(a) = args.next() {
        if a == "--" {
            break;
        }
        if a == "--env-file" {
            return args.next().map(PathBuf::from);
        }
        if let Some(v) = a.to_str().and_then(|s| s.strip_prefix("--env-file=")) {
            return Some(PathBuf::from(v));
        }
    }
    None
}

fn main() -> ExitCode {
    // Antes de qualquer thread: `dotenvy` usa `set_var`. Não sobrescreve o que já está definido.
    let carga = env_file_do_argv().map(|p| {
        dotenvy::from_path(&p)
            .map(|_| ())
            .map_err(|e| ErroCiclo::EnvFile {
                caminho: p.display().to_string(),
                erro: e.to_string(),
            })
    });
    let args = Args::parse();
    if args.ciclo {
        return ExitCode::from(ciclo(&args, carga).valor());
    }
    tracing_subscriber::fmt()
        .with_env_filter(filtro())
        .with_writer(std::io::stderr)
        .with_ansi(std::io::stderr().is_terminal())
        .init();
    let r = match carga {
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

fn filtro() -> EnvFilter {
    EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into())
}

fn executar(args: Args) -> Result<()> {
    // `requires` do clap não pega flag booleana (o padrão `false` conta como presente).
    if args.sim && !args.publicar {
        bail!("--sim só vale junto com --publicar");
    }
    let m = Mapeamento::carregar(&args.mapeamento)?;
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
    imprimir_publicacao(&pb.relatorio, inicio);
    Ok(())
}

fn imprimir_publicacao(rel: &Relatorio, inicio: Instant) {
    imprimir_relatorio(rel);
    println!("redirects_put: {}", rel.redirects.puts);
    println!("redirects_del: {}", rel.redirects.dels);
    println!("redirects_total: {}", rel.redirects.total);
    println!("tempo: {:.2}s", inicio.elapsed().as_secs_f64());
}

/// Pastas do `--ciclo`: `BESAVE_LOG_DIR`/`BESAVE_LOCK` ou `%LOCALAPPDATA%esave\…`.
struct Pastas {
    logs: PathBuf,
    trava: PathBuf,
    alerta: PathBuf,
}

fn pastas() -> Result<Pastas, ErroCiclo> {
    let var = |k| {
        std::env::var_os(k)
            .filter(|v: &OsString| !v.is_empty())
            .map(PathBuf::from)
    };
    let base = var("LOCALAPPDATA").map(|d| d.join("besave"));
    let logs = var("BESAVE_LOG_DIR")
        .or_else(|| base.as_ref().map(|b| b.join("logs")))
        .ok_or(ErroCiclo::PastaAusente("BESAVE_LOG_DIR"))?;
    let trava = var("BESAVE_LOCK")
        .or_else(|| base.as_ref().map(|b| b.join("worker.lock")))
        .ok_or(ErroCiclo::PastaAusente("BESAVE_LOCK"))?;
    let alerta = match &base {
        Some(b) => b.join("alerta.json"),
        None => trava.with_file_name("alerta.json"),
    };
    Ok(Pastas {
        logs,
        trava,
        alerta,
    })
}

/// stderr + arquivo do dia (sem ANSI). Devolve o erro de abertura do arquivo, se houve.
fn iniciar_log(dir: Option<&Path>, agora: i64) -> Option<std::io::Error> {
    let arquivo = dir.map(|d| {
        std::fs::create_dir_all(d).and_then(|()| {
            File::options()
                .create(true)
                .append(true)
                .open(arquivo_do_dia(d, agora))
        })
    });
    let (camada, erro) = match arquivo {
        Some(Ok(f)) => (
            Some(
                tracing_subscriber::fmt::layer()
                    .with_ansi(false)
                    .with_writer(Mutex::new(f)),
            ),
            None,
        ),
        Some(Err(e)) => (None, Some(e)),
        None => (None, None),
    };
    tracing_subscriber::registry()
        .with(filtro())
        .with(
            tracing_subscriber::fmt::layer()
                .with_writer(std::io::stderr)
                .with_ansi(std::io::stderr().is_terminal()),
        )
        .with(camada)
        .init();
    erro
}

/// `--ciclo`: trava, retenção de logs, `--publicar --sim`, relatório e alerta.
fn ciclo(args: &Args, carga: Option<Result<(), ErroCiclo>>) -> Codigo {
    let inicio = Instant::now();
    let agora = agora().unwrap_or(0);
    let pastas = pastas();
    if let Some(e) = iniciar_log(pastas.as_ref().ok().map(|p| p.logs.as_path()), agora) {
        warn!(erro = %e, "log em arquivo indisponível; seguindo só com stderr");
    }
    let pastas = match pastas {
        Ok(p) => p,
        Err(e) => return concluir(Err(Falha::config("config", &e)), None, agora),
    };
    let telegram = match ConfigTelegram::do_env() {
        Err(e) => return concluir(Err(Falha::config("config", &e)), None, agora),
        Ok(None) => {
            info!("alerta desligado: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID ausentes");
            None
        }
        Ok(Some(cfg)) => match TelegramHttp::new(cfg) {
            Ok(t) => Some(t),
            Err(e) => {
                warn!(erro = %e, "alerta indisponível: cliente do Telegram não iniciou");
                None
            }
        },
    };
    let alertas = telegram
        .as_ref()
        .map(|t| Alertas::new(t, pastas.alerta.clone(), host_do_env()));
    let alertas = alertas.as_ref();
    if let Some(Err(e)) = carga {
        return concluir(Err(Falha::config("env_file", &e)), alertas, agora);
    }
    let trava = match Trava::adquirir(&pastas.trava, agora) {
        Ok(Some(t)) => t,
        Ok(None) => {
            info!("ciclo anterior em andamento; este foi pulado");
            return Codigo::Ok;
        }
        Err(e) => return concluir(Err(Falha::execucao("trava", &e)), alertas, agora),
    };
    match limpar_antigos(&pastas.logs, agora) {
        Ok(removidos) => {
            for p in removidos {
                info!(arquivo = %p.display(), "log antigo removido");
            }
        }
        Err(e) => warn!(erro = %e, "limpando logs antigos"),
    }
    let resultado = executar_ciclo(args, agora).map(|rel| {
        imprimir_publicacao(&rel, inicio);
        let ms = u64::try_from(inicio.elapsed().as_millis()).unwrap_or(u64::MAX);
        (rel, ms)
    });
    let codigo = concluir(resultado, alertas, agora);
    drop(trava);
    codigo
}

/// Configuração (código 2 se faltar), fonte e destino; depois o mesmo `gerar()` do
/// `--publicar --sim`.
fn executar_ciclo(args: &Args, agora: i64) -> Result<Relatorio, Falha> {
    let m = Mapeamento::carregar(&args.mapeamento).map_err(|e| Falha::config("config", &e))?;
    let aws = ConfigAws::do_env().map_err(|e| Falha::config("config", &e))?;
    let dir_imagens = args
        .imagens_dir
        .clone()
        .ok_or_else(|| Falha::config("config", &ErroCiclo::ImagensAusente))?;
    let site = ConfigSite::do_env().map_err(|e| Falha::config("config", &e))?;
    let fonte: Box<dyn FonteOfertas> = match std::env::var("BESAVE_FONTE").as_deref() {
        Ok("fake") => Box::new(fake_demo(agora)),
        Ok("oracle") | Err(_) => {
            let cfg = ConfigOracle::do_env().map_err(|e| Falha::config("config", &e))?;
            Box::new(
                OracleFonte::conectar(&cfg).map_err(|e| Falha::execucao("conexao_oracle", &e))?,
            )
        }
        Ok(outra) => {
            return Err(Falha::config(
                "config",
                &ErroCiclo::FonteInvalida(outra.to_owned()),
            ));
        }
    };
    let ctx = ContextoAws::carregar().map_err(|e| match e {
        ErroAws::RegiaoAusente | ErroAws::ConfigAusente(_) => Falha::config("contexto_aws", &e),
        ErroAws::Runtime(_) => Falha::execucao("contexto_aws", &e),
    })?;
    let mut pub_ = PublicadorS3::new(&ctx, &aws.bucket);
    let mut kvs = RedirectsKvs::new(&ctx, &aws.kvs_arn);
    rodar(
        fonte.as_ref(),
        &m,
        &mut pub_,
        &mut kvs,
        &dir_imagens,
        &site,
        agora,
    )
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
    let (lidas, validas, rejeitadas) = contar_paginas(fonte, m)?;
    imprimir_contagens(lidas, validas, &rejeitadas);
    Ok(())
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

/// Dados de demonstração: as 3 ofertas das fixtures, uma por motivo de rejeição
/// e uma inativa há 8 dias (fora da fonte).
fn fake_demo(agora: i64) -> FakeFonte {
    const DIA: i64 = 86_400;
    let ok = |id, id_produto, loja: &str, titulo: &str, de, por, area: &str, publico: &str| {
        LinhaOferta {
            id,
            id_produto: Some(id_produto),
            loja: Some(loja.into()),
            titulo: Some(titulo.into()),
            preco_de: de,
            preco_por: Some(por),
            dt_oferta: Some(agora - DIA),
            area: Some(area.into()),
            publico: Some(publico.into()),
            ativo: true,
            url_afiliado: format!("https://loja.example/{id}"),
            ..Default::default()
        }
    };
    let base = ok(1000, 1, "Amazon", "Base", None, 10.0, "Tech", "U");
    let ofertas = vec![
        LinhaOferta {
            cupom: Some("besave10".into()),
            ..ok(
                5412,
                910,
                "Amazon",
                "Fone Bluetooth XYZ com ANC",
                Some(299.9),
                199.9,
                "Tecnologia",
                "Unissex",
            )
        },
        ok(
            5413,
            911,
            "Shopee",
            "Kit Skincare Vitamina C 3 passos",
            None,
            89.9,
            "Elas",
            "Mulher",
        ),
        LinhaOferta {
            ativo: false,
            dt_desativacao: Some(agora - DIA),
            ..ok(
                5420,
                912,
                "MercadoLivre",
                "Ração Premium Cães Adultos 15kg",
                Some(249.0),
                199.0,
                "Pet",
                "U",
            )
        },
        LinhaOferta {
            id: 1001,
            preco_por: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1002,
            titulo: Some("  ".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1003,
            loja: Some("Americanas".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1004,
            area: Some("Moda".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1005,
            publico: Some("Adulto".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1006,
            dt_oferta: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1007,
            id_produto: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1008,
            ativo: false,
            dt_desativacao: Some(agora - 8 * DIA),
            ..base
        },
    ];
    let produtos = vec![LinhaProduto {
        id_produto: 910,
        descricao: Some(
            "Fone over-ear com cancelamento ativo de ruído e 40 horas de bateria.".into(),
        ),
        marca: Some("XYZ".into()),
        preco_min: Some(179.9),
        preco_max: Some(349.9),
        ..Default::default()
    }];
    FakeFonte::new(ofertas, produtos, agora)
}
