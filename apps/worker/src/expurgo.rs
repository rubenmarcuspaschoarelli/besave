//! Expurgo diferido e em lotes (BSV-47; CONTRATO §7, MANIFEST §6 passo 7).
//!
//! O id que sai do conjunto publicado sai no mesmo ciclo dos chunks, do sitemap e da contagem;
//! a página, as duas imagens e a chave da KVS entram numa fila persistida em `_estado/expurgo.json`
//! e só são apagadas na janela noturna, até `max` ids por ciclo, com `DeleteObjects`.

use std::collections::{BTreeMap, HashSet};
use std::fmt;

use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn};

use crate::conversao::iso_utc;
use crate::imagens::{chave_grande, chave_small};
use crate::logs::FUSO_BRASILIA;
use crate::paginas::chave_pagina;
use crate::publicador::{ErroPublicador, LOTE_REMOCAO, META_ESTADO, Publicador};
use crate::redirects::{self, ErroRedirects, Redirects};

/// Fila persistida (MANIFEST §1).
pub const CHAVE_EXPURGO: &str = "_estado/expurgo.json";
/// Padrão de `BESAVE_EXPURGO_MAX`: ids por ciclo.
pub const MAX_PADRAO: usize = 3000;
/// Padrão de `BESAVE_EXPURGO_JANELA` (hora de Brasília).
pub const JANELA_PADRAO: &str = "02:00-05:00";
/// Chaves de S3 por id: página, `-small` e grande.
const CHAVES_POR_ID: usize = 3;
const MINUTOS_DIA: u32 = 24 * 60;

#[derive(Debug, thiserror::Error)]
pub enum ErroExpurgo {
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error(transparent)]
    Redirects(#[from] ErroRedirects),
    #[error("serializando {CHAVE_EXPURGO}: {0}")]
    Serializacao(serde_json::Error),
}

pub type Result<T, E = ErroExpurgo> = std::result::Result<T, E>;

#[derive(Debug, thiserror::Error)]
#[error("{var} inválida: {motivo}")]
pub struct ErroConfigExpurgo {
    pub var: &'static str,
    pub motivo: String,
}

/// Intervalo do dia em minutos, hora de Brasília. `inicio > fim` atravessa a meia-noite.
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Janela {
    inicio: u32,
    fim: u32,
}

impl fmt::Debug for Janela {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{:02}:{:02}-{:02}:{:02}",
            self.inicio / 60,
            self.inicio % 60,
            self.fim / 60,
            self.fim % 60
        )
    }
}

impl Janela {
    /// O dia inteiro (ensaio e testes).
    pub const DIA_INTEIRO: Self = Self {
        inicio: 0,
        fim: MINUTOS_DIA,
    };

    /// `HH:MM-HH:MM`; início igual ao fim é erro (janela vazia ou o dia todo, ambíguo).
    pub fn analisar(texto: &str) -> Result<Self, String> {
        let hhmm = |s: &str| -> Option<u32> {
            let (h, m) = s.trim().split_once(':')?;
            if h.len() != 2 || m.len() != 2 {
                return None;
            }
            let (h, m): (u32, u32) = (h.parse().ok()?, m.parse().ok()?);
            (h < 24 && m < 60).then_some(h * 60 + m)
        };
        let invalida = || format!("{texto:?}, esperado HH:MM-HH:MM (hora de Brasília)");
        let (a, b) = texto.split_once('-').ok_or_else(invalida)?;
        let (inicio, fim) = (hhmm(a).ok_or_else(invalida)?, hhmm(b).ok_or_else(invalida)?);
        if inicio == fim {
            return Err(format!("{texto:?}: início e fim iguais"));
        }
        Ok(Self { inicio, fim })
    }

    /// `agora` (segundos Unix UTC) cai na janela; início inclusivo, fim exclusivo.
    pub fn contem(&self, agora: i64) -> bool {
        let minuto =
            u32::try_from((agora + FUSO_BRASILIA).rem_euclid(86_400) / 60).unwrap_or_default();
        if self.inicio < self.fim {
            (self.inicio..self.fim).contains(&minuto)
        } else {
            minuto >= self.inicio || minuto < self.fim
        }
    }
}

/// `BESAVE_EXPURGO_JANELA` e `BESAVE_EXPURGO_MAX`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConfigExpurgo {
    pub janela: Janela,
    pub max: usize,
}

impl Default for ConfigExpurgo {
    fn default() -> Self {
        Self {
            janela: Janela::analisar(JANELA_PADRAO).unwrap_or(Janela::DIA_INTEIRO),
            max: MAX_PADRAO,
        }
    }
}

impl ConfigExpurgo {
    /// Sem janela: apaga a qualquer hora (ensaio e testes).
    pub fn sempre() -> Self {
        Self {
            janela: Janela::DIA_INTEIRO,
            max: usize::MAX,
        }
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroConfigExpurgo> {
        let ler = |k: &str| {
            env(k)
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty())
        };
        let padrao = Self::default();
        let janela = match ler("BESAVE_EXPURGO_JANELA") {
            None => padrao.janela,
            Some(v) => Janela::analisar(&v).map_err(|motivo| ErroConfigExpurgo {
                var: "BESAVE_EXPURGO_JANELA",
                motivo,
            })?,
        };
        let max =
            match ler("BESAVE_EXPURGO_MAX") {
                None => padrao.max,
                Some(v) => v.parse::<usize>().ok().filter(|n| *n >= 1).ok_or_else(|| {
                    ErroConfigExpurgo {
                        var: "BESAVE_EXPURGO_MAX",
                        motivo: format!("{v:?}, esperado inteiro ≥ 1"),
                    }
                })?,
            };
        Ok(Self { janela, max })
    }
}

/// O que o expurgo fez neste ciclo (`expurgo_*` no relatório).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct RelatorioExpurgo {
    /// Ids que entraram na fila neste ciclo.
    pub enfileirados: u64,
    /// Ids apagados (página, imagens e KVS) neste ciclo.
    pub removidos: u64,
    /// Chaves de S3 enviadas ao `DeleteObjects`.
    pub chaves: u64,
    /// Ids ainda na fila ao fim do ciclo.
    pub pendente: u64,
}

/// Conteúdo de `_estado/expurgo.json`: id → data de entrada (ISO 8601 UTC).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
struct Conteudo {
    /// A reconciliação de órfãs já rodou (uma vez só).
    #[serde(default)]
    reconciliado: bool,
    #[serde(default)]
    fila: BTreeMap<i64, String>,
}

#[derive(Debug, Clone, Default)]
pub struct FilaExpurgo {
    c: Conteudo,
    /// Bytes lidos do bucket; a fila só é regravada se diferir.
    lido: Option<Vec<u8>>,
}

impl FilaExpurgo {
    /// Arquivo ausente ou ilegível = fila vazia e reconciliação por fazer (as sobras voltam à fila).
    pub fn carregar(pub_: &dyn Publicador) -> Result<Self> {
        let lido = pub_.ler(CHAVE_EXPURGO)?;
        let c = match lido.as_deref().map(serde_json::from_slice::<Conteudo>) {
            None => Conteudo::default(),
            Some(Ok(c)) => c,
            Some(Err(e)) => {
                warn!(erro = %e, "{CHAVE_EXPURGO} ilegível; recomeçando a fila e reconciliando");
                Conteudo::default()
            }
        };
        Ok(Self { c, lido })
    }

    pub fn len(&self) -> usize {
        self.c.fila.len()
    }

    pub fn is_empty(&self) -> bool {
        self.c.fila.is_empty()
    }

    pub fn contem(&self, id: i64) -> bool {
        self.c.fila.contains_key(&id)
    }

    pub fn ids(&self) -> impl Iterator<Item = i64> + '_ {
        self.c.fila.keys().copied()
    }

    pub fn reconciliado(&self) -> bool {
        self.c.reconciliado
    }

    /// Ids que ainda não estavam na fila entram com a data de `agora`. Devolve quantos entraram.
    pub fn registrar(&mut self, ids: impl IntoIterator<Item = i64>, agora: i64) -> u64 {
        let em = iso_utc(agora);
        let mut novos = 0;
        for id in ids {
            if let std::collections::btree_map::Entry::Vacant(v) = self.c.fila.entry(id) {
                v.insert(em.clone());
                novos += 1;
            }
        }
        novos
    }

    /// Oferta que voltou ao conjunto publicado (reativada) não pode ser apagada: sai da fila.
    pub fn devolver_publicados(&mut self, publicados: &HashSet<i64>) -> u64 {
        let antes = self.c.fila.len();
        self.c.fila.retain(|id, _| !publicados.contains(id));
        (antes - self.c.fila.len()) as u64
    }

    /// Reconciliação única (BSV-47): imagens (`ids_imagens`, da listagem de `img/ofertas/`) e
    /// páginas (`oferta/`) de ids fora do conjunto publicado entram na fila. Só uma vez: depois
    /// o próprio ciclo mantém a fila. Devolve quantos entraram.
    pub fn reconciliar(
        &mut self,
        pub_: &dyn Publicador,
        ids_imagens: impl IntoIterator<Item = i64>,
        publicados: &HashSet<i64>,
        agora: i64,
    ) -> Result<u64> {
        if self.c.reconciliado {
            return Ok(0);
        }
        let mut orfas: Vec<i64> = ids_imagens.into_iter().collect();
        for chave in pub_.listar("oferta/")? {
            let id = chave
                .strip_prefix("oferta/")
                .and_then(|r| r.strip_suffix("/index.html"))
                .and_then(|id| id.parse::<i64>().ok());
            orfas.extend(id);
        }
        orfas.retain(|id| !publicados.contains(id));
        let novos = self.registrar(orfas, agora);
        self.c.reconciliado = true;
        info!(enfileiradas = novos, "reconciliação de órfãs do expurgo");
        Ok(novos)
    }

    /// Grava a fila se mudou. Devolve se gravou.
    pub fn salvar(&mut self, pub_: &mut dyn Publicador) -> Result<bool> {
        let json = serde_json::to_vec(&self.c).map_err(ErroExpurgo::Serializacao)?;
        if self.lido.as_deref() == Some(json.as_slice()) {
            return Ok(false);
        }
        pub_.gravar(CHAVE_EXPURGO, &json, &META_ESTADO)?;
        self.lido = Some(json);
        Ok(true)
    }

    /// Apaga a fila (página, imagens e KVS) se `agora` está na janela, até `cfg.max` ids, em
    /// chamadas de até `LOTE_REMOCAO` chaves. Depois de cada chamada, os ids cujas chaves já foram
    /// todas apagadas saem da KVS e da fila e o estado é gravado: ciclo interrompido retoma dali.
    /// Um id cortado ao meio pela fronteira do lote fica na fila até o fim da sua última chave
    /// (no máximo duas chaves são reenviadas, e o `DeleteObjects` de chave ausente não falha).
    pub fn executar(
        &mut self,
        cfg: &ConfigExpurgo,
        agora: i64,
        pub_: &mut dyn Publicador,
        kvs: &mut dyn Redirects,
    ) -> Result<RelatorioExpurgo> {
        let mut rel = RelatorioExpurgo {
            pendente: self.len() as u64,
            ..Default::default()
        };
        if self.is_empty() {
            return Ok(rel);
        }
        if !cfg.janela.contem(agora) {
            debug!(pendente = rel.pendente, janela = ?cfg.janela, "fora da janela do expurgo");
            return Ok(rel);
        }
        let ids: Vec<i64> = self.ids().take(cfg.max).collect();
        let chaves: Vec<String> = ids
            .iter()
            .flat_map(|id| [chave_pagina(*id), chave_small(*id), chave_grande(*id)])
            .collect();
        let mut enviadas = 0;
        let mut feitos = 0;
        for bloco in chaves.chunks(LOTE_REMOCAO) {
            pub_.remover_lote(bloco)?;
            enviadas += bloco.len();
            rel.chaves += bloco.len() as u64;
            let ate = enviadas / CHAVES_POR_ID;
            if ate > feitos {
                let prontos = &ids[feitos..ate];
                redirects::remover_chaves(prontos, kvs, pub_)?;
                for id in prontos {
                    self.c.fila.remove(id);
                }
                self.salvar(pub_)?;
                rel.removidos += prontos.len() as u64;
                feitos = ate;
            }
        }
        rel.pendente = self.len() as u64;
        info!(
            removidos = rel.removidos,
            chaves = rel.chaves,
            pendente = rel.pendente,
            "expurgo executado"
        );
        Ok(rel)
    }
}
