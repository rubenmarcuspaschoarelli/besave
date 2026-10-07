//! Página `avisos/{id}/index.html` (BSV-41): template minijinja embutido, texto sempre escapado.

use minijinja::{Environment, UndefinedBehavior, Value, context};

use crate::avisos::modelo::{Formato, LinhaAviso, chave_imagem};
use crate::pagina_html::{ErroTemplate, TABELA, URL_BASE, formatar};

const TEMPLATE: &str = include_str!("../../templates/aviso.html");
/// Canal 1 (`@besaveofertas`, `sql/bsv-40.sql`).
pub const CANAL_PADRAO: &str = "https://t.me/besaveofertas";

pub struct TemplateAviso {
    env: Environment<'static>,
    tabela: Value,
    canal: String,
}

impl TemplateAviso {
    /// `canal`: link do canal no rodapé da página.
    pub fn novo(canal: &str) -> Result<Self, ErroTemplate> {
        let tabela: serde_json::Value = serde_json::from_str(TABELA)?;
        let mut env = Environment::new();
        env.set_undefined_behavior(UndefinedBehavior::Strict);
        env.set_trim_blocks(true);
        env.set_lstrip_blocks(true);
        env.set_formatter(formatar);
        env.add_template("aviso.html", TEMPLATE)?;
        Ok(Self {
            env,
            tabela: Value::from_serialize(&tabela),
            canal: canal.to_owned(),
        })
    }

    /// `imagem`: formato da imagem publicada em `img/avisos/`, ou `None` (página sem imagem).
    /// Link interno inválido sai sem botão.
    pub fn renderizar(
        &self,
        a: &LinhaAviso,
        imagem: Option<Formato>,
    ) -> Result<String, ErroTemplate> {
        let t = self.env.get_template("aviso.html")?;
        Ok(t.render(context! {
            titulo => a.titulo.trim(),
            url => format!("{URL_BASE}/avisos/{}/", a.id),
            imagem => imagem.map(|f| format!("/{}", chave_imagem(a.id, f))),
            paragrafos => paragrafos(&a.texto),
            link => a.link_valido(),
            canal => self.canal.as_str(),
            tabela => self.tabela.clone(),
        })?)
    }
}

/// Linhas em branco separam parágrafos; cada parágrafo é a lista das suas linhas (sem espaços nas
/// pontas).
pub fn paragrafos(texto: &str) -> Vec<Vec<String>> {
    let mut out: Vec<Vec<String>> = Vec::new();
    let mut atual: Vec<String> = Vec::new();
    for l in texto.lines().map(str::trim) {
        if l.is_empty() {
            if !atual.is_empty() {
                out.push(std::mem::take(&mut atual));
            }
        } else {
            atual.push(l.to_owned());
        }
    }
    if !atual.is_empty() {
        out.push(atual);
    }
    out
}
