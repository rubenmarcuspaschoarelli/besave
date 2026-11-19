//! Aviso no canal (BSV-41): qual está devido, legenda e foto.

use std::path::Path;

use tracing::warn;

use crate::avisos::modelo::formato_imagem;
use crate::envio::fonte::AvisoCanal;
use crate::envio::foto::quadrado_jpeg;
use crate::envio::legenda::{caber, escapar};
use crate::envio::site::{Imagens, baixar, url};
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
    foto_aviso_de(&Imagens::pasta(dir), id, nome)
}

/// JPEG 800×800 do aviso. Com URL: `GET {url}{id}.{webp|jpg}` (extensão de `DS_IMAGEM`; a pasta não
/// é lida); sem URL, `{dir}/{nome}`. Sem imagem ou qualquer falha → `None` (com WARN).
pub fn foto_aviso_de(img: &Imagens, id: i64, nome: Option<&str>) -> Option<Vec<u8>> {
    let nome = nome.map(str::trim).filter(|n| !n.is_empty())?;
    let bytes = if let Some(base) = img.url {
        let Some(formato) = formato_imagem(nome) else {
            warn!(
                id,
                imagem = nome,
                "imagem do aviso fora de .webp/.jpg; aviso vai sem foto"
            );
            return None;
        };
        baixar(
            img.http,
            &url(base, &format!("{id}.{}", formato.extensao())),
        )
        .map_err(|e| e.to_string())
    } else if let Some(dir) = img.dir {
        img.disco.ler(&dir.join(nome)).map_err(|e| e.to_string())
    } else {
        warn!(
            id,
            imagem = nome,
            "BESAVE_AVISOS_URL e BESAVE_AVISOS_DIR ausentes; aviso vai sem foto"
        );
        return None;
    };
    let jpeg = bytes
        .and_then(|b| image::load_from_memory(&b).map_err(|e| e.to_string()))
        .and_then(|i| quadrado_jpeg(&i).map_err(|e| e.to_string()));
    match jpeg {
        Ok(j) => Some(j),
        Err(e) => {
            warn!(id, imagem = nome, erro = %e, "imagem do aviso indisponível; aviso vai sem foto");
            None
        }
    }
}
