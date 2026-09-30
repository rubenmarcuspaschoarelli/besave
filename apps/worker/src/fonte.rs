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
