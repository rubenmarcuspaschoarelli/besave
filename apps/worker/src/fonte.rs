//! Fronteira com o Oracle: tudo que o worker lê passa por `FonteOfertas`.

use std::cell::{Cell, RefCell};
use std::collections::{BTreeMap, HashMap};

use crate::avisos::modelo::LinhaAviso;
use crate::conversao::{LinhaOferta, LinhaProduto, faixa_publicacao};

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
    /// `DT_PUBLICACAO_SITE` = instante do ciclo de `agora` (o `dp` do card) nos ids com a data nula
    /// ou fora da faixa válida (BSV-40, BSV-36), num statement só e com commit; até `BLOCO_IN`
    /// ids. Devolve as linhas alteradas.
    fn marcar_publicadas_site(&self, ids: &[i64], agora: i64) -> Result<u64>;
    /// Todas as linhas de `AVISO` (BSV-41); o ciclo decide o que publica.
    fn avisos(&self) -> Result<Vec<LinhaAviso>>;
    /// `AVISO.DT_PUBLICACAO_SITE = SYSDATE` (só se nula) ou nula, com commit.
    fn marcar_aviso_site(&self, id: i64, publicado: bool) -> Result<()>;
}

/// Fonte em memória para testes. `agora` em segundos Unix UTC. Conta as chamadas de produto.
#[derive(Debug, Clone, Default)]
pub struct FakeFonte {
    ofertas: Vec<LinhaOferta>,
    produtos: Vec<LinhaProduto>,
    agora: i64,
    chamadas_produto: Cell<u64>,
    chamadas_produtos: Cell<u64>,
    /// id → `DT_PUBLICACAO_SITE` gravada por `marcar_publicadas_site`; `ofertas` devolve esse valor.
    publicadas_site: RefCell<BTreeMap<i64, i64>>,
    lotes_publicacao_site: Cell<u64>,
    falhar_publicacao_site: bool,
    avisos: RefCell<Vec<LinhaAviso>>,
    falhar_avisos: bool,
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

    /// `marcar_publicadas_site` passa a falhar (falha injetada).
    #[must_use]
    pub fn com_falha_publicacao_site(mut self) -> Self {
        self.falhar_publicacao_site = true;
        self
    }

    /// Linhas de `AVISO` (BSV-41).
    #[must_use]
    pub fn com_avisos(self, avisos: Vec<LinhaAviso>) -> Self {
        *self.avisos.borrow_mut() = avisos;
        self
    }

    /// `avisos` passa a falhar (falha injetada).
    #[must_use]
    pub fn com_falha_avisos(mut self) -> Self {
        self.falhar_avisos = true;
        self
    }

    /// Troca as linhas de `AVISO`, mantendo `DT_PUBLICACAO_SITE` de cada id.
    pub fn definir_avisos(&self, avisos: Vec<LinhaAviso>) {
        let mut atuais = self.avisos.borrow_mut();
        let datas: BTreeMap<i64, Option<i64>> = atuais
            .iter()
            .map(|a| (a.id, a.dt_publicacao_site))
            .collect();
        *atuais = avisos
            .into_iter()
            .map(|mut a| {
                if let Some(d) = datas.get(&a.id) {
                    a.dt_publicacao_site = *d;
                }
                a
            })
            .collect();
    }

    /// Linhas de `AVISO` como estão (com `DT_PUBLICACAO_SITE`).
    pub fn avisos_atuais(&self) -> Vec<LinhaAviso> {
        self.avisos.borrow().clone()
    }

    /// `DT_PUBLICACAO_SITE` gravada por id.
    pub fn publicadas_site(&self) -> BTreeMap<i64, i64> {
        self.publicadas_site.borrow().clone()
    }

    /// Chamadas de `marcar_publicadas_site` (um statement cada).
    pub fn lotes_publicacao_site(&self) -> u64 {
        self.lotes_publicacao_site.get()
    }
}

impl FonteOfertas for FakeFonte {
    fn ofertas(&self) -> Result<Vec<LinhaOferta>> {
        let limite = self.agora - JANELA_EXPURGO_SEGUNDOS;
        Ok(self
            .ofertas
            .iter()
            .filter(|l| l.ativo || l.dt_desativacao.is_some_and(|d| d >= limite))
            .map(|l| LinhaOferta {
                dt_publicacao_site: self
                    .publicadas_site
                    .borrow()
                    .get(&l.id)
                    .copied()
                    .or(l.dt_publicacao_site),
                ..l.clone()
            })
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

    fn marcar_publicadas_site(&self, ids: &[i64], agora: i64) -> Result<u64> {
        self.lotes_publicacao_site
            .set(self.lotes_publicacao_site.get() + 1);
        if self.falhar_publicacao_site {
            return Err(ErroFonte::ConfigInvalida(
                "DT_PUBLICACAO_SITE",
                "falha injetada".into(),
            ));
        }
        let (min, instante) = faixa_publicacao(agora);
        let mut datas = self.publicadas_site.borrow_mut();
        let mut n = 0;
        for l in self.ofertas.iter().filter(|l| ids.contains(&l.id)) {
            let atual = datas.get(&l.id).copied().or(l.dt_publicacao_site);
            if !atual.is_some_and(|d| (min..=instante).contains(&d)) {
                datas.insert(l.id, instante);
                n += 1;
            }
        }
        Ok(n)
    }

    fn avisos(&self) -> Result<Vec<LinhaAviso>> {
        if self.falhar_avisos {
            return Err(ErroFonte::ConfigInvalida("AVISO", "falha injetada".into()));
        }
        Ok(self.avisos.borrow().clone())
    }

    fn marcar_aviso_site(&self, id: i64, publicado: bool) -> Result<()> {
        for a in self.avisos.borrow_mut().iter_mut().filter(|a| a.id == id) {
            a.dt_publicacao_site = if publicado {
                a.dt_publicacao_site.or(Some(self.agora))
            } else {
                None
            };
        }
        Ok(())
    }
}

/// Dados de demonstração: as 3 ofertas das fixtures, uma por motivo de rejeição,
/// uma inativa há 8 dias (fora da fonte) e um aviso vigente sem imagem (BSV-41).
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
    FakeFonte::new(ofertas, produtos, agora).com_avisos(vec![LinhaAviso {
        id: 1,
        titulo: "Como o Besave funciona".into(),
        texto: "Os links deste canal são de afiliado.".into(),
        link_interno: Some("/".into()),
        ativo: true,
        dt_inicio: agora - DIA,
        ..Default::default()
    }])
}
