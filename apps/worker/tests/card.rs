//! CONV-02..11: LinhaOferta → OfertaCard (CONTRATO §3, §9).

mod comum;

use comum::{compactar, fixture};
use worker::conversao::{LinhaOferta, Rejeicao, centavos, iso_utc, para_card};
use worker::mapeamento::Mapeamento;
use worker::modelo::{Area, Loja, Publico};

const DT_5412: i64 = 1_790_253_600; // 2026-09-24T12:40:00Z
const DT_5413: i64 = 1_790_253_660; // 2026-09-24T12:41:00Z
const DT_5420: i64 = 1_790_150_400; // 2026-09-23T08:00:00Z
const DP_5412: i64 = 1_791_298_920; // 2026-10-06T15:02:00Z (= 5420)
const DP_5413: i64 = 1_791_372_600; // 2026-10-07T11:30:00Z
/// Relógio dos testes de card: 2026-10-07T12:00:00Z.
const AGORA_CARD: i64 = 1_791_374_400;

fn m() -> Mapeamento {
    Mapeamento::carregar(comum::caminho_mapeamento()).unwrap()
}

/// Linhas "como vêm do Oracle" equivalentes aos 3 registros de chunk-ok.json.
fn linhas_fixture() -> Vec<LinhaOferta> {
    vec![
        LinhaOferta {
            id: 5412,
            id_produto: Some(910),
            loja: Some("Amazon".into()),
            titulo: Some("  Fone Bluetooth XYZ com ANC ".into()),
            preco_de: Some(299.90),
            preco_por: Some(199.90),
            cupom: Some(" besave10 ".into()),
            dt_oferta: Some(DT_5412),
            area: Some("Tecnologia".into()),
            publico: Some("unisex".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5412".into(),
            dt_publicacao_site: Some(DP_5412),
            ..Default::default()
        },
        LinhaOferta {
            id: 5413,
            loja: Some("shopee".into()),
            titulo: Some("Kit Skincare Vitamina C 3 passos".into()),
            preco_de: None,
            preco_por: Some(89.90),
            dt_oferta: Some(DT_5413),
            area: Some("Elas".into()),
            publico: Some("Mulher".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5413".into(),
            dt_publicacao_site: Some(DP_5413),
            ..Default::default()
        },
        LinhaOferta {
            id: 5420,
            loja: Some("MercadoLivre".into()),
            titulo: Some("Ração Premium Cães Adultos 15kg".into()),
            preco_de: Some(249.00),
            preco_por: Some(199.00),
            dt_oferta: Some(DT_5420),
            area: Some("Pet".into()),
            publico: Some("U".into()),
            ativo: false,
            dt_desativacao: Some(DT_5420),
            url_afiliado: "https://loja.example/5420".into(),
            dt_publicacao_site: Some(DP_5412),
            ..Default::default()
        },
    ]
}

fn valida() -> LinhaOferta {
    linhas_fixture().remove(1)
}

#[test]
fn fixture_chunk_ok_byte_a_byte() {
    let m = m();
    let cards: Vec<_> = linhas_fixture()
        .iter()
        .map(|l| para_card(l, &m, AGORA_CARD).unwrap())
        .collect();
    assert_eq!(
        serde_json::to_string(&cards).unwrap(),
        compactar(&fixture("chunk-ok.json"))
    );
}

#[test]
fn orcamento_de_bytes_do_card() {
    let m = m();
    let tamanhos: Vec<usize> = linhas_fixture()
        .iter()
        .map(|l| {
            serde_json::to_string(&para_card(l, &m, AGORA_CARD).unwrap())
                .unwrap()
                .len()
        })
        .collect();
    let media = tamanhos.iter().sum::<usize>() as f64 / tamanhos.len() as f64;
    assert!(media <= 230.0, "média {media}"); // AD-074
}

/// AD-064: sem teto por card; título de 200 caracteres acentuados (> 220 B) é aceito inteiro.
#[test]
fn card_com_titulo_longo_acentuado_e_aceito() {
    let titulo = "é".repeat(200);
    let l = LinhaOferta {
        titulo: Some(titulo.clone()),
        ..valida()
    };
    let c = para_card(&l, &m(), AGORA_CARD).unwrap();
    assert_eq!(c.titulo, titulo);
    let bytes = serde_json::to_string(&c).unwrap().len();
    assert!(bytes > 220, "card com {bytes} bytes");
}

#[test]
fn enum_via_sinonimo() {
    let c = para_card(&linhas_fixture()[2], &m(), AGORA_CARD).unwrap();
    assert_eq!(c.loja, Loja::MercadoLivre);
    assert_eq!(c.area, Area::Pets);
    assert_eq!(c.publico, Publico::Unissex);
}

#[test]
fn rejeita_preco_por_ausente_zero_ou_negativo() {
    let m = m();
    for pp in [None, Some(0.0), Some(-5.0), Some(0.004)] {
        let l = LinhaOferta {
            preco_por: pp,
            ..valida()
        };
        assert_eq!(
            para_card(&l, &m, AGORA_CARD),
            Err(Rejeicao::PrecoPorInvalido),
            "pp={pp:?}"
        );
    }
}

#[test]
fn rejeita_titulo_vazio() {
    let m = m();
    for t in [None, Some("   ".to_string())] {
        let l = LinhaOferta {
            titulo: t,
            ..valida()
        };
        assert_eq!(para_card(&l, &m, AGORA_CARD), Err(Rejeicao::TituloVazio));
    }
}

#[test]
fn rejeita_loja_sem_mapeamento() {
    let l = LinhaOferta {
        loja: Some("Americanas".into()),
        ..valida()
    };
    assert_eq!(
        para_card(&l, &m(), AGORA_CARD),
        Err(Rejeicao::LojaSemMapeamento)
    );
    let l = LinhaOferta {
        loja: None,
        ..valida()
    };
    assert_eq!(
        para_card(&l, &m(), AGORA_CARD),
        Err(Rejeicao::LojaSemMapeamento)
    );
}

/// AREA-02: contrato 1.3 acrescentou a área OUTROS; não é mais rejeição.
#[test]
fn area_outros_nao_e_rejeitada() {
    let l = LinhaOferta {
        area: Some("Outros".into()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m(), AGORA_CARD).unwrap().area, Area::Outros);
}

#[test]
fn rejeita_area_sem_mapeamento() {
    let l = LinhaOferta {
        area: Some("Moda".into()),
        ..valida()
    };
    assert_eq!(
        para_card(&l, &m(), AGORA_CARD),
        Err(Rejeicao::AreaSemMapeamento)
    );
}

#[test]
fn rejeita_publico_sem_mapeamento() {
    let l = LinhaOferta {
        publico: Some("Adulto".into()),
        ..valida()
    };
    assert_eq!(
        para_card(&l, &m(), AGORA_CARD),
        Err(Rejeicao::PublicoSemMapeamento)
    );
}

#[test]
fn rejeita_data_nula() {
    let l = LinhaOferta {
        dt_oferta: None,
        ..valida()
    };
    assert_eq!(para_card(&l, &m(), AGORA_CARD), Err(Rejeicao::DataNula));
}

#[test]
fn preco_de_menor_ou_igual_vira_null_sem_rejeitar() {
    let m = m();
    for pd in [89.90, 50.00] {
        let l = LinhaOferta {
            preco_de: Some(pd),
            ..valida()
        };
        let c = para_card(&l, &m, AGORA_CARD).unwrap();
        assert_eq!(c.preco_de, None, "pd={pd}");
        assert!(serde_json::to_string(&c).unwrap().contains("\"pd\":null"));
    }
    let l = LinhaOferta {
        preco_de: Some(89.91),
        ..valida()
    };
    assert_eq!(para_card(&l, &m, AGORA_CARD).unwrap().preco_de, Some(8991));
}

#[test]
fn titulo_longo_cortado_em_197_na_fronteira_de_palavra() {
    let longo = "abcdefghi ".repeat(25); // 250 caracteres
    let l = LinhaOferta {
        titulo: Some(longo),
        ..valida()
    };
    let t = para_card(&l, &m(), AGORA_CARD).unwrap().titulo;
    let esperado = format!("{}…", "abcdefghi ".repeat(19).trim_end());
    assert_eq!(t, esperado);
    assert!(t.chars().count() <= 200);
}

#[test]
fn titulo_longo_sem_espaco_corta_seco_em_197() {
    let l = LinhaOferta {
        titulo: Some("á".repeat(250)),
        ..valida()
    };
    let t = para_card(&l, &m(), AGORA_CARD).unwrap().titulo;
    assert_eq!(t, format!("{}…", "á".repeat(197)));
}

#[test]
fn titulo_de_200_nao_e_cortado() {
    let t200 = "abcdefghi ".repeat(20).trim_end().to_string() + "x"; // 200 chars
    assert_eq!(t200.chars().count(), 200);
    let l = LinhaOferta {
        titulo: Some(t200.clone()),
        ..valida()
    };
    assert_eq!(para_card(&l, &m(), AGORA_CARD).unwrap().titulo, t200);
}

#[test]
fn centavos_half_up() {
    assert_eq!(centavos(19.995), 2000);
    assert_eq!(centavos(19.994), 1999);
    assert_eq!(centavos(199.90), 19990);
    assert_eq!(centavos(0.005), 1);
    assert_eq!(centavos(1.0), 100);
}

#[test]
fn inativa_tem_x_1_e_ativa_nao_tem_x() {
    let m = m();
    let l = LinhaOferta {
        ativo: false,
        ..valida()
    };
    let c = para_card(&l, &m, AGORA_CARD).unwrap();
    assert_eq!(c.x, Some(1));
    assert!(serde_json::to_string(&c).unwrap().ends_with(",\"x\":1}"));

    let c = para_card(&valida(), &m, AGORA_CARD).unwrap();
    assert_eq!(c.x, None);
    assert!(!serde_json::to_string(&c).unwrap().contains("\"x\""));
}

#[test]
fn cupom_so_espacos_fica_ausente() {
    let l = LinhaOferta {
        cupom: Some("   ".into()),
        ..valida()
    };
    let c = para_card(&l, &m(), AGORA_CARD).unwrap();
    assert_eq!(c.cupom, None);
    assert!(!serde_json::to_string(&c).unwrap().contains("\"c\""));
}

#[test]
fn data_iso_8601_utc() {
    assert_eq!(iso_utc(0), "1970-01-01T00:00:00Z");
    assert_eq!(iso_utc(951_868_799), "2000-02-29T23:59:59Z");
    assert_eq!(iso_utc(DT_5412), "2026-09-24T12:40:00Z");
}

/// URL-04: sem DS_URL_AFILIADO o card não existe (CONTRATO §10.1), nem a página.
#[test]
fn url_afiliado_vazia_rejeita_card_e_pagina() {
    let m = m();
    for url in ["", "   ", "\t\n"] {
        let l = LinhaOferta {
            url_afiliado: url.into(),
            id_produto: Some(911),
            ..valida()
        };
        assert_eq!(
            para_card(&l, &m, AGORA_CARD),
            Err(Rejeicao::UrlAfiliadoAusente),
            "{url:?}"
        );
        assert_eq!(
            worker::conversao::para_pagina(&l, None, &m),
            Err(Rejeicao::UrlAfiliadoAusente),
            "{url:?}"
        );
    }
}

// BSV-36 DP-01..04: `dp` = `DT_PUBLICACAO_SITE` na faixa `[2026-10-06, instante do ciclo]`;
// nula ou fora → instante do ciclo (agora truncado ao minuto); fora → WARN, sem rejeitar.

mod dp {
    use super::*;
    use std::io::Write;
    use std::sync::{Arc, Mutex};

    #[derive(Clone, Default)]
    struct Buffer(Arc<Mutex<Vec<u8>>>);

    impl Write for Buffer {
        fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
            self.0.lock().unwrap().extend_from_slice(b);
            Ok(b.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    fn com_log<T>(f: impl FnOnce() -> T) -> (T, String) {
        let buf = Buffer::default();
        let saida = buf.clone();
        let sub = tracing_subscriber::fmt()
            .with_writer(move || saida.clone())
            .with_ansi(false)
            .finish();
        let r = tracing::subscriber::with_default(sub, f);
        let log = String::from_utf8(buf.0.lock().unwrap().clone()).unwrap();
        (r, log)
    }

    fn com_data(d: Option<i64>) -> LinhaOferta {
        LinhaOferta {
            dt_publicacao_site: d,
            ..valida()
        }
    }

    /// 2026-10-07T12:00:37Z: relógio fora do minuto cheio.
    const AGORA_QUEBRADO: i64 = AGORA_CARD + 37;

    #[test]
    fn dp_01_data_da_coluna_em_utc() {
        let c = para_card(&com_data(Some(DP_5413)), &m(), AGORA_QUEBRADO).unwrap();
        assert_eq!(c.dt_publicacao, "2026-10-07T11:30:00Z");
        let c = para_card(&com_data(Some(DP_5412 + 17)), &m(), AGORA_QUEBRADO).unwrap();
        assert_eq!(c.dt_publicacao, "2026-10-06T15:02:17Z");
    }

    #[test]
    fn dp_01_limites_da_faixa_sao_aceitos_sem_warn() {
        let (c, log) = com_log(|| {
            (
                para_card(&com_data(Some(AGORA_CARD)), &m(), AGORA_QUEBRADO).unwrap(),
                para_card(&com_data(Some(1_791_244_800)), &m(), AGORA_QUEBRADO).unwrap(),
            )
        });
        assert_eq!(c.0.dt_publicacao, "2026-10-07T12:00:00Z");
        assert_eq!(c.1.dt_publicacao, "2026-10-06T00:00:00Z");
        assert!(!log.contains("WARN"), "{log}");
    }

    #[test]
    fn dp_02_nula_vira_instante_do_ciclo_truncado_ao_minuto() {
        let (c, log) = com_log(|| para_card(&com_data(None), &m(), AGORA_QUEBRADO).unwrap());
        assert_eq!(c.dt_publicacao, "2026-10-07T12:00:00Z");
        assert!(!log.contains("WARN"), "{log}");
    }

    #[test]
    fn dp_03_futura_vira_instante_do_ciclo_com_warn() {
        let (c, log) =
            com_log(|| para_card(&com_data(Some(AGORA_CARD + 60)), &m(), AGORA_QUEBRADO));
        let c = c.expect("data futura não rejeita a oferta");
        assert_eq!(c.dt_publicacao, "2026-10-07T12:00:00Z");
        assert!(
            log.lines().any(|l| l.contains("WARN")
                && l.contains("5413")
                && l.contains("DT_PUBLICACAO_SITE")),
            "{log}"
        );
    }

    #[test]
    fn dp_04_anterior_a_2026_10_06_vira_instante_do_ciclo_com_warn() {
        let (c, log) =
            com_log(|| para_card(&com_data(Some(1_791_244_800 - 1)), &m(), AGORA_QUEBRADO));
        let c = c.expect("data antiga não rejeita a oferta");
        assert_eq!(c.dt_publicacao, "2026-10-07T12:00:00Z");
        assert!(
            log.lines().any(|l| l.contains("WARN")
                && l.contains("5413")
                && l.contains("DT_PUBLICACAO_SITE")),
            "{log}"
        );
    }
}
