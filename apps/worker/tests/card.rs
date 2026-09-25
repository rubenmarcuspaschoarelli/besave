//! CONV-02..11: LinhaOferta → OfertaCard (CONTRATO §3, §9).

mod comum;

use comum::{compactar, fixture};
use worker::conversao::{LinhaOferta, Rejeicao, centavos, iso_utc, para_card};
use worker::mapeamento::Mapeamento;
use worker::modelo::{Area, Loja, Publico};

const DT_5412: i64 = 1_790_253_600; // 2026-09-24T12:40:00Z
const DT_5413: i64 = 1_790_253_660; // 2026-09-24T12:41:00Z
const DT_5420: i64 = 1_790_150_400; // 2026-09-23T08:00:00Z

fn m() -> Mapeamento {
    Mapeamento::carregar(comum::caminho_mapeamento()).unwrap()
}

/// Linhas "como vêm do Oracle" equivalentes aos 3 registros de chunk-ok.json.
fn linhas_fixture() -> Vec<LinhaOferta> {
    vec![
        LinhaOferta {
            id: 5412,
            id_produto: Some(910),
            loja: Some("Amazon".into()),
            titulo: Some("  Fone Bluetooth XYZ com ANC ".into()),
            preco_de: Some(299.90),
            preco_por: Some(199.90),
            cupom: Some(" besave10 ".into()),
            dt_oferta: Some(DT_5412),
            area: Some("Tecnologia".into()),
            publico: Some("unisex".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5412".into(),
            ..Default::default()
        },
        LinhaOferta {
            id: 5413,
            loja: Some("shopee".into()),
            titulo: Some("Kit Skincare Vitamina C 3 passos".into()),
            preco_de: None,
            preco_por: Some(89.90),
            dt_oferta: Some(DT_5413),
            area: Some("Elas".into()),
            publico: Some("Mulher".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5413".into(),
            ..Default::default()
        },
        LinhaOferta {
            id: 5420,
            loja: Some("MercadoLivre".into()),
            titulo: Some("Ração Premium Cães Adultos 15kg".into()),
            preco_de: Some(249.00),
            preco_por: Some(199.00),
            dt_oferta: Some(DT_5420),
            area: Some("Pet".into()),
            publico: Some("U".into()),
            ativo: false,
            dt_desativacao: Some(DT_5420),
            url_afiliado: "https://loja.example/5420".into(),
            ..Default::default()
        },
    ]
}

fn valida() -> LinhaOferta {
    linhas_fixture().remove(1)
}

#[test]
fn fixture_chunk_ok_byte_a_byte() {
    let m = m();
    let cards: Vec<_> = linhas_fixture()
        .iter()
        .map(|l| para_card(l, &m).unwrap())
        .collect();
    assert_eq!(
        serde_json::to_string(&cards).unwrap(),
        compactar(&fixture("chunk-ok.json"))
    );
}

#[test]
fn orcamento_de_bytes_do_card() {
    let m = m();
    let tamanhos: Vec<usize> = linhas_fixture()
        .iter()
        .map(|l| {
            serde_json::to_string(&para_card(l, &m).unwrap())
                .unwrap()
                .len()
        })
        .collect();
    for t in &tamanhos {
        assert!(*t <= 220, "card com {t} bytes");
    }
    let media = tamanhos.iter().sum::<usize>() as f64 / tamanhos.len() as f64;
    assert!(media <= 160.0, "média {media}");
}

#[test]
fn enum_via_sinonimo() {
    let c = para_card(&linhas_fixture()[2], &m()).unwrap();
    assert_eq!(c.loja, Loja::MercadoLivre);
    assert_eq!(c.area, Area::Pets);
    assert_eq!(c.publico, Publico::Unissex);
}

#[test]
fn rejeita_preco_por_ausente_zero_ou_negativo() {
    let m = m();
    for pp in [None, Some(0.0), Some(-5.0), Some(0.004)] {
        let l = LinhaOferta {
            preco_por: pp,
            ..valida()
        };
        assert_eq!(
            para_card(&l, &m),
            Err(Rejeicao::PrecoPorInvalido),
            "pp={pp:?}"
        );
    }
}

#[test]
fn rejeita_titulo_vazio() {
    let m = m();
    for t in [None, Some("   ".to_string())] {
        let l = LinhaOferta {
            titulo: t,
            ..valida()
        };
        assert_eq!(para_card(&l, &m), Err(Rejeicao::TituloVazio));
    }
}

#[test]
fn rejeita_loja_sem_mapeamento() {
    let l = LinhaOferta {
        loja: Some("Americanas".into()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m()), Err(Rejeicao::LojaSemMapeamento));
    let l = LinhaOferta {
        loja: None,
        ..valida()
    };
    assert_eq!(para_card(&l, &m()), Err(Rejeicao::LojaSemMapeamento));
}

#[test]
fn rejeita_area_sem_mapeamento() {
    let l = LinhaOferta {
        area: Some("Moda".into()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m()), Err(Rejeicao::AreaSemMapeamento));
}

#[test]
fn rejeita_publico_sem_mapeamento() {
    let l = LinhaOferta {
        publico: Some("Adulto".into()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m()), Err(Rejeicao::PublicoSemMapeamento));
}

#[test]
fn rejeita_data_nula() {
    let l = LinhaOferta {
        dt_oferta: None,
        ..valida()
    };
    assert_eq!(para_card(&l, &m()), Err(Rejeicao::DataNula));
}

#[test]
fn preco_de_menor_ou_igual_vira_null_sem_rejeitar() {
    let m = m();
    for pd in [89.90, 50.00] {
        let l = LinhaOferta {
            preco_de: Some(pd),
            ..valida()
        };
        let c = para_card(&l, &m).unwrap();
        assert_eq!(c.preco_de, None, "pd={pd}");
        assert!(serde_json::to_string(&c).unwrap().contains("\"pd\":null"));
    }
    let l = LinhaOferta {
        preco_de: Some(89.91),
        ..valida()
    };
    assert_eq!(para_card(&l, &m).unwrap().preco_de, Some(8991));
}

#[test]
fn titulo_longo_cortado_em_197_na_fronteira_de_palavra() {
    let longo = "abcdefghi ".repeat(25); // 250 caracteres
    let l = LinhaOferta {
        titulo: Some(longo),
        ..valida()
    };
    let t = para_card(&l, &m()).unwrap().titulo;
    let esperado = format!("{}…", "abcdefghi ".repeat(19).trim_end());
    assert_eq!(t, esperado);
    assert!(t.chars().count() <= 200);
}

#[test]
fn titulo_longo_sem_espaco_corta_seco_em_197() {
    let l = LinhaOferta {
        titulo: Some("á".repeat(250)),
        ..valida()
    };
    let t = para_card(&l, &m()).unwrap().titulo;
    assert_eq!(t, format!("{}…", "á".repeat(197)));
}

#[test]
fn titulo_de_200_nao_e_cortado() {
    let t200 = "abcdefghi ".repeat(20).trim_end().to_string() + "x"; // 200 chars
    assert_eq!(t200.chars().count(), 200);
    let l = LinhaOferta {
        titulo: Some(t200.clone()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m()).unwrap().titulo, t200);
}

#[test]
fn centavos_half_up() {
    assert_eq!(centavos(19.995), 2000);
    assert_eq!(centavos(19.994), 1999);
    assert_eq!(centavos(199.90), 19990);
    assert_eq!(centavos(0.005), 1);
    assert_eq!(centavos(1.0), 100);
}

#[test]
fn inativa_tem_x_1_e_ativa_nao_tem_x() {
    let m = m();
    let l = LinhaOferta {
        ativo: false,
        ..valida()
    };
    let c = para_card(&l, &m).unwrap();
    assert_eq!(c.x, Some(1));
    assert!(serde_json::to_string(&c).unwrap().ends_with(",\"x\":1}"));

    let c = para_card(&valida(), &m).unwrap();
    assert_eq!(c.x, None);
    assert!(!serde_json::to_string(&c).unwrap().contains("\"x\""));
}

#[test]
fn cupom_so_espacos_fica_ausente() {
    let l = LinhaOferta {
        cupom: Some("   ".into()),
        ..valida()
    };
    let c = para_card(&l, &m()).unwrap();
    assert_eq!(c.cupom, None);
    assert!(!serde_json::to_string(&c).unwrap().contains("\"c\""));
}

#[test]
fn data_iso_8601_utc() {
    assert_eq!(iso_utc(0), "1970-01-01T00:00:00Z");
    assert_eq!(iso_utc(951_868_799), "2000-02-29T23:59:59Z");
    assert_eq!(iso_utc(DT_5412), "2026-09-24T12:40:00Z");
}

/// URL-04: sem DS_URL_AFILIADO o card não existe (CONTRATO §10.1), nem a página.
#[test]
fn url_afiliado_vazia_rejeita_card_e_pagina() {
    let m = m();
    for url in ["", "   ", "\t\n"] {
        let l = LinhaOferta {
            url_afiliado: url.into(),
            id_produto: Some(911),
            ..valida()
        };
        assert_eq!(
            para_card(&l, &m),
            Err(Rejeicao::UrlAfiliadoAusente),
            "{url:?}"
        );
        assert_eq!(
            worker::conversao::para_pagina(&l, None, &m),
            Err(Rejeicao::UrlAfiliadoAusente),
            "{url:?}"
        );
    }
}
