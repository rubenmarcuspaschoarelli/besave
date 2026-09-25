//! FONTE-01, FONTE-02: FakeFonte aplica o filtro de expurgo (CONTRATO §7) e busca produto.

use worker::conversao::{LinhaOferta, LinhaProduto};
use worker::fonte::{FakeFonte, FonteOfertas};

const AGORA: i64 = 1_790_253_600;
const DIA: i64 = 86_400;

fn oferta(id: i64, ativo: bool, dt_desativacao: Option<i64>) -> LinhaOferta {
    LinhaOferta {
        id,
        ativo,
        dt_desativacao,
        ..Default::default()
    }
}

fn ids(f: &FakeFonte) -> Vec<i64> {
    f.ofertas().unwrap().iter().map(|l| l.id).collect()
}

#[test]
fn expurgo_de_7_dias() {
    let f = FakeFonte::new(
        vec![
            oferta(1, true, None),
            oferta(2, false, Some(AGORA - 8 * DIA)),
            oferta(3, false, Some(AGORA - 6 * DIA)),
            oferta(4, false, Some(AGORA - 7 * DIA)),
            oferta(5, false, None),
            oferta(6, true, Some(AGORA - 30 * DIA)),
        ],
        vec![],
        AGORA,
    );
    assert_eq!(ids(&f), vec![1, 3, 4, 6]);
}

#[test]
fn produto_por_id() {
    let p = LinhaProduto {
        id_produto: 910,
        marca: Some("XYZ".into()),
        ..Default::default()
    };
    let f = FakeFonte::new(vec![], vec![p.clone()], AGORA);
    assert_eq!(f.produto(910).unwrap(), Some(p));
    assert_eq!(f.produto(911).unwrap(), None);
}
