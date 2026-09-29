//! Sitemap, robots.txt e config do site (BSV-21, MANIFEST §1, CONTRATO §7.1).

use std::fmt::Write;

/// URLs por `sitemap-{n}.xml`: margem sob o limite de 50 000 do protocolo.
pub const MAX_URLS_SITEMAP: usize = 45_000;
pub const CHAVE_SITEMAP_INDEX: &str = "sitemap.xml";
pub const CHAVE_ROBOTS: &str = "robots.txt";
const BASE_PADRAO: &str = "https://besave.com.br";
const XMLNS: &str = "http://www.sitemaps.org/schemas/sitemap/0.9";

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
