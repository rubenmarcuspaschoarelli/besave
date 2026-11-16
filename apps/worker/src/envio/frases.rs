//! Frase de aviso no fim do post (BSV-62 Saída 3): `frases_canal.json` embutido ou
//! `BESAVE_FRASES_CANAL`; uma frase e um ícone por oferta, escolhidos por hash do id.

use std::path::Path;

use serde::Deserialize;
use sha2::{Digest, Sha256};
use tracing::warn;

/// Frase mais longa que isso (em caracteres) é descartada.
pub const MAX_FRASE: usize = 120;

const EMBUTIDO: &str = include_str!("../../frases_canal.json");

#[derive(Debug, thiserror::Error)]
pub enum ErroFrases {
    #[error("lendo {caminho}: {fonte}")]
    Leitura {
        caminho: String,
        fonte: std::io::Error,
    },
    #[error("JSON inválido: {0}")]
    Json(#[from] serde_json::Error),
    #[error("lista de {0} vazia")]
    ListaVazia(&'static str),
}

#[derive(Deserialize)]
struct Bruto {
    icones: Vec<String>,
    frases: Vec<String>,
}

/// Ícones e frases válidos (cada ícone é um item, mesmo com vários pontos de código).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frases {
    icones: Vec<String>,
    frases: Vec<String>,
}

/// Os 8 primeiros bytes (big-endian) do SHA-256 de `"{id}:{sal}"`.
fn h(id: i64, sal: &str) -> u64 {
    let d = Sha256::digest(format!("{id}:{sal}").as_bytes());
    let mut b = [0u8; 8];
    b.copy_from_slice(&d[..8]);
    u64::from_be_bytes(b)
}

fn indice(id: i64, sal: &str, n: usize) -> usize {
    // `n` ≥ 1 (lista vazia não passa de `de_json`).
    (h(id, sal) % n.max(1) as u64) as usize
}

impl Frases {
    /// JSON no formato de `frases_canal.json`. Frase vazia ou com mais de `MAX_FRASE` caracteres e
    /// ícone vazio saem com WARN; lista vazia depois disso é erro.
    pub fn de_json(txt: &str) -> Result<Self, ErroFrases> {
        let b: Bruto = serde_json::from_str(txt)?;
        let icones: Vec<String> = b
            .icones
            .iter()
            .map(|i| i.trim())
            .filter(|i| {
                if i.is_empty() {
                    warn!("ícone vazio em frases do canal; descartado");
                }
                !i.is_empty()
            })
            .map(str::to_owned)
            .collect();
        let frases: Vec<String> = b
            .frases
            .iter()
            .map(|f| f.trim())
            .filter(|f| {
                let n = f.chars().count();
                if n == 0 {
                    warn!("frase vazia em frases do canal; descartada");
                } else if n > MAX_FRASE {
                    warn!(
                        frase = f,
                        caracteres = n,
                        "frase do canal com mais de {MAX_FRASE} caracteres; descartada"
                    );
                }
                n > 0 && n <= MAX_FRASE
            })
            .map(str::to_owned)
            .collect();
        if icones.is_empty() {
            return Err(ErroFrases::ListaVazia("icones"));
        }
        if frases.is_empty() {
            return Err(ErroFrases::ListaVazia("frases"));
        }
        Ok(Self { icones, frases })
    }

    /// O `frases_canal.json` embutido no binário.
    pub fn embutidas() -> Result<Self, ErroFrases> {
        Self::de_json(EMBUTIDO)
    }

    /// `BESAVE_FRASES_CANAL`: arquivo ausente, ilegível, fora do formato ou com lista vazia → WARN
    /// e o embutido. Erro só se o embutido for inválido.
    pub fn carregar_ou_embutidas(caminho: Option<&Path>) -> Result<Self, ErroFrases> {
        let Some(c) = caminho else {
            return Self::embutidas();
        };
        let lido = std::fs::read_to_string(c)
            .map_err(|fonte| ErroFrases::Leitura {
                caminho: c.display().to_string(),
                fonte,
            })
            .and_then(|txt| Self::de_json(&txt));
        match lido {
            Ok(f) => Ok(f),
            Err(e) => {
                warn!(arquivo = %c.display(), erro = %e, "BESAVE_FRASES_CANAL inválido; usando as frases embutidas");
                Self::embutidas()
            }
        }
    }

    /// `(ícone, frase)` da oferta: `icones[h(id,"icone") mod m]`, `frases[h(id,"frase") mod n]`.
    pub fn escolher(&self, id: i64) -> (&str, &str) {
        let i = &self.icones[indice(id, "icone", self.icones.len())];
        let f = &self.frases[indice(id, "frase", self.frases.len())];
        (i, f)
    }

    pub fn icones(&self) -> &[String] {
        &self.icones
    }

    pub fn frases(&self) -> &[String] {
        &self.frases
    }
}
