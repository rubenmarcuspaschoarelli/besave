//! Página estática da oferta (BSV-20): template minijinja embutido, tabela de rótulos e filtros
//! de formatação pt-BR. Ligação à geração em massa é BSV-21.

use std::fmt::Write;

use minijinja::{
    AutoEscape, Environment, ErrorKind, Output, State, UndefinedBehavior, Value, context,
    escape_formatter,
};
use serde_json::json;

use crate::modelo::{OfertaPagina, Status};

const TEMPLATE: &str = include_str!("../templates/oferta.html");
/// `templates/areas.json`: rótulos e slugs de área, público e loja (CONTRATO §2.3).
pub const TABELA: &str = include_str!("../templates/areas.json");
pub const URL_BASE: &str = "https://besave.com.br";
/// Tamanho da `<meta name="description">` (caracteres).
const DESCRICAO_MAX: usize = 155;
/// Brasília não tem horário de verão desde 2019.
const FUSO_BRASILIA_MIN: i64 = -180;

#[derive(Debug, thiserror::Error)]
pub enum ErroTemplate {
    #[error("tabela de rótulos inválida: {0}")]
    Tabela(#[from] serde_json::Error),
    #[error("template: {0:#}")]
    Render(#[from] minijinja::Error),
}

/// Template compilado uma vez; `renderizar` é chamado por oferta.
pub struct TemplateOferta {
    env: Environment<'static>,
    tabela: Value,
}

impl TemplateOferta {
    pub fn novo() -> Result<Self, ErroTemplate> {
        let tabela: serde_json::Value = serde_json::from_str(TABELA)?;
        let mut env = Environment::new();
        env.set_undefined_behavior(UndefinedBehavior::Strict);
        env.set_trim_blocks(true);
        env.set_lstrip_blocks(true);
        env.set_formatter(formatar);
        env.add_filter("reais", reais);
        env.add_filter("milhar", milhar);
        env.add_filter("nota", nota);
        env.add_filter("data_br", data_br);
        env.add_template("oferta.html", TEMPLATE)?;
        Ok(Self {
            env,
            tabela: Value::from_serialize(&tabela),
        })
    }

    pub fn renderizar(&self, o: &OfertaPagina) -> Result<String, ErroTemplate> {
        let url = format!("{URL_BASE}/oferta/{}/", o.id);
        let imagem = format!("{URL_BASE}/img/ofertas/{}.webp", o.id);
        let encerrada = o.status == Status::Encerrada;
        let descricao = resumo(
            o.produto.as_ref().map_or(&o.titulo, |p| &p.descricao),
            DESCRICAO_MAX,
        );
        let disponibilidade = if encerrada {
            "https://schema.org/Discontinued"
        } else {
            "https://schema.org/InStock"
        };
        let jsonld = json!({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": o.titulo,
            "description": descricao,
            "image": imagem,
            "url": url,
            "offers": {
                "@type": "Offer",
                "price": decimal(o.preco_por),
                "priceCurrency": "BRL",
                "availability": disponibilidade,
                "url": url,
            },
        });
        let t = self.env.get_template("oferta.html")?;
        Ok(t.render(context! {
            o => Value::from_serialize(o),
            tabela => self.tabela.clone(),
            url,
            imagem,
            encerrada,
            descricao,
            jsonld => Value::from_serialize(&jsonld),
        })?)
    }
}

/// Escape HTML só de `& < > " '`: o padrão do minijinja também troca `/` por `&#x2f;`, o que
/// deixaria URLs e datas ilegíveis no HTML sem ganho de segurança.
fn formatar(out: &mut Output, state: &State, value: &Value) -> Result<(), minijinja::Error> {
    match (state.auto_escape(), value.as_str()) {
        (AutoEscape::Html, Some(s)) if !value.is_safe() => {
            for c in s.chars() {
                match c {
                    '&' => out.write_str("&amp;")?,
                    '<' => out.write_str("&lt;")?,
                    '>' => out.write_str("&gt;")?,
                    '"' => out.write_str("&quot;")?,
                    '\'' => out.write_str("&#x27;")?,
                    _ => out.write_char(c)?,
                }
            }
            Ok(())
        }
        _ => escape_formatter(out, state, value),
    }
}

/// Primeiros `n` caracteres, sem espaços nas pontas.
fn resumo(texto: &str, n: usize) -> String {
    texto
        .trim()
        .chars()
        .take(n)
        .collect::<String>()
        .trim_end()
        .to_string()
}

/// Centavos → `"199.90"` (schema.org `price`).
fn decimal(centavos: i64) -> String {
    format!("{}.{:02}", centavos / 100, centavos % 100)
}

/// `1832` → `"1.832"`.
fn milhar(n: i64) -> String {
    let digitos = n.unsigned_abs().to_string();
    let mut out = String::with_capacity(digitos.len() + digitos.len() / 3 + 1);
    if n < 0 {
        out.push('-');
    }
    for (i, c) in digitos.chars().enumerate() {
        if i > 0 && (digitos.len() - i).is_multiple_of(3) {
            out.push('.');
        }
        out.push(c);
    }
    out
}

/// Centavos → `"R$ 1.299,90"`.
fn reais(centavos: i64) -> String {
    format!(
        "R$ {},{:02}",
        milhar(centavos / 100),
        centavos.rem_euclid(100)
    )
}

/// `4.6` → `"4,6"`.
fn nota(n: f64) -> String {
    format!("{n:.1}").replace('.', ",")
}

/// `"2026-09-24T12:40:00Z"` → `"24/09/2026 às 09:40"` (horário de Brasília).
fn data_br(iso: &str) -> Result<String, minijinja::Error> {
    let invalida =
        || minijinja::Error::new(ErrorKind::InvalidOperation, format!("data inválida: {iso}"));
    let campo = |a: usize, b: usize| -> Result<i64, minijinja::Error> {
        iso.get(a..b)
            .and_then(|s| s.parse().ok())
            .ok_or_else(invalida)
    };
    if iso.len() != 20 || !iso.ends_with('Z') {
        return Err(invalida());
    }
    let (ano, mes, dia) = (campo(0, 4)?, campo(5, 7)?, campo(8, 10)?);
    let minutos = dias_de_civil(ano, mes, dia) * 1440
        + campo(11, 13)? * 60
        + campo(14, 16)?
        + FUSO_BRASILIA_MIN;
    let (a, m, d) = civil_de_dias(minutos.div_euclid(1440));
    let min_dia = minutos.rem_euclid(1440);
    Ok(format!(
        "{d:02}/{m:02}/{a:04} às {:02}:{:02}",
        min_dia / 60,
        min_dia % 60
    ))
}

/// Dias desde 1970-01-01 (algoritmo de H. Hinnant, calendário gregoriano proléptico).
fn dias_de_civil(ano: i64, mes: i64, dia: i64) -> i64 {
    let a = if mes <= 2 { ano - 1 } else { ano };
    let era = a.div_euclid(400);
    let ano_era = a - era * 400;
    let mes_mar = (mes + 9) % 12;
    let dia_ano = (153 * mes_mar + 2) / 5 + dia - 1;
    let dia_era = ano_era * 365 + ano_era / 4 - ano_era / 100 + dia_ano;
    era * 146_097 + dia_era - 719_468
}

fn civil_de_dias(dias: i64) -> (i64, i64, i64) {
    let z = dias + 719_468;
    let era = z.div_euclid(146_097);
    let dia_era = z - era * 146_097;
    let ano_era = (dia_era - dia_era / 1460 + dia_era / 36_524 - dia_era / 146_096) / 365;
    let dia_ano = dia_era - (365 * ano_era + ano_era / 4 - ano_era / 100);
    let mes_mar = (5 * dia_ano + 2) / 153;
    let dia = dia_ano - (153 * mes_mar + 2) / 5 + 1;
    let mes = if mes_mar < 10 {
        mes_mar + 3
    } else {
        mes_mar - 9
    };
    (ano_era + era * 400 + i64::from(mes <= 2), mes, dia)
}
