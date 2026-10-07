//! BSV-40 JAN-01..03, JAN-06: janela, cota e silêncio (padrões 180/2, 8–22 h, som 9–21 h).

use worker::envio::janela::{inicio_do_dia, lote_devido, silencioso};
use worker::envio::modelo::Parametros;

/// 2026-09-24 00:00 em Brasília (03:00Z).
const DIA0: i64 = 1_790_218_800;

fn hora(h: i64, m: i64) -> i64 {
    DIA0 + h * 3600 + m * 60
}

fn p() -> Parametros {
    Parametros::default()
}

/// JAN-03 (e JAN-01 nos limites da janela).
#[test]
fn casos_da_spec() {
    assert_eq!(lote_devido(&p(), hora(7, 59), 0), 0);
    assert_eq!(lote_devido(&p(), hora(8, 0), 0), 2);
    assert_eq!(lote_devido(&p(), hora(8, 5), 2), 0);
    assert_eq!(lote_devido(&p(), hora(8, 10), 2), 2);
    assert_eq!(lote_devido(&p(), hora(21, 59), 180), 0);
    assert_eq!(lote_devido(&p(), hora(22, 0), 0), 0);
}

/// JAN-01: fora de [8, 22) nunca envia, mesmo com nada enviado.
#[test]
fn fora_da_janela_nao_envia() {
    for (h, m) in [(0, 0), (3, 0), (7, 59), (22, 0), (22, 1), (23, 59)] {
        assert_eq!(lote_devido(&p(), hora(h, m), 0), 0, "{h}:{m}");
    }
}

/// JAN-02: `esperado − enviados = L` envia; `L − 1` não; nunca passa de `QT_MAX_DIA`.
#[test]
fn formula_do_ritmo() {
    // 12:00: 240 min de 840 → 2 + floor(180·240/840) = 2 + 51 = 53.
    assert_eq!(lote_devido(&p(), hora(12, 0), 51), 2);
    assert_eq!(lote_devido(&p(), hora(12, 0), 52), 0);
    // 21:59: 2 + floor(180·839/840) = 181 → teto 180.
    assert_eq!(lote_devido(&p(), hora(21, 59), 178), 2);
    assert_eq!(lote_devido(&p(), hora(21, 59), 179), 0);
    let tres = Parametros {
        qt_por_execucao: 3,
        ..p()
    };
    assert_eq!(lote_devido(&tres, hora(8, 0), 0), 3);
}

/// Parâmetros vêm da tabela: outra janela e outra cota mudam a decisão.
#[test]
fn parametros_mudam_a_janela() {
    let q = Parametros {
        hora_inicio: 10,
        hora_fim: 12,
        qt_max_dia: 10,
        ..p()
    };
    assert_eq!(lote_devido(&q, hora(9, 59), 0), 0);
    assert_eq!(lote_devido(&q, hora(10, 0), 0), 2);
    assert_eq!(lote_devido(&q, hora(12, 0), 0), 0);
}

/// JAN-06: 08:30 silencioso, 09:00 com som, 20:59 com som, 21:00 silencioso.
#[test]
fn silencio_fora_de_9_a_21() {
    assert!(silencioso(&p(), hora(8, 30)));
    assert!(!silencioso(&p(), hora(9, 0)));
    assert!(!silencioso(&p(), hora(20, 59)));
    assert!(silencioso(&p(), hora(21, 0)));
}

/// "Enviados hoje" conta a partir de 00:00 de Brasília, não de 00:00 UTC.
#[test]
fn dia_de_brasilia() {
    assert_eq!(inicio_do_dia(hora(0, 0)), DIA0);
    assert_eq!(inicio_do_dia(hora(23, 59)), DIA0);
    // 22:30 em Brasília já é o dia seguinte em UTC.
    assert_eq!(inicio_do_dia(hora(22, 30)), DIA0);
    assert_eq!(inicio_do_dia(hora(24, 0)), DIA0 + 86_400);
}
