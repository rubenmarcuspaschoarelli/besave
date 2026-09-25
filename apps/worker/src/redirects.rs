//! KeyValueStore de redirects `id → DS_URL_AFILIADO` da Function `/ir/{id}` (MANIFEST §5, §6).

use std::collections::BTreeMap;

use tracing::{info, warn};

/// Quota da KVS: valor ≤ 1 KB.
pub const LIMITE_VALOR_BYTES: usize = 1024;
/// Quota da KVS: 5 MB por store (soma de chaves + valores).
pub const LIMITE_KVS_BYTES: usize = 5 * 1024 * 1024;
/// Acima disso, trocar por Lambda@Edge + DynamoDB (MANIFEST §5).
pub const AVISO_ENTRADAS: usize = 40_000;

#[derive(Debug, thiserror::Error)]
pub enum ErroRedirects {
    #[error(
        "url de afiliado da oferta {id} tem {bytes} bytes; limite da KVS é {LIMITE_VALOR_BYTES}"
    )]
    ValorGrandeDemais { id: i64, bytes: usize },
    #[error("KVS ficaria com {bytes} bytes; limite é {LIMITE_KVS_BYTES}")]
    KvsAcimaDoLimite { bytes: usize },
    #[error("KVS {operacao}: {fonte}")]
    Kvs {
        operacao: &'static str,
        fonte: String,
    },
}

pub type Result<T, E = ErroRedirects> = std::result::Result<T, E>;

/// Chave = `id` em decimal; valor = URL.
pub trait Redirects {
    /// Entradas de chave numérica; as demais são ignoradas.
    fn listar(&self) -> Result<BTreeMap<i64, String>>;
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> Result<()>;
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct RelatorioRedirects {
    pub puts: u64,
    pub dels: u64,
    /// Entradas após a sincronização.
    pub total: u64,
}

/// Deixa a KVS igual a `ativos` (URLs trimadas) aplicando só o diff. Limites checados antes de
/// qualquer escrita; sem diff, `aplicar` não é chamado.
pub fn sincronizar_redirects(
    ativos: &[(i64, String)],
    kvs: &mut dyn Redirects,
) -> Result<RelatorioRedirects> {
    let alvo: BTreeMap<i64, &str> = ativos.iter().map(|(id, u)| (*id, u.trim())).collect();
    let mut bytes = 0;
    for (id, url) in &alvo {
        if url.len() > LIMITE_VALOR_BYTES {
            return Err(ErroRedirects::ValorGrandeDemais {
                id: *id,
                bytes: url.len(),
            });
        }
        bytes += id.to_string().len() + url.len();
    }
    if bytes > LIMITE_KVS_BYTES {
        return Err(ErroRedirects::KvsAcimaDoLimite { bytes });
    }
    if alvo.len() > AVISO_ENTRADAS {
        warn!(
            entradas = alvo.len(),
            limite = AVISO_ENTRADAS,
            "KVS de redirects perto do limite de 5 MB; planejar Lambda@Edge + DynamoDB"
        );
    }

    let atual = kvs.listar()?;
    let put: Vec<(i64, String)> = alvo
        .iter()
        .filter(|(id, url)| atual.get(id).map(String::as_str) != Some(**url))
        .map(|(id, url)| (*id, (*url).to_owned()))
        .collect();
    let del: Vec<i64> = atual
        .keys()
        .filter(|id| !alvo.contains_key(id))
        .copied()
        .collect();
    if !put.is_empty() || !del.is_empty() {
        kvs.aplicar(&put, &del)?;
    }
    info!(
        puts = put.len(),
        dels = del.len(),
        total = alvo.len(),
        "redirects sincronizados"
    );
    Ok(RelatorioRedirects {
        puts: put.len() as u64,
        dels: del.len() as u64,
        total: alvo.len() as u64,
    })
}

/// `"5412"` → `5412`; chave de outro dono → `None`.
pub fn id_da_chave(chave: &str) -> Option<i64> {
    let id: i64 = chave.parse().ok()?;
    (id.to_string() == chave).then_some(id)
}

/// `(put, del)` de uma chamada a `aplicar`.
pub type Aplicacao = (Vec<(i64, String)>, Vec<i64>);

/// KVS em memória para testes: registra cada `aplicar` e pode falhar sob demanda.
#[derive(Debug, Clone, Default)]
pub struct RedirectsMemoria {
    chaves: BTreeMap<String, String>,
    aplicados: Vec<Aplicacao>,
    falhar: bool,
}

impl RedirectsMemoria {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn com(estado: BTreeMap<i64, String>) -> Self {
        Self {
            chaves: estado
                .into_iter()
                .map(|(k, v)| (k.to_string(), v))
                .collect(),
            ..Self::default()
        }
    }

    /// Todo `aplicar` passa a falhar sem mudar o estado.
    pub fn falhando(mut self) -> Self {
        self.falhar = true;
        self
    }

    pub fn inserir_bruto(&mut self, chave: &str, valor: &str) {
        self.chaves.insert(chave.to_owned(), valor.to_owned());
    }

    /// Estado bruto, como a KVS guarda.
    pub fn chaves(&self) -> BTreeMap<String, String> {
        self.chaves.clone()
    }

    /// `(put, del)` de cada `aplicar` bem-sucedido, em ordem.
    pub fn aplicados(&self) -> &[Aplicacao] {
        &self.aplicados
    }
}

impl Redirects for RedirectsMemoria {
    fn listar(&self) -> Result<BTreeMap<i64, String>> {
        Ok(self
            .chaves
            .iter()
            .filter_map(|(k, v)| Some((id_da_chave(k)?, v.clone())))
            .collect())
    }

    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> Result<()> {
        if self.falhar {
            return Err(ErroRedirects::Kvs {
                operacao: "aplicar",
                fonte: "falha injetada".into(),
            });
        }
        for (id, url) in put {
            self.chaves.insert(id.to_string(), url.clone());
        }
        for id in del {
            self.chaves.remove(&id.to_string());
        }
        self.aplicados.push((put.to_vec(), del.to_vec()));
        Ok(())
    }
}
