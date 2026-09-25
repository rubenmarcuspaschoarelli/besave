//! CONV-07, CONV-09, CONV-10: LinhaOferta + LinhaProduto → OfertaPagina (CONTRATO §4).

mod comum;

use comum::{compactar, fixture};
use worker::conversao::{LinhaOferta, LinhaProduto, Rejeicao, para_card, para_pagina};
use worker::mapeamento::Mapeamento;
use worker::modelo::Status;

fn m() -> Mapeamento {
    Mapeamento::carregar(comum::caminho_mapeamento()).unwrap()
}

/// Linha e produto "como vêm do Oracle" equivalentes a oferta-pagina-ok.json.
fn linha() -> LinhaOferta {
    LinhaOferta {
        id: 5412,
        id_produto: Some(910),
        loja: Some("AMAZON".into()),
        titulo: Some(" Fone Bluetooth XYZ com ANC, 40h de bateria, resistente a água ".into()),
        preco_de: Some(299.90),
        preco_por: Some(199.90),
        cupom: Some("besave10".into()),
        nota: Some(4.6),
        qt_avaliacoes: Some(1832),
        dt_oferta: Some(1_790_253_600),
        area: Some("TECH".into()),
        publico: Some("Unissex".into()),
        ativo: true,
        dt_desativacao: None,
    }
}

fn produto() -> LinhaProduto {
    LinhaProduto {
        id_produto: 910,
        descricao: Some(
            "Fone over-ear com cancelamento ativo de ruído e 40 horas de bateria.\n\nConteúdo da embalagem: fone, cabo."
                .into(),
        ),
        marca: Some("XYZ".into()),
        fabricante: Some("XYZ Audio Ltda".into()),
        modelo: Some("XZ-400".into()),
        pais_origem: Some("China".into()),
        genero: None,
        faixa_etaria: Some("  ".into()),
        preco_min: Some(179.90),
        preco_max: Some(349.90),
    }
}

#[test]
fn fixture_oferta_pagina_ok_byte_a_byte() {
    let p = para_pagina(&linha(), Some(&produto()), &m()).unwrap();
    assert_eq!(
        serde_json::to_string(&p).unwrap(),
        compactar(&fixture("oferta-pagina-ok.json"))
    );
}

#[test]
fn titulo_longo_integral_na_pagina_e_cortado_no_card() {
    let longo = "abcdefghi ".repeat(25).trim_end().to_string(); // 249 caracteres
    let l = LinhaOferta {
        titulo: Some(longo.clone()),
        ..linha()
    };
    let m = m();
    assert_eq!(para_pagina(&l, None, &m).unwrap().titulo, longo);
    assert!(para_card(&l, &m).unwrap().titulo.ends_with('…'));
}

#[test]
fn inativa_encerrada_ativa_ativa() {
    let m = m();
    let l = LinhaOferta {
        ativo: false,
        ..linha()
    };
    let p = para_pagina(&l, None, &m).unwrap();
    assert_eq!(p.status, Status::Encerrada);
    assert!(
        serde_json::to_string(&p)
            .unwrap()
            .contains("\"status\":\"ENCERRADA\"")
    );
    assert_eq!(
        para_pagina(&linha(), None, &m).unwrap().status,
        Status::Ativa
    );
}

#[test]
fn sem_preco_de_desconto_null() {
    let l = LinhaOferta {
        preco_de: None,
        ..linha()
    };
    let p = para_pagina(&l, None, &m()).unwrap();
    assert_eq!(p.preco_de, None);
    assert_eq!(p.desconto_pct, None);
}

#[test]
fn rejeicoes_do_card_valem_para_a_pagina() {
    let l = LinhaOferta {
        preco_por: Some(0.0),
        ..linha()
    };
    assert_eq!(para_pagina(&l, None, &m()), Err(Rejeicao::PrecoPorInvalido));
}

#[test]
fn id_produto_ausente_rejeita_a_pagina() {
    let l = LinhaOferta {
        id_produto: None,
        ..linha()
    };
    assert_eq!(para_pagina(&l, None, &m()), Err(Rejeicao::IdProdutoAusente));
}
