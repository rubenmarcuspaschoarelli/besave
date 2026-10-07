//! `OfertaCanal` (CONTRATO §11), a linha do Oracle que a alimenta e os parâmetros por canal
//! (`PARAMETROS_ENVIO`, `sql/bsv-40.sql`).

use crate::conversao::{LinhaOferta, Rejeicao, desconto_pct, para_card, truncar};
use crate::mapeamento::Mapeamento;
use crate::modelo::Loja;

/// Destaque mais longo que isso é cortado com `…` (só o título é cortado para caber em 1024).
pub const MAX_DESTAQUE: usize = 200;

/// Uma linha de OFERTA para o envio: a linha do ciclo + as colunas que só o canal usa.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct LinhaCanal {
    pub oferta: LinhaOferta,
    /// `DS_OFERTA_DESTAQUE`
    pub destaque: Option<String>,
    /// `ST_RECORRENCIA = 1`
    pub recorrencia: bool,
    /// `DT_PUBLICACAO_SITE`, segundos Unix UTC; `None` = página ainda não está no ar.
    pub dt_publicacao_site: Option<i64>,
}

/// CONTRATO §11. Sem JSON publicado: só a legenda do post.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OfertaCanal {
    pub id: i64,
    pub id_produto: i64,
    pub loja: Loja,
    pub titulo: String,
    pub destaque: Option<String>,
    pub preco_de: Option<i64>,
    pub preco_por: i64,
    pub desconto_pct: Option<i64>,
    pub cupom: Option<String>,
    pub recorrencia: bool,
    /// ISO 8601 UTC.
    pub dt_oferta: String,
}

/// Regras do §9 + URL de afiliado + `id_produto` (só vai ao canal o que tem página).
pub fn para_canal(l: &LinhaCanal, m: &Mapeamento) -> Result<OfertaCanal, Rejeicao> {
    let card = para_card(&l.oferta, m)?;
    let id_produto = l
        .oferta
        .id_produto
        .filter(|&id| id >= 1)
        .ok_or(Rejeicao::IdProdutoAusente)?;
    let titulo = l
        .oferta
        .titulo
        .as_deref()
        .unwrap_or_default()
        .trim()
        .to_owned();
    let destaque = l
        .destaque
        .as_deref()
        .map(str::trim)
        .filter(|d| !d.is_empty())
        .map(|d| truncar(d, MAX_DESTAQUE));
    Ok(OfertaCanal {
        id: card.id,
        id_produto,
        loja: card.loja,
        titulo,
        destaque,
        preco_de: card.preco_de,
        preco_por: card.preco_por,
        desconto_pct: card.preco_de.map(|pd| desconto_pct(pd, card.preco_por)),
        cupom: card.cupom,
        recorrencia: l.recorrencia,
        dt_oferta: card.dt_oferta,
    })
}

/// `PARAMETROS_ENVIO` de um canal. Horas em Brasília; percentuais inteiros.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Parametros {
    pub qt_max_dia: u32,
    pub qt_por_execucao: u32,
    pub hora_inicio: u32,
    pub hora_fim: u32,
    pub hora_som_inicio: u32,
    pub hora_som_fim: u32,
    pub pc_desconto_min: i64,
    pub horas_oferta_max: i64,
    pub dias_repeticao: i64,
    pub pc_queda_repeticao: i64,
    pub pc_desconto_destaque: i64,
}

/// Os `DEFAULT` do DDL.
impl Default for Parametros {
    fn default() -> Self {
        Self {
            qt_max_dia: 180,
            qt_por_execucao: 2,
            hora_inicio: 8,
            hora_fim: 22,
            hora_som_inicio: 9,
            hora_som_fim: 21,
            pc_desconto_min: 30,
            horas_oferta_max: 24,
            dias_repeticao: 5,
            pc_queda_repeticao: 10,
            pc_desconto_destaque: 30,
        }
    }
}

/// `CANAL_ENVIO`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Canal {
    pub id: i64,
    /// `DS_CHAT_ID` (`@besaveofertas` ou id numérico).
    pub chat_id: String,
    pub ativo: bool,
}
