use std::collections::BTreeMap;
use std::io::IsTerminal;
use std::path::PathBuf;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use clap::{ArgGroup, Parser};
use tracing::warn;
use tracing_subscriber::EnvFilter;
use worker::aws::{ConfigAws, ContextoAws, PublicadorS3, RedirectsKvs};
use worker::conversao::{LinhaOferta, LinhaProduto, Rejeicao, para_pagina};
use worker::fonte::{FakeFonte, FonteOfertas};
use worker::geracao::{Relatorio, gerar};
use worker::mapeamento::Mapeamento;
use worker::oracle::{ConfigOracle, OracleFonte};
use worker::plano::publicar;
use worker::publicador::PublicadorLocal;
use worker::redirects::RedirectsMemoria;

/// Worker Besave. Fonte por `BESAVE_FONTE` (`oracle` | `fake`).
#[derive(Parser)]
#[command(version)]
#[command(group(ArgGroup::new("modo").required(true).args(["dry_run", "gerar", "publicar"])))]
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
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with_writer(std::io::stderr)
        .with_ansi(std::io::stderr().is_terminal())
        .init();

    let args = Args::parse();
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
    let fonte: Box<dyn FonteOfertas> = match std::env::var("BESAVE_FONTE").as_deref() {
        Ok("fake") => Box::new(fake_demo(agora)),
        Ok("oracle") | Err(_) => Box::new(
            OracleFonte::conectar(&ConfigOracle::do_env()?).context("conectando ao Oracle")?,
        ),
        Ok(outra) => bail!("BESAVE_FONTE inválida: {outra} (use oracle ou fake)"),
    };
    match (args.saida, aws) {
        (Some(saida), _) if args.gerar => gerar_em(fonte.as_ref(), &m, saida, agora),
        (_, Some(cfg)) => publicar_aws(fonte.as_ref(), &m, &cfg, agora, args.sim),
        _ => dry_run(fonte.as_ref(), &m),
    }
}

fn publicar_aws(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    cfg: &ConfigAws,
    agora: i64,
    sim: bool,
) -> Result<()> {
    let inicio = Instant::now();
    let ctx = ContextoAws::carregar()?;
    let mut pub_ = PublicadorS3::new(&ctx, &cfg.bucket);
    let mut kvs = RedirectsKvs::new(&ctx, &cfg.kvs_arn);
    let pb = publicar(fonte, m, &mut pub_, &mut kvs, agora, sim)
        .with_context(|| format!("publicando em s3://{}", cfg.bucket))?;
    if !sim {
        println!("PLANO: nada foi escrito. Rode com --sim para executar.");
        println!("bucket: {}", cfg.bucket);
        println!("kvs: {}", cfg.kvs_arn);
        for op in pb.plano.objetos.iter().chain(&pb.plano.redirects) {
            println!("  {op}");
        }
    }
    imprimir_relatorio(&pb.relatorio);
    println!("redirects_put: {}", pb.relatorio.redirects.puts);
    println!("redirects_del: {}", pb.relatorio.redirects.dels);
    println!("redirects_total: {}", pb.relatorio.redirects.total);
    println!("tempo: {:.2}s", inicio.elapsed().as_secs_f64());
    Ok(())
}

fn gerar_em(fonte: &dyn FonteOfertas, m: &Mapeamento, saida: PathBuf, agora: i64) -> Result<()> {
    let inicio = Instant::now();
    let mut pub_ = PublicadorLocal::new(&saida);
    // Espelho local não tem KVS: os redirects só existem no `--publicar`.
    let rel = gerar(fonte, m, &mut pub_, &mut RedirectsMemoria::new(), agora)
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
}

fn dry_run(fonte: &dyn FonteOfertas, m: &Mapeamento) -> Result<()> {
    let linhas = fonte.ofertas()?;
    let mut validas = 0u64;
    let mut rejeitadas: BTreeMap<Rejeicao, u64> = BTreeMap::new();
    for l in &linhas {
        let produto = match l.id_produto {
            Some(id) => fonte.produto(id)?,
            None => None,
        };
        match para_pagina(l, produto.as_ref(), m) {
            Ok(_) => validas += 1,
            Err(r) => {
                warn!(id = l.id, motivo = %r, "oferta rejeitada");
                *rejeitadas.entry(r).or_default() += 1;
            }
        }
    }
    imprimir_contagens(linhas.len() as u64, validas, &rejeitadas);
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
