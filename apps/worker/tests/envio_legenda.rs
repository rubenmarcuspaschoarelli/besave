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
        cupons: vec![],
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
        cupons: vec!["BESAVE10".into()],
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
        cupons: vec!["BESAVE10".into()],
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
        cupons: vec!["BESAVE10".into()],
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

// CAN-01 (BSV-50)
#[test]
fn varios_cupons_na_mesma_linha() {
    let o = OfertaCanal {
        cupons: vec![
            "MELI26TODOSITE".into(),
            "SITEMELI26".into(),
            "MELI26SITETODO".into(),
        ],
        ..oferta()
    };
    let l = legenda(&o, false, &p());
    assert!(
        l.contains(
            "🎟️ Cupons: <code>MELI26TODOSITE</code> · <code>SITEMELI26</code> · <code>MELI26SITETODO</code>"
        ),
        "{l}"
    );
    assert!(!l.contains("Cupom:"), "{l}");
    let e = legenda_encerrada(&o, &p());
    assert!(
        e.contains("🎟️ Cupons: MELI26TODOSITE · SITEMELI26 · MELI26SITETODO</s>"),
        "{e}"
    );
}

// CAN-02 (BSV-50)
#[test]
fn cupons_do_fim_saem_antes_do_titulo() {
    // Título que enche a legenda: com 5 códigos de 30 caracteres passa de 1024; o título só é
    // cortado depois que sobra 1 código.
    let codigos: Vec<String> = ["A", "B", "C", "D", "E"]
        .iter()
        .map(|c| c.repeat(30))
        .collect();
    let base = OfertaCanal {
        titulo: "Palavra longa ".repeat(60).trim().to_owned(),
        ..oferta()
    };
    let sem = legenda(&base, false, &p());
    assert!(tamanho(&sem) <= MAX_LEGENDA);

    // Título que deixa folga para exatamente 2 códigos de 30 (a legenda com 2 chega a 1024).
    let com = |k: usize, titulo: &str| OfertaCanal {
        titulo: titulo.to_owned(),
        cupons: codigos[..k].to_vec(),
        ..oferta()
    };
    let vazia = |k: usize| tamanho(&legenda(&com(k, ""), false, &p()));
    assert!(vazia(3) > vazia(2));
    let titulo_folga = "x".repeat(MAX_LEGENDA - vazia(2));
    let l = legenda(&com(5, &titulo_folga), false, &p());
    assert_eq!(tamanho(&l), MAX_LEGENDA);
    assert!(
        l.contains(&format!("<b>{titulo_folga}</b>")),
        "título intacto"
    );
    assert!(
        l.contains(&format!(
            "🎟️ Cupons: <code>{}</code> · <code>{}</code>\n",
            codigos[0], codigos[1]
        )),
        "{l}"
    );
    assert!(!l.contains(&codigos[2]), "o terceiro já saiu");

    // Mesma regra na legenda encerrada (texto riscado).
    let vazia_e = |k: usize| tamanho(&legenda_encerrada(&com(k, ""), &p()));
    assert!(vazia_e(3) > vazia_e(2));
    let titulo_e = "x".repeat(MAX_LEGENDA - vazia_e(2));
    let e = legenda_encerrada(&com(5, &titulo_e), &p());
    assert_eq!(tamanho(&e), MAX_LEGENDA);
    assert!(e.contains(&titulo_e), "título intacto");
    assert!(
        e.contains(&format!("🎟️ Cupons: {} · {}</s>", codigos[0], codigos[1])),
        "{e}"
    );
    assert!(!e.contains(&codigos[2]));

    // Nem 1 código cabe com o título inteiro: o título é cortado e o primeiro código fica.
    let enorme = OfertaCanal {
        titulo: "Palavra longa ".repeat(120).trim().to_owned(),
        cupons: codigos.clone(),
        ..oferta()
    };
    let l = legenda(&enorme, false, &p());
    assert!(tamanho(&l) <= MAX_LEGENDA);
    assert!(
        l.contains(&format!("🎟️ Cupom: <code>{}</code>", codigos[0])),
        "{l}"
    );
    assert!(l.lines().next().unwrap().ends_with("…</b>"));
}
