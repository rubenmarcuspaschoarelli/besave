//! BSV-62 WA-01, WA-02, LIM-01, LIM-02, FRA-01: legenda do WhatsApp, comparada inteira (lição 14).

use worker::envio::frases::Frases;
use worker::envio::legenda::{
    MAX_BYTES_WA, MAX_LEGENDA_WA, cabe_whatsapp, legenda, legenda_whatsapp,
};
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

fn uma(frase: &str) -> Frases {
    Frases::de_json(&serde_json::json!({"icones": ["🚨"], "frases": [frase]}).to_string()).unwrap()
}

fn f() -> Frases {
    uma("Atenção, a oferta pode expirar...")
}

const FRASE: &str = "🚨 _Atenção, a oferta pode expirar..._";
const LINK: &str = "Promoção Amazon: https://besave.io/5412?utm_source=whatsapp";

/// WA-01: com `pd`, 45% (selo), sem opcionais; as duas linhas em branco.
#[test]
fn basica() {
    assert_eq!(
        legenda_whatsapp(&oferta(), false, &p(), &f()),
        format!(
            "*Fone Bluetooth XYZ*\n\
             \n\
             🔥 *-45%*  ~R$ 299,90~  *R$ 164,90*\n\
             {LINK}\n\
             \n\
             {FRASE}"
        )
    );
}

/// WA-01: todas as opcionais (destaque, recorrência, caiu, 1 cupom), Mercado Livre.
#[test]
fn completa() {
    let o = OfertaCanal {
        destaque: Some("Menor preço em 30 dias".into()),
        recorrencia: true,
        cupons: vec!["BESAVE10".into()],
        loja: Loja::MercadoLivre,
        ..oferta()
    };
    assert_eq!(
        legenda_whatsapp(&o, true, &p(), &f()),
        format!(
            "*Fone Bluetooth XYZ*\n\
             \n\
             Menor preço em 30 dias\n\
             🔥 *-45%*  ~R$ 299,90~  *R$ 164,90*  🔁 _(Recorrência)_\n\
             📉 *Caiu mais o preço!!!*\n\
             🎟️ Cupom: `BESAVE10`\n\
             Promoção Mercado Livre: https://besave.io/5412?utm_source=whatsapp\n\
             \n\
             {FRASE}"
        )
    );
}

/// WA-01: sem `pd` e sem nenhuma opcional → as duas linhas em branco continuam; Shopee.
#[test]
fn sem_preco_de_sem_opcionais() {
    let o = OfertaCanal {
        preco_de: None,
        desconto_pct: None,
        loja: Loja::Shopee,
        ..oferta()
    };
    assert_eq!(
        legenda_whatsapp(&o, false, &p(), &f()),
        format!(
            "*Fone Bluetooth XYZ*\n\
             \n\
             *R$ 164,90*\n\
             Promoção Shopee: https://besave.io/5412?utm_source=whatsapp\n\
             \n\
             {FRASE}"
        )
    );
}

/// WA-01: 29% (abaixo do destaque) → sem selo, com preço riscado.
#[test]
fn vinte_e_nove_sem_selo() {
    let o = OfertaCanal {
        preco_de: Some(10000),
        preco_por: 7100,
        desconto_pct: Some(29),
        ..oferta()
    };
    assert_eq!(
        legenda_whatsapp(&o, false, &p(), &f()),
        format!(
            "*Fone Bluetooth XYZ*\n\
             \n\
             ~R$ 100,00~  *R$ 71,00*\n\
             {LINK}\n\
             \n\
             {FRASE}"
        )
    );
}

/// WA-01: 3 cupons na mesma linha.
#[test]
fn tres_cupons() {
    let o = OfertaCanal {
        cupons: vec!["A1".into(), "B2".into(), "C3".into()],
        ..oferta()
    };
    assert_eq!(
        legenda_whatsapp(&o, false, &p(), &f()),
        format!(
            "*Fone Bluetooth XYZ*\n\
             \n\
             🔥 *-45%*  ~R$ 299,90~  *R$ 164,90*\n\
             🎟️ Cupons: `A1` · `B2` · `C3`\n\
             {LINK}\n\
             \n\
             {FRASE}"
        )
    );
}

/// WA-01, FRA-01: o exemplo do dono (51217) com as frases embutidas; mesma frase e mesmo ícone do
/// post do Telegram da mesma oferta.
#[test]
fn exemplo_do_dono_51217_igual_ao_telegram() {
    let emb = Frases::embutidas().unwrap();
    // Valores fixos, calculados fora do código (ver envio_frases.rs).
    let (icone, frase) = ("🏃‍♂️", "Garanta agora, antes que o preço mude!");
    assert_eq!(emb.escolher(51217), (icone, frase));
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
    let wa = legenda_whatsapp(&o, false, &p(), &emb);
    assert_eq!(
        wa,
        format!(
            "*Protetor Solar Episol Sec FPS 60 Mantecorp 50g*\n\
             \n\
             🔥 *-52%*  ~R$ 104,00~  *R$ 50,00*\n\
             🎟️ Cupom: `MANTECORP15`\n\
             Promoção Mercado Livre: https://besave.io/51217?utm_source=whatsapp\n\
             \n\
             {icone} _{frase}_"
        )
    );
    let tg = legenda(&o, false, &p(), &emb);
    assert!(tg.ends_with(&format!("\n\n{icone} <i>{frase}</i>")), "{tg}");
    // Outra execução (outra carga das frases) dá o mesmo texto.
    assert_eq!(
        legenda_whatsapp(&o, false, &p(), &Frases::embutidas().unwrap()),
        wa
    );
}

/// WA-02: marcadores removidos do título, destaque, cupom e frase; espaços repetidos viram um.
#[test]
fn marcadores_removidos() {
    let o = OfertaCanal {
        titulo: "Kit *Pro*  _Max_ ~x~ `y`".into(),
        destaque: Some("Só *hoje*   e _amanhã_".into()),
        cupons: vec!["BE_SAVE".into()],
        ..oferta()
    };
    let l = legenda_whatsapp(&o, false, &p(), &uma("Corra, *é* ~agora~!"));
    assert_eq!(
        l,
        format!(
            "*Kit Pro Max x y*\n\
             \n\
             Só hoje e amanhã\n\
             🔥 *-45%*  ~R$ 299,90~  *R$ 164,90*\n\
             🎟️ Cupom: `BESAVE`\n\
             {LINK}\n\
             \n\
             🚨 _Corra, é agora!_"
        )
    );
}

/// LIM-01, LIM-02: título longo com 3 cupons → saem cupons, o título é cortado, a frase fica
/// inteira; ≤ 1024 caracteres e ≤ 4000 bytes.
#[test]
fn limite_com_frase_inteira() {
    let longa = format!("Fim {}", "ç".repeat(116));
    let o = OfertaCanal {
        titulo: "Palavra longa ".repeat(120).trim().to_owned(),
        destaque: Some("d".repeat(200)),
        cupons: vec!["A".repeat(30), "B".repeat(30), "C".repeat(30)],
        ..oferta()
    };
    let l = legenda_whatsapp(&o, true, &p(), &uma(&longa));
    assert!(l.chars().count() <= MAX_LEGENDA_WA, "{}", l.chars().count());
    assert!(l.len() <= MAX_BYTES_WA, "{}", l.len());
    assert!(
        l.ends_with(&format!("utm_source=whatsapp\n\n🚨 _{longa}_")),
        "{l}"
    );
    assert!(
        l.contains(&format!("🎟️ Cupom: `{}`\n", "A".repeat(30))),
        "{l}"
    );
    assert!(!l.contains(&"B".repeat(30)));
    assert!(l.lines().next().unwrap().ends_with("…*"), "{l}");
    // O corte não joga fora mais que o necessário.
    assert!(
        l.chars().count() > MAX_LEGENDA_WA - 20,
        "{}",
        l.chars().count()
    );
}

/// LIM-02: a regra de tamanho do WhatsApp mede caracteres e bytes. 1001 emojis de 4 bytes cabem
/// em 1024 caracteres, mas não em 4000 bytes.
#[test]
fn limite_em_bytes() {
    let mil = "😀".repeat(1000);
    assert!(cabe_whatsapp(&mil), "1000 caracteres, 4000 bytes");
    let mil_e_um = "😀".repeat(1001);
    assert_eq!(mil_e_um.chars().count(), 1001);
    assert!(!cabe_whatsapp(&mil_e_um), "4004 bytes");
    assert!(cabe_whatsapp(&"a".repeat(1024)));
    assert!(!cabe_whatsapp(&"a".repeat(1025)));
}

/// LIM-01: com o título emoji, a legenda inteira respeita os dois limites.
#[test]
fn titulo_de_emojis_cabe() {
    let o = OfertaCanal {
        titulo: "😀 ".repeat(1200).trim().to_owned(),
        destaque: Some("🔥".repeat(200)),
        ..oferta()
    };
    let l = legenda_whatsapp(&o, false, &p(), &f());
    assert!(cabe_whatsapp(&l), "{} {}", l.chars().count(), l.len());
    assert!(l.ends_with(&format!("\n\n{FRASE}")));
}
