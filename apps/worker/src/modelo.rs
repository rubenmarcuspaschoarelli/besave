//! Tipos do contrato (packages/contract/schema). Ordem dos campos = ordem das fixtures.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Loja {
    Amazon,
    Shopee,
    MercadoLivre,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Publico {
    Feminino,
    Masculino,
    Unissex,
    Infantil,
}

/// Ordem de declaração = ordem do enum no schema (e das chaves em `Manifest::areas`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Area {
    Tech,
    Players,
    MeuLar,
    Elas,
    Eles,
    Cultura,
    Familia,
    Pets,
    EsporteVida,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Status {
    Ativa,
    Encerrada,
}

/// CONTRATO.md §3.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OfertaCard {
    pub id: i64,
    #[serde(rename = "l")]
    pub loja: Loja,
    #[serde(rename = "t")]
    pub titulo: String,
    #[serde(rename = "pd")]
    pub preco_de: Option<i64>,
    #[serde(rename = "pp")]
    pub preco_por: i64,
    #[serde(rename = "c", skip_serializing_if = "Option::is_none")]
    pub cupom: Option<String>,
    #[serde(rename = "dt")]
    pub dt_oferta: String,
    #[serde(rename = "a")]
    pub area: Area,
    #[serde(rename = "p")]
    pub publico: Publico,
    /// `Some(1)` quando expirada (`ST_ATIVO = 0`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<u8>,
}

/// CONTRATO.md §4.1.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OfertaPagina {
    pub id: i64,
    pub id_produto: i64,
    pub loja: Loja,
    pub titulo: String,
    pub preco_de: Option<i64>,
    pub preco_por: i64,
    pub desconto_pct: Option<i64>,
    pub cupom: Option<String>,
    pub nota: Option<f64>,
    pub qt_avaliacoes: Option<i64>,
    pub dt_oferta: String,
    pub area: Area,
    pub publico: Publico,
    pub status: Status,
    pub produto: Option<Produto>,
}

/// CONTRATO.md §4.2.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Produto {
    pub descricao: String,
    pub marca: Option<String>,
    pub fabricante: Option<String>,
    pub modelo: Option<String>,
    pub pais_origem: Option<String>,
    pub genero: Option<String>,
    pub faixa_etaria: Option<String>,
    pub preco_min: Option<i64>,
    pub preco_max: Option<i64>,
}

/// MANIFEST.md §2.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub contrato: String,
    pub versao: u64,
    pub gerado_em: String,
    pub total_ofertas: u64,
    pub chunks: Vec<ChunkRef>,
    pub busca: Option<BuscaRef>,
    pub areas: BTreeMap<Area, u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChunkRef {
    pub n: u64,
    pub arquivo: String,
    pub ids: [i64; 2],
    pub qtd: u64,
    pub bytes: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BuscaRef {
    pub arquivo: String,
    pub bytes: u64,
}
