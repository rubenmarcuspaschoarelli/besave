//! CON-01 e FIL-01 (regras do §9 na projeção do canal).

use worker::conversao::{LinhaOferta, Rejeicao};
use worker::envio::modelo::{LinhaCanal, para_canal};
use worker::geracao::versao_contrato;
use worker::mapeamento::Mapeamento;
use worker::modelo::Loja;

fn m() -> Mapeamento {
    Mapeamento::embutido().unwrap()
}

fn linha() -> LinhaCanal {
    LinhaCanal {
        oferta: LinhaOferta {
            id: 5412,
            id_produto: Some(910),
            loja: Some("Mercado Livre".into()),
            titulo: Some("  Fone XYZ  ".into()),
            preco_de: Some(299.9),
            preco_por: Some(199.9),
            cupom: Some("besave10".into()),
            dt_oferta: Some(1_790_000_000),
            area: Some("Tech".into()),
            publico: Some("U".into()),
            ativo: true,
            url_afiliado: "https://loja.example/x".into(),
            ..Default::default()
        },
        destaque: Some("  Menor preço em 30 dias ".into()),
        recorrencia: true,
        dt_publicacao_site: Some(1_790_000_100),
    }
}

/// CON-01 (BSV-40), CON-03 (BSV-36): contrato 1.5.0.
#[test]
fn contrato_na_versao_1_5_0() {
    assert_eq!(versao_contrato().unwrap(), "1.5.0");
}

#[test]
fn projecao_do_canal_tem_os_campos_do_contrato() {
    let o = para_canal(&linha(), &m()).unwrap();
    assert_eq!(o.id, 5412);
    assert_eq!(o.id_produto, 910);
    assert_eq!(o.loja, Loja::MercadoLivre);
    assert_eq!(o.titulo, "Fone XYZ");
    assert_eq!(o.destaque.as_deref(), Some("Menor preço em 30 dias"));
    assert_eq!(o.preco_de, Some(29990));
    assert_eq!(o.preco_por, 19990);
    assert_eq!(o.desconto_pct, Some(33));
    assert_eq!(o.cupom.as_deref(), Some("BESAVE10"));
    assert!(o.recorrencia);
    assert_eq!(o.dt_oferta, "2026-09-21T14:13:20Z");
}

#[test]
fn titulo_integral_e_destaque_vazio_ausente() {
    let mut l = linha();
    let longo = "palavra ".repeat(60);
    l.oferta.titulo = Some(longo.clone());
    l.destaque = Some("   ".into());
    let o = para_canal(&l, &m()).unwrap();
    assert_eq!(o.titulo, longo.trim());
    assert_eq!(o.destaque, None);
}

#[test]
fn destaque_longo_cortado_em_200() {
    let mut l = linha();
    l.destaque = Some("abc ".repeat(80));
    let d = para_canal(&l, &m()).unwrap().destaque.unwrap();
    assert!(d.chars().count() <= 200, "{}", d.chars().count());
    assert!(d.ends_with('…'));
}

#[test]
fn sem_preco_de_nao_tem_desconto() {
    let mut l = linha();
    l.oferta.preco_de = None;
    let o = para_canal(&l, &m()).unwrap();
    assert_eq!((o.preco_de, o.desconto_pct), (None, None));
}

/// FIL-01: §9 + URL de afiliado + `id_produto`.
#[test]
fn rejeita_como_o_worker() {
    type Mexe = fn(&mut LinhaCanal);
    let casos: [(Mexe, Rejeicao); 6] = [
        (
            |l| l.oferta.preco_por = Some(0.0),
            Rejeicao::PrecoPorInvalido,
        ),
        (
            |l| l.oferta.titulo = Some(" ".into()),
            Rejeicao::TituloVazio,
        ),
        (
            |l| l.oferta.loja = Some("Americanas".into()),
            Rejeicao::LojaSemMapeamento,
        ),
        (|l| l.oferta.dt_oferta = None, Rejeicao::DataNula),
        (
            |l| l.oferta.url_afiliado = " ".into(),
            Rejeicao::UrlAfiliadoAusente,
        ),
        (|l| l.oferta.id_produto = None, Rejeicao::IdProdutoAusente),
    ];
    for (mexe, esperado) in casos {
        let mut l = linha();
        mexe(&mut l);
        assert_eq!(para_canal(&l, &m()), Err(esperado));
    }
}
