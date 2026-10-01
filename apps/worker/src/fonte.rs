//! Fronteira com o Oracle: tudo que o worker lê passa por `FonteOfertas`.

use std::cell::Cell;
use std::collections::HashMap;

use crate::conversao::{LinhaOferta, LinhaProduto};

#[derive(Debug, thiserror::Error)]
pub enum ErroFonte {
    #[error("variável de ambiente {0} ausente")]
    ConfigAusente(&'static str),
    #[error("variável de ambiente {0} inválida: {1}")]
    ConfigInvalida(&'static str, String),
    #[error("oracle: {0}")]
    Oracle(#[from] oracle::Error),
}

pub type Result<T, E = ErroFonte> = std::result::Result<T, E>;

/// Expiradas continuam publicadas por 7 dias após `DT_DESATIVACAO` (CONTRATO §7).
pub const JANELA_EXPURGO_SEGUNDOS: i64 = 7 * 86_400;

pub trait FonteOfertas {
    /// `ST_ATIVO = 1 OR DT_DESATIVACAO >= agora - 7 dias`.
    fn ofertas(&self) -> Result<Vec<LinhaOferta>>;
    /// Só para teste/compat: o ciclo usa `produtos` (sem N+1).
    fn produto(&self, id_produto: i64) -> Result<Option<LinhaProduto>>;
    /// Produtos dos ids pedidos, em lote; ids sem linha em PRODUTO ficam de fora.
    fn produtos(&self, ids: &[i64]) -> Result<HashMap<i64, LinhaProduto>>;
}

/// Fonte em memória para testes. `agora` em segundos Unix UTC. Conta as chamadas de produto.
#[derive(Debug, Clone, Default)]
pub struct FakeFonte {
    ofertas: Vec<LinhaOferta>,
    produtos: Vec<LinhaProduto>,
    agora: i64,
    chamadas_produto: Cell<u64>,
    chamadas_produtos: Cell<u64>,
}

impl FakeFonte {
    pub fn new(ofertas: Vec<LinhaOferta>, produtos: Vec<LinhaProduto>, agora: i64) -> Self {
        Self {
            ofertas,
            produtos,
            agora,
            ..Default::default()
        }
    }

    /// Chamadas de `produto` (unitário) desde a criação.
    pub fn chamadas_produto(&self) -> u64 {
        self.chamadas_produto.get()
    }

    /// Chamadas de `produtos` (lote) desde a criação.
    pub fn chamadas_produtos(&self) -> u64 {
        self.chamadas_produtos.get()
    }
}

impl FonteOfertas for FakeFonte {
    fn ofertas(&self) -> Result<Vec<LinhaOferta>> {
        let limite = self.agora - JANELA_EXPURGO_SEGUNDOS;
        Ok(self
            .ofertas
            .iter()
            .filter(|l| l.ativo || l.dt_desativacao.is_some_and(|d| d >= limite))
            .cloned()
            .collect())
    }

    fn produto(&self, id_produto: i64) -> Result<Option<LinhaProduto>> {
        self.chamadas_produto.set(self.chamadas_produto.get() + 1);
        Ok(self
            .produtos
            .iter()
            .find(|p| p.id_produto == id_produto)
            .cloned())
    }

    fn produtos(&self, ids: &[i64]) -> Result<HashMap<i64, LinhaProduto>> {
        self.chamadas_produtos.set(self.chamadas_produtos.get() + 1);
        Ok(self
            .produtos
            .iter()
            .filter(|p| ids.contains(&p.id_produto))
            .map(|p| (p.id_produto, p.clone()))
            .collect())
    }
}

/// Dados de demonstração: as 3 ofertas das fixtures, uma por motivo de rejeição
/// e uma inativa há 8 dias (fora da fonte).
pub fn fake_demo(agora: i64) -> FakeFonte {
    const DIA: i64 = 86_400;
    let ok = |id, id_produto, loja: &str, titulo: &str, de, por, area: &str, publico: &str| {
        LinhaOferta {
            id,
            id_produto: Some(id_produto),
            loja: Some(loja.into()),
            titulo: Some(titulo.into()),
            preco_de: de,
            preco_por: Some(por),
            dt_oferta: Some(agora - DIA),
            area: Some(area.into()),
            publico: Some(publico.into()),
            ativo: true,
            url_afiliado: format!("https://loja.example/{id}"),
            ..Default::default()
        }
    };
    let base = ok(1000, 1, "Amazon", "Base", None, 10.0, "Tech", "U");
    let ofertas = vec![
        LinhaOferta {
            cupom: Some("besave10".into()),
            ..ok(
                5412,
                910,
                "Amazon",
                "Fone Bluetooth XYZ com ANC",
                Some(299.9),
                199.9,
                "Tecnologia",
                "Unissex",
            )
        },
        ok(
            5413,
            911,
            "Shopee",
            "Kit Skincare Vitamina C 3 passos",
            None,
            89.9,
            "Elas",
            "Mulher",
        ),
        LinhaOferta {
            ativo: false,
            dt_desativacao: Some(agora - DIA),
            ..ok(
                5420,
                912,
                "MercadoLivre",
                "Ração Premium Cães Adultos 15kg",
                Some(249.0),
                199.0,
                "Pet",
                "U",
            )
        },
        LinhaOferta {
            id: 1001,
            preco_por: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1002,
            titulo: Some("  ".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1003,
            loja: Some("Americanas".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1004,
            area: Some("Moda".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1005,
            publico: Some("Adulto".into()),
            ..base.clone()
        },
        LinhaOferta {
            id: 1006,
            dt_oferta: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1007,
            id_produto: None,
            ..base.clone()
        },
        LinhaOferta {
            id: 1008,
            ativo: false,
            dt_desativacao: Some(agora - 8 * DIA),
            ..base
        },
    ];
    let produtos = vec![LinhaProduto {
        id_produto: 910,
        descricao: Some(
            "Fone over-ear com cancelamento ativo de ruído e 40 horas de bateria.".into(),
        ),
        marca: Some("XYZ".into()),
        preco_min: Some(179.9),
        preco_max: Some(349.9),
        ..Default::default()
    }];
    FakeFonte::new(ofertas, produtos, agora)
}
