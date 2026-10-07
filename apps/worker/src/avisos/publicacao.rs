//! Avisos no ciclo (BSV-41): página e imagem de cada aviso vigente, índice `_estado/avisos.json`
//! (só sobe o que mudou, AD-041), remoção do que saiu e `AVISO.DT_PUBLICACAO_SITE`.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::time::Instant;

use serde::{Deserialize, Serialize};
use tracing::{debug, warn};

use crate::avisos::modelo::{
    Formato, LinhaAviso, MAX_IMAGEM_PAGINA, chave_imagem, chave_pagina, formato_imagem,
};
use crate::avisos::pagina::{CANAL_PADRAO, TemplateAviso};
use crate::fonte::{ErroFonte, FonteOfertas};
use crate::pagina_html::ErroTemplate;
use crate::paginas::hash16;
use crate::publicador::{
    ErroPublicador, META_AVISO_JPG, META_AVISO_WEBP, META_ESTADO, META_PAGINA, Publicador,
};

pub const CHAVE_ESTADO_AVISOS: &str = "_estado/avisos.json";
const PREFIXO_PAGINAS: &str = "avisos/";
const PREFIXO_IMAGENS: &str = "img/avisos/";

#[derive(Debug, thiserror::Error)]
pub enum ErroAvisos {
    #[error(transparent)]
    Fonte(#[from] ErroFonte),
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error(transparent)]
    Template(#[from] ErroTemplate),
    #[error("serializando {CHAVE_ESTADO_AVISOS}: {0}")]
    Estado(serde_json::Error),
}

/// `BESAVE_AVISOS_DIR` (imagens) e `BESAVE_CANAL_URL` (link do canal na página).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigAvisos {
    pub dir: Option<PathBuf>,
    pub canal: String,
}

impl Default for ConfigAvisos {
    fn default() -> Self {
        Self {
            dir: None,
            canal: CANAL_PADRAO.to_owned(),
        }
    }
}

impl ConfigAvisos {
    pub fn do_env() -> Self {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Self {
        let opc = |k: &str| {
            env(k)
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty())
        };
        Self {
            dir: opc("BESAVE_AVISOS_DIR").map(PathBuf::from),
            canal: opc("BESAVE_CANAL_URL").unwrap_or_else(|| CANAL_PADRAO.to_owned()),
        }
    }
}

/// O que está no bucket para um aviso.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntradaAviso {
    /// hash16 do HTML; vazio = desconhecido (índice reconstruído).
    pub pagina: String,
    /// Chave da imagem publicada.
    pub imagem: Option<String>,
    pub hash_imagem: Option<String>,
}

/// Conteúdo de `_estado/avisos.json`: id → entrada.
pub type IndiceAvisos = BTreeMap<i64, EntradaAviso>;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioAvisos {
    /// Avisos vigentes com página no ar ao fim da fase.
    pub no_ar: u64,
    /// Páginas gravadas nesta execução.
    pub publicados: u64,
    pub imagens_publicadas: u64,
    /// Avisos que saíram do ar (página e imagem removidas).
    pub removidos: u64,
    /// Avisos não publicados por imagem em formato ou nome inválido.
    pub ignorados: u64,
    pub links_invalidos: u64,
    /// Páginas sem imagem por arquivo ausente, ilegível ou acima de 1 MB.
    pub sem_imagem: u64,
    pub datas_gravadas: u64,
    pub datas_anuladas: u64,
    /// 1 se a fase falhou (WARN; o ciclo segue).
    pub falhas: u64,
    pub tempo_ms: u64,
}

/// Índice sem arquivo: o que está no bucket, com hashes vazios (tudo sobe de novo e o que saiu é
/// removido).
fn indice_do_bucket(pub_: &dyn Publicador) -> Result<IndiceAvisos, ErroPublicador> {
    let mut idx = IndiceAvisos::new();
    for chave in pub_.listar(PREFIXO_PAGINAS)? {
        let id = chave
            .strip_prefix(PREFIXO_PAGINAS)
            .and_then(|r| r.strip_suffix("/index.html"))
            .and_then(|id| id.parse::<i64>().ok());
        if let Some(id) = id {
            idx.entry(id).or_default();
        }
    }
    for chave in pub_.listar(PREFIXO_IMAGENS)? {
        let id = chave
            .strip_prefix(PREFIXO_IMAGENS)
            .and_then(|r| r.split_once('.'))
            .and_then(|(id, _)| id.parse::<i64>().ok());
        if let Some(id) = id {
            let e = idx.entry(id).or_default();
            e.imagem = Some(chave);
            e.hash_imagem = Some(String::new());
        }
    }
    Ok(idx)
}

/// Bytes da imagem para a página; `None` (com WARN) se a pasta não está definida, o arquivo não
/// existe, não pode ser lido ou passa de 1 MB.
fn ler_imagem(dir: Option<&Path>, a: &LinhaAviso, nome: &str) -> Option<Vec<u8>> {
    let Some(dir) = dir else {
        warn!(
            id = a.id,
            imagem = nome,
            "BESAVE_AVISOS_DIR ausente; página do aviso sem imagem"
        );
        return None;
    };
    let caminho = dir.join(nome);
    let tamanho = match std::fs::metadata(&caminho) {
        Ok(m) => m.len(),
        Err(e) => {
            warn!(id = a.id, imagem = nome, erro = %e, "imagem do aviso indisponível; página sem imagem");
            return None;
        }
    };
    if tamanho > MAX_IMAGEM_PAGINA {
        warn!(
            id = a.id,
            imagem = nome,
            bytes = tamanho,
            "imagem do aviso acima de 1 MB; página sem imagem"
        );
        return None;
    }
    match std::fs::read(&caminho) {
        Ok(b) => Some(b),
        Err(e) => {
            warn!(id = a.id, imagem = nome, erro = %e, "lendo imagem do aviso; página sem imagem");
            None
        }
    }
}

/// Publica os avisos vigentes e remove os que saíram. `marcar`: grava/anula
/// `DT_PUBLICACAO_SITE` (falso com `BESAVE_DESTINO_LOCAL`). Ordem: imagem e página de cada aviso,
/// remoções, índice e, por último, as datas no Oracle.
pub fn publicar_avisos(
    fonte: &dyn FonteOfertas,
    pub_: &mut dyn Publicador,
    cfg: &ConfigAvisos,
    agora: i64,
    marcar: bool,
) -> Result<RelatorioAvisos, ErroAvisos> {
    let inicio = Instant::now();
    let mut rel = RelatorioAvisos::default();
    let lido = pub_.ler(CHAVE_ESTADO_AVISOS)?;
    let anterior = match lido.as_deref().map(serde_json::from_slice::<IndiceAvisos>) {
        Some(Ok(idx)) => idx,
        sem_indice => {
            if sem_indice.is_some() {
                warn!("{CHAVE_ESTADO_AVISOS} ilegível; reconstruindo pelo bucket");
            }
            indice_do_bucket(pub_)?
        }
    };
    let linhas = fonte.avisos()?;
    let t = TemplateAviso::novo(&cfg.canal)?;
    let mut novo = IndiceAvisos::new();

    for a in linhas.iter().filter(|a| a.vigente(agora)) {
        let antes = anterior.get(&a.id);
        let mut imagem: Option<(Formato, Vec<u8>)> = None;
        if let Some(nome) = a.imagem.as_deref().map(str::trim).filter(|n| !n.is_empty()) {
            let Some(f) = formato_imagem(nome) else {
                warn!(
                    id = a.id,
                    imagem = nome,
                    "imagem do aviso fora de .webp/.jpg; aviso ignorado"
                );
                rel.ignorados += 1;
                continue;
            };
            match ler_imagem(cfg.dir.as_deref(), a, nome) {
                Some(b) => imagem = Some((f, b)),
                None => rel.sem_imagem += 1,
            }
        }
        if a.link_interno.is_some() && a.link_valido().is_none() {
            warn!(
                id = a.id,
                link = a.link_interno.as_deref(),
                "DS_LINK_INTERNO fora de ^/[a-z0-9/_-]*$; página sem botão"
            );
            rel.links_invalidos += 1;
        }

        let mut entrada = EntradaAviso::default();
        if let Some((f, bytes)) = &imagem {
            let chave = chave_imagem(a.id, *f);
            let hash = hash16(bytes);
            let igual = antes.is_some_and(|e| {
                e.imagem.as_ref() == Some(&chave) && e.hash_imagem.as_ref() == Some(&hash)
            });
            if !igual {
                let meta = match f {
                    Formato::Jpg => META_AVISO_JPG,
                    Formato::Webp => META_AVISO_WEBP,
                };
                pub_.gravar(&chave, bytes, &meta)?;
                rel.imagens_publicadas += 1;
            }
            entrada.imagem = Some(chave);
            entrada.hash_imagem = Some(hash);
        }
        // Imagem anterior com outra chave (extensão trocada) ou que deixou de existir.
        if let Some(velha) = antes.and_then(|e| e.imagem.as_ref())
            && entrada.imagem.as_ref() != Some(velha)
        {
            pub_.remover(velha)?;
        }

        let html = t.renderizar(a, imagem.as_ref().map(|(f, _)| *f))?;
        let hash = hash16(html.as_bytes());
        if antes.map(|e| &e.pagina) != Some(&hash) {
            pub_.gravar(&chave_pagina(a.id), html.as_bytes(), &META_PAGINA)?;
            rel.publicados += 1;
        }
        entrada.pagina = hash;
        novo.insert(a.id, entrada);
    }
    rel.no_ar = novo.len() as u64;

    for (id, e) in anterior.iter().filter(|(id, _)| !novo.contains_key(id)) {
        pub_.remover(&chave_pagina(*id))?;
        if let Some(img) = &e.imagem {
            pub_.remover(img)?;
        }
        rel.removidos += 1;
        debug!(id, "aviso fora do ar");
    }

    let json = serde_json::to_vec(&novo).map_err(ErroAvisos::Estado)?;
    if lido.as_deref() != Some(json.as_slice()) {
        pub_.gravar(CHAVE_ESTADO_AVISOS, &json, &META_ESTADO)?;
    }

    if marcar {
        let no_ar: BTreeSet<i64> = novo.keys().copied().collect();
        for a in &linhas {
            match (no_ar.contains(&a.id), a.dt_publicacao_site.is_some()) {
                (true, false) => {
                    fonte.marcar_aviso_site(a.id, true)?;
                    rel.datas_gravadas += 1;
                }
                (false, true) => {
                    fonte.marcar_aviso_site(a.id, false)?;
                    rel.datas_anuladas += 1;
                }
                _ => {}
            }
        }
    }
    rel.tempo_ms = u64::try_from(inicio.elapsed().as_millis()).unwrap_or(u64::MAX);
    Ok(rel)
}
