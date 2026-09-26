//! Adaptadores AWS: `PublicadorS3` (bucket) e `RedirectsKvs` (CloudFront KeyValueStore).
//! Credenciais e região só pela cadeia padrão do SDK; retentativas são as do SDK.
//! `gerar()` é síncrono: cada método faz `block_on` num runtime `current_thread` compartilhado.

use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Arc;

use aws_config::SdkConfig;
use aws_sdk_cloudfrontkeyvaluestore::types::{DeleteKeyRequestListItem, PutKeyRequestListItem};
use aws_sdk_s3::error::DisplayErrorContext;
use aws_sdk_s3::primitives::ByteStream;
use tokio::runtime::Runtime;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tracing::warn;

use crate::imagens::{self, RelatorioImagens};
use crate::publicador::{self, ErroPublicador, META_IMAGEM, Meta, Publicador};
use crate::redirects::{self, ErroRedirects, Redirects, id_da_chave, lotes_kvs};

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

/// Pares `HeadObject`/`PutObject` em voo simultaneamente (regra 8): o gargalo de ~50 mil objetos
/// na primeira carga é rede, não CPU.
const MAX_EM_VOO: usize = 16;

/// Resultado de uma imagem processada pelo pool paralelo (espelha os ramos de
/// `imagens::publicar_imagens`, mas sem `&mut dyn Publicador` — cada tarefa fala com o S3 direto).
enum ResultadoImagem {
    Publicada {
        bytes_small: usize,
        bytes_grande: usize,
    },
    Reaproveitada,
    SemOrigem,
    Falha(imagens::MotivoFalhaImagem),
}

impl PublicadorS3 {
    /// Publica as imagens de `ids` com até `MAX_EM_VOO` pares `HeadObject`/`PutObject` em voo
    /// (regra 8), mesma política de `imagens::publicar_imagens` (regras 2-5). Os 10 placeholders
    /// são publicados antes, sequencialmente (10 objetos: paralelismo não compensa).
    ///
    /// `PublicadorLocal` e `PublicadorMemoria` continuam sequenciais via
    /// `imagens::publicar_imagens` — o pool é específico do S3 porque só ali HeadObject/PutObject
    /// são round-trips de rede caros o bastante para valer a pena sobrepor.
    pub fn publicar_imagens_paralelo(
        &mut self,
        ids: &[i64],
        dir: &Path,
    ) -> publicador::Result<RelatorioImagens> {
        imagens::publicar_placeholders(self)?;
        let rt = self.rt.clone();
        let cliente = self.cliente.clone();
        let bucket = self.bucket.clone();
        let dir = dir.to_path_buf();
        let ids = ids.to_vec();
        rt.block_on(async move {
            let semaforo = Arc::new(Semaphore::new(MAX_EM_VOO));
            let mut tarefas = JoinSet::new();
            for id in ids {
                let permissao = Arc::clone(&semaforo).acquire_owned().await.map_err(|e| {
                    ErroPublicador::Aws {
                        operacao: "semáforo do pool de imagens",
                        chave: String::new(),
                        fonte: texto_erro(e),
                    }
                })?;
                let cliente = cliente.clone();
                let bucket = bucket.clone();
                let dir = dir.clone();
                tarefas.spawn(async move {
                    let _permissao = permissao;
                    let resultado = publicar_imagem_paralela(&cliente, &bucket, &dir, id).await;
                    (id, resultado)
                });
            }
            let mut rel = RelatorioImagens::default();
            while let Some(saida) = tarefas.join_next().await {
                // `JoinError` só ocorre em pânico da tarefa; o `id` já se perdeu nesse caso.
                let (id, resultado) = saida.map_err(|e| ErroPublicador::Aws {
                    operacao: "tarefa de imagem em paralelo",
                    chave: "<tarefa perdida>".to_owned(),
                    fonte: texto_erro(e),
                })?;
                match resultado? {
                    ResultadoImagem::Publicada {
                        bytes_small,
                        bytes_grande,
                    } => {
                        rel.publicadas += 1;
                        rel.bytes += (bytes_small + bytes_grande) as u64;
                        rel.maior_small = rel.maior_small.max(bytes_small as u64);
                        rel.maior_grande = rel.maior_grande.max(bytes_grande as u64);
                    }
                    ResultadoImagem::Reaproveitada => rel.reaproveitadas += 1,
                    ResultadoImagem::SemOrigem => rel.sem_origem += 1,
                    ResultadoImagem::Falha(motivo) => rel.falhas.push((id, motivo)),
                }
            }
            Ok(rel)
        })
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
) -> publicador::Result<()> {
    cliente
        .put_object()
        .bucket(bucket)
        .key(chave)
        .body(ByteStream::from(bytes))
        .content_type(META_IMAGEM.content_type)
        .cache_control(META_IMAGEM.cache_control)
        .send()
        .await
        .map(|_| ())
        .map_err(|e| erro_s3("PutObject", chave, e))
}

/// Corpo de uma imagem dentro do pool: mesmas regras 2-5 de `imagens::publicar_imagens`, só que
/// fala com o S3 direto (sem `&mut dyn Publicador`, para poder rodar concorrente).
async fn publicar_imagem_paralela(
    cliente: &aws_sdk_s3::Client,
    bucket: &str,
    dir: &Path,
    id: i64,
) -> publicador::Result<ResultadoImagem> {
    let chave_small = imagens::chave_small(id);
    let chave_grande = imagens::chave_grande(id);
    if existe_async(cliente, bucket, &chave_small).await?
        && existe_async(cliente, bucket, &chave_grande).await?
    {
        return Ok(ResultadoImagem::Reaproveitada);
    }
    let (origem_small, origem_grande) = imagens::origem(dir, id);
    let (Ok(bytes_small), Ok(bytes_grande)) =
        (std::fs::read(&origem_small), std::fs::read(&origem_grande))
    else {
        return Ok(ResultadoImagem::SemOrigem);
    };
    if !imagens::e_webp(&bytes_small) || !imagens::e_webp(&bytes_grande) {
        return Ok(ResultadoImagem::Falha(imagens::MotivoFalhaImagem::NaoWebp));
    }
    let bytes_small = if bytes_small.len() > imagens::ORCAMENTO_SMALL {
        match imagens::ajustar_small(&bytes_small) {
            Ok(b) => b,
            Err(_) => {
                return Ok(ResultadoImagem::Falha(
                    imagens::MotivoFalhaImagem::FalhaRecodificacao,
                ));
            }
        }
    } else {
        bytes_small
    };
    let (tamanho_small, tamanho_grande) = (bytes_small.len(), bytes_grande.len());
    gravar_async(cliente, bucket, &chave_small, bytes_small).await?;
    gravar_async(cliente, bucket, &chave_grande, bytes_grande).await?;
    Ok(ResultadoImagem::Publicada {
        bytes_small: tamanho_small,
        bytes_grande: tamanho_grande,
    })
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

    /// Um `UpdateKeys` por lote de `lotes_kvs` (puts e deletes juntos), encadeando o `ETag`
    /// a partir de `DescribeKeyValueStore`.
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> redirects::Result<()> {
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
            for (puts, dels) in chamadas {
                etag = self
                    .cliente
                    .update_keys()
                    .kvs_arn(&self.arn)
                    .if_match(etag)
                    .set_puts(puts)
                    .set_deletes(dels)
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
