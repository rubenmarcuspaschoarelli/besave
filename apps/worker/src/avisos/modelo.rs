//! Linha de `AVISO` (`sql/bsv-41.sql`) e as regras que o ciclo e o envio compartilham.

/// Imagem da página acima disso: página sem imagem (BSV-41 regra 2).
pub const MAX_IMAGEM_PAGINA: u64 = 1_048_576;

/// Uma linha de `AVISO`. Datas em segundos Unix UTC.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct LinhaAviso {
    pub id: i64,
    pub titulo: String,
    pub texto: String,
    /// `DS_IMAGEM`: nome do arquivo em `BESAVE_AVISOS_DIR`.
    pub imagem: Option<String>,
    pub link_interno: Option<String>,
    pub ativo: bool,
    pub dt_inicio: i64,
    pub dt_fim: Option<i64>,
    pub dt_publicacao_site: Option<i64>,
}

impl LinhaAviso {
    /// `ST_ATIVO = 1` e `DT_INICIO ≤ agora < DT_FIM` (fim nulo = sem fim).
    pub fn vigente(&self, agora: i64) -> bool {
        self.ativo && self.dt_inicio <= agora && self.dt_fim.is_none_or(|f| agora < f)
    }

    /// `DS_LINK_INTERNO` se casar `^/[a-z0-9/_-]*$`; senão `None`.
    pub fn link_valido(&self) -> Option<&str> {
        self.link_interno
            .as_deref()
            .filter(|l| link_interno_valido(l))
    }
}

/// `^/[a-z0-9/_-]*$`: só caminho do próprio site (regra 3). `//…` também é recusado: o navegador o
/// lê como URL de outro domínio.
pub fn link_interno_valido(l: &str) -> bool {
    l.starts_with('/')
        && !l.starts_with("//")
        && l.bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b"/_-".contains(&b))
}

/// Formato aceito para a imagem do aviso.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Formato {
    Webp,
    Jpg,
}

impl Formato {
    pub fn extensao(self) -> &'static str {
        match self {
            Self::Webp => "webp",
            Self::Jpg => "jpg",
        }
    }
}

/// `.webp` ou `.jpg` (sem diferenciar maiúsculas) e nome sem caminho; senão `None`.
pub fn formato_imagem(nome: &str) -> Option<Formato> {
    if nome.contains(['/', '\\']) || nome.contains("..") {
        return None;
    }
    let (_, ext) = nome.rsplit_once('.')?;
    match ext.to_ascii_lowercase().as_str() {
        "webp" => Some(Formato::Webp),
        "jpg" => Some(Formato::Jpg),
        _ => None,
    }
}

/// `"avisos/{id}/index.html"` (MANIFEST §1).
pub fn chave_pagina(id: i64) -> String {
    format!("avisos/{id}/index.html")
}

/// `"img/avisos/{id}.{webp|jpg}"` (MANIFEST §1).
pub fn chave_imagem(id: i64, f: Formato) -> String {
    format!("img/avisos/{id}.{}", f.extensao())
}
