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
use tracing::warn;

use crate::publicador::{self, ErroPublicador, Meta, Publicador};
use crate::redirects::{self, ErroRedirects, Redirects, id_da_chave};

/// Quota do `UpdateKeys`: 50 chaves (ou 3 MB) por chamada.
const LOTE_KVS: usize = 50;

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

    /// `UpdateKeys` em lotes de 50 (puts, depois deletes), encadeando o `ETag` a partir de
    /// `DescribeKeyValueStore`.
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> redirects::Result<()> {
        let puts = put
            .iter()
            .map(|(id, url)| {
                PutKeyRequestListItem::builder()
                    .key(id.to_string())
                    .value(url)
                    .build()
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| erro_kvs("UpdateKeys", e))?;
        let dels = del
            .iter()
            .map(|id| {
                DeleteKeyRequestListItem::builder()
                    .key(id.to_string())
                    .build()
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| erro_kvs("UpdateKeys", e))?;
        self.rt.block_on(async {
            let mut etag = self
                .cliente
                .describe_key_value_store()
                .kvs_arn(&self.arn)
                .send()
                .await
                .map_err(|e| erro_kvs("DescribeKeyValueStore", e))?
                .e_tag()
                .to_owned();
            let lotes = puts
                .chunks(LOTE_KVS)
                .map(|p| (Some(p.to_vec()), None))
                .chain(dels.chunks(LOTE_KVS).map(|d| (None, Some(d.to_vec()))));
            for (p, d) in lotes {
                etag = self
                    .cliente
                    .update_keys()
                    .kvs_arn(&self.arn)
                    .if_match(etag)
                    .set_puts(p)
                    .set_deletes(d)
                    .send()
                    .await
                    .map_err(|e| erro_kvs("UpdateKeys", e))?
                    .e_tag()
                    .to_owned();
            }
            Ok(())
        })
    }
}
