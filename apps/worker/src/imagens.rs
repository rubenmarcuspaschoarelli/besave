//! Imagens WebP do robô → S3 (BSV-13). O robô já entrega `{dir}/{id}/{id}[-small].webp`;
//! o worker copia com verificação de orçamento (MANIFEST §1, §6, §7).

use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::path::{Path, PathBuf};

use image::{
    DynamicImage, ImageEncoder, ImageFormat, codecs::webp::WebPEncoder, imageops::FilterType,
};
use tracing::warn;

use crate::modelo::Area;
use crate::paginas::hash16;
use crate::publicador::{ErroPublicador, META_ESTADO, META_IMAGEM, Meta, Publicador};

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
    #[error(transparent)]
    Indice(#[from] ErroIndice),
}

/// Erro ao ler ou gravar `_estado/imagens.json`.
#[derive(Debug, thiserror::Error)]
pub enum ErroIndice {
    #[error(transparent)]
    Publicador(#[from] ErroPublicador),
    #[error("serializando {CHAVE_INDICE}: {0}")]
    Serializacao(serde_json::Error),
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
    /// Subconjunto de `publicadas`: o id já estava no índice com outro hash (imagem trocada).
    pub reenviadas: u64,
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

/// Bytes WebP do placeholder versionado da área (embutido no binário).
pub fn placeholder(area: Area) -> &'static [u8] {
    placeholders()
        .into_iter()
        .find(|(a, _)| *a == area)
        .map_or(&[], |(_, b)| b)
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

/// Índice do que já está no bucket (MANIFEST §1): id → hash16 da origem. Também guarda quando
/// `img/ofertas/` foi listada pela última vez (`_relistado_em`), para a reconciliação periódica.
pub const CHAVE_INDICE: &str = "_estado/imagens.json";
/// Chave reservada do índice: segundos Unix UTC da última listagem de `img/ofertas/`.
const CHAVE_RELISTADO: &str = "_relistado_em";
/// Padrão de `BESAVE_IMAGENS_RELISTAR_HORAS`.
pub const RELISTAR_HORAS_PADRAO: u64 = 24;

#[derive(Debug, thiserror::Error)]
#[error("{var} inválida: {motivo}")]
pub struct ErroConfigImagens {
    pub var: &'static str,
    pub motivo: String,
}

/// `BESAVE_IMAGENS_RELISTAR` e `BESAVE_IMAGENS_RELISTAR_HORAS` (BSV-45).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConfigImagens {
    /// Lista `img/ofertas/` neste ciclo, com o índice em ordem.
    pub relistar: bool,
    /// Intervalo entre listagens de reconciliação; `0` lista todo ciclo.
    pub relistar_horas: u64,
}

impl Default for ConfigImagens {
    fn default() -> Self {
        Self {
            relistar: false,
            relistar_horas: RELISTAR_HORAS_PADRAO,
        }
    }
}

impl ConfigImagens {
    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self, ErroConfigImagens> {
        let ler = |k: &str| {
            env(k)
                .map(|v| v.trim().to_owned())
                .filter(|v| !v.is_empty())
        };
        let relistar = match ler("BESAVE_IMAGENS_RELISTAR").as_deref() {
            None | Some("0" | "false") => false,
            Some("1" | "true") => true,
            Some(outro) => {
                return Err(ErroConfigImagens {
                    var: "BESAVE_IMAGENS_RELISTAR",
                    motivo: format!("{outro:?}, esperado 0 ou 1"),
                });
            }
        };
        let relistar_horas = match ler("BESAVE_IMAGENS_RELISTAR_HORAS") {
            None => RELISTAR_HORAS_PADRAO,
            Some(v) => v.parse::<u64>().map_err(|_| ErroConfigImagens {
                var: "BESAVE_IMAGENS_RELISTAR_HORAS",
                motivo: format!("{v:?}, esperado inteiro ≥ 0"),
            })?,
        };
        Ok(Self {
            relistar,
            relistar_horas,
        })
    }
}

/// `_estado/imagens.json`: objeto plano `id → hash16`, mais `_relistado_em`. Lido uma vez por
/// ciclo e regravado só quando muda (AD-041).
#[derive(Debug, Clone, Default)]
pub struct IndiceImagens {
    hashes: BTreeMap<i64, String>,
    relistado_em: Option<i64>,
    /// Ausente, ilegível ou fora do formato: o ciclo reconstrói listando `img/ofertas/`.
    confiavel: bool,
    /// Bytes lidos do bucket; o índice só é regravado se diferir.
    lido: Option<Vec<u8>>,
}

fn hash_valido(h: &str) -> bool {
    h.len() == 16 && h.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

impl IndiceImagens {
    /// Índice ausente, JSON inválido ou valor fora do formato = índice vazio e não confiável
    /// (WARN no caso inválido). Erro de leitura do bucket propaga.
    pub fn carregar(pub_: &dyn Publicador) -> Result<Self, ErroIndice> {
        let lido = pub_.ler(CHAVE_INDICE)?;
        let Some(bytes) = lido.as_deref() else {
            return Ok(Self::default());
        };
        let Some(mut indice) = Self::de_json(bytes) else {
            warn!("{CHAVE_INDICE} ilegível ou fora do formato; reconstruindo pela listagem");
            return Ok(Self::default());
        };
        indice.lido = lido;
        Ok(indice)
    }

    fn de_json(bytes: &[u8]) -> Option<Self> {
        let mapa: BTreeMap<String, String> = serde_json::from_slice(bytes).ok()?;
        let mut indice = Self {
            confiavel: true,
            ..Self::default()
        };
        for (k, v) in mapa {
            if k == CHAVE_RELISTADO {
                indice.relistado_em = Some(v.parse().ok()?);
            } else if k.starts_with('_') {
                continue;
            } else if hash_valido(&v) {
                indice.hashes.insert(k.parse().ok()?, v);
            } else {
                return None;
            }
        }
        Some(indice)
    }

    pub fn len(&self) -> usize {
        self.hashes.len()
    }

    pub fn is_empty(&self) -> bool {
        self.hashes.is_empty()
    }

    pub fn contem(&self, id: i64) -> bool {
        self.hashes.contains_key(&id)
    }

    fn hash(&self, id: i64) -> Option<&str> {
        self.hashes.get(&id).map(String::as_str)
    }

    /// O ciclo precisa listar `img/ofertas/`: índice não confiável, `BESAVE_IMAGENS_RELISTAR`,
    /// reconciliação do expurgo por fazer (`fila_reconciliada` falso) ou intervalo vencido.
    pub fn deve_listar(&self, cfg: &ConfigImagens, fila_reconciliada: bool, agora: i64) -> bool {
        if !self.confiavel || cfg.relistar || !fila_reconciliada {
            return true;
        }
        let limite = i64::try_from(cfg.relistar_horas.saturating_mul(3600)).unwrap_or(i64::MAX);
        self.relistado_em
            .is_none_or(|t| agora.saturating_sub(t) >= limite)
    }

    fn definir(&mut self, id: i64, hash: String) {
        self.hashes.insert(id, hash);
    }

    /// Tira do índice os ids cujas imagens o expurgo apagou (BSV-47).
    pub fn remover(&mut self, ids: &[i64]) {
        for id in ids {
            self.hashes.remove(id);
        }
    }

    /// Grava o índice se mudou. Devolve se gravou.
    pub fn salvar(&mut self, pub_: &mut dyn Publicador) -> Result<bool, ErroIndice> {
        let mut mapa: BTreeMap<String, String> = self
            .hashes
            .iter()
            .map(|(id, h)| (id.to_string(), h.clone()))
            .collect();
        if let Some(t) = self.relistado_em {
            mapa.insert(CHAVE_RELISTADO.to_owned(), t.to_string());
        }
        let json = serde_json::to_vec(&mapa).map_err(ErroIndice::Serializacao)?;
        if self.lido.as_deref() == Some(json.as_slice()) {
            return Ok(false);
        }
        pub_.gravar(CHAVE_INDICE, &json, &META_ESTADO)?;
        self.lido = Some(json);
        self.confiavel = true;
        Ok(true)
    }
}

/// Chaves de imagem que já estão no destino. `img/placeholder/` é listado todo ciclo (10 chaves);
/// `img/ofertas/` só quando o índice não basta (BSV-45, AD-044). Só memória; nada é persistido.
#[derive(Debug, Clone, Default)]
pub struct ImagensExistentes {
    /// `None` = não listou neste ciclo.
    ofertas: Option<HashSet<String>>,
    placeholders: HashSet<String>,
    estranhas: u64,
}

impl ImagensExistentes {
    /// Lista `img/placeholder/` e, com `ofertas`, `img/ofertas/` (uma vez cada). Chave de oferta
    /// com nome inesperado fica fora do conjunto e é só contada.
    pub fn listar(pub_: &dyn Publicador, ofertas: bool) -> Result<Self, ErroImagens> {
        let listar = |prefixo: &'static str| {
            pub_.listar(prefixo)
                .map_err(|fonte| ErroImagens::Listagem { prefixo, fonte })
        };
        let mut existentes = Self::default();
        if ofertas {
            let mut conjunto = HashSet::new();
            for chave in listar(PREFIXO_OFERTAS)? {
                if chave_de_oferta_valida(&chave) {
                    conjunto.insert(chave);
                } else {
                    existentes.estranhas += 1;
                }
            }
            existentes.ofertas = Some(conjunto);
        }
        existentes.placeholders = listar(PREFIXO_PLACEHOLDER)?.into_iter().collect();
        Ok(existentes)
    }

    /// Ids que têm ao menos uma imagem em `img/ofertas/` (reconciliação do expurgo, BSV-47).
    /// Vazio se `img/ofertas/` não foi listada.
    pub fn ids_de_oferta(&self) -> BTreeSet<i64> {
        self.ofertas
            .iter()
            .flatten()
            .filter_map(|c| {
                let nome = c.strip_prefix(PREFIXO_OFERTAS)?.strip_suffix(".webp")?;
                nome.strip_suffix("-small").unwrap_or(nome).parse().ok()
            })
            .collect()
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

/// Copia as imagens de `ids` de `dir` para o destino quando o hash da origem difere do índice
/// (BSV-45) e garante os 10 placeholders de área. Lê o índice, lista `img/ofertas/` só se
/// `IndiceImagens::deve_listar` (fila já reconciliada) e regrava o índice no fim.
pub fn publicar_imagens(
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
    cfg: &ConfigImagens,
    agora: i64,
) -> Result<RelatorioImagens, ErroImagens> {
    let mut indice = IndiceImagens::carregar(pub_)?;
    let existentes = ImagensExistentes::listar(pub_, indice.deve_listar(cfg, true, agora))?;
    publicar_imagens_com(&existentes, &mut indice, ids, dir, pub_, agora)
}

/// `publicar_imagens` com índice e listagem já feitos (o `gerar` mede a listagem à parte e usa o
/// índice de novo no expurgo). O índice é gravado depois dos uploads; um bloco que falha fica
/// fora dele, os anteriores entram (regra 2).
pub fn publicar_imagens_com(
    existentes: &ImagensExistentes,
    indice: &mut IndiceImagens,
    ids: &[i64],
    dir: &Path,
    pub_: &mut dyn Publicador,
    agora: i64,
) -> Result<RelatorioImagens, ErroImagens> {
    publicar_placeholders(existentes, pub_)?;
    let mut rel = RelatorioImagens {
        chaves_estranhas: existentes.estranhas,
        ..Default::default()
    };
    for bloco in ids.chunks(TAMANHO_BLOCO) {
        if let Err(e) = processar_bloco(bloco, existentes, indice, dir, pub_, &mut rel) {
            if let Err(e2) = indice.salvar(pub_) {
                warn!(erro = %e2, "não gravou {CHAVE_INDICE} depois da falha de envio");
            }
            return Err(e.into());
        }
    }
    if existentes.ofertas.is_some() {
        indice.relistado_em = Some(agora);
    }
    indice.salvar(pub_)?;
    Ok(rel)
}

/// Um bloco: no máximo 1 `gravar_lote` com tudo que precisa subir. `dir`/CPU (leitura de disco,
/// hash, assinatura, `ajustar_small`) continuam por id, síncronos — só a rede é agrupada.
fn processar_bloco(
    ids: &[i64],
    existentes: &ImagensExistentes,
    indice: &mut IndiceImagens,
    dir: &Path,
    pub_: &mut dyn Publicador,
    rel: &mut RelatorioImagens,
) -> Result<(), ErroPublicador> {
    let mut a_gravar: Vec<(String, Vec<u8>, Meta)> = Vec::new();
    let mut enviados: Vec<(i64, String)> = Vec::new();
    for &id in ids {
        let (chave_s, chave_g) = (chave_small(id), chave_grande(id));
        let (origem_s, origem_g) = origem(dir, id);
        let (Ok(bytes_s), Ok(bytes_g)) = (std::fs::read(&origem_s), std::fs::read(&origem_g))
        else {
            rel.sem_origem += 1;
            continue;
        };
        let hash = hash16(&[bytes_g.as_slice(), bytes_s.as_slice()].concat());
        let anterior = indice.hash(id);
        // `Some` só quando listou: o par inteiro está no bucket?
        let no_bucket = existentes
            .ofertas
            .as_ref()
            .map(|o| o.contains(&chave_s) && o.contains(&chave_g));
        if anterior == Some(hash.as_str()) && no_bucket != Some(false) {
            rel.reaproveitadas += 1;
            continue;
        }
        if anterior.is_none() && no_bucket == Some(true) {
            // Reconstrução com o par no bucket: registra o hash, sem upload (regra 5).
            indice.definir(id, hash);
            rel.reaproveitadas += 1;
            continue;
        }
        let troca = anterior.is_some_and(|h| h != hash);
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
        if troca {
            rel.reenviadas += 1;
        }
        a_gravar.push((chave_s, bytes_s, META_IMAGEM));
        a_gravar.push((chave_g, bytes_g, META_IMAGEM));
        enviados.push((id, hash));
    }
    if !a_gravar.is_empty() {
        pub_.gravar_lote(&a_gravar)?;
    }
    for (id, hash) in enviados {
        indice.definir(id, hash);
    }
    Ok(())
}
