//! Legenda do post (BSV-40 regra 6, layout da BSV-62), `parse_mode=HTML`, ≤ 1024 caracteres.

use crate::conversao::truncar;
use crate::envio::frases::Frases;
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

/// `https://besave.io/{id}?utm_source=whatsapp`
pub fn link_whatsapp(id: i64) -> String {
    format!("https://{DOMINIO_CURTO}/{id}?utm_source=whatsapp")
}

/// Limites da legenda do WhatsApp (BSV-62): caracteres e bytes UTF-8 (`DS_LEGENDA` é
/// `VARCHAR2(4000 BYTE)`).
pub const MAX_LEGENDA_WA: usize = 1024;
pub const MAX_BYTES_WA: usize = 4000;

/// Cabe nos dois limites do WhatsApp.
pub fn cabe_whatsapp(s: &str) -> bool {
    s.chars().count() <= MAX_LEGENDA_WA && s.len() <= MAX_BYTES_WA
}

/// Texto variável no WhatsApp: sem `*`, `_`, `~` e `` ` `` (não há escape) e com espaços repetidos
/// virando um.
pub fn limpar_whatsapp(s: &str) -> String {
    let sem: String = s
        .chars()
        .filter(|c| !matches!(c, '*' | '_' | '~' | '`'))
        .collect();
    sem.split(' ')
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
}

/// Tamanho como o Telegram limita, contado em unidades UTF-16 do HTML bruto (≥ o texto visível).
pub fn tamanho(s: &str) -> usize {
    s.encode_utf16().count()
}

/// Uma linha em HTML do Telegram, em texto puro (a legenda encerrada usa o texto, riscado) e na
/// marcação do WhatsApp (BSV-62).
struct Linha {
    html: String,
    texto: String,
    wa: String,
}

fn linha(html: String, texto: String, wa: String) -> Linha {
    Linha { html, texto, wa }
}

/// Linhas depois do título, na ordem da regra 6. Opcionais vazias não entram. `n_cupons` = quantos
/// códigos entram (BSV-50: o que não cabe sai do fim). Devolve as linhas e, à parte, a linha do
/// link (a legenda encerrada não a usa).
fn corpo(o: &OfertaCanal, caiu: bool, p: &Parametros, n_cupons: usize) -> (Vec<Linha>, Linha) {
    let mut v = Vec::new();
    if let Some(d) = &o.destaque {
        v.push(linha(escapar(d), d.clone(), limpar_whatsapp(d)));
    }
    let mut html = Vec::new();
    let mut texto = Vec::new();
    let mut wa = Vec::new();
    if let Some(pct) = o.desconto_pct.filter(|&pct| pct >= p.pc_desconto_destaque) {
        html.push(format!("🔥 <b>-{pct}%</b>"));
        texto.push(format!("🔥 -{pct}%"));
        wa.push(format!("🔥 *-{pct}%*"));
    }
    if let Some(de) = o.preco_de {
        html.push(format!("<s>{}</s>", reais(de)));
        texto.push(reais(de));
        wa.push(format!("~{}~", reais(de)));
    }
    html.push(format!("<b>{}</b>", reais(o.preco_por)));
    texto.push(reais(o.preco_por));
    wa.push(format!("*{}*", reais(o.preco_por)));
    if o.recorrencia {
        html.push("🔁 <i>(Recorrência)</i>".to_owned());
        texto.push("🔁 (Recorrência)".to_owned());
        wa.push("🔁 _(Recorrência)_".to_owned());
    }
    v.push(linha(html.join("  "), texto.join("  "), wa.join("  ")));
    if caiu {
        v.push(linha(
            "📉 <b>Caiu mais o preço!!!</b>".to_owned(),
            "📉 Caiu mais o preço!!!".to_owned(),
            "📉 *Caiu mais o preço!!!*".to_owned(),
        ));
    }
    let codigos = &o.cupons[..n_cupons.min(o.cupons.len())];
    if !codigos.is_empty() {
        let rotulo = if codigos.len() == 1 {
            "Cupom"
        } else {
            "Cupons"
        };
        let html: Vec<String> = codigos
            .iter()
            .map(|c| format!("<code>{}</code>", escapar(c)))
            .collect();
        let wa: Vec<String> = codigos
            .iter()
            .map(|c| format!("`{}`", limpar_whatsapp(c)))
            .collect();
        v.push(linha(
            format!("🎟️ {rotulo}: {}", html.join(" · ")),
            format!("🎟️ {rotulo}: {}", codigos.join(" · ")),
            format!("🎟️ {rotulo}: {}", wa.join(" · ")),
        ));
    }
    let loja = nome_loja(o.loja);
    let link = linha(
        format!(
            "Promoção {loja}: <a href=\"{}\">{DOMINIO_CURTO}/{}</a>",
            link(o.id),
            o.id
        ),
        String::new(),
        format!("Promoção {loja}: {}", link_whatsapp(o.id)),
    );
    (v, link)
}

/// Cabe no limite do Telegram (`MAX_LEGENDA` em UTF-16).
fn cabe_telegram(s: &str) -> bool {
    tamanho(s) <= MAX_LEGENDA
}

/// Corta o título (fronteira de palavra + `…`) no maior tamanho com que `montar(título)` cabe em
/// `MAX_LEGENDA` (busca binária: o escape faz o HTML crescer mais que o título).
pub(crate) fn caber(titulo: &str, montar: impl Fn(&str) -> String) -> String {
    caber_em(titulo, cabe_telegram, montar)
}

/// `caber` com a regra de tamanho do canal.
fn caber_em(titulo: &str, cabe: fn(&str) -> bool, montar: impl Fn(&str) -> String) -> String {
    let inteira = montar(titulo);
    let total = titulo.chars().count();
    if cabe(&inteira) || total <= MIN_TITULO {
        return inteira;
    }
    let (mut cabe_ate, mut nao_cabe) = (MIN_TITULO, total);
    while nao_cabe - cabe_ate > 1 {
        let meio = cabe_ate + (nao_cabe - cabe_ate) / 2;
        if cabe(&montar(&truncar(titulo, meio))) {
            cabe_ate = meio;
        } else {
            nao_cabe = meio;
        }
    }
    montar(&truncar(titulo, cabe_ate))
}

/// Monta a legenda com todos os cupons; se não couber, tira códigos do fim (fica 1) antes de
/// cortar o título. A frase e as linhas em branco estão em `montar`: nunca são cortadas.
fn ajustar(
    o: &OfertaCanal,
    titulo: &str,
    cabe: fn(&str) -> bool,
    montar: impl Fn(usize, &str) -> String,
) -> String {
    for n in (1..=o.cupons.len()).rev() {
        let inteira = montar(n, titulo);
        if cabe(&inteira) {
            return inteira;
        }
    }
    let n = o.cupons.len().min(1);
    caber_em(titulo, cabe, |t| montar(n, t))
}

/// Legenda do post (BSV-62): título, linha em branco, corpo, link, linha em branco e
/// `{ícone} <i>{frase}</i>`.
pub fn legenda(o: &OfertaCanal, caiu: bool, p: &Parametros, frases: &Frases) -> String {
    let (icone, frase) = frases.escolher(o.id);
    let aviso = format!("{icone} <i>{}</i>", escapar(frase));
    ajustar(o, &o.titulo, cabe_telegram, |n, titulo| {
        let (linhas, link) = corpo(o, caiu, p, n);
        [format!("<b>{}</b>", escapar(titulo)), String::new()]
            .into_iter()
            .chain(linhas.into_iter().map(|l| l.html))
            .chain([link.html, String::new(), aviso.clone()])
            .collect::<Vec<_>>()
            .join("\n")
    })
}

/// Legenda do WhatsApp (BSV-62 Saída 5): as mesmas linhas e a mesma frase do Telegram, na marcação
/// do WhatsApp, ≤ `MAX_LEGENDA_WA` caracteres e ≤ `MAX_BYTES_WA` bytes.
pub fn legenda_whatsapp(o: &OfertaCanal, caiu: bool, p: &Parametros, frases: &Frases) -> String {
    let (icone, frase) = frases.escolher(o.id);
    let aviso = format!("{icone} _{}_", limpar_whatsapp(frase));
    let titulo = limpar_whatsapp(&o.titulo);
    ajustar(o, &titulo, cabe_whatsapp, |n, titulo| {
        let (linhas, link) = corpo(o, caiu, p, n);
        [format!("*{titulo}*"), String::new()]
            .into_iter()
            .chain(linhas.into_iter().map(|l| l.wa))
            .chain([link.wa, String::new(), aviso.clone()])
            .collect::<Vec<_>>()
            .join("\n")
    })
}

/// Legenda de oferta expirada: aviso no topo e o texto original riscado (título, linha em branco,
/// corpo), sem link, sem "Caiu mais" e sem frase.
pub fn legenda_encerrada(o: &OfertaCanal, p: &Parametros) -> String {
    ajustar(o, &o.titulo, cabe_telegram, |n, titulo| {
        let (linhas, _) = corpo(o, false, p, n);
        let texto = [titulo.to_owned(), String::new()]
            .into_iter()
            .chain(linhas.into_iter().map(|l| l.texto))
            .collect::<Vec<_>>()
            .join("\n");
        format!("⛔ <b>Oferta encerrada</b>\n<s>{}</s>", escapar(&texto))
    })
}
