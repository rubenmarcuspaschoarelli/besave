//! KeyValueStore de redirects `id → DS_URL_AFILIADO` da Function `/ir/{id}` (MANIFEST §5, §6).

use std::cell::Cell;
use std::collections::BTreeMap;
use std::fmt;

use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::paginas::hash16;
use crate::publicador::{ErroPublicador, META_ESTADO, Publicador};

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
    #[error("url de afiliado da oferta {id} vazia; a KVS não recebe valor vazio")]
    ValorVazio { id: i64 },
    #[error("KVS ficaria com {bytes} bytes; limite é {LIMITE_KVS_BYTES}")]
    KvsAcimaDoLimite { bytes: usize },
    #[error("KVS {operacao}: {fonte}")]
    Kvs {
        operacao: &'static str,
        fonte: String,
    },
    #[error("índice {CHAVE_INDICE}: {0}")]
    Indice(ErroPublicador),
    #[error("serializando {CHAVE_INDICE}: {0}")]
    IndiceSerializacao(serde_json::Error),
}

pub type Result<T, E = ErroRedirects> = std::result::Result<T, E>;

/// `ItemCount` e `ETag` da KVS (`DescribeKeyValueStore`, `UpdateKeys`). O `ETag` muda a cada
/// escrita; `item_count` conta todas as chaves, inclusive as não numéricas.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct EstadoKvs {
    pub item_count: u64,
    pub etag: String,
}

/// Chave = `id` em decimal; valor = URL.
pub trait Redirects {
    /// Entradas de chave numérica; as demais são ignoradas.
    fn listar(&self) -> Result<BTreeMap<i64, String>>;
    /// Estado atual, sem listar.
    fn descrever(&self) -> Result<EstadoKvs>;
    /// Aplica o diff e devolve o estado depois da última escrita.
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> Result<EstadoKvs>;
}

/// Caminho que o ciclo tomou (BSV-12c).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum ModoRedirects {
    /// Diff contra `_estado/redirects.json`, sem listar a KVS.
    Indice,
    /// `listar()` completo e índice reconstruído.
    #[default]
    Reconstrucao,
}

impl fmt::Display for ModoRedirects {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Indice => "indice",
            Self::Reconstrucao => "reconstrucao",
        })
    }
}

/// Por que o índice não foi usado.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MotivoReconstrucao {
    IndiceAusente,
    IndiceIlegivel,
    EtagDivergente,
    ItemCountDivergente,
}

impl fmt::Display for MotivoReconstrucao {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::IndiceAusente => "indice_ausente",
            Self::IndiceIlegivel => "indice_ilegivel",
            Self::EtagDivergente => "etag_divergente",
            Self::ItemCountDivergente => "item_count_divergente",
        })
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct RelatorioRedirects {
    pub puts: u64,
    pub dels: u64,
    /// Entradas após a sincronização.
    pub total: u64,
    pub modo: ModoRedirects,
    /// Só em `Reconstrucao` vinda de `carregar_base`.
    pub motivo: Option<MotivoReconstrucao>,
}

/// Índice da KVS no bucket (BSV-12c): hash da URL, nunca a URL (link de afiliado).
pub const CHAVE_INDICE: &str = "_estado/redirects.json";

/// Conteúdo de `CHAVE_INDICE`: `ItemCount`/`ETag` da KVS ao fim do ciclo que o gravou e
/// id → hash16 da URL.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct IndiceRedirects {
    pub kvs_item_count: u64,
    pub kvs_etag: String,
    pub urls: BTreeMap<i64, String>,
}

/// O que o ciclo sabe da KVS antes do diff: id → hash16 da URL, vindo do índice ou da listagem.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BaseRedirects {
    pub urls: BTreeMap<i64, String>,
    pub modo: ModoRedirects,
    pub motivo: Option<MotivoReconstrucao>,
    estado: EstadoKvs,
    /// Bytes do índice lido; o índice novo só é gravado se diferir.
    lido: Option<Vec<u8>>,
}

fn hashes(mapa: BTreeMap<i64, String>) -> BTreeMap<i64, String> {
    mapa.into_iter()
        .map(|(id, url)| (id, hash16(url.as_bytes())))
        .collect()
}

/// 1 `descrever` + 1 leitura do índice. Índice confiável (existe, é legível e `ETag`/`ItemCount`
/// batem com a KVS) → base = índice, sem listar. Senão, `WARN` com o motivo e `listar()` completo.
/// Erro de leitura do bucket (não de conteúdo) aborta.
pub fn carregar_base(kvs: &dyn Redirects, pub_: &dyn Publicador) -> Result<BaseRedirects> {
    let estado = kvs.descrever()?;
    let lido = pub_.ler(CHAVE_INDICE).map_err(ErroRedirects::Indice)?;
    let confiavel = match lido
        .as_deref()
        .map(serde_json::from_slice::<IndiceRedirects>)
    {
        None => Err(MotivoReconstrucao::IndiceAusente),
        Some(Err(_)) => Err(MotivoReconstrucao::IndiceIlegivel),
        Some(Ok(i)) if i.kvs_etag != estado.etag => Err(MotivoReconstrucao::EtagDivergente),
        Some(Ok(i)) if i.kvs_item_count != estado.item_count => {
            Err(MotivoReconstrucao::ItemCountDivergente)
        }
        Some(Ok(i)) => Ok(i.urls),
    };
    let (urls, modo, motivo) = match confiavel {
        Ok(urls) => (urls, ModoRedirects::Indice, None),
        Err(m) => {
            warn!(motivo = %m, "índice de redirects não confiável; listando a KVS");
            (hashes(kvs.listar()?), ModoRedirects::Reconstrucao, Some(m))
        }
    };
    Ok(BaseRedirects {
        urls,
        modo,
        motivo,
        estado,
        lido,
    })
}

/// URLs trimadas por id, com os limites da KVS checados antes de qualquer escrita.
fn validar(ativos: &[(i64, String)]) -> Result<BTreeMap<i64, &str>> {
    let alvo: BTreeMap<i64, &str> = ativos.iter().map(|(id, u)| (*id, u.trim())).collect();
    let mut bytes = 0;
    for (id, url) in &alvo {
        if url.is_empty() {
            return Err(ErroRedirects::ValorVazio { id: *id });
        }
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
    Ok(alvo)
}

/// Diff por hash16 da URL: put do que é novo ou mudou; del do que saiu. Sem diff, `aplicar` não é
/// chamado e o estado devolvido é `None`.
fn aplicar_diff(
    alvo: &BTreeMap<i64, &str>,
    base: &BTreeMap<i64, String>,
    kvs: &mut dyn Redirects,
) -> Result<(RelatorioRedirects, Option<EstadoKvs>)> {
    let put: Vec<(i64, String)> = alvo
        .iter()
        .filter(|(id, url)| base.get(id) != Some(&hash16(url.as_bytes())))
        .map(|(id, url)| (*id, (*url).to_owned()))
        .collect();
    let del: Vec<i64> = base
        .keys()
        .filter(|id| !alvo.contains_key(id))
        .copied()
        .collect();
    let estado = if !put.is_empty() || !del.is_empty() {
        Some(kvs.aplicar(&put, &del)?)
    } else {
        None
    };
    info!(
        puts = put.len(),
        dels = del.len(),
        total = alvo.len(),
        "redirects sincronizados"
    );
    let rel = RelatorioRedirects {
        puts: put.len() as u64,
        dels: del.len() as u64,
        total: alvo.len() as u64,
        ..Default::default()
    };
    Ok((rel, estado))
}

/// Deixa a KVS igual a `ativos` (URLs trimadas) aplicando só o diff contra uma listagem completa.
/// Limites checados antes de qualquer escrita; sem diff, `aplicar` não é chamado.
///
/// Regra: a KVS espelha o conjunto **publicado** (`ST_ATIVO = 1 OR DT_DESATIVACAO >= hoje - 7`),
/// não `ST_ATIVO`. Oferta expirada mantém o redirect até o expurgo e some junto com a página.
pub fn sincronizar_redirects(
    ativos: &[(i64, String)],
    kvs: &mut dyn Redirects,
) -> Result<RelatorioRedirects> {
    let alvo = validar(ativos)?;
    let base = hashes(kvs.listar()?);
    Ok(aplicar_diff(&alvo, &base, kvs)?.0)
}

/// Como `sincronizar_redirects`, mas contra `base` (de `carregar_base`), sem listar; depois grava
/// o índice com o `ETag`/`ItemCount` pós-escrita, se ele mudou. Falha ao gravar o índice é erro:
/// o ciclo aborta antes do manifest e o próximo reconstrói.
pub fn sincronizar_com_indice(
    ativos: &[(i64, String)],
    base: BaseRedirects,
    kvs: &mut dyn Redirects,
    pub_: &mut dyn Publicador,
) -> Result<RelatorioRedirects> {
    let alvo = validar(ativos)?;
    let (mut rel, estado) = aplicar_diff(&alvo, &base.urls, kvs)?;
    let estado = estado.unwrap_or(base.estado);
    let indice = IndiceRedirects {
        kvs_item_count: estado.item_count,
        kvs_etag: estado.etag,
        urls: alvo
            .iter()
            .map(|(id, url)| (*id, hash16(url.as_bytes())))
            .collect(),
    };
    let json = serde_json::to_vec(&indice).map_err(ErroRedirects::IndiceSerializacao)?;
    if base.lido.as_deref() != Some(json.as_slice()) {
        pub_.gravar(CHAVE_INDICE, &json, &META_ESTADO)
            .map_err(ErroRedirects::Indice)?;
    }
    rel.modo = base.modo;
    rel.motivo = base.motivo;
    Ok(rel)
}

/// Quota do `UpdateKeys`: 50 chaves (ou 3 MB; com valor ≤ 1 KB, 50 chaves ficam em ~50 KB).
pub const LOTE_KVS: usize = 50;

/// Uma chamada `UpdateKeys`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct LoteKvs {
    pub puts: Vec<(i64, String)>,
    pub dels: Vec<i64>,
}

/// Diff em lotes de até `LOTE_KVS` chaves, na ordem puts → deletes; o lote da fronteira leva
/// os dois. Diff vazio → nenhum lote.
pub fn lotes_kvs(put: &[(i64, String)], del: &[i64]) -> Vec<LoteKvs> {
    let mut lotes: Vec<LoteKvs> = Vec::new();
    let mut atual = LoteKvs::default();
    let mut cheio = |atual: &mut LoteKvs| {
        if atual.puts.len() + atual.dels.len() == LOTE_KVS {
            lotes.push(std::mem::take(atual));
        }
    };
    for p in put {
        atual.puts.push(p.clone());
        cheio(&mut atual);
    }
    for d in del {
        atual.dels.push(*d);
        cheio(&mut atual);
    }
    if !atual.puts.is_empty() || !atual.dels.is_empty() {
        lotes.push(atual);
    }
    lotes
}

/// `"5412"` → `5412`; chave de outro dono → `None`.
pub fn id_da_chave(chave: &str) -> Option<i64> {
    let id: i64 = chave.parse().ok()?;
    (id.to_string() == chave).then_some(id)
}

/// `(put, del)` de uma chamada a `aplicar`.
pub type Aplicacao = (Vec<(i64, String)>, Vec<i64>);

/// KVS em memória para testes: registra cada `aplicar`, conta `listar`/`descrever` e pode falhar
/// sob demanda. `ETag` = `m{n}`, com `n` = escritas desde a criação (`aplicar` e `inserir_bruto`).
#[derive(Debug, Clone, Default)]
pub struct RedirectsMemoria {
    chaves: BTreeMap<String, String>,
    aplicados: Vec<Aplicacao>,
    falhar: bool,
    escritas: u64,
    etag_forcado: Option<String>,
    listar_chamadas: Cell<u64>,
    descrever_chamadas: Cell<u64>,
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

    /// Escrita "por fora" do worker: muda o `ETag`.
    pub fn inserir_bruto(&mut self, chave: &str, valor: &str) {
        self.chaves.insert(chave.to_owned(), valor.to_owned());
        self.escritas += 1;
    }

    /// Fixa o `ETag` devolvido daqui em diante, independente das escritas.
    pub fn definir_etag(&mut self, etag: &str) {
        self.etag_forcado = Some(etag.to_owned());
    }

    /// Chamadas a `listar` desde a criação.
    pub fn listar_chamadas(&self) -> u64 {
        self.listar_chamadas.get()
    }

    /// Chamadas a `descrever` desde a criação.
    pub fn descrever_chamadas(&self) -> u64 {
        self.descrever_chamadas.get()
    }

    fn estado(&self) -> EstadoKvs {
        EstadoKvs {
            item_count: self.chaves.len() as u64,
            etag: self
                .etag_forcado
                .clone()
                .unwrap_or_else(|| format!("m{}", self.escritas)),
        }
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
        self.listar_chamadas.set(self.listar_chamadas.get() + 1);
        Ok(self
            .chaves
            .iter()
            .filter_map(|(k, v)| Some((id_da_chave(k)?, v.clone())))
            .collect())
    }

    fn descrever(&self) -> Result<EstadoKvs> {
        self.descrever_chamadas
            .set(self.descrever_chamadas.get() + 1);
        Ok(self.estado())
    }

    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> Result<EstadoKvs> {
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
        self.escritas += 1;
        Ok(self.estado())
    }
}
