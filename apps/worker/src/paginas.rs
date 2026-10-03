//! Páginas de oferta em massa (BSV-21): render, só sobe o que mudou, expurgo (MANIFEST §1, §4, §7).

use std::collections::{BTreeMap, HashSet};
use std::time::{Duration, Instant};

use sha2::{Digest, Sha256};
use tracing::{debug, warn};

use crate::modelo::OfertaPagina;
use crate::pagina_html::TemplateOferta;
use crate::publicador::{ErroPublicador, META_PAGINA, Meta, Publicador};

/// HTML de oferta sem imagens (MANIFEST §7).
pub const ORCAMENTO_HTML: usize = 30_720;
/// Itens por `gravar_lote` (mesmo bloco das imagens, BSV-13).
const TAMANHO_BLOCO: usize = 64;

#[derive(Debug, thiserror::Error)]
pub enum ErroPaginas {
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error("página da oferta {id} tem {bytes} bytes; orçamento é {ORCAMENTO_HTML}")]
    PaginaAcimaDoOrcamento { id: i64, bytes: usize },
}

/// id → hash16 do HTML publicado.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct IndicePaginas(pub BTreeMap<i64, String>);

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioPaginas {
    pub renderizadas: u64,
    pub publicadas: u64,
    pub inalteradas: u64,
    pub removidas: u64,
    /// Ids cujo render falhou (não publicados nesta execução).
    pub falhas: Vec<i64>,
    /// Maior HTML renderizado, em bytes.
    pub maior_html: u64,
    /// Soma do tempo gasto só em `renderizar`.
    pub tempo_render_ms: u64,
}

/// `"oferta/{id}/index.html"` (MANIFEST §1).
pub fn chave_pagina(id: i64) -> String {
    format!("oferta/{id}/index.html")
}

/// 16 primeiros hex do SHA-256 (mesmo formato do hash de chunk).
pub fn hash16(bytes: &[u8]) -> String {
    hex::encode(&Sha256::digest(bytes)[..8])
}

/// Página de até `ORCAMENTO_HTML` bytes passa; acima disso, erro.
pub fn checar_orcamento_html(id: i64, bytes: usize) -> Result<(), ErroPaginas> {
    if bytes > ORCAMENTO_HTML {
        return Err(ErroPaginas::PaginaAcimaDoOrcamento { id, bytes });
    }
    Ok(())
}

/// Renderiza cada página e sobe, em lotes de `TAMANHO_BLOCO`, só as que têm hash diferente do
/// `anterior`; depois remove as páginas de ids do `anterior` que saíram de `paginas` (expurgo,
/// CONTRATO §7). Erro de render: loga o id, não publica e segue (mantém o hash anterior, se havia).
/// Página acima do orçamento ou falha de upload aborta.
pub fn publicar_paginas(
    paginas: &[OfertaPagina],
    t: &TemplateOferta,
    pub_: &mut dyn Publicador,
    anterior: &IndicePaginas,
) -> Result<(IndicePaginas, RelatorioPaginas), ErroPaginas> {
    let mut novo = BTreeMap::new();
    let mut rel = RelatorioPaginas::default();
    let mut tempo = Duration::ZERO;
    for bloco in paginas.chunks(TAMANHO_BLOCO) {
        let mut lote: Vec<(String, Vec<u8>, Meta)> = Vec::new();
        for o in bloco {
            let inicio = Instant::now();
            let render = t.renderizar(o);
            tempo += inicio.elapsed();
            let html = match render {
                Ok(h) => h,
                Err(e) => {
                    warn!(id = o.id, erro = %e, "falha no render; página não publicada");
                    rel.falhas.push(o.id);
                    if let Some(h) = anterior.0.get(&o.id) {
                        novo.insert(o.id, h.clone());
                    }
                    continue;
                }
            };
            rel.renderizadas += 1;
            checar_orcamento_html(o.id, html.len())?;
            rel.maior_html = rel.maior_html.max(html.len() as u64);
            let hash = hash16(html.as_bytes());
            if anterior.0.get(&o.id) == Some(&hash) {
                rel.inalteradas += 1;
            } else {
                lote.push((chave_pagina(o.id), html.into_bytes(), META_PAGINA));
                rel.publicadas += 1;
            }
            novo.insert(o.id, hash);
        }
        if !lote.is_empty() {
            pub_.gravar_lote(&lote)?;
        }
    }

    let atuais: HashSet<i64> = paginas.iter().map(|o| o.id).collect();
    for id in anterior.0.keys().filter(|id| !atuais.contains(id)) {
        pub_.remover(&chave_pagina(*id))?;
        rel.removidas += 1;
        debug!(id, "página expurgada");
    }
    rel.tempo_render_ms = u64::try_from(tempo.as_millis()).unwrap_or(u64::MAX);
    Ok((IndicePaginas(novo), rel))
}
