//! Adaptadores AWS: `PublicadorS3` (bucket) e `RedirectsKvs` (CloudFront KeyValueStore).
//! Credenciais e região só pela cadeia padrão do SDK; retentativas são as do SDK.
//! `gerar()` é síncrono: cada método faz `block_on` num runtime `current_thread` compartilhado.

use std::collections::BTreeMap;
use std::sync::Arc;

use aws_config::SdkConfig;
use aws_sdk_cloudfrontkeyvaluestore::types::{DeleteKeyRequestListItem, PutKeyRequestListItem};
use aws_sdk_s3::error::DisplayErrorContext;
use aws_sdk_s3::primitives::ByteStream;
use tokio::runtime::Runtime;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tracing::warn;

use crate::publicador::{self, ErroPublicador, Meta, Publicador};
use crate::redirects::{self, ErroRedirects, EstadoKvs, Redirects, id_da_chave, lotes_kvs};

#[derive(Debug, thiserror::Error)]
pub enum ErroAws {
    #[error("variável de ambiente {0} ausente")]
    ConfigAusente(&'static str),
    #[error("região AWS ausente: defina AWS_REGION ou a região do perfil")]
    RegiaoAusente,
    #[error("criando runtime tokio: {0}")]
    Runtime(std::io::Error),
}

/// Destino do `--publicar`. Sem campo de credencial.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigAws {
    /// `BESAVE_BUCKET`
    pub bucket: String,
    /// `BESAVE_KVS_ARN`
    pub kvs_arn: String,
}

impl ConfigAws {
    pub fn do_env() -> Result<Self, ErroAws> {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroAws> {
        let obrig = |k: &'static str| {
            env(k)
                .filter(|v| !v.trim().is_empty())
                .ok_or(ErroAws::ConfigAusente(k))
        };
        Ok(Self {
            bucket: obrig("BESAVE_BUCKET")?,
            kvs_arn: obrig("BESAVE_KVS_ARN")?,
        })
    }
}

/// Runtime + `SdkConfig` compartilhados pelos dois adaptadores.
#[derive(Clone)]
pub struct ContextoAws {
    rt: Arc<Runtime>,
    sdk: SdkConfig,
}

impl ContextoAws {
    /// Cadeia padrão do SDK (env `AWS_*`, perfil, SSO…).
    pub fn carregar() -> Result<Self, ErroAws> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(ErroAws::Runtime)?;
        let sdk = rt.block_on(aws_config::load_from_env());
        if sdk.region().is_none() {
            return Err(ErroAws::RegiaoAusente);
        }
        Ok(Self {
            rt: Arc::new(rt),
            sdk,
        })
    }
}

fn texto_erro(e: impl std::error::Error) -> String {
    DisplayErrorContext(e).to_string()
}

pub struct PublicadorS3 {
    rt: Arc<Runtime>,
    cliente: aws_sdk_s3::Client,
    bucket: String,
}

impl PublicadorS3 {
    pub fn new(ctx: &ContextoAws, bucket: impl Into<String>) -> Self {
        Self {
            rt: ctx.rt.clone(),
            cliente: aws_sdk_s3::Client::new(&ctx.sdk),
            bucket: bucket.into(),
        }
    }
}

fn erro_s3(operacao: &'static str, chave: &str, e: impl std::error::Error) -> ErroPublicador {
    ErroPublicador::Aws {
        operacao,
        chave: chave.to_owned(),
        fonte: texto_erro(e),
    }
}

impl Publicador for PublicadorS3 {
    /// `HeadObject`; 404 → `false`. Nunca baixa o objeto.
    fn existe(&self, chave: &str) -> publicador::Result<bool> {
        let r = self.rt.block_on(
            self.cliente
                .head_object()
                .bucket(&self.bucket)
                .key(chave)
                .send(),
        );
        match r {
            Ok(_) => Ok(true),
            Err(e) if e.as_service_error().is_some_and(|s| s.is_not_found()) => Ok(false),
            Err(e) => Err(erro_s3("HeadObject", chave, e)),
        }
    }

    /// `GetObject`; só o worker chama para `manifest.json` (chunks são comparados pelo nome).
    fn ler(&self, chave: &str) -> publicador::Result<Option<Vec<u8>>> {
        self.rt.block_on(async {
            let r = self
                .cliente
                .get_object()
                .bucket(&self.bucket)
                .key(chave)
                .send()
                .await;
            let saida = match r {
                Ok(s) => s,
                Err(e) if e.as_service_error().is_some_and(|s| s.is_no_such_key()) => {
                    return Ok(None);
                }
                Err(e) => return Err(erro_s3("GetObject", chave, e)),
            };
            let corpo = saida
                .body
                .collect()
                .await
                .map_err(|e| erro_s3("GetObject", chave, e))?;
            Ok(Some(corpo.into_bytes().to_vec()))
        })
    }

    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> publicador::Result<()> {
        self.rt
            .block_on(
                self.cliente
                    .put_object()
                    .bucket(&self.bucket)
                    .key(chave)
                    .body(ByteStream::from(bytes.to_vec()))
                    .content_type(meta.content_type)
                    .set_content_encoding(meta.content_encoding.map(str::to_owned))
                    .cache_control(meta.cache_control)
                    .send(),
            )
            .map(|_| ())
            .map_err(|e| erro_s3("PutObject", chave, e))
    }

    /// `DeleteObject`; chave ausente não é erro no S3.
    fn remover(&mut self, chave: &str) -> publicador::Result<()> {
        self.rt
            .block_on(
                self.cliente
                    .delete_object()
                    .bucket(&self.bucket)
                    .key(chave)
                    .send(),
            )
            .map(|_| ())
            .map_err(|e| erro_s3("DeleteObject", chave, e))
    }

    /// `ListObjectsV2` paginado.
    fn listar(&self, prefixo: &str) -> publicador::Result<Vec<String>> {
        let paginas = self
            .rt
            .block_on(
                self.cliente
                    .list_objects_v2()
                    .bucket(&self.bucket)
                    .prefix(prefixo)
                    .into_paginator()
                    .send()
                    .try_collect(),
            )
            .map_err(|e| erro_s3("ListObjectsV2", prefixo, e))?;
        let mut chaves: Vec<String> = paginas
            .into_iter()
            .flat_map(|p| p.contents.unwrap_or_default())
            .filter_map(|o| o.key)
            .collect();
        chaves.sort();
        Ok(chaves)
    }

    /// Sobrescreve o default sequencial do trait: até `MAX_EM_VOO` `HeadObject` em voo (regra 8
    /// da BSV-13 — o gargalo de ~50 mil objetos na primeira carga é rede, não CPU). A ordem dos
    /// resultados bate com `chaves`; erro de uma tarefa aborta o lote (mesma semântica de
    /// `existe` unitário, que também propaga erro).
    fn existem(&self, chaves: &[&str]) -> publicador::Result<Vec<bool>> {
        let rt = self.rt.clone();
        let cliente = self.cliente.clone();
        let bucket = self.bucket.clone();
        let chaves: Vec<String> = chaves.iter().map(|c| (*c).to_owned()).collect();
        rt.block_on(async move {
            let n = chaves.len();
            let semaforo = Arc::new(Semaphore::new(MAX_EM_VOO));
            let mut tarefas = JoinSet::new();
            for (i, chave) in chaves.into_iter().enumerate() {
                let permissao = permissao(&semaforo).await?;
                let cliente = cliente.clone();
                let bucket = bucket.clone();
                tarefas.spawn(async move {
                    let _permissao = permissao;
                    (i, existe_async(&cliente, &bucket, &chave).await)
                });
            }
            let mut resultados = vec![false; n];
            while let Some(saida) = tarefas.join_next().await {
                let (i, r) = saida.map_err(erro_tarefa_perdida)?;
                resultados[i] = r?;
            }
            Ok(resultados)
        })
    }

    /// Sobrescreve o default sequencial do trait: até `MAX_EM_VOO` `PutObject` em voo (regra 8).
    fn gravar_lote(&mut self, itens: &[(String, Vec<u8>, Meta)]) -> publicador::Result<()> {
        let rt = self.rt.clone();
        let cliente = self.cliente.clone();
        let bucket = self.bucket.clone();
        let itens = itens.to_vec();
        rt.block_on(async move {
            let semaforo = Arc::new(Semaphore::new(MAX_EM_VOO));
            let mut tarefas = JoinSet::new();
            for (chave, bytes, meta) in itens {
                let permissao = permissao(&semaforo).await?;
                let cliente = cliente.clone();
                let bucket = bucket.clone();
                tarefas.spawn(async move {
                    let _permissao = permissao;
                    gravar_async(&cliente, &bucket, &chave, bytes, meta).await
                });
            }
            while let Some(saida) = tarefas.join_next().await {
                saida.map_err(erro_tarefa_perdida)??;
            }
            Ok(())
        })
    }
}

/// Pares `HeadObject`/`PutObject` em voo simultaneamente (regra 8, BSV-13): o gargalo de ~50 mil
/// objetos na primeira carga é rede, não CPU. `PublicadorLocal`/`PublicadorMemoria` continuam
/// sequenciais (default do trait) — só aqui, no S3, o round-trip de rede compensa sobrepor.
const MAX_EM_VOO: usize = 16;

async fn permissao(
    semaforo: &Arc<Semaphore>,
) -> publicador::Result<tokio::sync::OwnedSemaphorePermit> {
    Arc::clone(semaforo)
        .acquire_owned()
        .await
        .map_err(|e| ErroPublicador::Aws {
            operacao: "semáforo do pool de imagens",
            chave: String::new(),
            fonte: texto_erro(e),
        })
}

/// `JoinError` só ocorre em pânico da tarefa; o índice/chave já se perderam nesse caso.
fn erro_tarefa_perdida(e: tokio::task::JoinError) -> ErroPublicador {
    ErroPublicador::Aws {
        operacao: "tarefa em paralelo",
        chave: "<tarefa perdida>".to_owned(),
        fonte: texto_erro(e),
    }
}

async fn existe_async(
    cliente: &aws_sdk_s3::Client,
    bucket: &str,
    chave: &str,
) -> publicador::Result<bool> {
    let r = cliente.head_object().bucket(bucket).key(chave).send().await;
    match r {
        Ok(_) => Ok(true),
        Err(e) if e.as_service_error().is_some_and(|s| s.is_not_found()) => Ok(false),
        Err(e) => Err(erro_s3("HeadObject", chave, e)),
    }
}

async fn gravar_async(
    cliente: &aws_sdk_s3::Client,
    bucket: &str,
    chave: &str,
    bytes: Vec<u8>,
    meta: Meta,
) -> publicador::Result<()> {
    cliente
        .put_object()
        .bucket(bucket)
        .key(chave)
        .body(ByteStream::from(bytes))
        .content_type(meta.content_type)
        .set_content_encoding(meta.content_encoding.map(str::to_owned))
        .cache_control(meta.cache_control)
        .send()
        .await
        .map(|_| ())
        .map_err(|e| erro_s3("PutObject", chave, e))
}

pub struct RedirectsKvs {
    rt: Arc<Runtime>,
    cliente: aws_sdk_cloudfrontkeyvaluestore::Client,
    arn: String,
}

impl RedirectsKvs {
    pub fn new(ctx: &ContextoAws, arn: impl Into<String>) -> Self {
        Self {
            rt: ctx.rt.clone(),
            cliente: aws_sdk_cloudfrontkeyvaluestore::Client::new(&ctx.sdk),
            arn: arn.into(),
        }
    }
}

fn erro_kvs(operacao: &'static str, e: impl std::error::Error) -> ErroRedirects {
    ErroRedirects::Kvs {
        operacao,
        fonte: texto_erro(e),
    }
}

impl Redirects for RedirectsKvs {
    /// `ListKeys` paginado; chaves não numéricas são ignoradas.
    fn listar(&self) -> redirects::Result<BTreeMap<i64, String>> {
        let itens = self
            .rt
            .block_on(
                self.cliente
                    .list_keys()
                    .kvs_arn(&self.arn)
                    .into_paginator()
                    .items()
                    .send()
                    .try_collect(),
            )
            .map_err(|e| erro_kvs("ListKeys", e))?;
        let mut mapa = BTreeMap::new();
        for item in itens {
            match id_da_chave(item.key()) {
                Some(id) => {
                    mapa.insert(id, item.value().to_owned());
                }
                None => warn!(chave = item.key(), "chave não numérica na KVS ignorada"),
            }
        }
        Ok(mapa)
    }

    /// `DescribeKeyValueStore`; `ItemCount` negativo (não documentado) vira 0.
    fn descrever(&self) -> redirects::Result<EstadoKvs> {
        let d = self
            .rt
            .block_on(
                self.cliente
                    .describe_key_value_store()
                    .kvs_arn(&self.arn)
                    .send(),
            )
            .map_err(|e| erro_kvs("DescribeKeyValueStore", e))?;
        Ok(EstadoKvs {
            item_count: u64::try_from(d.item_count()).unwrap_or(0),
            etag: d.e_tag().to_owned(),
        })
    }

    /// Um `UpdateKeys` por lote de `lotes_kvs` (puts e deletes juntos). O 1º usa `If-Match: etag`
    /// (lido em `carregar_base`, sem `DescribeKeyValueStore` aqui); os seguintes encadeiam o `ETag`
    /// devolvido pelo anterior. `ConflictException` → `Concorrencia`. Devolve `ItemCount`/`ETag` da
    /// última `UpdateKeys`.
    fn aplicar(
        &mut self,
        etag: &str,
        put: &[(i64, String)],
        del: &[i64],
    ) -> redirects::Result<EstadoKvs> {
        let mut chamadas = Vec::new();
        for lote in lotes_kvs(put, del) {
            let puts = lote
                .puts
                .iter()
                .map(|(id, url)| {
                    PutKeyRequestListItem::builder()
                        .key(id.to_string())
                        .value(url)
                        .build()
                })
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| erro_kvs("UpdateKeys", e))?;
            let dels = lote
                .dels
                .iter()
                .map(|id| {
                    DeleteKeyRequestListItem::builder()
                        .key(id.to_string())
                        .build()
                })
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| erro_kvs("UpdateKeys", e))?;
            chamadas.push((
                (!puts.is_empty()).then_some(puts),
                (!dels.is_empty()).then_some(dels),
            ));
        }
        if chamadas.is_empty() {
            return self.descrever();
        }
        self.rt.block_on(async {
            let mut etag = etag.to_owned();
            let mut item_count = 0;
            for (puts, dels) in chamadas {
                let r = self
                    .cliente
                    .update_keys()
                    .kvs_arn(&self.arn)
                    .if_match(etag.clone())
                    .set_puts(puts)
                    .set_deletes(dels)
                    .send()
                    .await
                    .map_err(|e| {
                        if e.as_service_error()
                            .is_some_and(|s| s.is_conflict_exception())
                        {
                            ErroRedirects::Concorrencia {
                                etag: etag.clone(),
                                fonte: texto_erro(e),
                            }
                        } else {
                            erro_kvs("UpdateKeys", e)
                        }
                    })?;
                item_count = u64::try_from(r.item_count()).unwrap_or(0);
                etag = r.e_tag().to_owned();
            }
            Ok(EstadoKvs { item_count, etag })
        })
    }
}
