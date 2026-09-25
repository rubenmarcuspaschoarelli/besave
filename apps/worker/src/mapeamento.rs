//! Texto livre do Oracle → enum, via packages/contract/mapeamento.json (CONTRATO §2).

use std::collections::HashMap;
use std::path::Path;

use serde::Deserialize;
use unicode_normalization::UnicodeNormalization;
use unicode_normalization::char::is_combining_mark;

use crate::modelo::{Area, Loja, Publico};

#[derive(Debug, thiserror::Error)]
pub enum ErroMapeamento {
    #[error("lendo {caminho}: {fonte}")]
    Leitura {
        caminho: String,
        fonte: std::io::Error,
    },
    #[error("mapeamento inválido em {caminho}: {fonte}")]
    Json {
        caminho: String,
        fonte: serde_json::Error,
    },
}

#[derive(Debug, Clone, Deserialize)]
pub struct Mapeamento {
    loja: HashMap<String, Loja>,
    publico: HashMap<String, Publico>,
    area: HashMap<String, Area>,
}

impl Mapeamento {
    pub fn carregar(caminho: impl AsRef<Path>) -> Result<Self, ErroMapeamento> {
        let caminho = caminho.as_ref();
        let txt = std::fs::read_to_string(caminho).map_err(|fonte| ErroMapeamento::Leitura {
            caminho: caminho.display().to_string(),
            fonte,
        })?;
        let bruto: Mapeamento =
            serde_json::from_str(&txt).map_err(|fonte| ErroMapeamento::Json {
                caminho: caminho.display().to_string(),
                fonte,
            })?;
        Ok(Self {
            loja: normalizar_chaves(bruto.loja),
            publico: normalizar_chaves(bruto.publico),
            area: normalizar_chaves(bruto.area),
        })
    }

    pub fn loja(&self, texto: &str) -> Option<Loja> {
        self.loja.get(&normalizar(texto)).copied()
    }

    pub fn publico(&self, texto: &str) -> Option<Publico> {
        self.publico.get(&normalizar(texto)).copied()
    }

    pub fn area(&self, texto: &str) -> Option<Area> {
        self.area.get(&normalizar(texto)).copied()
    }
}

fn normalizar_chaves<V>(m: HashMap<String, V>) -> HashMap<String, V> {
    m.into_iter().map(|(k, v)| (normalizar(&k), v)).collect()
}

/// Maiúsculas, sem acento (NFKD sem marcas combinantes), trim, espaços simples.
pub fn normalizar(texto: &str) -> String {
    let sem_acento: String = texto.nfkd().filter(|c| !is_combining_mark(*c)).collect();
    sem_acento
        .to_uppercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
