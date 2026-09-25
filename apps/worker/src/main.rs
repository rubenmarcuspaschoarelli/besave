use std::collections::BTreeMap;
use std::io::IsTerminal;
use std::path::PathBuf;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use clap::{ArgGroup, Parser};
use tracing::warn;
use tracing_subscriber::EnvFilter;
use worker::conversao::{LinhaOferta, LinhaProduto, Rejeicao, para_pagina};
use worker::fonte::{FakeFonte, FonteOfertas};
use worker::geracao::gerar;
use worker::mapeamento::Mapeamento;
use worker::oracle::{ConfigOracle, OracleFonte};
use worker::publicador::PublicadorLocal;

/// Worker Besave. Fonte por `BESAVE_FONTE` (`oracle` | `fake`).
#[derive(Parser)]
#[command(version)]
#[command(group(ArgGroup::new("modo").required(true).args(["dry_run", "gerar"])))]
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
    let m = Mapeamento::carregar(&args.mapeamento)?;
    let agora = agora()?;
    let fonte: Box<dyn FonteOfertas> = match std::env::var("BESAVE_FONTE").as_deref() {
        Ok("fake") => Box::new(fake_demo(agora)),
        Ok("oracle") | Err(_) => Box::new(
            OracleFonte::conectar(&ConfigOracle::do_env()?).context("conectando ao Oracle")?,
        ),
        Ok(outra) => bail!("BESAVE_FONTE inválida: {outra} (use oracle ou fake)"),
    };
    match args.saida {
        Some(saida) if args.gerar => gerar_em(fonte.as_ref(), &m, saida, agora),
        _ => dry_run(fonte.as_ref(), &m),
    }
}

fn gerar_em(fonte: &dyn FonteOfertas, m: &Mapeamento, saida: PathBuf, agora: i64) -> Result<()> {
    let inicio = Instant::now();
    let mut pub_ = PublicadorLocal::new(&saida);
    let rel = gerar(fonte, m, &mut pub_, agora)
        .with_context(|| format!("gerando em {}", saida.display()))?;
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
    println!("tempo: {:.2}s", inicio.elapsed().as_secs_f64());
    Ok(())
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
