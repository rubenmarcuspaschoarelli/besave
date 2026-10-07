//! BSV-41 PAG-09: headers de `avisos/` e `img/avisos/` (MANIFEST §4).

use worker::publicador::{META_PAGINA, Meta, meta_para};

const AVISO_IMG: &str = "public, max-age=3600";

/// PAG-09: página igual a `oferta/*`; imagem com cache curto (pode ser trocada no mesmo nome).
#[test]
fn headers_dos_avisos() {
    assert_eq!(meta_para("avisos/7/index.html"), Some(META_PAGINA));
    assert_eq!(
        meta_para("img/avisos/7.jpg"),
        Some(Meta {
            content_type: "image/jpeg",
            content_encoding: None,
            cache_control: AVISO_IMG,
        })
    );
    assert_eq!(
        meta_para("img/avisos/7.webp"),
        Some(Meta {
            content_type: "image/webp",
            content_encoding: None,
            cache_control: AVISO_IMG,
        })
    );
    assert_eq!(meta_para("img/avisos/7.png"), None);
    assert_eq!(meta_para("avisos/7/foto.jpg"), None);
    // As de oferta não mudam.
    assert_eq!(
        meta_para("img/ofertas/7.webp").map(|m| m.cache_control),
        Some("public, max-age=31536000, immutable")
    );
}
