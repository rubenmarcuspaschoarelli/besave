//! Uma execução do envio (BSV-40): lote da janela (regras 1–7), edições de expiradas (regra 8) e
//! limites do Telegram (regra 9).

use std::path::Path;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::envio::aviso::{devido, foto_aviso, legenda_aviso};
use crate::envio::canal::{CanalTelegram, ErroCanal, Relogio};
use crate::envio::fonte::FonteEnvio;
use crate::envio::foto::OrigemFoto;
use crate::envio::janela::{esperado, inicio_do_dia, lote_devido, silencioso};
use crate::envio::legenda::{legenda, legenda_encerrada};
use crate::envio::modelo::para_canal;
use crate::envio::selecao::selecionar;
use crate::execucao::Falha;
use crate::fonte::ErroFonte;
use crate::imagens::ErroImagem;
use crate::mapeamento::Mapeamento;
use crate::modelo::Area;

/// Edições de expiradas por execução.
pub const MAX_EDICOES: usize = 20;
/// Intervalo mínimo entre chamadas ao Telegram.
pub const INTERVALO_MS: i64 = 1000;

#[derive(Debug, thiserror::Error)]
pub enum ErroEnvio {
    #[error("canal {0} sem linha em PARAMETROS_ENVIO")]
    SemParametros(i64),
}

/// Por que a execução não enviou nada (além de "nada devido").
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Parada {
    CanalAusente,
    CanalInativo,
    Pausa,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioEnvio {
    pub canal: i64,
    pub enviados_hoje: u64,
    pub devido: u32,
    pub enviados: u32,
    pub editadas: u32,
    /// Edições recusadas com 400 (post apagado ou já editado): marcadas e não repetidas.
    pub edicoes_descartadas: u32,
    /// `retry_after` de um 429: a execução parou aqui.
    pub retry_after: Option<u64>,
    pub parada: Option<Parada>,
    /// Id do aviso postado nesta execução (BSV-41).
    pub aviso: Option<i64>,
    /// O aviso falhou (Oracle ou Telegram ≠ 429); o lote de ofertas seguiu.
    pub aviso_falhou: bool,
}

impl RelatorioEnvio {
    /// Pares `chave=valor` do log.
    pub fn linha(&self, tempo_ms: u64) -> String {
        let parada = match self.parada {
            None => "-",
            Some(Parada::CanalAusente) => "canal_ausente",
            Some(Parada::CanalInativo) => "canal_inativo",
            Some(Parada::Pausa) => "pausa",
        };
        format!(
            "canal={} enviados_hoje={} devido={} enviados={} editadas={} edicoes_descartadas={} aviso={} aviso_falhou={} retry_after={} parada={parada} tempo_ms={tempo_ms}",
            self.canal,
            self.enviados_hoje,
            self.devido,
            self.enviados,
            self.editadas,
            self.edicoes_descartadas,
            self.aviso
                .map_or_else(|| "-".to_owned(), |id| id.to_string()),
            u8::from(self.aviso_falhou),
            self.retry_after
                .map_or_else(|| "-".to_owned(), |s| s.to_string()),
        )
    }
}

/// Monta a foto do post: `envio::foto::foto` em produção.
pub type Fotografo = fn(Option<&Path>, i64, Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem>;

pub struct Contexto<'a> {
    pub fonte: &'a dyn FonteEnvio,
    pub telegram: &'a dyn CanalTelegram,
    pub relogio: &'a dyn Relogio,
    pub m: &'a Mapeamento,
    /// `BESAVE_IMAGENS_DIR`; `None` → placeholder.
    pub dir_imagens: Option<&'a Path>,
    /// `BESAVE_AVISOS_DIR`; `None` → avisos vão sem foto.
    pub dir_avisos: Option<&'a Path>,
    pub foto: Fotografo,
    pub canal: i64,
    /// Fim da espera de um 429 anterior (segundos Unix).
    pub pausa_ate: Option<i64>,
}

/// No máximo uma chamada ao Telegram por `INTERVALO_MS`.
struct Ritmo<'a> {
    relogio: &'a dyn Relogio,
    ultima: Option<i64>,
}

impl Ritmo<'_> {
    fn esperar(&mut self) {
        if let Some(u) = self.ultima {
            let falta = u + INTERVALO_MS - self.relogio.agora_ms();
            if falta > 0 {
                self.relogio
                    .dormir(Duration::from_millis(falta.unsigned_abs()));
            }
        }
        self.ultima = Some(self.relogio.agora_ms());
    }
}

/// Uma execução. Erro do Oracle ou do Telegram (fora 429) → `Falha` (código 1, alerta).
pub fn rodar(ctx: &Contexto) -> Result<RelatorioEnvio, Falha> {
    let agora = ctx.relogio.agora();
    let mut rel = RelatorioEnvio {
        canal: ctx.canal,
        ..Default::default()
    };
    if ctx.pausa_ate.is_some_and(|p| agora < p) {
        info!(
            pausa_ate = ctx.pausa_ate,
            "Telegram pediu espera (429); execução pulada"
        );
        rel.parada = Some(Parada::Pausa);
        return Ok(rel);
    }
    let fonte = ctx.fonte;
    let ler = |e: ErroFonte| Falha::execucao("leitura_oracle", &e);
    let canal = match fonte.canal(ctx.canal).map_err(ler)? {
        None => {
            warn!(canal = ctx.canal, "canal sem linha em CANAL_ENVIO");
            rel.parada = Some(Parada::CanalAusente);
            return Ok(rel);
        }
        Some(c) if !c.ativo => {
            info!(canal = ctx.canal, "canal inativo (ST_ATIVO = 0)");
            rel.parada = Some(Parada::CanalInativo);
            return Ok(rel);
        }
        Some(c) => c,
    };
    // Lidos uma vez por execução (regra 10).
    let p = fonte
        .parametros(ctx.canal)
        .map_err(ler)?
        .ok_or_else(|| Falha::config("parametros", &ErroEnvio::SemParametros(ctx.canal)))?;
    let mut ritmo = Ritmo {
        relogio: ctx.relogio,
        ultima: None,
    };

    let mudo = silencioso(&p, agora);
    // BSV-41: no máximo 1 aviso, antes do lote, na janela do canal; fora da cota de ofertas.
    if esperado(&p, agora).is_some()
        && let Some(s) = enviar_aviso(ctx, &canal.chat_id, mudo, &mut ritmo, &mut rel)
    {
        warn!(
            retry_after = s,
            "Telegram pediu espera (429); continua na próxima"
        );
        rel.retry_after = Some(s);
        return Ok(rel);
    }

    rel.enviados_hoje = fonte
        .enviados_desde(ctx.canal, inicio_do_dia(agora))
        .map_err(ler)?;
    rel.devido = lote_devido(&p, agora, rel.enviados_hoje);
    let candidatas =
        selecionar(fonte, ctx.m, &p, ctx.canal, agora, rel.devido as usize).map_err(ler)?;
    for c in candidatas {
        let texto = legenda(&c.oferta, c.caiu, &p);
        let (jpeg, origem) = (ctx.foto)(ctx.dir_imagens, c.oferta.id, c.area)
            .map_err(|e| Falha::execucao("foto", &e))?;
        // Regra 7: a linha existe antes do envio; sem ela, nada vai ao Telegram.
        let id_envio = fonte
            .reservar(ctx.canal, &c.oferta, ctx.relogio.agora())
            .map_err(|e| Falha::execucao("reserva_oracle", &e))?;
        ritmo.esperar();
        match ctx
            .telegram
            .enviar_foto(&canal.chat_id, &jpeg, &texto, mudo)
        {
            Ok(message_id) => {
                fonte
                    .confirmar(id_envio, message_id)
                    .map_err(|e| Falha::execucao("confirmacao_oracle", &e))?;
                rel.enviados += 1;
                info!(id = c.oferta.id, message_id, silencioso = mudo, foto = ?origem, caiu = c.caiu, "oferta enviada ao canal");
            }
            Err(e) => {
                cancelar(fonte, id_envio, c.oferta.id);
                if let ErroCanal::Limite(s) = e {
                    warn!(
                        retry_after = s,
                        "Telegram pediu espera (429); continua na próxima"
                    );
                    rel.retry_after = Some(s);
                    return Ok(rel);
                }
                return Err(Falha::execucao("envio_telegram", &e));
            }
        }
    }

    for e in fonte.expiradas(ctx.canal, MAX_EDICOES).map_err(ler)? {
        let texto = match para_canal(&e.linha, ctx.m) {
            Ok(o) => legenda_encerrada(&o, &p),
            Err(_) => "⛔ <b>Oferta encerrada</b>".to_owned(),
        };
        ritmo.esperar();
        match ctx
            .telegram
            .editar_legenda(&canal.chat_id, e.message_id, &texto)
        {
            Ok(()) => rel.editadas += 1,
            Err(ErroCanal::Limite(s)) => {
                warn!(
                    retry_after = s,
                    "Telegram pediu espera (429); continua na próxima"
                );
                rel.retry_after = Some(s);
                return Ok(rel);
            }
            Err(ErroCanal::Recusada {
                status: 400,
                descricao,
            }) => {
                warn!(
                    id = e.linha.oferta.id,
                    message_id = e.message_id,
                    descricao,
                    "edição recusada; não será repetida"
                );
                rel.edicoes_descartadas += 1;
            }
            Err(err) => return Err(Falha::execucao("edicao_telegram", &err)),
        }
        fonte
            .marcar_editada(e.id_envio, ctx.relogio.agora())
            .map_err(|err| Falha::execucao("edicao_oracle", &err))?;
    }
    Ok(rel)
}

/// Posta o aviso devido (reserva → envia → confirma). Falha (Oracle ou Telegram ≠ 429) → WARN,
/// linha apagada e `aviso_falhou`; devolve o `retry_after` de um 429.
fn enviar_aviso(
    ctx: &Contexto,
    chat_id: &str,
    mudo: bool,
    ritmo: &mut Ritmo,
    rel: &mut RelatorioEnvio,
) -> Option<u64> {
    let fonte = ctx.fonte;
    let avisos = match fonte.avisos_canal(ctx.canal) {
        Ok(v) => v,
        Err(e) => {
            warn!(erro = %e, "lendo avisos do canal; segue sem aviso");
            rel.aviso_falhou = true;
            return None;
        }
    };
    let a = devido(&avisos, ctx.relogio.agora())?;
    let id = a.aviso.id;
    let texto = legenda_aviso(a);
    let foto = foto_aviso(ctx.dir_avisos, id, a.aviso.imagem.as_deref());
    // Regra 4: a linha existe antes do envio; sem ela, nada vai ao Telegram.
    let id_envio = match fonte.reservar_aviso(id, ctx.canal, ctx.relogio.agora()) {
        Ok(i) => i,
        Err(e) => {
            warn!(id, erro = %e, "reservando ENVIO_AVISO; aviso não enviado");
            rel.aviso_falhou = true;
            return None;
        }
    };
    ritmo.esperar();
    let r = match &foto {
        Some(jpeg) => ctx.telegram.enviar_foto(chat_id, jpeg, &texto, mudo),
        None => ctx.telegram.enviar_mensagem(chat_id, &texto, mudo),
    };
    match r {
        Ok(message_id) => {
            if let Err(e) = fonte.confirmar_aviso(id_envio, message_id) {
                // A linha fica sem `message_id`: conta como envio, sem duplicata.
                warn!(id, id_envio, erro = %e, "confirmando ENVIO_AVISO");
            }
            rel.aviso = Some(id);
            info!(
                id,
                message_id,
                silencioso = mudo,
                foto = foto.is_some(),
                "aviso enviado ao canal"
            );
            None
        }
        Err(e) => {
            if let Err(e) = fonte.cancelar_aviso(id_envio) {
                warn!(id, id_envio, erro = %e, "apagando a linha de um aviso que falhou");
            }
            if let ErroCanal::Limite(s) = e {
                return Some(s);
            }
            warn!(id, erro = %e, "aviso recusado pelo Telegram; segue o lote de ofertas");
            rel.aviso_falhou = true;
            None
        }
    }
}

/// Apaga a linha de um envio que falhou. Se o Oracle também falhar, a linha fica sem
/// `message_id`: a oferta não é reenviada (sem duplicata), só não ganha edição.
fn cancelar(fonte: &dyn FonteEnvio, id_envio: i64, id: i64) {
    if let Err(e) = fonte.cancelar(id_envio) {
        warn!(id, id_envio, erro = %e, "apagando a linha de um envio que falhou");
    }
}

/// `envio-estado.json`: fim da espera pedida por um 429.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EstadoEnvio {
    pub pausa_ate: Option<i64>,
}

impl EstadoEnvio {
    /// Ausente ou ilegível → sem pausa.
    pub fn carregar(caminho: &Path) -> Self {
        match std::fs::read(caminho) {
            Ok(b) => serde_json::from_slice(&b).unwrap_or_else(|e| {
                warn!(erro = %e, "envio-estado.json ilegível; ignorado");
                Self::default()
            }),
            Err(_) => Self::default(),
        }
    }

    pub fn salvar(&self, caminho: &Path) {
        let r = caminho
            .parent()
            .map_or(Ok(()), std::fs::create_dir_all)
            .and_then(|()| {
                let json = serde_json::to_vec(self).map_err(std::io::Error::other)?;
                std::fs::write(caminho, json)
            });
        if let Err(e) = r {
            warn!(erro = %e, "gravando envio-estado.json");
        }
    }

    /// Estado depois de uma execução que terminou em `agora`.
    pub fn depois(rel: &RelatorioEnvio, agora: i64, anterior: Self) -> Self {
        match rel.retry_after {
            Some(s) => Self {
                pausa_ate: Some(agora + i64::try_from(s).unwrap_or(i64::MAX / 2)),
            },
            None if rel.parada == Some(Parada::Pausa) => anterior,
            None => Self::default(),
        }
    }
}

/// Uma prévia do `--sim`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Previa {
    pub id: i64,
    pub legenda: String,
    pub jpeg: Vec<u8>,
    pub origem: OrigemFoto,
}

/// O aviso que o `--sim` postaria.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PreviaAviso {
    pub id: i64,
    pub legenda: String,
    /// `None`: vai como `sendMessage`.
    pub jpeg: Option<Vec<u8>>,
}

/// O que a execução faria agora, sem Telegram e sem escrita no Oracle.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Simulacao {
    pub enviados_hoje: u64,
    pub devido: u32,
    pub silencioso: bool,
    /// Próximas `QT_POR_EXECUCAO` candidatas, mesmo fora da janela.
    pub previas: Vec<Previa>,
    /// Posts que seriam editados como "Oferta encerrada" (até `MAX_EDICOES`).
    pub expiradas: usize,
    pub parada: Option<Parada>,
    /// Aviso devido agora pelo intervalo (mesmo fora da janela).
    pub aviso: Option<PreviaAviso>,
    pub na_janela: bool,
}

/// `--sim`: só leituras.
pub fn simular(ctx: &Contexto) -> Result<Simulacao, Falha> {
    let agora = ctx.relogio.agora();
    let fonte = ctx.fonte;
    let ler = |e: ErroFonte| Falha::execucao("leitura_oracle", &e);
    let mut sim = Simulacao::default();
    match fonte.canal(ctx.canal).map_err(ler)? {
        None => sim.parada = Some(Parada::CanalAusente),
        Some(c) if !c.ativo => sim.parada = Some(Parada::CanalInativo),
        Some(_) => {}
    }
    let p = fonte
        .parametros(ctx.canal)
        .map_err(ler)?
        .ok_or_else(|| Falha::config("parametros", &ErroEnvio::SemParametros(ctx.canal)))?;
    sim.enviados_hoje = fonte
        .enviados_desde(ctx.canal, inicio_do_dia(agora))
        .map_err(ler)?;
    sim.devido = lote_devido(&p, agora, sim.enviados_hoje);
    sim.silencioso = silencioso(&p, agora);
    sim.na_janela = esperado(&p, agora).is_some();
    let avisos = fonte.avisos_canal(ctx.canal).map_err(ler)?;
    sim.aviso = devido(&avisos, agora).map(|a| PreviaAviso {
        id: a.aviso.id,
        legenda: legenda_aviso(a),
        jpeg: foto_aviso(ctx.dir_avisos, a.aviso.id, a.aviso.imagem.as_deref()),
    });
    let n = sim.devido.max(p.qt_por_execucao) as usize;
    for c in selecionar(fonte, ctx.m, &p, ctx.canal, agora, n).map_err(ler)? {
        let (jpeg, origem) = (ctx.foto)(ctx.dir_imagens, c.oferta.id, c.area)
            .map_err(|e| Falha::execucao("foto", &e))?;
        sim.previas.push(Previa {
            id: c.oferta.id,
            legenda: legenda(&c.oferta, c.caiu, &p),
            jpeg,
            origem,
        });
    }
    sim.expiradas = fonte.expiradas(ctx.canal, MAX_EDICOES).map_err(ler)?.len();
    Ok(sim)
}
