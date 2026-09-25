//! Linha do Oracle → projeções do contrato (CONTRATO §3, §4, §9).

use tracing::warn;

use crate::mapeamento::Mapeamento;
use crate::modelo::{OfertaCard, OfertaPagina, Produto, Status};

/// Uma linha de OFERTA como a fonte entrega. Datas em segundos Unix UTC.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct LinhaOferta {
    pub id: i64,
    pub id_produto: Option<i64>,
    /// `DS_LOJA`
    pub loja: Option<String>,
    /// `DS_TITULO`
    pub titulo: Option<String>,
    /// `VL_PRECO_DE`, em reais
    pub preco_de: Option<f64>,
    /// `VL_PRECO_POR`, em reais
    pub preco_por: Option<f64>,
    pub cupom: Option<String>,
    /// `NR_NOTA_AVALIACAO`
    pub nota: Option<f64>,
    /// `QT_AVALIACAO`
    pub qt_avaliacoes: Option<i64>,
    pub dt_oferta: Option<i64>,
    /// `DS_COMUNIDADE`
    pub area: Option<String>,
    pub publico: Option<String>,
    /// `ST_ATIVO = 1`
    pub ativo: bool,
    pub dt_desativacao: Option<i64>,
}

/// Uma linha de PRODUTO. Preços em reais.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct LinhaProduto {
    pub id_produto: i64,
    /// `DS_DESCRICAO_PRODUTO`
    pub descricao: Option<String>,
    pub marca: Option<String>,
    pub fabricante: Option<String>,
    pub modelo: Option<String>,
    pub pais_origem: Option<String>,
    pub genero: Option<String>,
    pub faixa_etaria: Option<String>,
    /// `VR_PRECO_MINIMO`
    pub preco_min: Option<f64>,
    /// `VR_PRECO_MAXIMO`
    pub preco_max: Option<f64>,
}

/// Motivo de rejeição (CONTRATO §9). O registro não é publicado.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, thiserror::Error)]
pub enum Rejeicao {
    #[error("preco_por ausente ou <= 0")]
    PrecoPorInvalido,
    #[error("titulo vazio")]
    TituloVazio,
    #[error("loja sem mapeamento")]
    LojaSemMapeamento,
    #[error("area sem mapeamento")]
    AreaSemMapeamento,
    #[error("publico sem mapeamento")]
    PublicoSemMapeamento,
    #[error("dt_oferta nula")]
    DataNula,
    #[error("id_produto ausente")]
    IdProdutoAusente,
}

const MAX_TITULO_CARD: usize = 200;
const MAX_CUPOM: usize = 30;
const MAX_TITULO_PAGINA: usize = 400;
const MAX_DESCRICAO: usize = 600;

pub fn para_card(l: &LinhaOferta, m: &Mapeamento) -> Result<OfertaCard, Rejeicao> {
    let pp = l
        .preco_por
        .map(centavos)
        .filter(|&pp| pp > 0)
        .ok_or(Rejeicao::PrecoPorInvalido)?;
    let titulo = l
        .titulo
        .as_deref()
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .ok_or(Rejeicao::TituloVazio)?;
    let texto = |s: &Option<String>| s.as_deref().unwrap_or_default().to_owned();
    let loja = m.loja(&texto(&l.loja)).ok_or(Rejeicao::LojaSemMapeamento)?;
    let area = m.area(&texto(&l.area)).ok_or(Rejeicao::AreaSemMapeamento)?;
    let publico = m
        .publico(&texto(&l.publico))
        .ok_or(Rejeicao::PublicoSemMapeamento)?;
    let dt = l.dt_oferta.ok_or(Rejeicao::DataNula)?;

    Ok(OfertaCard {
        id: l.id,
        loja,
        titulo: truncar(titulo, MAX_TITULO_CARD),
        preco_de: l.preco_de.map(centavos).filter(|&pd| pd > pp),
        preco_por: pp,
        cupom: cupom(l),
        dt_oferta: iso_utc(dt),
        area,
        publico,
        x: (!l.ativo).then_some(1),
    })
}

/// Página da oferta: card validado + campos completos. `id_produto` é obrigatório aqui.
pub fn para_pagina(
    l: &LinhaOferta,
    p: Option<&LinhaProduto>,
    m: &Mapeamento,
) -> Result<OfertaPagina, Rejeicao> {
    let card = para_card(l, m)?;
    let id_produto = l
        .id_produto
        .filter(|&id| id >= 1)
        .ok_or(Rejeicao::IdProdutoAusente)?;
    let integral = l.titulo.as_deref().unwrap_or_default().trim();
    let titulo = truncar(integral, MAX_TITULO_PAGINA);
    if titulo.len() != integral.len() {
        warn!(
            id = l.id,
            "titulo > {MAX_TITULO_PAGINA} caracteres; cortado na página"
        );
    }
    Ok(OfertaPagina {
        id: card.id,
        id_produto,
        loja: card.loja,
        titulo,
        preco_de: card.preco_de,
        preco_por: card.preco_por,
        desconto_pct: card.preco_de.map(|pd| desconto_pct(pd, card.preco_por)),
        cupom: card.cupom,
        nota: l
            .nota
            .filter(|n| (0.0..=5.0).contains(n))
            .map(|n| (n * 10.0).round() / 10.0),
        qt_avaliacoes: l.qt_avaliacoes.filter(|&q| q >= 0),
        dt_oferta: card.dt_oferta,
        area: card.area,
        publico: card.publico,
        status: if l.ativo {
            Status::Ativa
        } else {
            Status::Encerrada
        },
        produto: p.and_then(produto),
    })
}

/// `round((1 - pp/pd) * 100)` meia para cima, em inteiros, limitado a 0..=99. Exige `pd > pp > 0`.
fn desconto_pct(pd: i64, pp: i64) -> i64 {
    let pct = (200 * (pd - pp) + pd) / (2 * pd);
    pct.clamp(0, 99)
}

fn produto(p: &LinhaProduto) -> Option<Produto> {
    let descricao = p
        .descricao
        .as_deref()?
        .replace("\r\n", "\n")
        .split("\n\n")
        .map(str::trim)
        .find(|b| !b.is_empty())
        .map(|b| truncar(b, MAX_DESCRICAO))?;
    let texto = |s: &Option<String>, max: usize| {
        let t = s.as_deref()?.trim();
        (!t.is_empty()).then(|| t.chars().take(max).collect::<String>())
    };
    let preco = |v: Option<f64>| v.map(centavos).filter(|&c| c > 0);
    Some(Produto {
        descricao,
        marca: texto(&p.marca, 40),
        fabricante: texto(&p.fabricante, 80),
        modelo: texto(&p.modelo, 200),
        pais_origem: texto(&p.pais_origem, 40),
        genero: texto(&p.genero, 20),
        faixa_etaria: texto(&p.faixa_etaria, 20),
        preco_min: preco(p.preco_min),
        preco_max: preco(p.preco_max),
    })
}

fn cupom(l: &LinhaOferta) -> Option<String> {
    let c = l.cupom.as_deref()?.trim().to_uppercase();
    if c.is_empty() {
        return None;
    }
    let valido = c.chars().count() <= MAX_CUPOM
        && c.chars()
            .all(|ch| ch.is_ascii_uppercase() || ch.is_ascii_digit() || ch == '_' || ch == '-');
    if !valido {
        warn!(id = l.id, cupom = %c, "cupom fora do padrão; omitido");
        return None;
    }
    Some(c)
}

/// Reais → centavos, arredondando meia para cima sobre o decimal que o `f64` representa
/// (`19.995` → `2000`, embora `19.995 * 100.0` seja `1999.49…`). Não finito → 0.
pub fn centavos(n: f64) -> i64 {
    if !n.is_finite() {
        return 0;
    }
    // Display de f64 dá o decimal mais curto que faz round-trip, sem notação científica.
    let s = n.abs().to_string();
    let (inteiro, frac) = s.split_once('.').unwrap_or((&s, ""));
    let mut digitos = frac
        .bytes()
        .map(|b| i64::from(b - b'0'))
        .chain(std::iter::repeat(0));
    let (d1, d2, d3) = (
        digitos.next().unwrap_or(0),
        digitos.next().unwrap_or(0),
        digitos.next().unwrap_or(0),
    );
    let reais: i64 = inteiro.parse().unwrap_or(i64::MAX / 100);
    let c = reais
        .saturating_mul(100)
        .saturating_add(d1 * 10 + d2 + i64::from(d3 >= 5));
    if n < 0.0 { -c } else { c }
}

/// Corta em `max` caracteres: `max - 3` na última fronteira de palavra + `…` (CONTRATO §3).
pub(crate) fn truncar(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        return s.to_owned();
    }
    let corte: String = s.chars().take(max - 3).collect();
    let base = match corte.rfind(char::is_whitespace) {
        Some(i) => corte[..i].trim_end(),
        None => corte.as_str(),
    };
    format!("{base}…")
}

/// Segundos Unix → `YYYY-MM-DDThh:mm:ssZ`.
pub fn iso_utc(segundos: i64) -> String {
    let dias = segundos.div_euclid(86_400);
    let s = segundos.rem_euclid(86_400);
    let (a, m, d) = data_civil(dias);
    format!(
        "{a:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        s / 3600,
        s % 3600 / 60,
        s % 60
    )
}

/// Dias desde 1970-01-01 → (ano, mês, dia). Algoritmo `civil_from_days` de H. Hinnant.
fn data_civil(dias: i64) -> (i64, i64, i64) {
    let z = dias + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let a = yoe + era * 400 + i64::from(m <= 2);
    (a, m, d)
}
