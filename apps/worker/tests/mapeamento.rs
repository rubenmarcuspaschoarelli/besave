//! CONV-01: sinônimos → enum após normalização (CONTRATO §2, mapeamento.json).

mod comum;

use worker::mapeamento::{Mapeamento, normalizar};
use worker::modelo::{Area, Loja, Publico};

fn m() -> Mapeamento {
    Mapeamento::carregar(comum::caminho_mapeamento()).unwrap()
}

#[test]
fn normaliza_maiusculas_acento_trim_espacos() {
    assert_eq!(normalizar("  Família   &  filhos "), "FAMILIA & FILHOS");
    assert_eq!(normalizar("criança"), "CRIANCA");
    assert_eq!(normalizar("Mercado\tLivre"), "MERCADO LIVRE");
}

#[test]
fn loja_por_sinonimo() {
    let m = m();
    assert_eq!(m.loja("MERCADOLIVRE"), Some(Loja::MercadoLivre));
    assert_eq!(m.loja("Mercado  Livre"), Some(Loja::MercadoLivre));
    assert_eq!(m.loja(" ml "), Some(Loja::MercadoLivre));
    assert_eq!(m.loja("Amazon"), Some(Loja::Amazon));
}

#[test]
fn area_por_sinonimo() {
    let m = m();
    assert_eq!(m.area("Família & filhos"), Some(Area::Familia));
    assert_eq!(m.area("casa"), Some(Area::MeuLar));
    assert_eq!(m.area("Esporte e Vida"), Some(Area::EsporteVida));
}

#[test]
fn publico_por_sinonimo() {
    let m = m();
    assert_eq!(m.publico(" criança "), Some(Publico::Infantil));
    assert_eq!(m.publico("mulher"), Some(Publico::Feminino));
}

#[test]
fn sem_mapeamento_devolve_none() {
    let m = m();
    assert_eq!(m.loja("AMERICANAS"), None);
    assert_eq!(m.area("ESPORTES RADICAIS"), None);
    assert_eq!(m.publico(""), None);
}

/// CIC-08 (BSV-14): o mapeamento embutido no binário é o mesmo `mapeamento.json` do contrato.
#[test]
fn embutido_igual_ao_arquivo_do_contrato() {
    let e = Mapeamento::embutido().unwrap();
    let f = m();
    for t in ["MERCADOLIVRE", " ml ", "Amazon", "Shopee", "Americanas"] {
        assert_eq!(e.loja(t), f.loja(t), "{t}");
    }
    for t in [
        "Família & filhos",
        "casa",
        "Esporte e Vida",
        "Tecnologia",
        "Moda",
    ] {
        assert_eq!(e.area(t), f.area(t), "{t}");
    }
    for t in [" criança ", "mulher", "Unissex", "Adulto"] {
        assert_eq!(e.publico(t), f.publico(t), "{t}");
    }
    assert_eq!(e.loja("Amazon"), Some(Loja::Amazon));
}
