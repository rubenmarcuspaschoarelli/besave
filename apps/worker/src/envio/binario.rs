//! `besave-envio` (BSV-40): `.env`, pastas, log diário próprio, trava própria, alerta próprio,
//! estado de pausa, `--sim`; devolve o código de saída do Agendador (0, 1, 2, como a BSV-14).

use std::ffi::OsString;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::time::Instant;

use tracing::{error, info, warn};

use crate::alerta::{Alertas, ConfigTelegram, TITULO_ENVIO, host_do_env};
use crate::ciclo::{ErroCiclo, iniciar_log_em};
use crate::envio::canal::{CanalTelegram, ErroCanal, Relogio, RelogioSistema};
use crate::envio::foto::foto;
use crate::envio::http::{CanalTelegramHttp, ConfigCanal};
use crate::envio::oracle::OracleEnvio;
use crate::envio::rodada::{Contexto, EstadoEnvio, RelatorioEnvio, Simulacao, rodar, simular};
use crate::execucao::{Codigo, Falha};
use crate::logs::{HoraBrasilia, PREFIXO_ENVIO, arquivo_do_dia_de, limpar_antigos_de};
use crate::mapeamento::Mapeamento;
use crate::oracle::ConfigOracle;

/// Canal padrão (`@besaveofertas`, `sql/bsv-40.sql`).
pub const CANAL_PADRAO: i64 = 1;

#[derive(Debug, thiserror::Error)]
pub enum ErroBinario {
    #[error("BESAVE_ENVIO_CANAL inválida: {0} (use o ID_CANAL, inteiro)")]
    CanalInvalido(String),
}

/// Argumentos: `--sim`, `--env-file <arq>` ou `--env-file=<arq>`, em qualquer ordem.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Argumentos {
    pub sim: bool,
    pub env_file: Option<PathBuf>,
}

pub fn argumentos(args: &[OsString]) -> Result<Argumentos, ErroCiclo> {
    let mut a = Argumentos::default();
    let mut it = args.iter();
    let invalido = || {
        let texto: Vec<_> = args.iter().map(|a| a.to_string_lossy()).collect();
        ErroCiclo::Argumento(texto.join(" "))
    };
    while let Some(x) = it.next() {
        if x == "--sim" && !a.sim {
            a.sim = true;
        } else if x == "--env-file" && a.env_file.is_none() {
            a.env_file = Some(PathBuf::from(it.next().ok_or_else(invalido)?));
        } else if let Some(v) = x
            .to_str()
            .and_then(|s| s.strip_prefix("--env-file="))
            .filter(|_| a.env_file.is_none())
        {
            a.env_file = Some(PathBuf::from(v));
        } else {
            return Err(invalido());
        }
    }
    Ok(a)
}

struct Pastas {
    logs: PathBuf,
    trava: PathBuf,
    alerta: PathBuf,
    estado: PathBuf,
}

/// `BESAVE_LOG_DIR` (o mesmo do ciclo), `BESAVE_ENVIO_LOCK` ou `%LOCALAPPDATA%\besave\…`.
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
    let trava = var("BESAVE_ENVIO_LOCK")
        .or_else(|| base.as_ref().map(|b| b.join("envio.lock")))
        .ok_or(ErroCiclo::PastaAusente("BESAVE_ENVIO_LOCK"))?;
    let junto = |nome: &str| match &base {
        Some(b) => b.join(nome),
        None => trava.with_file_name(nome),
    };
    Ok(Pastas {
        logs,
        alerta: junto("alerta-envio.json"),
        estado: junto("envio-estado.json"),
        trava,
    })
}

fn canal_do_env() -> Result<i64, ErroBinario> {
    match std::env::var("BESAVE_ENVIO_CANAL") {
        Ok(v) if !v.trim().is_empty() => {
            v.trim().parse().map_err(|_| ErroBinario::CanalInvalido(v))
        }
        _ => Ok(CANAL_PADRAO),
    }
}

fn var_caminho(k: &str) -> Option<PathBuf> {
    std::env::var_os(k)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}

/// Loga o relatório (ou a falha) e avisa o bot de alertas. O alerta nunca muda o código.
fn concluir(
    resultado: Result<(RelatorioEnvio, u64), Falha>,
    alertas: Option<&Alertas>,
    agora: i64,
) -> Codigo {
    match resultado {
        Ok((rel, ms)) => {
            info!("relatorio {}", rel.linha(ms));
            if let Some(a) = alertas {
                a.sucesso(agora);
            }
            Codigo::Ok
        }
        Err(f) => {
            error!(fase = %f.fase, variante = %f.variante, erro = %f.erro, "falha no envio");
            if let Some(a) = alertas {
                a.falha(&f.variante, f.fase, agora);
            }
            f.codigo
        }
    }
}

/// Texto do `--sim` (stdout e `sim.txt`).
pub fn texto_simulacao(sim: &Simulacao, fotos: &[PathBuf]) -> String {
    let mut t = String::new();
    let _ = writeln!(
        t,
        "enviados hoje: {}\nlote devido agora: {}\nsilencioso agora: {}\nexpiradas a editar: {}",
        sim.enviados_hoje,
        sim.devido,
        if sim.silencioso { "sim" } else { "não" },
        sim.expiradas
    );
    match &sim.aviso {
        Some(a) => {
            let _ = writeln!(
                t,
                "\n--- aviso {} ({}, {})\n{}",
                a.id,
                if a.jpeg.is_some() {
                    "sendPhoto"
                } else {
                    "sendMessage"
                },
                if sim.na_janela {
                    "na janela: vai agora"
                } else {
                    "fora da janela: não vai agora"
                },
                a.legenda
            );
        }
        None => {
            let _ = writeln!(t, "nenhum aviso devido agora");
        }
    }
    if let Some(p) = sim.parada {
        let _ = writeln!(t, "parada: {p:?}");
    }
    if sim.previas.is_empty() {
        let _ = writeln!(t, "nenhuma candidata agora");
    }
    for (i, p) in sim.previas.iter().enumerate() {
        let foto = fotos
            .get(i)
            .map_or_else(|| "-".to_owned(), |f| f.display().to_string());
        let _ = writeln!(
            t,
            "\n--- oferta {} (foto: {:?} → {foto})\n{}",
            p.id, p.origem, p.legenda
        );
    }
    t
}

/// Grava as fotos e o texto do `--sim` em `{temp}/besave-envio-sim/` e imprime o texto.
fn mostrar_simulacao(sim: &Simulacao) {
    let dir = std::env::temp_dir().join("besave-envio-sim");
    let mut fotos = Vec::new();
    if let Err(e) = std::fs::create_dir_all(&dir) {
        warn!(erro = %e, "criando a pasta do --sim");
    }
    for p in &sim.previas {
        let caminho = dir.join(format!("{}.jpg", p.id));
        match std::fs::write(&caminho, &p.jpeg) {
            Ok(()) => fotos.push(caminho),
            Err(e) => {
                warn!(erro = %e, "gravando foto do --sim");
                fotos.push(PathBuf::new());
            }
        }
    }
    if let Some(a) = &sim.aviso
        && let Some(jpeg) = &a.jpeg
        && let Err(e) = std::fs::write(dir.join(format!("aviso-{}.jpg", a.id)), jpeg)
    {
        warn!(erro = %e, "gravando foto do aviso do --sim");
    }
    let texto = texto_simulacao(sim, &fotos);
    if let Err(e) = std::fs::write(dir.join("sim.txt"), &texto) {
        warn!(erro = %e, "gravando sim.txt");
    }
    info!(pasta = %dir.display(), previas = sim.previas.len(), "--sim: nada enviado nem gravado no Oracle");
    print!("{texto}");
}

/// Uma execução do `besave-envio`. `previa`: resultado do `.env`/argumentos, lido antes de tudo.
pub fn executar(sim: bool, previa: Option<Result<(), ErroCiclo>>) -> Codigo {
    let inicio = Instant::now();
    let relogio = RelogioSistema;
    let agora = relogio.agora();
    let pastas = pastas();
    let arquivo = pastas.as_ref().ok().map(|p| {
        (
            p.logs.as_path(),
            arquivo_do_dia_de(&p.logs, PREFIXO_ENVIO, agora),
        )
    });
    if let Some(e) = iniciar_log_em(arquivo, sim, HoraBrasilia::default()) {
        warn!(erro = %e, "log em arquivo indisponível");
    }
    let pastas = match pastas {
        Ok(p) => p,
        Err(e) => return concluir(Err(Falha::config("config", &e)), None, agora),
    };
    // Alerta de falha: o mesmo bot de alertas do ciclo, estado próprio. `--sim` não alerta.
    let alerta_tg = match ConfigTelegram::do_env() {
        Err(e) => return concluir(Err(Falha::config("config", &e)), None, agora),
        Ok(None) => {
            info!("alerta desligado: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID ausentes");
            None
        }
        Ok(Some(_)) if sim => None,
        Ok(Some(cfg)) => match crate::telegram::TelegramHttp::new(cfg) {
            Ok(t) => Some(t),
            Err(e) => {
                warn!(erro = %e, "alerta indisponível: cliente do Telegram não iniciou");
                None
            }
        },
    };
    let alertas = alerta_tg
        .as_ref()
        .map(|t| Alertas::new(t, pastas.alerta.clone(), host_do_env()).com_titulo(TITULO_ENVIO));
    let alertas = alertas.as_ref();
    if let Some(Err(e)) = previa {
        let fase = match e {
            ErroCiclo::EnvFile { .. } => "env_file",
            _ => "config",
        };
        return concluir(Err(Falha::config(fase, &e)), alertas, agora);
    }
    let trava = if sim {
        None
    } else {
        match crate::trava::Trava::adquirir(&pastas.trava, agora) {
            Ok(Some(t)) => Some(t),
            Ok(None) => {
                info!("envio anterior em andamento; este foi pulado");
                return Codigo::Ok;
            }
            Err(e) => return concluir(Err(Falha::execucao("trava", &e)), alertas, agora),
        }
    };
    match limpar_antigos_de(&pastas.logs, PREFIXO_ENVIO, agora) {
        Ok(removidos) => {
            for p in removidos {
                info!(arquivo = %p.display(), "log antigo removido");
            }
        }
        Err(e) => warn!(erro = %e, "limpando logs antigos"),
    }
    let resultado = rodar_envio(sim, &pastas.estado, &relogio).map(|rel| {
        let ms = u64::try_from(inicio.elapsed().as_millis()).unwrap_or(u64::MAX);
        (rel, ms)
    });
    let codigo = match resultado {
        // `--sim` já imprimiu; sem relatório nem alerta.
        Ok((None, _)) => Codigo::Ok,
        Ok((Some(rel), ms)) => concluir(Ok((rel, ms)), alertas, agora),
        Err(f) => concluir(Err(f), alertas, agora),
    };
    drop(trava);
    codigo
}

/// Telegram do `--sim`: qualquer chamada é erro (o `simular` não chama).
struct SemTelegram;

impl CanalTelegram for SemTelegram {
    fn enviar_foto(&self, _: &str, _: &[u8], _: &str, _: bool) -> Result<i64, ErroCanal> {
        Err(ErroCanal::Conexao("--sim não envia".to_owned()))
    }

    fn editar_legenda(&self, _: &str, _: i64, _: &str) -> Result<(), ErroCanal> {
        Err(ErroCanal::Conexao("--sim não envia".to_owned()))
    }

    fn enviar_mensagem(&self, _: &str, _: &str, _: bool) -> Result<i64, ErroCanal> {
        Err(ErroCanal::Conexao("--sim não envia".to_owned()))
    }
}

/// Configuração (código 2 se faltar), Oracle e a execução; `None` no `--sim`.
fn rodar_envio(
    sim: bool,
    estado: &Path,
    relogio: &RelogioSistema,
) -> Result<Option<RelatorioEnvio>, Falha> {
    let m = Mapeamento::carregar_ou_embutido(var_caminho("BESAVE_MAPEAMENTO").as_deref())
        .map_err(|e| Falha::config("config", &e))?;
    let canal = canal_do_env().map_err(|e| Falha::config("config", &e))?;
    let dir_imagens = var_caminho("BESAVE_IMAGENS_DIR");
    let dir_avisos = var_caminho("BESAVE_AVISOS_DIR");
    if dir_imagens.is_none() {
        warn!("BESAVE_IMAGENS_DIR ausente: todas as fotos serão o placeholder da área");
    }
    let telegram = if sim {
        None
    } else {
        let cfg = ConfigCanal::do_env().map_err(|e| Falha::config("config", &e))?;
        Some(CanalTelegramHttp::new(cfg).map_err(|e| Falha::execucao("cliente_telegram", &e))?)
    };
    let cfg = ConfigOracle::do_env().map_err(|e| Falha::config("config", &e))?;
    let fonte = OracleEnvio::conectar(&cfg).map_err(|e| Falha::execucao("conexao_oracle", &e))?;
    let anterior = EstadoEnvio::carregar(estado);
    let ctx = Contexto {
        fonte: &fonte,
        telegram: telegram
            .as_ref()
            .map_or(&SemTelegram as &dyn CanalTelegram, |t| t),
        relogio,
        m: &m,
        dir_imagens: dir_imagens.as_deref(),
        dir_avisos: dir_avisos.as_deref(),
        foto,
        canal,
        pausa_ate: anterior.pausa_ate,
    };
    if sim {
        mostrar_simulacao(&simular(&ctx)?);
        return Ok(None);
    }
    let rel = rodar(&ctx)?;
    let novo = EstadoEnvio::depois(&rel, relogio.agora(), anterior);
    if novo != anterior {
        novo.salvar(estado);
    }
    Ok(Some(rel))
}
