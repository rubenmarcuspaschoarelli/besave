//! EXP-10..: falha do expurgo não falha o ciclo (BSV-47, decisão do dono). O site já foi publicado:
//! `DT_PUBLICACAO_SITE`, avisos e relatório seguem; os ids ficam na fila; o Telegram recebe um aviso
//! com a variante `Expurgo`, no máximo um a cada 2 h, sem contar como falha do ciclo.

mod comum;

use std::cell::RefCell;
use std::path::PathBuf;

use comum::{AGORA, dir_imagens_vazio, linha, mapeamento};
use worker::alerta::{Alertas, ErroTelegram, Telegram};
use worker::avisos::modelo::LinhaAviso;
use worker::avisos::publicacao::ConfigAvisos;
use worker::execucao::{concluir, marcar_publicacao_site, publicar_avisos_ciclo, rodar};
use worker::expurgo::FilaExpurgo;
use worker::fonte::FakeFonte;
use worker::geracao::Relatorio;
use worker::publicador::PublicadorMemoria;
use worker::redirects::RedirectsMemoria;
use worker::site::ConfigSite;

/// 2026-09-25T05:30:00Z = 02:30 em Brasília: dentro da janela padrão.
const NA_JANELA: i64 = AGORA + 16 * 3600 + 50 * 60;

#[derive(Default)]
struct TelegramFake(RefCell<Vec<String>>);

impl Telegram for TelegramFake {
    fn enviar(&self, texto: &str) -> Result<(), ErroTelegram> {
        self.0.borrow_mut().push(texto.to_owned());
        Ok(())
    }
}

fn estado(nome: &str) -> PathBuf {
    std::env::temp_dir()
        .join(format!(
            "besave-expurgo-falha-{nome}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
        .join("alerta.json")
}

fn aviso() -> LinhaAviso {
    LinhaAviso {
        id: 7,
        titulo: "Aviso".into(),
        texto: "Texto.".into(),
        ativo: true,
        dt_inicio: AGORA - 86_400,
        ..Default::default()
    }
}

/// Publica ids 1..=3; depois, na janela, o Oracle só devolve o 1 e o novo 4 e o `DeleteObjects`
/// falha. Devolve o relatório do 2º ciclo, o bucket e a fonte do 2º ciclo.
fn ciclo_com_expurgo_falhando() -> (Relatorio, PublicadorMemoria, FakeFonte) {
    let site = ConfigSite::default();
    let mut p = PublicadorMemoria::new().falhando_em_remover_lote_na(1);
    let mut kvs = RedirectsMemoria::new();
    let inicial = FakeFonte::new(vec![linha(1), linha(2), linha(3)], vec![], AGORA);
    rodar(
        &inicial,
        &mapeamento(),
        &mut p,
        &mut kvs,
        &dir_imagens_vazio(),
        &site,
        AGORA,
    )
    .unwrap();
    let fonte =
        FakeFonte::new(vec![linha(1), linha(4)], vec![], NA_JANELA).com_avisos(vec![aviso()]);
    let rel = rodar(
        &fonte,
        &mapeamento(),
        &mut p,
        &mut kvs,
        &dir_imagens_vazio(),
        &site,
        NA_JANELA,
    )
    .expect("falha do expurgo não pode falhar o ciclo");
    (rel, p, fonte)
}

#[test]
fn falha_do_expurgo_deixa_o_ciclo_ok_e_os_ids_na_fila() {
    let (rel, p, _) = ciclo_com_expurgo_falhando();
    assert!(rel.expurgo.falhou);
    assert_eq!((rel.expurgo.removidos, rel.expurgo.pendente), (0, 2));
    let fila = FilaExpurgo::carregar(&p).unwrap();
    assert_eq!(fila.ids().collect::<Vec<_>>(), [2, 3], "ids seguem na fila");
}

#[test]
fn expurgo_falhando_ainda_grava_dt_publicacao_site_e_executa_os_avisos() {
    let (mut rel, mut p, fonte) = ciclo_com_expurgo_falhando();
    marcar_publicacao_site(&fonte, &mut rel);
    assert!(
        fonte.publicadas_site().contains_key(&4),
        "oferta nova sem DT_PUBLICACAO_SITE: {:?}",
        fonte.publicadas_site()
    );
    assert!(rel.publicacao_site_marcadas >= 1 && rel.publicacao_site_falhas == 0);
    publicar_avisos_ciclo(
        &fonte,
        &mut p,
        &ConfigAvisos::default(),
        NA_JANELA,
        true,
        &mut rel,
    );
    assert_eq!((rel.avisos.publicados, rel.avisos.falhas), (1, 0));
}

#[test]
fn expurgo_falhando_avisa_com_variante_propria_uma_vez_por_duas_horas() {
    let (rel, _, _) = ciclo_com_expurgo_falhando();
    let t = TelegramFake::default();
    let e = estado("aviso");
    let alertas = Alertas::new(&t, e.clone(), "vps".into());
    let sucesso = |agora| concluir(Ok((rel.clone(), 10)), Some(&alertas), agora);
    sucesso(NA_JANELA);
    sucesso(NA_JANELA + 300);
    {
        let msgs = t.0.borrow();
        assert_eq!(msgs.len(), 1, "{msgs:?}");
        assert!(msgs[0].contains("erro: Expurgo"), "{}", msgs[0]);
        assert!(msgs[0].contains("fase: expurgo"), "{}", msgs[0]);
    }
    sucesso(NA_JANELA + 2 * 3600);
    assert_eq!(t.0.borrow().len(), 2);
    // Não é falha do ciclo: nada de "recuperado" depois, e o contador de falhas fica zerado.
    let json: serde_json::Value = serde_json::from_slice(&std::fs::read(&e).unwrap()).unwrap();
    assert_eq!(json["falhas"], 0, "{json}");
}

#[test]
fn expurgo_sem_falha_nao_avisa() {
    let site = ConfigSite::default();
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    let fonte = FakeFonte::new(vec![linha(1)], vec![], AGORA);
    let rel = rodar(
        &fonte,
        &mapeamento(),
        &mut p,
        &mut kvs,
        &dir_imagens_vazio(),
        &site,
        AGORA,
    )
    .unwrap();
    assert!(!rel.expurgo.falhou);
    let t = TelegramFake::default();
    let alertas = Alertas::new(&t, estado("sem"), "vps".into());
    concluir(Ok((rel, 10)), Some(&alertas), AGORA);
    assert!(t.0.borrow().is_empty());
}
