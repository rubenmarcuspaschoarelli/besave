//! Execução agendada (BSV-14): o caminho único do `besave-worker --ciclo` e do `besave-ciclo`
//! (sem console). `.env`, pastas, log em arquivo, trava, retenção, `--publicar --sim`, relatório
//! e alerta; devolve o código de saída do Agendador.

use std::ffi::OsString;
use std::fs::File;
use std::io::IsTerminal;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use tracing::{info, warn};
use tracing_subscriber::EnvFilter;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;

use crate::alerta::{Alertas, ConfigSemNovas, ConfigTelegram, host_do_env};
use crate::aws::{ConfigAws, ContextoAws, ErroAws, PublicadorS3, RedirectsKvs};
use crate::execucao::{Codigo, Falha, concluir, marcar_publicacao_site, rodar};
use crate::fonte::{FonteOfertas, fake_demo};
use crate::geracao::Relatorio;
use crate::logs::{HoraBrasilia, arquivo_do_dia, limpar_antigos};
use crate::mapeamento::Mapeamento;
use crate::oracle::{ConfigOracle, OracleFonte};
use crate::publicador::PublicadorLocal;
use crate::redirects::RedirectsMemoria;
use crate::site::ConfigSite;
use crate::telegram::TelegramHttp;
use crate::trava::Trava;

/// Erros do ciclo fora de `gerar()`; o nome da variante vai para o alerta.
#[derive(Debug, thiserror::Error)]
pub enum ErroCiclo {
    #[error("--env-file {caminho}: {erro}")]
    EnvFile { caminho: String, erro: String },
    #[error("argumento inválido: {0} (use --env-file <arquivo>)")]
    Argumento(String),
    #[error("{0} ausente: defina LOCALAPPDATA ou {0}")]
    PastaAusente(&'static str),
    #[error("BESAVE_IMAGENS_DIR (ou --imagens-dir) é obrigatória com --ciclo")]
    ImagensAusente,
    #[error("BESAVE_FONTE inválida: {0} (use oracle ou fake)")]
    FonteInvalida(String),
}

/// `--env-file <arq>` ou `--env-file=<arq>` nos argumentos (sem o nome do programa).
pub fn env_file_dos_args(args: impl IntoIterator<Item = OsString>) -> Option<PathBuf> {
    let mut args = args.into_iter();
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

/// Texto do erro do `.env` sem o conteúdo da linha: o `LineParse` do `dotenvy` ecoa a linha,
/// que pode ter token ou senha.
fn erro_env_file(e: &dotenvy::Error) -> String {
    match e {
        dotenvy::Error::LineParse(_, pos) => {
            format!("linha malformada (posição {pos}); caminhos do Windows vão entre aspas simples")
        }
        dotenvy::Error::Io(io) => io.to_string(),
        dotenvy::Error::EnvVar(v) => v.to_string(),
        _ => "erro ao ler o arquivo".to_owned(),
    }
}

/// Carrega o `.env` sem sobrescrever o ambiente. Chamar antes de qualquer thread (`set_var`).
pub fn carregar_env_file(p: &Path) -> Result<(), ErroCiclo> {
    dotenvy::from_path(p)
        .map(|_| ())
        .map_err(|e| ErroCiclo::EnvFile {
            caminho: p.display().to_string(),
            erro: erro_env_file(&e),
        })
}

/// Filtro de log: `RUST_LOG` ou `info`.
pub fn filtro() -> EnvFilter {
    EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into())
}

/// Recebe o relatório de um ciclo publicado e o tempo decorrido.
pub type AoPublicar<'a> = &'a dyn Fn(&Relatorio, Duration);

/// Como o binário chama o ciclo.
pub struct Opcoes<'a> {
    /// Override explícito do mapeamento; `None` = o embutido no binário.
    pub mapeamento: Option<PathBuf>,
    pub imagens_dir: Option<PathBuf>,
    /// Log também no stderr (`--ciclo`); o `besave-ciclo` só escreve no arquivo.
    pub stderr: bool,
    /// Chamado com o relatório de um ciclo publicado (o `--ciclo` imprime no stdout).
    pub ao_publicar: Option<AoPublicar<'a>>,
}

impl Opcoes<'_> {
    /// `BESAVE_MAPEAMENTO` (override; sem ela, o mapeamento embutido) e `BESAVE_IMAGENS_DIR`,
    /// sem saída em console.
    pub fn do_env() -> Self {
        let var = |k| std::env::var_os(k).filter(|v: &OsString| !v.is_empty());
        Self {
            mapeamento: var("BESAVE_MAPEAMENTO").map(PathBuf::from),
            imagens_dir: var("BESAVE_IMAGENS_DIR").map(PathBuf::from),
            stderr: false,
            ao_publicar: None,
        }
    }
}

/// Pastas do ciclo: `BESAVE_LOG_DIR`/`BESAVE_LOCK` ou `%LOCALAPPDATA%\besave\…`.
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

/// Arquivo do dia (sem ANSI) e, se `stderr`, também o stderr. Devolve o erro de abertura do
/// arquivo, se houve.
pub fn iniciar_log(
    dir: Option<&Path>,
    agora: i64,
    stderr: bool,
    hora: HoraBrasilia,
) -> Option<std::io::Error> {
    iniciar_log_em(dir.map(|d| (d, arquivo_do_dia(d, agora))), stderr, hora)
}

/// Como `iniciar_log`, com o arquivo já escolhido: `(pasta, arquivo)`.
pub fn iniciar_log_em(
    arquivo: Option<(&Path, PathBuf)>,
    stderr: bool,
    hora: HoraBrasilia,
) -> Option<std::io::Error> {
    let arquivo = arquivo.map(|(d, caminho)| {
        std::fs::create_dir_all(d)
            .and_then(|()| File::options().create(true).append(true).open(caminho))
    });
    let (camada, erro) = match arquivo {
        Some(Ok(f)) => (
            Some(
                tracing_subscriber::fmt::layer()
                    .with_timer(hora)
                    .with_ansi(false)
                    .with_writer(Mutex::new(f)),
            ),
            None,
        ),
        Some(Err(e)) => (None, Some(e)),
        None => (None, None),
    };
    let console = stderr.then(|| {
        tracing_subscriber::fmt::layer()
            .with_timer(hora)
            .with_writer(std::io::stderr)
            .with_ansi(std::io::stderr().is_terminal())
    });
    tracing_subscriber::registry()
        .with(filtro())
        .with(console)
        .with(camada)
        .init();
    erro
}

fn destino_local() -> Option<PathBuf> {
    std::env::var_os("BESAVE_DESTINO_LOCAL")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}

/// `BESAVE_AGORA` (segundos Unix), mas só com `BESAVE_DESTINO_LOCAL` (ensaio e testes):
/// publicação real usa sempre o relógio do sistema.
fn relogio_fixo() -> Option<i64> {
    destino_local()
        .and_then(|_| std::env::var("BESAVE_AGORA").ok())
        .and_then(|v| v.parse().ok())
}

/// Segundos Unix: `relogio_fixo` ou o relógio do sistema.
fn agora() -> i64 {
    relogio_fixo().unwrap_or_else(|| {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |d| i64::try_from(d.as_secs()).unwrap_or(i64::MAX))
    })
}

/// Trava, retenção de logs, `--publicar --sim`, relatório e alerta. `previa`: resultado do
/// `.env`/argumentos, lido pelo binário antes de tudo.
pub fn executar(op: &Opcoes, previa: Option<Result<(), ErroCiclo>>) -> Codigo {
    let inicio = Instant::now();
    let agora = agora();
    let pastas = pastas();
    let dir_logs = pastas.as_ref().ok().map(|p| p.logs.as_path());
    let hora = relogio_fixo().map_or_else(HoraBrasilia::default, |s| HoraBrasilia::fixa(s * 1000));
    if let Some(e) = iniciar_log(dir_logs, agora, op.stderr, hora) {
        warn!(erro = %e, "log em arquivo indisponível");
    }
    let pastas = match pastas {
        Ok(p) => p,
        Err(e) => return concluir(Err(Falha::config("config", &e)), None, agora),
    };
    let sem_novas = match ConfigSemNovas::do_env() {
        Ok(c) => c,
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
        .map(|t| Alertas::new(t, pastas.alerta.clone(), host_do_env()).com_sem_novas(sem_novas));
    let alertas = alertas.as_ref();
    if let Some(Err(e)) = previa {
        let fase = match e {
            ErroCiclo::EnvFile { .. } => "env_file",
            _ => "config",
        };
        return concluir(Err(Falha::config(fase, &e)), alertas, agora);
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
    let resultado = publicar_ciclo(op, agora).map(|rel| {
        if let Some(f) = op.ao_publicar {
            f(&rel, inicio.elapsed());
        }
        let ms = u64::try_from(inicio.elapsed().as_millis()).unwrap_or(u64::MAX);
        (rel, ms)
    });
    let codigo = concluir(resultado, alertas, agora);
    drop(trava);
    codigo
}

/// Para onde o ciclo publica.
enum Destino {
    Aws(ConfigAws),
    /// `BESAVE_DESTINO_LOCAL`: pasta no layout do bucket + KVS em memória (ensaio e testes sem AWS).
    Local(PathBuf),
}

/// Configuração (código 2 se faltar), fonte e destino; depois o mesmo `gerar()` do
/// `--publicar --sim`.
fn publicar_ciclo(op: &Opcoes, agora: i64) -> Result<Relatorio, Falha> {
    let m = Mapeamento::carregar_ou_embutido(op.mapeamento.as_deref())
        .map_err(|e| Falha::config("config", &e))?;
    let destino = match destino_local() {
        Some(dir) => Destino::Local(dir),
        None => Destino::Aws(ConfigAws::do_env().map_err(|e| Falha::config("config", &e))?),
    };
    let dir_imagens = op
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
    let fonte = fonte.as_ref();
    match destino {
        Destino::Local(dir) => {
            warn!(pasta = %dir.display(), "BESAVE_DESTINO_LOCAL definida: publicando na pasta, não no S3");
            let mut pub_ = PublicadorLocal::new(&dir);
            let mut kvs = RedirectsMemoria::new();
            let rel = rodar(fonte, &m, &mut pub_, &mut kvs, &dir_imagens, &site, agora)?;
            // O site não foi publicado de verdade: o canal não pode achar que a página existe.
            info!("BESAVE_DESTINO_LOCAL definida: DT_PUBLICACAO_SITE não gravada");
            Ok(rel)
        }
        Destino::Aws(aws) => {
            let ctx = ContextoAws::carregar().map_err(|e| match e {
                ErroAws::RegiaoAusente | ErroAws::ConfigAusente(_) => {
                    Falha::config("contexto_aws", &e)
                }
                ErroAws::Runtime(_) => Falha::execucao("contexto_aws", &e),
            })?;
            let mut pub_ = PublicadorS3::new(&ctx, &aws.bucket);
            let mut kvs = RedirectsKvs::new(&ctx, &aws.kvs_arn);
            let mut rel = rodar(fonte, &m, &mut pub_, &mut kvs, &dir_imagens, &site, agora)?;
            marcar_publicacao_site(fonte, &mut rel);
            Ok(rel)
        }
    }
}
