//! Imagens WebP do robô → S3 (BSV-13). O robô já entrega `{dir}/{id}/{id}[-small].webp`;
//! o worker copia com verificação de orçamento (MANIFEST §1, §6, §7).

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use image::{
    DynamicImage, ImageEncoder, ImageFormat, codecs::webp::WebPEncoder, imageops::FilterType,
};
use tracing::warn;

use crate::modelo::Area;
use crate::publicador::{ErroPublicador, META_IMAGEM, Meta, Publicador};

/// Orçamento da imagem pequena (MANIFEST §7): acima disso, `ajustar_small` recodifica.
pub const ORCAMENTO_SMALL: usize = 25_600;
/// Acima disso a imagem grande só gera aviso; publica do mesmo jeito (regra 3).
pub const AVISO_GRANDE: usize = 300_000;
/// Lado maior de `-small.webp` após `ajustar_small` (regra 3).
pub const LADO_SMALL: u32 = 320;
/// Piso do redimensionamento iterativo: evita loop indefinido numa imagem que não cabe.
const LADO_MINIMO: u32 = 32;

#[derive(Debug, thiserror::Error)]
pub enum ErroImagem {
    #[error("decodificando imagem de origem: {0}")]
    Decode(String),
    #[error("codificando WebP: {0}")]
    Encode(String),
}

/// Erro de `publicar_imagens`. Listagem que falha aborta o ciclo: cair para "tudo novo"
/// reenviaria ~21 mil objetos em silêncio (BSV-13b).
#[derive(Debug, thiserror::Error)]
pub enum ErroImagens {
    #[error("listando {prefixo} para decidir o reaproveitamento de imagens: {fonte}")]
    Listagem {
        prefixo: &'static str,
        fonte: ErroPublicador,
    },
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
}

/// Prefixo das imagens de oferta (CONTRATO §6).
pub const PREFIXO_OFERTAS: &str = "img/ofertas/";
/// Prefixo dos placeholders de área (CONTRATO §6).
pub const PREFIXO_PLACEHOLDER: &str = "img/placeholder/";

/// Motivo de falha ao publicar a imagem de um id (regra 2, regra 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum MotivoFalhaImagem {
    #[error("nao_webp")]
    NaoWebp,
    #[error("falha_recodificacao")]
    FalhaRecodificacao,
}

/// Contagens e amostras de uma execução de `publicar_imagens`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RelatorioImagens {
    pub publicadas: u64,
    pub reaproveitadas: u64,
    pub sem_origem: u64,
    pub reprocessadas: u64,
    pub falhas: Vec<(i64, MotivoFalhaImagem)>,
    /// Bytes efetivamente gravados nesta execução (soma das duas chaves de cada id publicado).
    pub bytes: u64,
    /// Maior `-small.webp` publicado nesta execução, em bytes (0 se nenhum).
    pub maior_small: u64,
    /// Maior `{id}.webp` publicado nesta execução, em bytes (0 se nenhum).
    pub maior_grande: u64,
    /// Chaves em `img/ofertas/` fora de `{id}.webp`/`{id}-small.webp`: ignoradas, nunca removidas.
    pub chaves_estranhas: u64,
}

/// `"img/ofertas/{id}-small.webp"` (CONTRATO §6).
pub fn chave_small(id: i64) -> String {
    format!("img/ofertas/{id}-small.webp")
}

/// `"img/ofertas/{id}.webp"` (CONTRATO §6).
pub fn chave_grande(id: i64) -> String {
    format!("img/ofertas/{id}.webp")
}

/// `({dir}/{id}/{id}-small.webp, {dir}/{id}/{id}.webp)`: caminhos que o robô já grava.
pub fn origem(dir: &Path, id: i64) -> (PathBuf, PathBuf) {
    let base = dir.join(id.to_string());
    (
        base.join(format!("{id}-small.webp")),
        base.join(format!("{id}.webp")),
    )
}

/// Contêiner RIFF/WebP: `RIFF` em 0..4, `WEBP` em 8..12 (regra 2). Não decodifica a imagem.
pub fn e_webp(bytes: &[u8]) -> bool {
    bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP"
}

// SPEC_DEVIATION: a spec do ticket pede "qualidade descendo de 80 até 40"; o encoder WebP da
// crate `image` (via `image-webp`, checado em docs.rs) só faz VP8L (sem-perdas) — não existe
// parâmetro de qualidade. Um encoder com qualidade lossy real (crate `webp`) embute libwebp via
// `libwebp-sys`, exigindo toolchain C no build, e a regra 9 só permite a dependência `image`.
// Reason: reduzir a resolução progressivamente (320 → 3/4 a cada volta, piso 32 px) e recodificar
// sem perdas cumpre o mesmo critério de aceite (≤ 25 600 B, WebP válido, lado ≤ 320 px) com uma
// única dependência pura-Rust, sem trocar o encoder por um com dependência nativa.
/// Decodifica, redimensiona o lado maior a `alvo` e recodifica sem perdas; repete reduzindo o
/// lado até caber no orçamento ou atingir `LADO_MINIMO` (regra 3).
pub fn ajustar_small(bytes: &[u8]) -> Result<Vec<u8>, ErroImagem> {
    let original = image::load_from_memory_with_format(bytes, ImageFormat::WebP)
        .map_err(|e| ErroImagem::Decode(e.to_string()))?;
    let mut alvo = LADO_SMALL;
    loop {
        let redimensionada = redimensionar(&original, alvo);
        let codificada = codificar_webp_sem_perdas(&redimensionada)?;
        if codificada.len() <= ORCAMENTO_SMALL || alvo <= LADO_MINIMO {
            return Ok(codificada);
        }
        alvo = (alvo * 3 / 4).max(LADO_MINIMO);
    }
}

/// Redimensiona só quando o lado maior excede `alvo`; nunca aumenta a imagem. `resize` já encaixa
/// a imagem numa caixa `alvo × alvo` preservando a proporção (lado maior = `alvo`).
fn redimensionar(img: &DynamicImage, alvo: u32) -> DynamicImage {
    if img.width().max(img.height()) <= alvo {
        img.clone()
    } else {
        img.resize(alvo, alvo, FilterType::Lanczos3)
    }
}

fn codificar_webp_sem_perdas(img: &DynamicImage) -> Result<Vec<u8>, ErroImagem> {
    let rgba = img.to_rgba8();
    let mut saida = Vec::new();
    WebPEncoder::new_lossless(&mut saida)
        .write_image(
            rgba.as_raw(),
            rgba.width(),
            rgba.height(),
            image::ExtendedColorType::Rgba8,
        )
        .map_err(|e| ErroImagem::Encode(e.to_string()))?;
    Ok(saida)
}

/// `"img/placeholder/{slug}.webp"` (CONTRATO §6 e §2.3: slug de URL da área, não o valor do
/// enum — BSV-20 já referencia esses caminhos).
pub fn chave_placeholder(area: Area) -> String {
    format!("img/placeholder/{}.webp", area.slug())
}

/// Os 10 placeholders versionados, embutidos no binário (regra 5): nenhuma dependência de
/// arquivo em disco em tempo de execução, e o worker nunca falha por placeholder ausente.
fn placeholders() -> [(Area, &'static [u8]); 10] {
    [
        (
            Area::Tech,
            include_bytes!("../assets/placeholder/tech.webp"),
        ),
        (
            Area::Players,
            include_bytes!("../assets/placeholder/players.webp"),
        ),
        (
            Area::MeuLar,
            include_bytes!("../assets/placeholder/meu-lar.webp"),
        ),
        (
            Area::Elas,
            include_bytes!("../assets/placeholder/elas.webp"),
        ),
        (
            Area::Eles,
            include_bytes!("../assets/placeholder/eles.webp"),
        ),
        (
            Area::Cultura,
            include_bytes!("../assets/placeholder/cultura.webp"),
        ),
        (
            Area::Familia,
            include_bytes!("../assets/placeholder/familia.webp"),
        ),
        (
            Area::Pets,
            include_bytes!("../assets/placeholder/pets.webp"),
        ),
        (
            Area::EsporteVida,
            include_bytes!("../assets/placeholder/esporte-vida.webp"),
        ),
        (
            Area::Outros,
            include_bytes!("../assets/placeholder/outros.webp"),
        ),
    ]
}

/// Publica os 10 placeholders ausentes de `existentes`; reaproveita os demais (regra 5).
/// Uma gravação `gravar_lote` (nunca 10 chamadas unitárias).
fn publicar_placeholders(
    existentes: &ImagensExistentes,
    pub_: &mut dyn Publicador,
) -> Result<(), ErroPublicador> {
    let a_gravar: Vec<(String, Vec<u8>, Meta)> = placeholders()
        .into_iter()
        .map(|(area, bytes)| (chave_placeholder(area), bytes))
        .filter(|(chave, _)| !existentes.placeholders.contains(chave))
        .map(|(chave, bytes)| (chave, bytes.to_vec(), META_IMAGEM))
        .collect();
    if !a_gravar.is_empty() {
        pub_.gravar_lote(&a_gravar)?;
    }
    Ok(())
}

/// Chaves de imagem que já estão no destino, obtidas por listagem (BSV-13b): ~22 `ListObjectsV2`
/// para 21 mil objetos no S3, em vez de um `HeadObject` por chave. Só memória; nada é persistido.
#[derive(Debug, Clone, Default)]
pub struct ImagensExistentes {
    ofertas: HashSet<String>,
    placeholders: HashSet<String>,
    estranhas: u64,
}

impl ImagensExistentes {
    /// Lista `img/ofertas/` e `img/placeholder/`, cada um uma vez. Chave de oferta com nome
    /// inesperado fica fora do conjunto e é só contada.
    pub fn listar(pub_: &dyn Publicador) -> Result<Self, ErroImagens> {
        let listar = |prefixo: &'static str| {
            pub_.listar(prefixo)
                .map_err(|fonte| ErroImagens::Listagem { prefixo, fonte })
        };
        let mut ofertas = HashSet::new();
        let mut estranhas = 0;
        for chave in listar(PREFIXO_OFERTAS)? {
            if chave_de_oferta_valida(&chave) {
                ofertas.insert(chave);
            } else {
                estranhas += 1;
            }
        }
        let placeholders = listar(PREFIXO_PLACEHOLDER)?.into_iter().collect();
        Ok(Self {
            ofertas,
            placeholders,
            estranhas,
        })
    }
}

/// `img/ofertas/{id}.webp` ou `img/ofertas/{id}-small.webp`, com `id` só de dígitos.
fn chave_de_oferta_valida(chave: &str) -> bool {
    let Some(nome) = chave
        .strip_prefix(PREFIXO_OFERTAS)
        .and_then(|n| n.strip_suffix(".webp"))
    else {
        return false;
    };
    let id = nome.strip_suffix("-small").unwrap_or(nome);
    !id.is_empty() && id.bytes().all(|b| b.is_ascii_digit())
}

/// Ids por chamada de `gravar_lote` (2 chaves por id): equilibra o tamanho do lote paralelo no S3
/// contra o custo de refazer o lote inteiro se uma tarefa falhar. Revisão do dono (BSV-13).
const TAMANHO_BLOCO: usize = 64;

/// Copia as imagens de `ids` de `dir` para o destino, em blocos de `TAMANHO_BLOCO` (regras 2, 3,
/// 4, 5), e garante os 10 placeholders de área (regra 5). Existência vem de uma listagem
/// (`ImagensExistentes::listar`), nunca de `existe`/`existem` (BSV-13b). Reaproveitamento
/// (regra 4) e ausência de origem (regra 5) nunca retornam erro; falha de assinatura WebP conta
/// em `RelatorioImagens.falhas` e não interrompe o processamento (regra 2).
pub fn publicar_imagens(
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
) -> Result<RelatorioImagens, ErroImagens> {
    let existentes = ImagensExistentes::listar(pub_)?;
    publicar_imagens_com(&existentes, ids, dir, pub_)
}

/// `publicar_imagens` com o conjunto já listado (o `gerar` mede a listagem à parte).
pub fn publicar_imagens_com(
    existentes: &ImagensExistentes,
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
) -> Result<RelatorioImagens, ErroImagens> {
    publicar_placeholders(existentes, pub_)?;
    let mut rel = RelatorioImagens {
        chaves_estranhas: existentes.estranhas,
        ..Default::default()
    };
    for bloco in ids.chunks(TAMANHO_BLOCO) {
        processar_bloco(bloco, existentes, dir, pub_, &mut rel)?;
    }
    Ok(rel)
}

/// Um bloco: no máximo 1 `gravar_lote` com tudo que precisa subir. `dir`/CPU (leitura de disco,
/// assinatura, `ajustar_small`) continuam por id, síncronos — só a rede é agrupada.
fn processar_bloco(
    ids: &[i64],
    existentes: &ImagensExistentes,
    dir: &Path,
    pub_: &mut dyn Publicador,
    rel: &mut RelatorioImagens,
) -> Result<(), ErroPublicador> {
    let mut a_gravar: Vec<(String, Vec<u8>, Meta)> = Vec::new();
    for &id in ids {
        let (chave_s, chave_g) = (chave_small(id), chave_grande(id));
        if existentes.ofertas.contains(&chave_s) && existentes.ofertas.contains(&chave_g) {
            rel.reaproveitadas += 1;
            continue;
        }
        let (origem_s, origem_g) = origem(dir, id);
        let (Ok(bytes_s), Ok(bytes_g)) = (std::fs::read(&origem_s), std::fs::read(&origem_g))
        else {
            rel.sem_origem += 1;
            continue;
        };
        if !e_webp(&bytes_s) || !e_webp(&bytes_g) {
            rel.falhas.push((id, MotivoFalhaImagem::NaoWebp));
            continue;
        }
        let bytes_s = if bytes_s.len() > ORCAMENTO_SMALL {
            rel.reprocessadas += 1;
            warn!(
                id,
                bytes = bytes_s.len(),
                "small acima do orçamento; recodificando"
            );
            match ajustar_small(&bytes_s) {
                Ok(b) => b,
                Err(e) => {
                    warn!(id, erro = %e, "falha ao recodificar small; oferta sem imagem");
                    rel.falhas.push((id, MotivoFalhaImagem::FalhaRecodificacao));
                    continue;
                }
            }
        } else {
            bytes_s
        };
        if bytes_g.len() > AVISO_GRANDE {
            warn!(
                id,
                bytes = bytes_g.len(),
                "imagem grande acima de 300 KB; publicando assim mesmo"
            );
        }
        rel.bytes += (bytes_s.len() + bytes_g.len()) as u64;
        rel.maior_small = rel.maior_small.max(bytes_s.len() as u64);
        rel.maior_grande = rel.maior_grande.max(bytes_g.len() as u64);
        rel.publicadas += 1;
        a_gravar.push((chave_s, bytes_s, META_IMAGEM));
        a_gravar.push((chave_g, bytes_g, META_IMAGEM));
    }
    if !a_gravar.is_empty() {
        pub_.gravar_lote(&a_gravar)?;
    }
    Ok(())
}
