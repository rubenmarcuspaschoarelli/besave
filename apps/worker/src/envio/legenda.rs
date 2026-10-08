//! Legenda do post (BSV-40 regra 6), `parse_mode=HTML`, ≤ 1024 caracteres.

use crate::conversao::truncar;
use crate::envio::modelo::{OfertaCanal, Parametros};
use crate::modelo::Loja;

/// Limite do Telegram para legenda de foto.
pub const MAX_LEGENDA: usize = 1024;
/// Domínio curto (BSV-16): `besave.io/{id}` → 301 para `/oferta/{id}/`.
pub const DOMINIO_CURTO: &str = "besave.io";
/// Título nunca fica menor que isso (3 caracteres + `…`).
const MIN_TITULO: usize = 4;

/// `&`, `<`, `>` e `"` como entidades (únicas aceitas pelo HTML do Telegram).
pub fn escapar(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            _ => out.push(c),
        }
    }
    out
}

/// Centavos → `R$ 1.234,56`.
pub fn reais(centavos: i64) -> String {
    let (inteiro, frac) = (centavos.abs() / 100, centavos.abs() % 100);
    let digitos = inteiro.to_string();
    let mut milhar = String::new();
    for (i, c) in digitos.chars().enumerate() {
        if i > 0 && (digitos.len() - i) % 3 == 0 {
            milhar.push('.');
        }
        milhar.push(c);
    }
    let sinal = if centavos < 0 { "-" } else { "" };
    format!("R$ {sinal}{milhar},{frac:02}")
}

pub fn nome_loja(l: Loja) -> &'static str {
    match l {
        Loja::Amazon => "Amazon",
        Loja::MercadoLivre => "Mercado Livre",
        Loja::Shopee => "Shopee",
    }
}

/// `https://besave.io/{id}?utm_source=telegram`
pub fn link(id: i64) -> String {
    format!("https://{DOMINIO_CURTO}/{id}?utm_source=telegram")
}

/// Tamanho como o Telegram limita, contado em unidades UTF-16 do HTML bruto (≥ o texto visível).
pub fn tamanho(s: &str) -> usize {
    s.encode_utf16().count()
}

/// Uma linha em HTML e em texto puro (a legenda encerrada usa o texto, riscado).
struct Linha {
    html: String,
    texto: String,
}

fn linha(html: String, texto: String) -> Linha {
    Linha { html, texto }
}

/// Linhas depois do título, na ordem da regra 6. Opcionais vazias não entram.
/// Devolve as linhas e, à parte, a linha do link (a legenda encerrada não a usa).
fn corpo(o: &OfertaCanal, caiu: bool, p: &Parametros) -> (Vec<Linha>, String) {
    let mut v = Vec::new();
    if let Some(d) = &o.destaque {
        v.push(linha(escapar(d), d.clone()));
    }
    let mut html = Vec::new();
    let mut texto = Vec::new();
    if let Some(pct) = o.desconto_pct.filter(|&pct| pct >= p.pc_desconto_destaque) {
        html.push(format!("🔥 <b>-{pct}%</b>"));
        texto.push(format!("🔥 -{pct}%"));
    }
    if let Some(de) = o.preco_de {
        html.push(format!("<s>{}</s>", reais(de)));
        texto.push(reais(de));
    }
    html.push(format!("<b>{}</b>", reais(o.preco_por)));
    texto.push(reais(o.preco_por));
    if o.recorrencia {
        html.push("🔁 <i>(Recorrência)</i>".to_owned());
        texto.push("🔁 (Recorrência)".to_owned());
    }
    v.push(linha(html.join("  "), texto.join("  ")));
    if caiu {
        v.push(linha(
            "📉 <b>Caiu mais o preço!!!</b>".to_owned(),
            "📉 Caiu mais o preço!!!".to_owned(),
        ));
    }
    if let Some(c) = &o.cupom {
        v.push(linha(
            format!("🎟️ Cupom: <code>{}</code>", escapar(c)),
            format!("🎟️ Cupom: {c}"),
        ));
    }
    let loja = nome_loja(o.loja);
    let link = format!(
        "Promoção {loja}: <a href=\"{}\">{DOMINIO_CURTO}/{}</a>",
        link(o.id),
        o.id
    );
    (v, link)
}

/// Corta o título (fronteira de palavra + `…`) no maior tamanho com que `montar(título)` cabe em
/// `MAX_LEGENDA` (busca binária: o escape faz o HTML crescer mais que o título).
pub(crate) fn caber(titulo: &str, montar: impl Fn(&str) -> String) -> String {
    let inteira = montar(titulo);
    let total = titulo.chars().count();
    if tamanho(&inteira) <= MAX_LEGENDA || total <= MIN_TITULO {
        return inteira;
    }
    let (mut cabe, mut nao_cabe) = (MIN_TITULO, total);
    while nao_cabe - cabe > 1 {
        let meio = cabe + (nao_cabe - cabe) / 2;
        if tamanho(&montar(&truncar(titulo, meio))) <= MAX_LEGENDA {
            cabe = meio;
        } else {
            nao_cabe = meio;
        }
    }
    montar(&truncar(titulo, cabe))
}

/// Legenda do post.
pub fn legenda(o: &OfertaCanal, caiu: bool, p: &Parametros) -> String {
    let (linhas, link) = corpo(o, caiu, p);
    caber(&o.titulo, |t| {
        std::iter::once(format!("<b>{}</b>", escapar(t)))
            .chain(linhas.iter().map(|l| l.html.clone()))
            .chain(std::iter::once(link.clone()))
            .collect::<Vec<_>>()
            .join("\n")
    })
}

/// Legenda de oferta expirada: aviso no topo e o texto original riscado, sem link nem "Caiu mais".
pub fn legenda_encerrada(o: &OfertaCanal, p: &Parametros) -> String {
    let (linhas, _) = corpo(o, false, p);
    caber(&o.titulo, |t| {
        let texto = std::iter::once(t.to_owned())
            .chain(linhas.iter().map(|l| l.texto.clone()))
            .collect::<Vec<_>>()
            .join("\n");
        format!("⛔ <b>Oferta encerrada</b>\n<s>{}</s>", escapar(&texto))
    })
}
