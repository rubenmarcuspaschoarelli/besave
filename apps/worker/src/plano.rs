//! `--publicar` sem `--sim`: `gerar` roda contra o destino real, mas as escritas só são
//! registradas (proteção contra publicar no bucket errado).

use std::collections::BTreeMap;
use std::fmt;
use std::path::Path;

use crate::fonte::FonteOfertas;
use crate::geracao::{Relatorio, Result, gerar};
use crate::mapeamento::Mapeamento;
use crate::publicador::{self, Meta, Publicador};
use crate::redirects::{self, Redirects};
use crate::site::ConfigSite;

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

/// Chaves de exemplo por linha de resumo de páginas.
const EXEMPLOS_PAGINA: usize = 5;

fn e_pagina(chave: &str) -> bool {
    chave.starts_with("oferta/") && chave.ends_with("/index.html")
}

/// Escritas planejadas, na ordem em que o `--sim` as faria em cada destino.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Plano {
    pub objetos: Vec<Operacao>,
    pub redirects: Vec<Operacao>,
}

impl Plano {
    /// Texto que o `--publicar` imprime: uma seção por destino, uma operação por linha.
    /// A KVS é sincronizada depois dos chunks e antes de `manifest.prev.json`/`manifest.json`.
    /// Páginas de oferta (até ~30 mil) viram uma linha por tipo, com contagem e até
    /// `EXEMPLOS_PAGINA` chaves, na posição da primeira operação daquele tipo.
    pub fn linhas(&self) -> Vec<String> {
        let op = |o: &Operacao| format!("  {o}");
        let mut v = vec!["S3:".to_owned()];
        // Por tipo ("gravar", "remover"): linha reservada em `v` e chaves das páginas.
        let mut paginas: [(&str, Option<usize>, Vec<&str>); 2] =
            [("gravar", None, Vec::new()), ("remover", None, Vec::new())];
        for o in &self.objetos {
            let (tipo, chave) = match o {
                Operacao::Gravar { chave, .. } if e_pagina(chave) => (0, chave),
                Operacao::Remover { chave } if e_pagina(chave) => (1, chave),
                _ => {
                    v.push(op(o));
                    continue;
                }
            };
            let (_, linha, chaves) = &mut paginas[tipo];
            if linha.is_none() {
                *linha = Some(v.len());
                v.push(String::new());
            }
            chaves.push(chave.as_str());
        }
        for (tipo, linha, chaves) in paginas {
            if let Some(i) = linha {
                let ex: Vec<&str> = chaves.iter().take(EXEMPLOS_PAGINA).copied().collect();
                v[i] = format!(
                    "  páginas a {tipo}: {} (ex.: {})",
                    chaves.len(),
                    ex.join(", ")
                );
            }
        }
        v.push("KVS (aplicada antes do manifest.json):".to_owned());
        v.extend(self.redirects.iter().map(op));
        v
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Publicacao {
    pub relatorio: Relatorio,
    /// Vazio quando `sim`.
    pub plano: Plano,
}

/// `gerar` no destino. Sem `sim`, nenhuma escrita chega a `pub_` nem a `kvs`.
// Os argumentos de `gerar` mais `sim`; agrupar só para o lint esconderia a paridade.
#[allow(clippy::too_many_arguments)]
pub fn publicar(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    pub_: &mut dyn Publicador,
    kvs: &mut dyn Redirects,
    dir_imagens: &Path,
    site: &ConfigSite,
    agora: i64,
    sim: bool,
) -> Result<Publicacao> {
    if sim {
        let relatorio = gerar(fonte, m, pub_, kvs, dir_imagens, site, agora)?;
        return Ok(Publicacao {
            relatorio,
            plano: Plano::default(),
        });
    }
    let mut p = PublicadorPlano::new(pub_);
    let mut r = RedirectsPlano::new(kvs);
    let relatorio = gerar(fonte, m, &mut p, &mut r, dir_imagens, site, agora)?;
    Ok(Publicacao {
        relatorio,
        plano: Plano {
            objetos: p.ops,
            redirects: r.ops,
        },
    })
}
