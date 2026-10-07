//! BSV-41 PAG-03..06: página `avisos/{id}/index.html`.

use worker::avisos::modelo::{Formato, LinhaAviso};
use worker::avisos::pagina::TemplateAviso;

const CANAL: &str = "https://t.me/besaveofertas";

fn aviso(id: i64) -> LinhaAviso {
    LinhaAviso {
        id,
        titulo: "Como o Besave funciona".into(),
        texto: "Primeiro parágrafo.\nSegunda linha.\n\nSegundo parágrafo.".into(),
        imagem: Some("aviso.jpg".into()),
        link_interno: Some("/elas/".into()),
        ativo: true,
        ..Default::default()
    }
}

fn render(a: &LinhaAviso, img: Option<Formato>) -> String {
    TemplateAviso::novo(CANAL)
        .unwrap()
        .renderizar(a, img)
        .unwrap()
}

/// PAG-03: título, imagem, parágrafos, link do canal, CSS e `noindex`.
#[test]
fn pagina_completa() {
    let h = render(&aviso(7), Some(Formato::Jpg));
    assert!(
        h.contains("<h1 class=\"titulo\">Como o Besave funciona</h1>"),
        "{h}"
    );
    assert!(
        h.contains("<title>Como o Besave funciona | Besave</title>"),
        "{h}"
    );
    assert!(h.contains("src=\"/img/avisos/7.jpg\""), "{h}");
    assert!(
        h.contains("<p>Primeiro parágrafo.<br>Segunda linha.</p>"),
        "{h}"
    );
    assert!(h.contains("<p>Segundo parágrafo.</p>"), "{h}");
    assert!(h.contains(&format!("href=\"{CANAL}\"")), "{h}");
    assert!(
        h.contains("<link rel=\"stylesheet\" href=\"/assets/besave.css\">"),
        "{h}"
    );
    assert!(
        h.contains("<meta name=\"robots\" content=\"noindex\">"),
        "{h}"
    );
    assert!(
        h.contains("<link rel=\"canonical\" href=\"https://besave.com.br/avisos/7/\">"),
        "{h}"
    );
    let webp = render(&aviso(7), Some(Formato::Webp));
    assert!(webp.contains("src=\"/img/avisos/7.webp\""), "{webp}");
}

/// PAG-03 (sem imagem): nenhum `<img>` na página.
#[test]
fn pagina_sem_imagem() {
    let h = render(&aviso(7), None);
    assert!(!h.contains("<img"), "{h}");
    assert!(!h.contains("/img/avisos/"), "{h}");
}

/// PAG-04: HTML do banco sai escapado.
#[test]
fn texto_escapado() {
    let a = LinhaAviso {
        titulo: "<script>alert(1)</script> Título".into(),
        texto: "Oi <script>alert(2)</script> & <b>tchau</b>".into(),
        ..aviso(8)
    };
    let h = render(&a, None);
    assert!(!h.contains("<script>"), "{h}");
    assert!(!h.contains("<b>tchau"), "{h}");
    assert!(
        h.contains("&lt;script&gt;alert(1)&lt;/script&gt; Título"),
        "{h}"
    );
    assert!(
        h.contains("Oi &lt;script&gt;alert(2)&lt;/script&gt; &amp; &lt;b&gt;tchau&lt;/b&gt;"),
        "{h}"
    );
}

/// PAG-05: link interno válido vira botão com o caminho.
#[test]
fn botao_com_link_interno() {
    let a = LinhaAviso {
        link_interno: Some("/oferta/12345/".into()),
        ..aviso(9)
    };
    let h = render(&a, None);
    assert!(
        h.contains("<a class=\"cta\" href=\"/oferta/12345/\">"),
        "{h}"
    );
    let raiz = render(
        &LinhaAviso {
            link_interno: Some("/".into()),
            ..aviso(9)
        },
        None,
    );
    assert!(raiz.contains("<a class=\"cta\" href=\"/\">"), "{raiz}");
}

/// PAG-06: link externo ou fora de `^/[a-z0-9/_-]*$` → sem botão; ausente → sem botão.
#[test]
fn sem_botao_com_link_invalido() {
    for link in [
        Some("https://loja.com"),
        Some("//loja.com"),
        // Casa a regex, mas `//host` é URL de outro domínio no navegador.
        Some("//lojacom"),
        Some("/Elas/"),
        Some("/elas/?x=1"),
        Some("/ir/5412\" onclick=\"x"),
        Some("elas/"),
        None,
    ] {
        let a = LinhaAviso {
            link_interno: link.map(str::to_owned),
            ..aviso(10)
        };
        let h = render(&a, None);
        assert!(!h.contains("class=\"cta\""), "{link:?}: {h}");
        assert!(!h.contains("loja.com"), "{link:?}: {h}");
    }
}
