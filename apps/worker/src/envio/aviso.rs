//! Aviso no canal (BSV-41): qual está devido, legenda e foto.

use std::path::Path;

use tracing::warn;

use crate::avisos::modelo::formato_imagem;
use crate::envio::fonte::AvisoCanal;
use crate::envio::foto::quadrado_jpeg;
use crate::envio::legenda::{caber, escapar};
use crate::pagina_html::URL_BASE;

/// `https://besave.com.br/avisos/{id}/?utm_source=telegram`
pub fn link_aviso(id: i64) -> String {
    format!("{URL_BASE}/avisos/{id}/?utm_source=telegram")
}

/// O aviso a enviar agora: ligação e aviso ativos, aviso vigente e no ar (`DT_PUBLICACAO_SITE`),
/// imagem em formato aceito e `agora − último envio ≥ intervalo`; entre os devidos, o de maior
/// atraso (nunca enviado = maior), empate pelo menor id.
pub fn devido(avisos: &[AvisoCanal], agora: i64) -> Option<&AvisoCanal> {
    avisos
        .iter()
        .filter(|a| a.ativo && a.aviso.vigente(agora) && a.aviso.dt_publicacao_site.is_some())
        .filter(|a| match a.aviso.imagem.as_deref() {
            Some(nome) if formato_imagem(nome.trim()).is_none() => {
                warn!(
                    id = a.aviso.id,
                    imagem = nome,
                    "imagem do aviso fora de .webp/.jpg; aviso ignorado"
                );
                false
            }
            _ => true,
        })
        .filter_map(|a| {
            let atraso = a.ultimo_envio.map_or(i64::MAX, |u| agora - u);
            (atraso >= a.intervalo_min * 60).then_some((atraso, a))
        })
        .max_by(|(x, a), (y, b)| x.cmp(y).then(b.aviso.id.cmp(&a.aviso.id)))
        .map(|(_, a)| a)
}

/// `<b>{título}</b>` / `{texto}` / `Saiba mais`, escapados, ≤ 1024: só o texto é cortado.
pub fn legenda_aviso(a: &AvisoCanal) -> String {
    let titulo = escapar(a.aviso.titulo.trim());
    let link = format!("<a href=\"{}\">Saiba mais</a>", link_aviso(a.aviso.id));
    caber(a.aviso.texto.trim(), |t| {
        format!("<b>{titulo}</b>\n{}\n{link}", escapar(t))
    })
}

/// JPEG 800×800 de `{dir}/{nome}`; `None` (com WARN) se não há imagem, pasta, arquivo legível ou
/// imagem decodificável: o aviso vai como `sendMessage`.
pub fn foto_aviso(dir: Option<&Path>, id: i64, nome: Option<&str>) -> Option<Vec<u8>> {
    let nome = nome.map(str::trim).filter(|n| !n.is_empty())?;
    let Some(dir) = dir else {
        warn!(
            id,
            imagem = nome,
            "BESAVE_AVISOS_DIR ausente; aviso vai sem foto"
        );
        return None;
    };
    let img = std::fs::read(dir.join(nome))
        .map_err(|e| e.to_string())
        .and_then(|b| image::load_from_memory(&b).map_err(|e| e.to_string()))
        .and_then(|img| quadrado_jpeg(&img).map_err(|e| e.to_string()));
    match img {
        Ok(jpeg) => Some(jpeg),
        Err(e) => {
            warn!(id, imagem = nome, erro = %e, "imagem do aviso indisponível; aviso vai sem foto");
            None
        }
    }
}
