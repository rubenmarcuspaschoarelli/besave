//! Desenvolvimento (BSV-20): `cargo run --bin render-oferta -- fixture.json > out.html`.

use anyhow::{Context, Result};
use worker::modelo::OfertaPagina;
use worker::pagina_html::TemplateOferta;

fn main() -> Result<()> {
    let caminho = std::env::args()
        .nth(1)
        .context("uso: render-oferta <oferta-pagina.json>")?;
    let json = std::fs::read_to_string(&caminho).with_context(|| format!("lendo {caminho}"))?;
    let oferta: OfertaPagina =
        serde_json::from_str(&json).with_context(|| format!("{caminho} não é OfertaPagina"))?;
    print!("{}", TemplateOferta::novo()?.renderizar(&oferta)?);
    Ok(())
}
