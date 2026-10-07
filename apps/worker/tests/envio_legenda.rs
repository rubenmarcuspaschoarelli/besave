//! BSV-40 LEG-01..04: legenda do post e legenda de oferta encerrada.

use worker::envio::legenda::{MAX_LEGENDA, legenda, legenda_encerrada, reais, tamanho};
use worker::envio::modelo::{OfertaCanal, Parametros};
use worker::modelo::Loja;

fn oferta() -> OfertaCanal {
    OfertaCanal {
        id: 5412,
        id_produto: 910,
        loja: Loja::Amazon,
        titulo: "Fone Bluetooth XYZ".into(),
        destaque: None,
        preco_de: Some(29990),
        preco_por: 16490,
        desconto_pct: Some(45),
        cupom: None,
        recorrencia: false,
        dt_oferta: "2026-09-24T12:40:00Z".into(),
    }
}

fn p() -> Parametros {
    Parametros::default()
}

/// LEG-01, LEG-02, LEG-04: com `pd`, 45% (selo), sem opcionais.
#[test]
fn legenda_basica() {
    let l = legenda(&oferta(), false, &p());
    assert_eq!(
        l,
        "<b>Fone Bluetooth XYZ</b>\n\
         🔥 <b>-45%</b>  <s>R$ 299,90</s>  <b>R$ 164,90</b>\n\
         Promoção Amazon: <a href=\"https://besave.io/5412?utm_source=telegram\">besave.io/5412</a>"
    );
}

/// LEG-02: todas as linhas opcionais, na ordem da regra 6.
#[test]
fn legenda_completa() {
    let o = OfertaCanal {
        destaque: Some("Menor preço em 30 dias".into()),
        recorrencia: true,
        cupom: Some("BESAVE10".into()),
        loja: Loja::MercadoLivre,
        ..oferta()
    };
    let l = legenda(&o, true, &p());
    let linhas: Vec<&str> = l.lines().collect();
    assert_eq!(
        linhas,
        vec![
            "<b>Fone Bluetooth XYZ</b>",
            "Menor preço em 30 dias",
            "🔥 <b>-45%</b>  <s>R$ 299,90</s>  <b>R$ 164,90</b>  🔁 <i>(Recorrência)</i>",
            "📉 <b>Caiu mais o preço!!!</b>",
            "🎟️ Cupom: <code>BESAVE10</code>",
            "Promoção Mercado Livre: <a href=\"https://besave.io/5412?utm_source=telegram\">besave.io/5412</a>",
        ]
    );
}

/// LEG-02: sem `pd` → nem selo nem preço riscado; Shopee.
#[test]
fn sem_preco_de() {
    let o = OfertaCanal {
        preco_de: None,
        desconto_pct: None,
        loja: Loja::Shopee,
        ..oferta()
    };
    let l = legenda(&o, false, &p());
    assert!(!l.contains("<s>"), "{l}");
    assert!(!l.contains("🔥"), "{l}");
    assert!(l.contains("\n<b>R$ 164,90</b>\n"), "{l}");
    assert!(l.contains("Promoção Shopee:"), "{l}");
}

/// LEG-02: 29% com destaque a partir de 30 → sem selo, com preço riscado; 30% → selo.
#[test]
fn selo_a_partir_do_parametro() {
    let o = OfertaCanal {
        preco_de: Some(10000),
        preco_por: 7100,
        desconto_pct: Some(29),
        ..oferta()
    };
    let l = legenda(&o, false, &p());
    assert!(!l.contains("-29%"), "{l}");
    assert!(l.contains("<s>R$ 100,00</s>  <b>R$ 71,00</b>"), "{l}");
    let o = OfertaCanal {
        preco_por: 7000,
        desconto_pct: Some(30),
        ..o
    };
    assert!(legenda(&o, false, &p()).contains("🔥 <b>-30%</b>"));
}

/// LEG-01: título, destaque e cupom escapados.
#[test]
fn texto_escapado() {
    let o = OfertaCanal {
        titulo: "Kit <Pro> & \"Max\"".into(),
        destaque: Some("A<B".into()),
        ..oferta()
    };
    let l = legenda(&o, false, &p());
    assert!(
        l.starts_with("<b>Kit &lt;Pro&gt; &amp; &quot;Max&quot;</b>\nA&lt;B\n"),
        "{l}"
    );
}

/// LEG-03: título longo cortado para a legenda caber em 1024; o resto intacto.
#[test]
fn titulo_longo_cortado() {
    let o = OfertaCanal {
        titulo: "Palavra & longa ".repeat(120).trim().to_owned(),
        destaque: Some("d".repeat(200)),
        cupom: Some("BESAVE10".into()),
        recorrencia: true,
        ..oferta()
    };
    let l = legenda(&o, true, &p());
    assert!(tamanho(&l) <= MAX_LEGENDA, "{}", tamanho(&l));
    assert!(l.chars().count() <= MAX_LEGENDA);
    let titulo = l.lines().next().unwrap();
    assert!(titulo.starts_with("<b>Palavra &amp; longa"), "{titulo}");
    assert!(titulo.ends_with("…</b>"), "{titulo}");
    // Não sobra entidade quebrada no corte.
    assert!(
        !titulo.contains("&amp…") && !titulo.contains("&…"),
        "{titulo}"
    );
    assert!(l.ends_with("besave.io/5412</a>"), "{l}");
    assert!(l.contains("🎟️ Cupom: <code>BESAVE10</code>"));
    // Folga pequena: o corte não joga fora mais que o necessário.
    assert!(tamanho(&l) > MAX_LEGENDA - 40, "{}", tamanho(&l));
}

/// Título que cabe não é cortado.
#[test]
fn titulo_que_cabe_fica_inteiro() {
    let titulo = "x".repeat(700);
    let o = OfertaCanal {
        titulo: titulo.clone(),
        ..oferta()
    };
    let l = legenda(&o, false, &p());
    assert!(l.starts_with(&format!("<b>{titulo}</b>")));
}

#[test]
fn reais_com_milhar() {
    assert_eq!(reais(123456), "R$ 1.234,56");
    assert_eq!(reais(5), "R$ 0,05");
    assert_eq!(reais(100000000), "R$ 1.000.000,00");
    assert_eq!(reais(99900), "R$ 999,00");
}

/// EXP-01: aviso no topo, texto original riscado, sem link e sem "Caiu mais".
#[test]
fn legenda_encerrada_riscada_sem_link() {
    let o = OfertaCanal {
        cupom: Some("BESAVE10".into()),
        titulo: "Fone <XYZ>".into(),
        ..oferta()
    };
    let l = legenda_encerrada(&o, &p());
    assert_eq!(
        l,
        "⛔ <b>Oferta encerrada</b>\n<s>Fone &lt;XYZ&gt;\n\
         🔥 -45%  R$ 299,90  R$ 164,90\n🎟️ Cupom: BESAVE10</s>"
    );
    assert!(!l.contains("href"));
    assert!(tamanho(&l) <= MAX_LEGENDA);
}
