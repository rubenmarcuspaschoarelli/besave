//! Fonte → chunks + manifest publicados (MANIFEST §2, §3, §6).

use std::cell::Cell;
use std::collections::{BTreeMap, HashSet};
use std::path::Path;
use std::time::{Duration, Instant};

use tracing::{debug, info, warn};

use crate::chunks::{ErroChunk, chave_chunk, comprimir_br, particionar, serializar_chunk};
use crate::conversao::{LinhaOferta, Rejeicao, iso_utc, para_card, para_pagina};
use crate::fonte::{ErroFonte, FonteOfertas};
use crate::imagens::{self, ErroImagens, ImagensExistentes, RelatorioImagens};
use crate::mapeamento::Mapeamento;
use crate::modelo::{ChunkRef, Manifest, OfertaCard};
use crate::publicador::{ErroPublicador, META_CHUNK, META_MANIFEST, Publicador};
use crate::redirects::{
    self, ErroRedirects, EstadoKvs, Redirects, RelatorioRedirects, carregar_base,
    sincronizar_com_indice,
};
use crate::site::{ConfigSite, ErroSite, RelatorioSite, publicar_site};

/// Orçamento de chunk comprimido (MANIFEST §7, `bytes.maximum` do schema).
pub const ORCAMENTO_CHUNK: u64 = 61_440;
pub const CHAVE_MANIFEST: &str = "manifest.json";
/// Cópia do manifest da execução anterior (regra de órfãos: 2 últimos manifests).
pub const CHAVE_MANIFEST_ANTERIOR: &str = "manifest.prev.json";
pub const PREFIXO_CHUNKS: &str = "data/chunks/";

const PACKAGE_CONTRATO: &str = include_str!("../../../packages/contract/package.json");

#[derive(Debug, thiserror::Error)]
pub enum ErroGeracao {
    #[error(transparent)]
    Fonte(#[from] ErroFonte),
    #[error(transparent)]
    Chunk(#[from] ErroChunk),
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error(transparent)]
    Imagens(#[from] ErroImagens),
    #[error(transparent)]
    Redirects(#[from] ErroRedirects),
    #[error(transparent)]
    Site(#[from] ErroSite),
    #[error("chunk {n} tem {bytes} bytes comprimido; orçamento é {ORCAMENTO_CHUNK}")]
    ChunkAcimaDoOrcamento { n: u64, bytes: u64 },
    #[error("manifest.json anterior inválido: {0}")]
    ManifestAnteriorInvalido(serde_json::Error),
    #[error("serializando manifest: {0}")]
    Manifest(serde_json::Error),
    #[error("versão ilegível em packages/contract/package.json")]
    VersaoContrato,
}

pub type Result<T, E = ErroGeracao> = std::result::Result<T, E>;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Relatorio {
    pub lidas: u64,
    pub validas: u64,
    pub rejeitadas: BTreeMap<Rejeicao, u64>,
    pub chunks_escritos: u64,
    pub chunks_reaproveitados: u64,
    pub chunks_removidos: u64,
    /// Soma dos `bytes` (comprimidos) dos chunks do manifest.
    pub bytes_totais: u64,
    /// `(n, bytes)` do maior chunk comprimido.
    pub maior_chunk: Option<(u64, u64)>,
    pub versao: u64,
    /// Maior `dt` entre os cards publicados (ativos ou expirados); `None` se o conjunto é vazio.
    pub dt_mais_recente: Option<i64>,
    pub redirects: RelatorioRedirects,
    pub imagens: RelatorioImagens,
    /// CSS, páginas, sitemaps, robots e índice `_estado/` (BSV-21).
    pub site: RelatorioSite,
    pub tempos: Tempos,
    /// Ids do conjunto publicado (cards válidos, ativos e expirados).
    pub ids_publicados: Vec<i64>,
    /// Linhas com `DT_PUBLICACAO_SITE` gravada neste ciclo (BSV-40; fora de `gerar`).
    pub publicacao_site_marcadas: u64,
    /// Lotes do `UPDATE` de `DT_PUBLICACAO_SITE` que falharam.
    pub publicacao_site_falhas: u64,
}

/// Tempo de cada fase de `gerar()`, em ms (BSV-13b). `*_listagem` é parte da fase acima dela.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Tempos {
    /// Ofertas, conversão, produtos em lote e páginas em memória.
    pub leitura_fonte: u64,
    pub imagens: u64,
    pub imagens_listagem: u64,
    pub chunks: u64,
    /// CSS, páginas, sitemaps, robots e índice (`publicar_site`).
    pub paginas: u64,
    /// `carregar_base` (índice ou listagem da KVS) + `sincronizar_com_indice`.
    pub redirects: u64,
    /// Soma de todos os `Redirects::listar` do ciclo.
    pub redirects_listagem: u64,
    /// Leitura do manifest anterior + gravação de `manifest.prev.json` e `manifest.json`.
    pub manifest: u64,
    /// Chunks órfãos + expurgo de imagens.
    pub orfaos: u64,
}

fn ms(d: Duration) -> u64 {
    u64::try_from(d.as_millis()).unwrap_or(u64::MAX)
}

/// Repassa tudo a `dentro` e soma o tempo gasto em `listar` (`Tempos::redirects_listagem`).
struct ListagemCronometrada<'a> {
    dentro: &'a mut dyn Redirects,
    gasto: Cell<Duration>,
}

impl Redirects for ListagemCronometrada<'_> {
    fn listar(&self) -> redirects::Result<BTreeMap<i64, String>> {
        let inicio = Instant::now();
        let r = self.dentro.listar();
        self.gasto.set(self.gasto.get() + inicio.elapsed());
        r
    }

    fn descrever(&self) -> redirects::Result<EstadoKvs> {
        self.dentro.descrever()
    }

    fn aplicar(
        &mut self,
        etag: &str,
        put: &[(i64, String)],
        del: &[i64],
    ) -> redirects::Result<EstadoKvs> {
        self.dentro.aplicar(etag, put, del)
    }
}

/// `version` de `packages/contract/package.json`, embutido no build.
pub fn versao_contrato() -> Result<String> {
    let v: serde_json::Value =
        serde_json::from_str(PACKAGE_CONTRATO).map_err(|_| ErroGeracao::VersaoContrato)?;
    v["version"]
        .as_str()
        .map(str::to_owned)
        .ok_or(ErroGeracao::VersaoContrato)
}

/// Lê a fonte (ofertas e, em lote, os produtos), publica as imagens (MANIFEST §6 passo 1), grava
/// os chunks novos, publica CSS, páginas, sitemaps, robots e o índice `_estado/` (passo 3),
/// sincroniza a KVS de redirects e, por último, o manifest; depois remove os chunks que não estão nem no manifest
/// novo nem no anterior e as imagens de ids que saíram do conjunto publicado (CONTRATO §7). Falha
/// na KVS mantém o manifest antigo (MANIFEST §6). `agora` em segundos Unix UTC.
pub fn gerar(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    pub_: &mut dyn Publicador,
    redirects: &mut dyn Redirects,
    dir_imagens: &Path,
    site: &ConfigSite,
    agora: i64,
) -> Result<Relatorio> {
    let mut redirects = ListagemCronometrada {
        dentro: redirects,
        gasto: Cell::new(Duration::ZERO),
    };
    let contrato = versao_contrato()?;
    let gerado_em = iso_utc(agora);
    let versao = versao_de(&gerado_em);
    let t = Instant::now();
    let anterior_bytes = pub_.ler(CHAVE_MANIFEST)?;
    let anterior: Option<Manifest> = anterior_bytes
        .as_deref()
        .map(serde_json::from_slice)
        .transpose()
        .map_err(ErroGeracao::ManifestAnteriorInvalido)?;
    let mut d_manifest = t.elapsed();
    // Conjunto publicado no ciclo anterior (a KVS espelha exatamente isso, decisão de BSV-12):
    // referência para saber quais imagens expurgar quando um id sai do conjunto. Vem do índice
    // `_estado/redirects.json` quando confiável; só a reconstrução lista a KVS (BSV-12c).
    let t = Instant::now();
    let base_redirects = carregar_base(&redirects, &*pub_)?;
    let ids_anteriores: HashSet<i64> = base_redirects.urls.keys().copied().collect();
    let mut d_redirects = t.elapsed();

    let t = Instant::now();
    let linhas = fonte.ofertas()?;
    let mut rel = Relatorio {
        lidas: linhas.len() as u64,
        versao,
        ..Default::default()
    };
    let mut cards = Vec::with_capacity(linhas.len());
    let mut urls = Vec::with_capacity(linhas.len());
    let mut validas: Vec<&LinhaOferta> = Vec::with_capacity(linhas.len());
    for l in &linhas {
        match publicavel(l, m) {
            Ok(c) => {
                urls.push((c.id, l.url_afiliado.trim().to_owned()));
                cards.push(c);
                validas.push(l);
            }
            Err(r) => {
                warn!(id = l.id, motivo = %r, "oferta rejeitada");
                *rel.rejeitadas.entry(r).or_default() += 1;
            }
        }
    }
    rel.validas = cards.len() as u64;
    rel.ids_publicados = cards.iter().map(|c| c.id).collect();
    rel.dt_mais_recente = validas.iter().filter_map(|l| l.dt_oferta).max();

    // Produtos em lote, antes de qualquer escrita (sem N+1 no Oracle). `para_pagina` valida o
    // mesmo que `publicavel`, então toda linha válida vira página.
    let ids_produto: Vec<i64> = validas.iter().filter_map(|l| l.id_produto).collect();
    let produtos = fonte.produtos(&ids_produto)?;
    let paginas: Vec<_> = validas
        .iter()
        .filter_map(|l| {
            let p = l.id_produto.and_then(|id| produtos.get(&id));
            para_pagina(l, p, m)
                .inspect_err(|r| warn!(id = l.id, motivo = %r, "card sem página"))
                .ok()
        })
        .collect();
    let d_leitura_fonte = t.elapsed();

    // MANIFEST §6 passo 1: imagens antes de qualquer chunk.
    let t = Instant::now();
    let ids_publicaveis: Vec<i64> = cards.iter().map(|c| c.id).collect();
    let existentes = ImagensExistentes::listar(pub_)?;
    let d_imagens_listagem = t.elapsed();
    rel.imagens = imagens::publicar_imagens_com(&existentes, &ids_publicaveis, dir_imagens, pub_)?;
    let d_imagens = t.elapsed();

    let t = Instant::now();

    let mut areas = BTreeMap::new();
    for c in cards.iter().filter(|c| c.x.is_none()) {
        *areas.entry(c.area).or_default() += 1;
    }

    // Tudo serializado e medido antes da primeira gravação: estouro de orçamento não publica nada.
    let mut prontos = Vec::new();
    for (n, cs) in particionar(cards) {
        let (Some(primeiro), Some(ultimo)) = (cs.first(), cs.last()) else {
            continue;
        };
        let (json, hash) = serializar_chunk(&cs)?;
        let br = comprimir_br(&json)?;
        let bytes = br.len() as u64;
        checar_orcamento(n, bytes)?;
        let r = ChunkRef {
            n,
            arquivo: chave_chunk(n, &hash),
            ids: [primeiro.id, ultimo.id],
            qtd: cs.len() as u64,
            bytes,
        };
        prontos.push((r, br));
    }

    for (r, br) in &prontos {
        if pub_.existe(&r.arquivo)? {
            rel.chunks_reaproveitados += 1;
            debug!(n = r.n, arquivo = %r.arquivo, "chunk reaproveitado");
        } else {
            pub_.gravar(&r.arquivo, br, &META_CHUNK)?;
            rel.chunks_escritos += 1;
            debug!(n = r.n, arquivo = %r.arquivo, qtd = r.qtd, bytes = r.bytes, "chunk gravado");
        }
    }
    let chunks: Vec<ChunkRef> = prontos.into_iter().map(|(r, _)| r).collect();
    rel.bytes_totais = chunks.iter().map(|r| r.bytes).sum();
    rel.maior_chunk = chunks
        .iter()
        .max_by_key(|r| r.bytes)
        .map(|r| (r.n, r.bytes));
    let d_chunks = t.elapsed();

    // MANIFEST §6 passo 3: CSS, páginas, sitemaps, robots e índice, antes da KVS e do manifest.
    let t = Instant::now();
    rel.site = publicar_site(&paginas, site, pub_)?;
    let d_paginas = t.elapsed();

    let t = Instant::now();
    rel.redirects = sincronizar_com_indice(&urls, base_redirects, &mut redirects, pub_)?;
    d_redirects += t.elapsed();

    let t = Instant::now();

    let manifest = Manifest {
        contrato,
        versao,
        gerado_em,
        total_ofertas: rel.validas,
        chunks,
        busca: None,
        areas,
    };
    let json = serde_json::to_vec(&manifest).map_err(ErroGeracao::Manifest)?;
    if let Some(b) = &anterior_bytes {
        pub_.gravar(CHAVE_MANIFEST_ANTERIOR, b, &META_MANIFEST)?;
    }
    pub_.gravar(CHAVE_MANIFEST, &json, &META_MANIFEST)?;
    d_manifest += t.elapsed();

    let t = Instant::now();

    let vivos: HashSet<&str> = manifest
        .chunks
        .iter()
        .chain(anterior.iter().flat_map(|a| &a.chunks))
        .map(|r| r.arquivo.as_str())
        .collect();
    for chave in pub_.listar(PREFIXO_CHUNKS)? {
        if !vivos.contains(chave.as_str()) {
            pub_.remover(&chave)?;
            rel.chunks_removidos += 1;
            debug!(arquivo = %chave, "chunk órfão removido");
        }
    }

    // Expurgo de imagens (CONTRATO §7): id publicado no ciclo anterior e ausente neste.
    let ids_publicaveis: HashSet<i64> = ids_publicaveis.into_iter().collect();
    for id in ids_anteriores.difference(&ids_publicaveis) {
        pub_.remover(&imagens::chave_small(*id))?;
        pub_.remover(&imagens::chave_grande(*id))?;
        debug!(id, "imagens expurgadas");
    }
    rel.tempos = Tempos {
        leitura_fonte: ms(d_leitura_fonte),
        imagens: ms(d_imagens),
        imagens_listagem: ms(d_imagens_listagem),
        chunks: ms(d_chunks),
        paginas: ms(d_paginas),
        redirects: ms(d_redirects),
        redirects_listagem: ms(redirects.gasto.get()),
        manifest: ms(d_manifest),
        orfaos: ms(t.elapsed()),
    };

    info!(
        lidas = rel.lidas,
        validas = rel.validas,
        rejeitadas = rel.rejeitadas.values().sum::<u64>(),
        chunks = manifest.chunks.len(),
        escritos = rel.chunks_escritos,
        reaproveitados = rel.chunks_reaproveitados,
        removidos = rel.chunks_removidos,
        bytes = rel.bytes_totais,
        redirects_put = rel.redirects.puts,
        redirects_del = rel.redirects.dels,
        paginas_publicadas = rel.site.paginas.publicadas,
        paginas_removidas = rel.site.paginas.removidas,
        versao,
        "manifest publicado"
    );
    Ok(rel)
}

/// `--dry-run`: converte cada linha em página com os produtos carregados em lote, sem escrever
/// nada. Devolve `(lidas, válidas, rejeitadas por motivo)`; rejeições são logadas com o id.
pub fn contar_paginas(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
) -> Result<(u64, u64, BTreeMap<Rejeicao, u64>)> {
    contar_paginas_dt(fonte, m).map(|(lidas, validas, rej, _)| (lidas, validas, rej))
}

/// `(lidas, válidas, rejeitadas por motivo, maior dt entre as válidas)`.
pub type ContagemDt = (u64, u64, BTreeMap<Rejeicao, u64>, Option<i64>);

/// Como `contar_paginas`, com o maior `dt` entre as linhas válidas (`None` se não há nenhuma).
pub fn contar_paginas_dt(fonte: &dyn FonteOfertas, m: &Mapeamento) -> Result<ContagemDt> {
    let linhas = fonte.ofertas()?;
    let ids: Vec<i64> = linhas.iter().filter_map(|l| l.id_produto).collect();
    let produtos = fonte.produtos(&ids)?;
    let mut validas = 0;
    let mut rejeitadas = BTreeMap::new();
    let mut dt_max: Option<i64> = None;
    for l in &linhas {
        let p = l.id_produto.and_then(|id| produtos.get(&id));
        match para_pagina(l, p, m) {
            Ok(_) => {
                validas += 1;
                dt_max = dt_max.max(l.dt_oferta);
            }
            Err(r) => {
                warn!(id = l.id, motivo = %r, "oferta rejeitada");
                *rejeitadas.entry(r).or_default() += 1;
            }
        }
    }
    Ok((linhas.len() as u64, validas, rejeitadas, dt_max))
}

/// Chunk comprimido de até `ORCAMENTO_CHUNK` bytes passa; acima disso, erro.
pub fn checar_orcamento(n: u64, bytes: u64) -> Result<()> {
    if bytes > ORCAMENTO_CHUNK {
        return Err(ErroGeracao::ChunkAcimaDoOrcamento { n, bytes });
    }
    Ok(())
}

/// Card publicável: válido (inclui URL de afiliado) e com página possível (`id_produto`), as
/// mesmas regras do `--dry-run`.
fn publicavel(l: &LinhaOferta, m: &Mapeamento) -> Result<OfertaCard, Rejeicao> {
    let card = para_card(l, m)?;
    if l.id_produto.is_none_or(|id| id < 1) {
        return Err(Rejeicao::IdProdutoAusente);
    }
    Ok(card)
}

/// `2026-09-24T13:05:00Z` → `20260924130500`.
fn versao_de(iso: &str) -> u64 {
    iso.bytes()
        .filter(u8::is_ascii_digit)
        .fold(0, |v, d| v * 10 + u64::from(d - b'0'))
}
