//! Fronteira de escrita: tudo que o worker publica passa por `Publicador` (MANIFEST §1, §4).

use std::collections::BTreeMap;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};

use serde::Serialize;

#[derive(Debug, thiserror::Error)]
pub enum ErroPublicador {
    #[error("{operacao} {chave}: {fonte}")]
    Io {
        operacao: &'static str,
        chave: String,
        fonte: std::io::Error,
    },
    #[error("S3 {operacao} {chave}: {fonte}")]
    Aws {
        operacao: &'static str,
        chave: String,
        fonte: String,
    },
    #[error("serializando headers de {chave}: {fonte}")]
    Meta {
        chave: String,
        fonte: serde_json::Error,
    },
}

pub type Result<T, E = ErroPublicador> = std::result::Result<T, E>;

/// Headers do objeto (MANIFEST §4).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Meta {
    pub content_type: &'static str,
    pub content_encoding: Option<&'static str>,
    pub cache_control: &'static str,
}

pub const META_CHUNK: Meta = Meta {
    content_type: "application/json",
    content_encoding: Some("br"),
    cache_control: IMUTAVEL,
};

pub const META_MANIFEST: Meta = Meta {
    content_type: "application/json",
    content_encoding: None,
    cache_control: "public, max-age=300, stale-while-revalidate=60",
};

const IMUTAVEL: &str = "public, max-age=31536000, immutable";
const HTML: &str = "text/html; charset=utf-8";

const fn meta(content_type: &'static str, cache_control: &'static str) -> Meta {
    Meta {
        content_type,
        content_encoding: None,
        cache_control,
    }
}

/// Headers de cada chave pela tabela de MANIFEST §4; `None` fora dela.
/// `manifest.prev.json` segue o `manifest.json`; `_app/**` tem `Content-Type` pela extensão.
pub fn meta_para(chave: &str) -> Option<Meta> {
    const CURTO: &str = "public, max-age=300";
    let ext = chave.rsplit_once('.').map(|(_, e)| e);
    let raiz = !chave.contains('/');
    match chave {
        "manifest.json" | "manifest.prev.json" => Some(META_MANIFEST),
        "index.html" => Some(meta(HTML, CURTO)),
        "robots.txt" => Some(meta("text/plain; charset=utf-8", CURTO)),
        _ if raiz && chave.starts_with("sitemap") && ext == Some("xml") => {
            Some(meta("application/xml", CURTO))
        }
        _ if chave.starts_with("data/chunks/") || chave.starts_with("data/busca/") => {
            Some(META_CHUNK)
        }
        _ if chave.starts_with("oferta/") => chave.ends_with("/index.html").then_some(meta(
            HTML,
            "public, max-age=600, stale-while-revalidate=300",
        )),
        _ if chave.starts_with("img/") => {
            (ext == Some("webp")).then_some(meta("image/webp", IMUTAVEL))
        }
        _ if chave.starts_with("_app/") => tipo_por_extensao(ext?).map(|ct| meta(ct, IMUTAVEL)),
        _ if !raiz && !chave.starts_with("data/") && chave.ends_with("/index.html") => {
            Some(meta(HTML, CURTO))
        }
        _ => None,
    }
}

/// `Content-Type` "conforme" dos arquivos do build do SvelteKit.
fn tipo_por_extensao(ext: &str) -> Option<&'static str> {
    Some(match ext {
        "js" => "text/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "json" => "application/json",
        "html" => HTML,
        "svg" => "image/svg+xml",
        "webp" => "image/webp",
        "png" => "image/png",
        "woff2" => "font/woff2",
        _ => return None,
    })
}

/// Chaves usam `/` e são relativas à raiz do bucket (`data/chunks/5-….json.br`).
pub trait Publicador {
    fn existe(&self, chave: &str) -> Result<bool>;
    fn ler(&self, chave: &str) -> Result<Option<Vec<u8>>>;
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> Result<()>;
    /// Chave ausente não é erro.
    fn remover(&mut self, chave: &str) -> Result<()>;
    /// Chaves que começam com `prefixo`, ordenadas.
    fn listar(&self, prefixo: &str) -> Result<Vec<String>>;
}

/// Sufixo do arquivo de headers gravado ao lado de cada objeto pelo `PublicadorLocal`.
pub const SUFIXO_META: &str = ".meta.json";

/// Espelho do bucket numa pasta: `raiz/chave` + `raiz/chave.meta.json`.
#[derive(Debug, Clone)]
pub struct PublicadorLocal {
    raiz: PathBuf,
}

impl PublicadorLocal {
    pub fn new(raiz: impl Into<PathBuf>) -> Self {
        Self { raiz: raiz.into() }
    }

    fn caminho(&self, chave: &str) -> PathBuf {
        self.raiz.join(chave)
    }
}

fn erro_io(operacao: &'static str, chave: &str) -> impl FnOnce(std::io::Error) -> ErroPublicador {
    let chave = chave.to_owned();
    move |fonte| ErroPublicador::Io {
        operacao,
        chave,
        fonte,
    }
}

impl Publicador for PublicadorLocal {
    fn existe(&self, chave: &str) -> Result<bool> {
        self.caminho(chave)
            .try_exists()
            .map_err(erro_io("verificando", chave))
    }

    fn ler(&self, chave: &str) -> Result<Option<Vec<u8>>> {
        match std::fs::read(self.caminho(chave)) {
            Ok(b) => Ok(Some(b)),
            Err(e) if e.kind() == ErrorKind::NotFound => Ok(None),
            Err(e) => Err(erro_io("lendo", chave)(e)),
        }
    }

    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> Result<()> {
        let caminho = self.caminho(chave);
        if let Some(pai) = caminho.parent() {
            std::fs::create_dir_all(pai).map_err(erro_io("criando pasta de", chave))?;
        }
        std::fs::write(&caminho, bytes).map_err(erro_io("gravando", chave))?;
        let json = serde_json::to_vec(meta).map_err(|fonte| ErroPublicador::Meta {
            chave: chave.to_owned(),
            fonte,
        })?;
        std::fs::write(self.caminho(&format!("{chave}{SUFIXO_META}")), json)
            .map_err(erro_io("gravando headers de", chave))
    }

    fn remover(&mut self, chave: &str) -> Result<()> {
        for c in [chave.to_owned(), format!("{chave}{SUFIXO_META}")] {
            match std::fs::remove_file(self.caminho(&c)) {
                Ok(()) => {}
                Err(e) if e.kind() == ErrorKind::NotFound => {}
                Err(e) => return Err(erro_io("removendo", &c)(e)),
            }
        }
        Ok(())
    }

    fn listar(&self, prefixo: &str) -> Result<Vec<String>> {
        let base = prefixo.rfind('/').map_or("", |i| &prefixo[..=i]);
        let mut chaves = Vec::new();
        coletar(&self.caminho(base), base, &mut chaves)?;
        chaves.retain(|c| c.starts_with(prefixo) && !c.ends_with(SUFIXO_META));
        chaves.sort();
        Ok(chaves)
    }
}

/// Arquivos sob `dir` como chaves `rel/…`. Pasta ausente = vazia.
fn coletar(dir: &Path, rel: &str, out: &mut Vec<String>) -> Result<()> {
    let entradas = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(e) if e.kind() == ErrorKind::NotFound => return Ok(()),
        Err(e) => return Err(erro_io("listando", rel)(e)),
    };
    for entrada in entradas {
        let entrada = entrada.map_err(erro_io("listando", rel))?;
        let chave = format!("{rel}{}", entrada.file_name().to_string_lossy());
        let tipo = entrada.file_type().map_err(erro_io("listando", &chave))?;
        if tipo.is_dir() {
            coletar(&entrada.path(), &format!("{chave}/"), out)?;
        } else {
            out.push(chave);
        }
    }
    Ok(())
}

/// Publicador em memória para testes. Guarda o histórico de gravações em ordem.
#[derive(Debug, Clone, Default)]
pub struct PublicadorMemoria {
    objetos: BTreeMap<String, (Vec<u8>, Meta)>,
    gravacoes: Vec<String>,
    remocoes: Vec<String>,
}

impl PublicadorMemoria {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn meta(&self, chave: &str) -> Option<Meta> {
        self.objetos.get(chave).map(|(_, m)| *m)
    }

    /// Chaves passadas a `gravar`, na ordem, desde a criação.
    pub fn gravacoes(&self) -> &[String] {
        &self.gravacoes
    }

    /// Chaves passadas a `remover`, na ordem, desde a criação.
    pub fn remocoes(&self) -> &[String] {
        &self.remocoes
    }
}

impl Publicador for PublicadorMemoria {
    fn existe(&self, chave: &str) -> Result<bool> {
        Ok(self.objetos.contains_key(chave))
    }

    fn ler(&self, chave: &str) -> Result<Option<Vec<u8>>> {
        Ok(self.objetos.get(chave).map(|(b, _)| b.clone()))
    }

    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> Result<()> {
        self.objetos
            .insert(chave.to_owned(), (bytes.to_vec(), *meta));
        self.gravacoes.push(chave.to_owned());
        Ok(())
    }

    fn remover(&mut self, chave: &str) -> Result<()> {
        self.objetos.remove(chave);
        self.remocoes.push(chave.to_owned());
        Ok(())
    }

    fn listar(&self, prefixo: &str) -> Result<Vec<String>> {
        Ok(self
            .objetos
            .keys()
            .filter(|c| c.starts_with(prefixo))
            .cloned()
            .collect())
    }
}
