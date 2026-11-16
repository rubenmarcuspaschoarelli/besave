//! BSV-40 LEG-01..04, BSV-50 CAN-01..02 e BSV-62 LAY/LIM/ENC: legenda do post do Telegram e
//! legenda de oferta encerrada. O layout é o da BSV-62 (linhas em branco e frase de aviso).

use worker::envio::frases::Frases;
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

/// Uma frase e um ícone só: a linha final é conhecida em todo id.
fn uma(frase: &str) -> Frases {
    Frases::de_json(&serde_json::json!({"icones": ["🚨"], "frases": [frase]}).to_string()).unwrap()
}

const FRASE: &str = "Atenção, a oferta pode expirar...";
const LINHA_FRASE: &str = "🚨 <i>Atenção, a oferta pode expirar...</i>";

fn f() -> Frases {
    uma(FRASE)
}

const LINK: &str =
    "Promoção Amazon: <a href=\"https://besave.io/5412?utm_source=telegram\">besave.io/5412</a>";

/// LEG-01, LEG-02, LEG-04, LAY-01: com `pd`, 45% (selo), sem opcionais.
#[test]
fn legenda_basica() {
    let l = legenda(&oferta(), false, &p(), &f());
    assert_eq!(
        l,
        format!(
            "<b>Fone Bluetooth XYZ</b>\n\
             \n\
             🔥 <b>-45%</b>  <s>R$ 299,90</s>  <b>R$ 164,90</b>\n\
             {LINK}\n\
             \n\
             {LINHA_FRASE}"
        )
    );
}

/// LEG-02, LAY-01: todas as linhas opcionais, na ordem da regra 6, entre as linhas em branco.
#[test]
fn legenda_completa() {
    let o = OfertaCanal {
        destaque: Some("Menor preço em 30 dias".into()),
        recorrencia: true,
        cupons: vec!["BESAVE10".into()],
        loja: Loja::MercadoLivre,
        ..oferta()
    };
    let l = legenda(&o, true, &p(), &f());
    let linhas: Vec<&str> = l.split('\n').collect();
    assert_eq!(
        linhas,
        vec![
            "<b>Fone Bluetooth XYZ</b>",
            "",
            "Menor preço em 30 dias",
            "🔥 <b>-45%</b>  <s>R$ 299,90</s>  <b>R$ 164,90</b>  🔁 <i>(Recorrência)</i>",
            "📉 <b>Caiu mais o preço!!!</b>",
            "🎟️ Cupom: <code>BESAVE10</code>",
            "Promoção Mercado Livre: <a href=\"https://besave.io/5412?utm_source=telegram\">besave.io/5412</a>",
            "",
            LINHA_FRASE,
        ]
    );
}

/// LEG-02, LAY-01: sem `pd` → nem selo nem preço riscado; Shopee; sem nenhuma opcional as duas
/// linhas em branco continuam.
#[test]
fn sem_preco_de() {
    let o = OfertaCanal {
        preco_de: None,
        desconto_pct: None,
        loja: Loja::Shopee,
        ..oferta()
    };
    let l = legenda(&o, false, &p(), &f());
    assert_eq!(
        l,
        format!(
            "<b>Fone Bluetooth XYZ</b>\n\
             \n\
             <b>R$ 164,90</b>\n\
             Promoção Shopee: <a href=\"https://besave.io/5412?utm_source=telegram\">besave.io/5412</a>\n\
             \n\
             {LINHA_FRASE}"
        )
    );
}

/// LEG-02, LAY-01: 29% com destaque a partir de 30 → sem selo, com preço riscado; 30% → selo.
#[test]
fn selo_a_partir_do_parametro() {
    let o = OfertaCanal {
        preco_de: Some(10000),
        preco_por: 7100,
        desconto_pct: Some(29),
        ..oferta()
    };
    let l = legenda(&o, false, &p(), &f());
    assert_eq!(
        l,
        format!(
            "<b>Fone Bluetooth XYZ</b>\n\
             \n\
             <s>R$ 100,00</s>  <b>R$ 71,00</b>\n\
             {LINK}\n\
             \n\
             {LINHA_FRASE}"
        )
    );
    let o = OfertaCanal {
        preco_por: 7000,
        desconto_pct: Some(30),
        ..o
    };
    assert!(legenda(&o, false, &p(), &f()).contains("\n🔥 <b>-30%</b>  <s>R$ 100,00</s>"));
}

/// LEG-01: título, destaque e cupom escapados.
#[test]
fn texto_escapado() {
    let o = OfertaCanal {
        titulo: "Kit <Pro> & \"Max\"".into(),
        destaque: Some("A<B".into()),
        ..oferta()
    };
    let l = legenda(&o, false, &p(), &f());
    assert!(
        l.starts_with("<b>Kit &lt;Pro&gt; &amp; &quot;Max&quot;</b>\n\nA&lt;B\n"),
        "{l}"
    );
}

/// LAY-02: frase escapada no HTML do Telegram.
#[test]
fn frase_escapada() {
    let l = legenda(&oferta(), false, &p(), &uma("Corra <já> & aproveite!"));
    assert!(
        l.ends_with("\n\n🚨 <i>Corra &lt;já&gt; &amp; aproveite!</i>"),
        "{l}"
    );
}

/// LEG-03, LIM-01: título longo cortado para a legenda caber em 1024; o resto intacto, a frase
/// inteira na última linha.
#[test]
fn titulo_longo_cortado() {
    let o = OfertaCanal {
        titulo: "Palavra & longa ".repeat(120).trim().to_owned(),
        destaque: Some("d".repeat(200)),
        cupons: vec!["BESAVE10".into()],
        recorrencia: true,
        ..oferta()
    };
    let l = legenda(&o, true, &p(), &f());
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
    assert!(
        l.ends_with(&format!("besave.io/5412</a>\n\n{LINHA_FRASE}")),
        "{l}"
    );
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
    let l = legenda(&o, false, &p(), &f());
    assert!(l.starts_with(&format!("<b>{titulo}</b>\n\n")));
}

#[test]
fn reais_com_milhar() {
    assert_eq!(reais(123456), "R$ 1.234,56");
    assert_eq!(reais(5), "R$ 0,05");
    assert_eq!(reais(100000000), "R$ 1.000.000,00");
    assert_eq!(reais(99900), "R$ 999,00");
}

/// EXP-01, ENC-01: aviso no topo, texto original riscado com a linha em branco depois do título,
/// sem link, sem "Caiu mais" e sem frase.
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
         \n\
         🔥 -45%  R$ 299,90  R$ 164,90\n🎟️ Cupom: BESAVE10</s>"
    );
    assert!(!l.contains("href"));
    assert!(tamanho(&l) <= MAX_LEGENDA);
    // Nenhuma frase das embutidas.
    let emb = Frases::embutidas().unwrap();
    assert!(emb.frases().iter().all(|fr| !l.contains(fr.as_str())));
}

// CAN-01 (BSV-50), LAY-01 com 3 cupons
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
    let l = legenda(&o, false, &p(), &f());
    assert_eq!(
        l,
        format!(
            "<b>Fone Bluetooth XYZ</b>\n\
             \n\
             🔥 <b>-45%</b>  <s>R$ 299,90</s>  <b>R$ 164,90</b>\n\
             🎟️ Cupons: <code>MELI26TODOSITE</code> · <code>SITEMELI26</code> · <code>MELI26SITETODO</code>\n\
             {LINK}\n\
             \n\
             {LINHA_FRASE}"
        )
    );
    let e = legenda_encerrada(&o, &p());
    assert!(
        e.contains("🎟️ Cupons: MELI26TODOSITE · SITEMELI26 · MELI26SITETODO</s>"),
        "{e}"
    );
}

/// LAY-01: o exemplo do dono, oferta 51217 (Mercado Livre, R$ 104,00 → R$ 50,00, -52%, cupom
/// `MANTECORP15`), com a frase e o ícone que o hash escolhe para o id (valores fixos, calculados
/// fora do código: ver `envio_frases.rs`). O título é ilustrativo.
#[test]
fn exemplo_do_dono_51217() {
    let emb = Frases::embutidas().unwrap();
    let (icone, frase) = ("🏃‍♂️", "Garanta agora, antes que o preço mude!");
    let o = OfertaCanal {
        id: 51217,
        loja: Loja::MercadoLivre,
        titulo: "Protetor Solar Episol Sec FPS 60 Mantecorp 50g".into(),
        preco_de: Some(10400),
        preco_por: 5000,
        desconto_pct: Some(52),
        cupons: vec!["MANTECORP15".into()],
        ..oferta()
    };
    assert_eq!(
        legenda(&o, false, &p(), &emb),
        format!(
            "<b>Protetor Solar Episol Sec FPS 60 Mantecorp 50g</b>\n\
             \n\
             🔥 <b>-52%</b>  <s>R$ 104,00</s>  <b>R$ 50,00</b>\n\
             🎟️ Cupom: <code>MANTECORP15</code>\n\
             Promoção Mercado Livre: <a href=\"https://besave.io/51217?utm_source=telegram\">besave.io/51217</a>\n\
             \n\
             {icone} <i>{frase}</i>"
        )
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
    let sem = legenda(&base, false, &p(), &f());
    assert!(tamanho(&sem) <= MAX_LEGENDA);

    // Título que deixa folga para exatamente 2 códigos de 30 (a legenda com 2 chega a 1024).
    let com = |k: usize, titulo: &str| OfertaCanal {
        titulo: titulo.to_owned(),
        cupons: codigos[..k].to_vec(),
        ..oferta()
    };
    let vazia = |k: usize| tamanho(&legenda(&com(k, ""), false, &p(), &f()));
    assert!(vazia(3) > vazia(2));
    let titulo_folga = "x".repeat(MAX_LEGENDA - vazia(2));
    let l = legenda(&com(5, &titulo_folga), false, &p(), &f());
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
    let l = legenda(&enorme, false, &p(), &f());
    assert!(tamanho(&l) <= MAX_LEGENDA);
    assert!(
        l.contains(&format!("🎟️ Cupom: <code>{}</code>", codigos[0])),
        "{l}"
    );
    assert!(l.lines().next().unwrap().ends_with("…</b>"));
}

/// LIM-01: título longo com 3 cupons e a frase mais longa possível (120 caracteres): saem cupons,
/// depois o título é cortado; a frase fica inteira e a legenda ≤ 1024 (UTF-16).
#[test]
fn frase_nunca_cortada() {
    let longa = format!("Fim {}", "ç".repeat(116));
    assert_eq!(longa.chars().count(), 120);
    let o = OfertaCanal {
        titulo: "Palavra longa ".repeat(120).trim().to_owned(),
        destaque: Some("d".repeat(200)),
        cupons: vec!["A".repeat(30), "B".repeat(30), "C".repeat(30)],
        ..oferta()
    };
    let l = legenda(&o, true, &p(), &uma(&longa));
    assert!(tamanho(&l) <= MAX_LEGENDA, "{}", tamanho(&l));
    assert!(
        l.ends_with(&format!("</a>\n\n🚨 <i>{longa}</i>")),
        "frase inteira no fim: {l}"
    );
    assert!(l.contains(&format!("🎟️ Cupom: <code>{}</code>\n", "A".repeat(30))));
    assert!(!l.contains(&"B".repeat(30)));
    assert!(l.lines().next().unwrap().ends_with("…</b>"));
    assert!(tamanho(&l) > MAX_LEGENDA - 40, "{}", tamanho(&l));
}
