//! BSV-62 FRA-01..05: frases de aviso, embutidas ou de `BESAVE_FRASES_CANAL`, escolhidas por id.

use std::collections::HashMap;
use std::path::PathBuf;

use worker::envio::frases::{Frases, MAX_FRASE};

/// As 12 frases e os 11 ícones da spec (Saída 3), exatamente como estão.
const FRASES_SPEC: [&str; 12] = [
    "Atenção, esta promoção pode acabar logo!",
    "Atenção, esta oportunidade pode acabar daqui a pouco...",
    "Aproveite enquanto o preço ainda está baixo!",
    "Garanta agora, antes que o preço mude!",
    "Tudo que é bom dura pouco, aproveite!",
    "Não deixe para depois, pode acabar!",
    "Aproveite agora, essa oferta é só por instantes!",
    "Não fique de fora, a promoção já está no fim!",
    "Compre hoje e fuja do próximo aumento de preço!",
    "Atenção, a oferta pode expirar...",
    "Seja rápido, descontos assim não duram muito tempo!",
    "Clique e garanta o seu antes que o preço mude!",
];
const ICONES_SPEC: [&str; 11] = [
    "🚨",
    "⚠️",
    "☝️",
    "❗",
    "🆘",
    "🙈",
    "🏃‍♂️",
    "🏃‍♀️",
    "🏃",
    "🙉",
    "🙊",
];
/// U+1F3C3 U+200D U+2642 U+FE0F.
const CORREDOR: &str = "\u{1F3C3}\u{200D}\u{2642}\u{FE0F}";

fn arquivo(nome: &str, conteudo: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-frases-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    let p = d.join("frases.json");
    std::fs::write(&p, conteudo).unwrap();
    p
}

fn embutidas() -> Frases {
    Frases::embutidas().unwrap()
}

#[test]
fn embutidas_sao_as_da_spec() {
    let f = embutidas();
    assert_eq!(f.frases(), FRASES_SPEC.map(String::from));
    assert_eq!(f.icones(), ICONES_SPEC.map(String::from));
}

/// FRA-01: a mesma oferta dá o mesmo par, sempre (e em outra carga do arquivo).
#[test]
fn escolha_deterministica() {
    let a = embutidas();
    let b = Frases::carregar_ou_embutidas(None).unwrap();
    for id in [1, 51217, 5412, 999_999] {
        assert_eq!(a.escolher(id), a.escolher(id));
        assert_eq!(a.escolher(id), b.escolher(id));
    }
}

/// FRA-01: valores fixos, calculados fora do código (SHA-256 de `"{id}:frase"` / `"{id}:icone"`,
/// 8 primeiros bytes big-endian, `mod 12` / `mod 11`, com o `hashlib` do Python).
#[test]
fn escolha_com_valores_fixos() {
    let f = embutidas();
    let casos = [
        (51217, CORREDOR, "Garanta agora, antes que o preço mude!"),
        (5412, CORREDOR, "Não deixe para depois, pode acabar!"),
        (1, "🏃", "Clique e garanta o seu antes que o preço mude!"),
        (2, "☝️", "Garanta agora, antes que o preço mude!"),
        (3, CORREDOR, "Não fique de fora, a promoção já está no fim!"),
    ];
    for (id, icone, frase) in casos {
        assert_eq!(f.escolher(id), (icone, frase), "id {id}");
    }
}

/// Posição de `x` na lista.
fn pos(lista: &[String], x: &str) -> usize {
    lista.iter().position(|s| s == x).unwrap()
}

/// FRA-02: 1.000 ids seguidos usam todas, nenhuma passa de 15% e vizinhos não seguem a lista.
#[test]
fn mil_ids_espalham() {
    let f = embutidas();
    let ids = 51_000..52_000_i64;
    let mut por_frase: HashMap<&str, usize> = HashMap::new();
    let mut por_icone: HashMap<&str, usize> = HashMap::new();
    for id in ids.clone() {
        let (i, fr) = f.escolher(id);
        *por_frase.entry(fr).or_default() += 1;
        *por_icone.entry(i).or_default() += 1;
    }
    assert_eq!(por_frase.len(), FRASES_SPEC.len(), "{por_frase:?}");
    assert_eq!(por_icone.len(), ICONES_SPEC.len(), "{por_icone:?}");
    assert!(
        por_frase.values().all(|&n| n <= 150),
        "frase acima de 15%: {por_frase:?}"
    );
    assert!(
        por_icone.values().all(|&n| n <= 150),
        "ícone acima de 15%: {por_icone:?}"
    );
    // Vizinhos na ordem da lista (`id mod n` faz isso em 100% dos pares).
    let mut seguidos_f = 0;
    let mut seguidos_i = 0;
    for id in 51_000..51_999_i64 {
        let (i0, f0) = f.escolher(id);
        let (i1, f1) = f.escolher(id + 1);
        let (nf, ni) = (f.frases().len(), f.icones().len());
        if pos(f.frases(), f1) == (pos(f.frases(), f0) + 1) % nf {
            seguidos_f += 1;
        }
        if pos(f.icones(), i1) == (pos(f.icones(), i0) + 1) % ni {
            seguidos_i += 1;
        }
    }
    // Ao acaso, ~1/12 e ~1/11 dos 999 pares (≈ 85); 200 é folga larga.
    assert!(seguidos_f < 200, "frases seguem a lista: {seguidos_f}");
    assert!(seguidos_i < 200, "ícones seguem a lista: {seguidos_i}");
}

/// FRA-03: o ícone de vários pontos de código sai inteiro.
#[test]
fn corredor_sai_inteiro() {
    let f = embutidas();
    let id = (1..1000_i64)
        .find(|&id| f.escolher(id).0 == CORREDOR)
        .expect("algum id escolhe 🏃‍♂️");
    assert_eq!(f.escolher(id).0.chars().count(), 4);
    // Todo ícone escolhido é um item inteiro da lista.
    for id in 1..1000_i64 {
        assert!(ICONES_SPEC.contains(&f.escolher(id).0));
    }
}

/// FRA-04: arquivo válido com 2 frases → só essas 2.
#[test]
fn arquivo_com_duas_frases() {
    let p = arquivo(
        "duas",
        r#"{"_obs": "x", "icones": ["🚨"], "frases": ["Primeira frase.", "Segunda frase."]}"#,
    );
    let f = Frases::carregar_ou_embutidas(Some(&p)).unwrap();
    let mut vistas: Vec<&str> = (1..1000_i64).map(|id| f.escolher(id).1).collect();
    vistas.sort_unstable();
    vistas.dedup();
    assert_eq!(vistas, vec!["Primeira frase.", "Segunda frase."]);
    assert!((1..1000_i64).all(|id| f.escolher(id).0 == "🚨"));
}

/// FRA-04: inválido, lista vazia ou ausente → embutidas.
#[test]
fn arquivo_ruim_usa_embutidas() {
    let casos = [
        arquivo("json", "{ isto não é json"),
        arquivo("formato", r#"{"frases": ["a"]}"#),
        arquivo("frases-vazia", r#"{"icones": ["🚨"], "frases": []}"#),
        arquivo("icones-vazia", r#"{"icones": [], "frases": ["a"]}"#),
        arquivo(
            "so-invalidas",
            r#"{"icones": ["🚨"], "frases": ["  ", ""]}"#,
        ),
        PathBuf::from("C:/nao/existe/besave-frases.json"),
    ];
    for p in casos {
        assert_eq!(
            Frases::carregar_ou_embutidas(Some(&p)).unwrap(),
            embutidas(),
            "{}",
            p.display()
        );
    }
}

/// FRA-05: frase vazia ou com mais de 120 caracteres sai; 120 exatos ficam.
#[test]
fn frase_longa_ou_vazia_descartada() {
    let cabe = "é".repeat(MAX_FRASE);
    let passa = "é".repeat(MAX_FRASE + 1);
    let json = serde_json::json!({
        "icones": ["🚨", "  "],
        "frases": ["", "   ", passa, cabe, "  Curta.  "]
    })
    .to_string();
    let f = Frases::de_json(&json).unwrap();
    assert_eq!(f.frases(), [cabe, "Curta.".to_owned()]);
    assert_eq!(f.icones(), ["🚨".to_owned()]);
}
