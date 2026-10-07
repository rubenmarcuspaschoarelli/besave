//! Candidatas ao canal (BSV-40 regras 2–4): filtros, repetição por produto e ordem.

use std::cmp::Reverse;
use std::collections::HashSet;

use tracing::debug;

use crate::envio::fonte::{FonteEnvio, UltimoEnvio};
use crate::envio::modelo::{OfertaCanal, Parametros, para_canal};
use crate::fonte::Result;
use crate::mapeamento::Mapeamento;
use crate::modelo::Area;

const DIA: i64 = 86_400;

/// Oferta escolhida: a projeção, a área (placeholder da foto) e se leva "Caiu mais o preço!!!".
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidata {
    pub oferta: OfertaCanal,
    pub area: Area,
    pub caiu: bool,
}

/// Até `n` candidatas, na ordem de envio. A repetição considera também as escolhidas antes no
/// mesmo lote.
pub fn selecionar(
    fonte: &dyn FonteEnvio,
    m: &Mapeamento,
    p: &Parametros,
    canal: i64,
    agora: i64,
    n: usize,
) -> Result<Vec<Candidata>> {
    if n == 0 {
        return Ok(Vec::new());
    }
    let desde = agora - p.horas_oferta_max * 3600;
    let mut todas: Vec<(OfertaCanal, Area)> = fonte
        .candidatas(canal, desde)?
        .into_iter()
        .filter(|l| {
            l.oferta.ativo
                && l.dt_publicacao_site.is_some()
                && l.oferta.dt_oferta.is_some_and(|d| d >= desde)
        })
        .filter_map(|l| {
            let o = para_canal(&l, m)
                .inspect_err(|r| debug!(id = l.oferta.id, motivo = %r, "fora do canal"))
                .ok()?;
            let area = m.area(l.oferta.area.as_deref().unwrap_or_default())?;
            Some((o, area))
        })
        .filter(|(o, _)| o.desconto_pct.is_none_or(|pct| pct >= p.pc_desconto_min))
        .collect();
    let ids: Vec<i64> = todas.iter().map(|(o, _)| o.id).collect();
    let enviadas = fonte.enviadas(canal, &ids)?;
    todas.retain(|(o, _)| !enviadas.contains(&o.id));
    todas.sort_by_key(|(o, _)| {
        (
            Reverse(o.desconto_pct.unwrap_or(0)),
            o.cupom.is_none(),
            Reverse(o.dt_oferta.clone()),
            Reverse(o.id),
        )
    });

    // "Há menos de N dias": `DT_ENVIO > agora − N dias`.
    let limite = agora - p.dias_repeticao * DIA;
    let produtos: Vec<i64> = todas
        .iter()
        .map(|(o, _)| o.id_produto)
        .collect::<HashSet<_>>()
        .into_iter()
        .collect();
    let mut historico = fonte.ultimos_por_produto(canal, &produtos, limite)?;
    historico.retain(|_, u| u.dt_envio > limite);

    let mut escolhidas = Vec::with_capacity(n);
    for (o, area) in todas {
        if escolhidas.len() == n {
            break;
        }
        let caiu = match historico.get(&o.id_produto) {
            None => false,
            Some(u) if caiu_o_bastante(o.preco_por, u.preco_por, p.pc_queda_repeticao) => true,
            Some(_) => {
                debug!(id = o.id, "produto enviado há pouco sem queda suficiente");
                continue;
            }
        };
        historico.insert(
            o.id_produto,
            UltimoEnvio {
                preco_por: o.preco_por,
                dt_envio: agora,
            },
        );
        escolhidas.push(Candidata {
            oferta: o,
            area,
            caiu,
        });
    }
    Ok(escolhidas)
}

/// `pp ≤ último × (1 − queda/100)`, em inteiros.
fn caiu_o_bastante(pp: i64, ultimo: i64, queda_pct: i64) -> bool {
    i128::from(pp) * 100 <= i128::from(ultimo) * i128::from(100 - queda_pct)
}
