//! Janela, cota e ritmo do envio (BSV-40 regra 1), no horário de Brasília (-03:00 fixo).

use crate::envio::modelo::Parametros;
use crate::logs::FUSO_BRASILIA;

const DIA: i64 = 86_400;

/// Minutos desde 00:00 de Brasília.
pub fn minuto_local(agora: i64) -> i64 {
    (agora + FUSO_BRASILIA).rem_euclid(DIA) / 60
}

/// 00:00 de Brasília do dia de `agora`, em segundos Unix.
pub fn inicio_do_dia(agora: i64) -> i64 {
    let local = agora + FUSO_BRASILIA;
    local - local.rem_euclid(DIA) - FUSO_BRASILIA
}

/// `min(QT_MAX_DIA, L + floor(QT_MAX_DIA × minutos_desde_INICIO / minutos_da_janela))`;
/// `None` fora de `[INICIO, FIM)`.
pub fn esperado(p: &Parametros, agora: i64) -> Option<u64> {
    let m = minuto_local(agora);
    let (ini, fim) = (i64::from(p.hora_inicio) * 60, i64::from(p.hora_fim) * 60);
    if m < ini || m >= fim {
        return None;
    }
    let max = i64::from(p.qt_max_dia);
    let ritmo = max * (m - ini) / (fim - ini);
    u64::try_from((i64::from(p.qt_por_execucao) + ritmo).min(max)).ok()
}

/// Tamanho do lote desta execução: `L` se `esperado − enviados_hoje ≥ L`, senão 0.
pub fn lote_devido(p: &Parametros, agora: i64, enviados_hoje: u64) -> u32 {
    let l = p.qt_por_execucao;
    match esperado(p, agora) {
        Some(e) if e.saturating_sub(enviados_hoje) >= u64::from(l) => l,
        _ => 0,
    }
}

/// `disable_notification`: fora de `[SOM_INICIO, SOM_FIM)`.
pub fn silencioso(p: &Parametros, agora: i64) -> bool {
    let m = minuto_local(agora);
    m < i64::from(p.hora_som_inicio) * 60 || m >= i64::from(p.hora_som_fim) * 60
}
