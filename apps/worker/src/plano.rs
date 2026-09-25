//! `--publicar` sem `--sim`: `gerar` roda contra o destino real, mas as escritas só são
//! registradas (proteção contra publicar no bucket errado).

use std::collections::BTreeMap;
use std::fmt;

use crate::fonte::FonteOfertas;
use crate::geracao::{Relatorio, Result, gerar};
use crate::mapeamento::Mapeamento;
use crate::publicador::{self, Meta, Publicador};
use crate::redirects::{self, Redirects};

/// Uma escrita que o `--sim` faria.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Operacao {
    Gravar {
        chave: String,
        bytes: u64,
        cache_control: &'static str,
    },
    Remover {
        chave: String,
    },
    PutKey {
        id: i64,
        url: String,
    },
    DeleteKey {
        id: i64,
    },
}

impl fmt::Display for Operacao {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Gravar {
                chave,
                bytes,
                cache_control,
            } => write!(f, "gravar {chave} ({bytes} B, {cache_control})"),
            Self::Remover { chave } => write!(f, "remover {chave}"),
            Self::PutKey { id, url } => write!(f, "putKey {id} {url}"),
            Self::DeleteKey { id } => write!(f, "deleteKey {id}"),
        }
    }
}

/// Lê do destino; escritas viram `Operacao`.
pub struct PublicadorPlano<'a> {
    destino: &'a dyn Publicador,
    pub ops: Vec<Operacao>,
}

impl<'a> PublicadorPlano<'a> {
    pub fn new(destino: &'a dyn Publicador) -> Self {
        Self {
            destino,
            ops: Vec::new(),
        }
    }
}

impl Publicador for PublicadorPlano<'_> {
    fn existe(&self, chave: &str) -> publicador::Result<bool> {
        self.destino.existe(chave)
    }

    fn ler(&self, chave: &str) -> publicador::Result<Option<Vec<u8>>> {
        self.destino.ler(chave)
    }

    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> publicador::Result<()> {
        self.ops.push(Operacao::Gravar {
            chave: chave.to_owned(),
            bytes: bytes.len() as u64,
            cache_control: meta.cache_control,
        });
        Ok(())
    }

    fn remover(&mut self, chave: &str) -> publicador::Result<()> {
        self.ops.push(Operacao::Remover {
            chave: chave.to_owned(),
        });
        Ok(())
    }

    fn listar(&self, prefixo: &str) -> publicador::Result<Vec<String>> {
        self.destino.listar(prefixo)
    }
}

/// Lê a KVS de destino; `aplicar` vira `PutKey`/`DeleteKey`.
pub struct RedirectsPlano<'a> {
    destino: &'a dyn Redirects,
    pub ops: Vec<Operacao>,
}

impl<'a> RedirectsPlano<'a> {
    pub fn new(destino: &'a dyn Redirects) -> Self {
        Self {
            destino,
            ops: Vec::new(),
        }
    }
}

impl Redirects for RedirectsPlano<'_> {
    fn listar(&self) -> redirects::Result<BTreeMap<i64, String>> {
        self.destino.listar()
    }

    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> redirects::Result<()> {
        self.ops
            .extend(put.iter().map(|(id, url)| Operacao::PutKey {
                id: *id,
                url: url.clone(),
            }));
        self.ops
            .extend(del.iter().map(|&id| Operacao::DeleteKey { id }));
        Ok(())
    }
}

/// Escritas planejadas, na ordem em que o `--sim` as faria em cada destino.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Plano {
    pub objetos: Vec<Operacao>,
    pub redirects: Vec<Operacao>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Publicacao {
    pub relatorio: Relatorio,
    /// Vazio quando `sim`.
    pub plano: Plano,
}

/// `gerar` no destino. Sem `sim`, nenhuma escrita chega a `pub_` nem a `kvs`.
pub fn publicar(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    pub_: &mut dyn Publicador,
    kvs: &mut dyn Redirects,
    agora: i64,
    sim: bool,
) -> Result<Publicacao> {
    if sim {
        let relatorio = gerar(fonte, m, pub_, kvs, agora)?;
        return Ok(Publicacao {
            relatorio,
            plano: Plano::default(),
        });
    }
    let mut p = PublicadorPlano::new(pub_);
    let mut r = RedirectsPlano::new(kvs);
    let relatorio = gerar(fonte, m, &mut p, &mut r, agora)?;
    Ok(Publicacao {
        relatorio,
        plano: Plano {
            objetos: p.ops,
            redirects: r.ops,
        },
    })
}
