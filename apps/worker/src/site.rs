//! Sitemap, robots.txt e índice `_estado/` do site (BSV-21, MANIFEST §1, CONTRATO §7.1). O CSS das
//! páginas (`/assets/besave.css`) é gerado e publicado pelo site (BSV-30, AD-078).

use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write;

use tracing::{debug, warn};

use crate::modelo::{OfertaPagina, Status};
use crate::pagina_html::{ErroTemplate, TemplateOferta};
use crate::paginas::{ErroPaginas, IndicePaginas, RelatorioPaginas, hash16, publicar_paginas};
use crate::publicador::{ErroPublicador, META_ESTADO, META_ROBOTS, META_SITEMAP, Publicador};

/// URLs por `sitemap-{n}.xml`: margem sob o limite de 50 000 do protocolo.
pub const MAX_URLS_SITEMAP: usize = 45_000;
pub const CHAVE_SITEMAP_INDEX: &str = "sitemap.xml";
pub const CHAVE_ROBOTS: &str = "robots.txt";
/// Índice do que já está no bucket: id → hash16 da página, mais `_robots` e cada `sitemap*.xml`.
/// Lido uma vez por execução; regravado só quando muda. `_css` de índices antigos é ignorado.
pub const CHAVE_ESTADO: &str = "_estado/paginas.json";
const CHAVE_ESTADO_ROBOTS: &str = "_robots";
const BASE_PADRAO: &str = "https://besave.com.br";
const XMLNS: &str = "http://www.sitemaps.org/schemas/sitemap/0.9";

#[derive(Debug, thiserror::Error)]
pub enum ErroSite {
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error(transparent)]
    Paginas(#[from] ErroPaginas),
    #[error(transparent)]
    Template(#[from] ErroTemplate),
    #[error("serializando {CHAVE_ESTADO}: {0}")]
    Estado(serde_json::Error),
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioSite {
    pub paginas: RelatorioPaginas,
    pub sitemaps_publicados: u64,
    pub sitemaps_removidos: u64,
    pub robots_publicado: bool,
    pub indice_gravado: bool,
}

/// Conteúdo de `_estado/paginas.json`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct EstadoSite {
    pub paginas: IndicePaginas,
    pub robots: Option<String>,
    pub sitemaps: BTreeMap<String, String>,
}

impl EstadoSite {
    /// `None` se não for um objeto JSON de strings. Chaves desconhecidas são ignoradas.
    pub fn de_json(bytes: &[u8]) -> Option<Self> {
        let mapa: BTreeMap<String, String> = serde_json::from_slice(bytes).ok()?;
        let mut e = Self::default();
        for (k, v) in mapa {
            match k.as_str() {
                CHAVE_ESTADO_ROBOTS => e.robots = Some(v),
                _ if k.starts_with("sitemap") => {
                    e.sitemaps.insert(k, v);
                }
                _ => {
                    if let Ok(id) = k.parse::<i64>() {
                        e.paginas.0.insert(id, v);
                    }
                }
            }
        }
        Some(e)
    }

    /// Objeto plano: `{"5412": "…", "_robots": "…", "sitemap-1.xml": "…"}`.
    pub fn para_json(&self) -> Result<Vec<u8>, serde_json::Error> {
        let mut mapa: BTreeMap<String, &str> = self
            .paginas
            .0
            .iter()
            .map(|(id, h)| (id.to_string(), h.as_str()))
            .collect();
        if let Some(h) = &self.robots {
            mapa.insert(CHAVE_ESTADO_ROBOTS.to_owned(), h);
        }
        for (k, h) in &self.sitemaps {
            mapa.insert(k.clone(), h);
        }
        serde_json::to_vec(&mapa)
    }
}

/// Estado sem índice: só as páginas `oferta/{id}/index.html` que já estão no bucket, com hash vazio
/// (nunca igual a um hash16, então todas sobem de novo; as de ids fora do conjunto atual são
/// expurgadas por `publicar_paginas`).
fn paginas_no_bucket(pub_: &dyn Publicador) -> Result<EstadoSite, ErroPublicador> {
    let mut e = EstadoSite::default();
    for chave in pub_.listar("oferta/")? {
        let id = chave
            .strip_prefix("oferta/")
            .and_then(|r| r.strip_suffix("/index.html"))
            .and_then(|id| id.parse::<i64>().ok());
        if let Some(id) = id {
            e.paginas.0.insert(id, String::new());
        }
    }
    Ok(e)
}

/// MANIFEST §6 passo 3, na ordem: páginas (com expurgo), sitemaps (só ATIVAS com página no
/// bucket), robots e, por último, o índice. Cada objeto só sobe se o hash difere do índice
/// anterior. Índice ausente ou ilegível: tudo sobe (páginas são idempotentes) e o conjunto anterior
/// de páginas é reconstruído do bucket, para que as órfãs sejam expurgadas mesmo sem índice.
pub fn publicar_site(
    paginas: &[OfertaPagina],
    cfg: &ConfigSite,
    pub_: &mut dyn Publicador,
) -> Result<RelatorioSite, ErroSite> {
    let lido = pub_.ler(CHAVE_ESTADO)?;
    let anterior = match lido.as_deref().map(EstadoSite::de_json) {
        Some(Some(e)) => e,
        sem_indice => {
            if sem_indice.is_some() {
                warn!("{CHAVE_ESTADO} ilegível; tratando como ausente e reenviando tudo");
            }
            paginas_no_bucket(pub_)?
        }
    };
    let mut rel = RelatorioSite::default();
    let mut novo = EstadoSite::default();

    let t = TemplateOferta::novo()?;
    let (indice, rel_paginas) = publicar_paginas(paginas, &t, pub_, &anterior.paginas)?;
    rel.paginas = rel_paginas;

    let ativas: Vec<(i64, &str)> = paginas
        .iter()
        .filter(|o| o.status == Status::Ativa && indice.0.contains_key(&o.id))
        .map(|o| (o.id, o.dt_oferta.as_str()))
        .collect();
    novo.paginas = indice;
    let arquivos = sitemaps(&ativas, &cfg.base);
    let atuais: BTreeSet<&str> = arquivos.iter().map(|(c, _)| c.as_str()).collect();
    // Filhos antes do index (o index nunca aponta para arquivo que ainda não subiu).
    for (chave, bytes) in &arquivos {
        let h = hash16(bytes);
        if anterior.sitemaps.get(chave) != Some(&h) {
            pub_.gravar(chave, bytes, &META_SITEMAP)?;
            rel.sitemaps_publicados += 1;
        }
        novo.sitemaps.insert(chave.clone(), h);
    }
    for chave in pub_.listar("sitemap-")? {
        if !atuais.contains(chave.as_str()) {
            pub_.remover(&chave)?;
            rel.sitemaps_removidos += 1;
            debug!(chave, "sitemap que não é mais gerado removido");
        }
    }

    let texto = robots(cfg.indexavel, &cfg.base);
    let h = hash16(texto.as_bytes());
    if anterior.robots.as_ref() != Some(&h) {
        pub_.gravar(CHAVE_ROBOTS, texto.as_bytes(), &META_ROBOTS)?;
        rel.robots_publicado = true;
    }
    novo.robots = Some(h);

    let json = novo.para_json().map_err(ErroSite::Estado)?;
    if lido.as_deref() != Some(json.as_slice()) {
        pub_.gravar(CHAVE_ESTADO, &json, &META_ESTADO)?;
        rel.indice_gravado = true;
    }
    Ok(rel)
}

#[derive(Debug, thiserror::Error)]
pub enum ErroConfigSite {
    #[error("variável de ambiente {0} inválida: {1}")]
    Invalida(&'static str, String),
}

/// `BESAVE_BASE_URL` (sem `/` final) e `BESAVE_INDEXAVEL`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigSite {
    pub base: String,
    pub indexavel: bool,
}

impl Default for ConfigSite {
    fn default() -> Self {
        Self {
            base: BASE_PADRAO.to_owned(),
            indexavel: false,
        }
    }
}

impl ConfigSite {
    pub fn do_env() -> Result<Self, ErroConfigSite> {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroConfigSite> {
        let base = env("BESAVE_BASE_URL")
            .filter(|v| !v.is_empty())
            .unwrap_or_else(|| BASE_PADRAO.to_owned());
        if !base.starts_with("https://") && !base.starts_with("http://") {
            return Err(ErroConfigSite::Invalida(
                "BESAVE_BASE_URL",
                format!("{base:?}, esperado http(s)://…"),
            ));
        }
        // Flag de SEO: nunca liga por erro de digitação.
        let indexavel = match env("BESAVE_INDEXAVEL").as_deref() {
            None | Some("" | "false" | "0") => false,
            Some("true" | "1") => true,
            Some(outro) => {
                return Err(ErroConfigSite::Invalida(
                    "BESAVE_INDEXAVEL",
                    format!("{outro:?}, esperado true ou false"),
                ));
            }
        };
        Ok(Self {
            base: base.trim_end_matches('/').to_owned(),
            indexavel,
        })
    }
}

/// `sitemap-{n}.xml` (n a partir de 1), um por bloco de `MAX_URLS_SITEMAP` ofertas ativas em ordem
/// de id, e por último o index `sitemap.xml`. `ativas` = `(id, dt_oferta ISO UTC)`; `lastmod` é a
/// data (AAAA-MM-DD) de `dt_oferta`. Sem ativas, sai um `sitemap-1.xml` vazio: o index nunca
/// aponta para arquivo inexistente.
pub fn sitemaps(ativas: &[(i64, &str)], base: &str) -> Vec<(String, Vec<u8>)> {
    let base = escapar(base);
    let mut ordenadas = ativas.to_vec();
    ordenadas.sort_unstable_by_key(|(id, _)| *id);
    let blocos: Vec<&[(i64, &str)]> = if ordenadas.is_empty() {
        vec![&[]]
    } else {
        ordenadas.chunks(MAX_URLS_SITEMAP).collect()
    };
    let mut out = Vec::with_capacity(blocos.len() + 1);
    let mut index =
        format!("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<sitemapindex xmlns=\"{XMLNS}\">\n");
    for (i, bloco) in blocos.iter().enumerate() {
        let chave = format!("sitemap-{}.xml", i + 1);
        let mut xml = String::with_capacity(bloco.len() * 90 + 128);
        xml.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        let _ = writeln!(xml, "<urlset xmlns=\"{XMLNS}\">");
        for (id, dt) in *bloco {
            let data = escapar(dt.get(..10).unwrap_or(dt));
            let _ = writeln!(
                xml,
                "<url><loc>{base}/oferta/{id}/</loc><lastmod>{data}</lastmod></url>"
            );
        }
        xml.push_str("</urlset>\n");
        let _ = writeln!(index, "<sitemap><loc>{base}/{chave}</loc></sitemap>");
        out.push((chave, xml.into_bytes()));
    }
    index.push_str("</sitemapindex>\n");
    out.push((CHAVE_SITEMAP_INDEX.to_owned(), index.into_bytes()));
    out
}

/// Não indexável enquanto o site está em `*.cloudfront.net` (conteúdo duplicado); a virada de DNS
/// liga `BESAVE_INDEXAVEL`.
pub fn robots(indexavel: bool, base: &str) -> String {
    if indexavel {
        format!("User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
    } else {
        "User-agent: *\nDisallow: /\n".to_owned()
    }
}

fn escapar(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(c),
        }
    }
    out
}
