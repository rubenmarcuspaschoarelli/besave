//! Fronteira com o Oracle: tudo que o worker lê passa por `FonteOfertas`.

use crate::conversao::{LinhaOferta, LinhaProduto};

#[derive(Debug, thiserror::Error)]
pub enum ErroFonte {
    #[error("variável de ambiente {0} ausente")]
    ConfigAusente(&'static str),
    #[error("oracle: {0}")]
    Oracle(#[from] oracle::Error),
}

pub type Result<T, E = ErroFonte> = std::result::Result<T, E>;

/// Expiradas continuam publicadas por 7 dias após `DT_DESATIVACAO` (CONTRATO §7).
pub const JANELA_EXPURGO_SEGUNDOS: i64 = 7 * 86_400;

pub trait FonteOfertas {
    /// `ST_ATIVO = 1 OR DT_DESATIVACAO >= agora - 7 dias`.
    fn ofertas(&self) -> Result<Vec<LinhaOferta>>;
    fn produto(&self, id_produto: i64) -> Result<Option<LinhaProduto>>;
}

/// Fonte em memória para testes. `agora` em segundos Unix UTC.
#[derive(Debug, Clone, Default)]
pub struct FakeFonte {
    ofertas: Vec<LinhaOferta>,
    produtos: Vec<LinhaProduto>,
    agora: i64,
}

impl FakeFonte {
    pub fn new(ofertas: Vec<LinhaOferta>, produtos: Vec<LinhaProduto>, agora: i64) -> Self {
        Self {
            ofertas,
            produtos,
            agora,
        }
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
        Ok(self
            .produtos
            .iter()
            .find(|p| p.id_produto == id_produto)
            .cloned())
    }
}
