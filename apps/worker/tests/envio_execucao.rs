//! BSV-40 JAN-04, JAN-05, JAN-07, DUP-01..02, EXP-01..02, LIM-01..02: execuções do envio com
//! Oracle, Telegram e relógio falsos.

mod comum;

use comum::{linha_canal, mapeamento};
use std::cell::RefCell;
use std::path::Path;

use worker::envio::canal::{CanalTelegram, Chamada, ErroCanal, FakeCanal, RelogioFake};
use worker::envio::fonte::{FakeEnvio, RegistroEnvio};
use worker::envio::foto::{OrigemFoto, foto};
use worker::envio::modelo::{Canal, LinhaCanal, Parametros};
use worker::envio::rodada::{Contexto, EstadoEnvio, Parada, RelatorioEnvio, rodar};
use worker::execucao::{Codigo, Falha};
use worker::imagens::ErroImagem;
use worker::logs::FUSO_BRASILIA;
use worker::modelo::Area;

/// 2026-09-24 00:00 em Brasília (03:00Z).
const DIA0: i64 = 1_790_218_800;

fn hora(h: i64, m: i64) -> i64 {
    DIA0 + h * 3600 + m * 60
}

/// Oferta com 50% de desconto, `dt` às 07:00 do dia e página no ar (vale o dia inteiro).
fn oferta(id: i64) -> LinhaCanal {
    let mut l = linha_canal(id, Some(200.0), 100.0);
    l.oferta.dt_oferta = Some(hora(7, 0));
    l.dt_publicacao_site = Some(hora(7, 0));
    l
}

fn fonte(n: i64) -> FakeEnvio {
    FakeEnvio::new(Parametros::default(), (1..=n).map(oferta).collect())
}

fn rodar_em(
    f: &FakeEnvio,
    tg: &FakeCanal,
    r: &RelogioFake,
    t: i64,
    pausa_ate: Option<i64>,
) -> Result<RelatorioEnvio, Falha> {
    r.definir(t);
    let m = mapeamento();
    rodar(&Contexto {
        fonte: f,
        telegram: tg,
        relogio: r,
        m: &m,
        dir_imagens: None,
        dir_avisos: None,
        foto: foto_rapida,
        canal: 1,
        pausa_ate,
    })
}

/// Foto falsa (a real, 800×800, é coberta em `envio_foto.rs` e em `post_com_foto_real`).
fn foto_rapida(_: Option<&Path>, id: i64, area: Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem> {
    Ok((vec![0xFF, 0xD8, id as u8], OrigemFoto::Placeholder(area)))
}

fn fotos(tg: &FakeCanal) -> Vec<Chamada> {
    tg.chamadas()
        .into_iter()
        .filter(|c| c.metodo == "sendPhoto")
        .collect()
}

fn hora_local(ms: i64) -> i64 {
    (ms / 1000 + FUSO_BRASILIA).rem_euclid(86_400) / 3600
}

/// JAN-04: um dia com execuções a cada 5 min → 180 (± 2) posts, todos entre 08:00 e 22:00,
/// no máximo 2 por execução.
#[test]
fn dia_simulado() {
    let f = fonte(400);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    for k in 0..288 {
        let antes = tg.contar("sendPhoto");
        let rel = rodar_em(&f, &tg, &r, DIA0 + k * 300, None).unwrap();
        let depois = tg.contar("sendPhoto");
        assert!(depois - antes <= 2, "execução {k}: {}", depois - antes);
        assert_eq!(rel.enviados as usize, depois - antes);
    }
    let posts = fotos(&tg);
    assert!((178..=182).contains(&posts.len()), "{}", posts.len());
    for c in &posts {
        let h = hora_local(c.ms);
        assert!((8..22).contains(&h), "post às {h} h");
    }
    // Tudo confirmado: cada linha tem `message_id`.
    let envios = f.envios();
    assert_eq!(envios.len(), posts.len());
    assert!(envios.iter().all(|e| e.message_id.is_some()));
}

/// JAN-05: depois de 1 h parado, a execução seguinte envia só um lote.
#[test]
fn parada_de_uma_hora_recupera_um_lote() {
    let f = fonte(100);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let mut t = hora(8, 0);
    while t <= hora(10, 0) {
        rodar_em(&f, &tg, &r, t, None).unwrap();
        t += 300;
    }
    let antes = tg.contar("sendPhoto");
    let rel = rodar_em(&f, &tg, &r, hora(11, 5), None).unwrap();
    assert_eq!(tg.contar("sendPhoto") - antes, 2);
    assert_eq!(rel.devido, 2);
}

/// JAN-06 na execução: 08:30 silencioso, 09:00 com som.
#[test]
fn silencio_no_envio() {
    let f = fonte(10);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(8, 30), None).unwrap();
    let f2 = fonte(10);
    let tg2 = FakeCanal::new(&r);
    rodar_em(&f2, &tg2, &r, hora(9, 0), None).unwrap();
    assert!(!fotos(&tg).is_empty() && fotos(&tg).iter().all(|c| c.silencioso));
    assert!(!fotos(&tg2).is_empty() && fotos(&tg2).iter().all(|c| !c.silencioso));
}

/// JAN-07: ≥ 1 s entre chamadas consecutivas (lote e edições na mesma execução).
#[test]
fn um_segundo_entre_chamadas() {
    let f = fonte(10);
    // Dois posts antigos de ofertas que expiraram: viram edições na mesma execução.
    for (id_envio, id) in [(1, 501), (2, 502)] {
        let mut l = oferta(id);
        l.oferta.ativo = false;
        f.adicionar(l);
        f.registrar(RegistroEnvio {
            id_envio,
            canal: 1,
            id_oferta: id,
            id_produto: Some(id),
            preco_por: 10000,
            message_id: Some(id),
            dt_envio: hora(8, 0) - 86_400,
            dt_edicao: None,
        });
    }
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(8, 0), None).unwrap();
    let c = tg.chamadas();
    assert_eq!(c.len(), 4, "{c:?}");
    for par in c.windows(2) {
        assert!(
            par[1].ms - par[0].ms >= 1000,
            "{} → {}",
            par[0].ms,
            par[1].ms
        );
    }
}

/// Post: foto real 800×800 (placeholder da área), legenda com link, chat da tabela.
#[test]
fn post_com_foto_real() {
    let f = fonte(1).com_canal(Canal {
        id: 1,
        chat_id: "-100123".into(),
        ativo: true,
    });
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    rodar(&Contexto {
        fonte: &f,
        telegram: &tg,
        relogio: &r,
        m: &m,
        dir_imagens: None,
        dir_avisos: None,
        foto,
        canal: 1,
        pausa_ate: None,
    })
    .unwrap();
    let c = &fotos(&tg)[0];
    assert_eq!(c.chat_id, "-100123");
    let img = image::load_from_memory_with_format(&c.jpeg, image::ImageFormat::Jpeg).unwrap();
    assert_eq!((img.width(), img.height()), (800, 800));
    assert!(
        c.legenda
            .contains("https://besave.io/1?utm_source=telegram")
    );
}

/// DUP-01: sucesso grava `NR_MESSAGE_ID`; falha do Telegram apaga a linha e falha a execução.
#[test]
fn falha_do_telegram_apaga_a_linha() {
    let f = fonte(2);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    tg.roteirizar([
        Ok(()),
        Err(ErroCanal::Recusada {
            status: 400,
            descricao: "Bad Request".into(),
        }),
    ]);
    let falha = rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap_err();
    assert_eq!(falha.codigo, Codigo::Falha);
    assert_eq!(falha.fase, "envio_telegram");
    let envios = f.envios();
    assert_eq!(envios.len(), 1, "{envios:?}");
    assert_eq!(envios[0].message_id, Some(1000));
    // A oferta que falhou volta a ser candidata.
    let tg2 = FakeCanal::new(&r);
    rodar_em(&f, &tg2, &r, hora(10, 10), None).unwrap();
    assert_eq!(fotos(&tg2).len(), 1);
}

/// Telegram que, a cada envio, guarda o que o Oracle fake tem naquele instante.
struct Espiao<'a> {
    f: &'a FakeEnvio,
    visto: RefCell<Vec<Vec<RegistroEnvio>>>,
}

impl CanalTelegram for Espiao<'_> {
    fn enviar_foto(&self, _: &str, _: &[u8], _: &str, _: bool) -> Result<i64, ErroCanal> {
        self.visto.borrow_mut().push(self.f.envios());
        Ok(77)
    }
    fn editar_legenda(&self, _: &str, _: i64, _: &str) -> Result<(), ErroCanal> {
        Ok(())
    }
    fn enviar_mensagem(&self, _: &str, _: &str, _: bool) -> Result<i64, ErroCanal> {
        Ok(78)
    }
}

/// DUP-01: no instante do `sendPhoto` a linha já existe, sem `message_id`; depois, com ele.
#[test]
fn linha_gravada_antes_do_envio() {
    let f = fonte(1);
    let r = RelogioFake::em(hora(10, 0));
    let espiao = Espiao {
        f: &f,
        visto: RefCell::new(Vec::new()),
    };
    let m = mapeamento();
    rodar(&Contexto {
        fonte: &f,
        telegram: &espiao,
        relogio: &r,
        m: &m,
        dir_imagens: None,
        dir_avisos: None,
        foto: foto_rapida,
        canal: 1,
        pausa_ate: None,
    })
    .unwrap();
    let visto = espiao.visto.borrow();
    assert_eq!(visto.len(), 1);
    assert_eq!(visto[0].len(), 1);
    assert_eq!((visto[0][0].id_oferta, visto[0][0].message_id), (1, None));
    assert_eq!(f.envios()[0].message_id, Some(77));
}

/// DUP-02: Oracle falha antes do envio → 0 chamadas ao Telegram.
#[test]
fn falha_no_oracle_nao_envia() {
    let f = fonte(2);
    f.falhar_reserva(true);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let falha = rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap_err();
    assert_eq!(falha.fase, "reserva_oracle");
    assert!(tg.chamadas().is_empty());
}

/// EXP-01: oferta enviada expira → 1 edição com "Oferta encerrada", `DT_EDICAO` gravada; a
/// execução seguinte não edita de novo. Vale fora da janela.
#[test]
fn expirada_editada_uma_vez() {
    let f = fonte(1);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap();
    let message_id = fotos(&tg)[0].message_id;
    f.expirar(1);
    let tg2 = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg2, &r, hora(23, 0), None).unwrap();
    assert_eq!(rel.editadas, 1);
    let c = tg2.chamadas();
    assert_eq!(c.len(), 1);
    assert_eq!(c[0].metodo, "editMessageCaption");
    assert_eq!(c[0].message_id, message_id);
    assert!(
        c[0].legenda.starts_with("⛔ <b>Oferta encerrada</b>\n<s>"),
        "{}",
        c[0].legenda
    );
    assert!(!c[0].legenda.contains("href"));
    assert!(f.envios()[0].dt_edicao.is_some());
    let tg3 = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg3, &r, hora(23, 5), None).unwrap();
    assert_eq!(rel.editadas, 0);
    assert!(tg3.chamadas().is_empty());
}

/// EXP-02: 25 expiradas → 20 numa execução, 5 na seguinte.
#[test]
fn ate_20_edicoes_por_execucao() {
    let f = FakeEnvio::new(Parametros::default(), vec![]);
    for id in 1..=25 {
        let mut l = oferta(id);
        l.oferta.ativo = false;
        f.adicionar(l);
        f.registrar(RegistroEnvio {
            id_envio: id,
            canal: 1,
            id_oferta: id,
            id_produto: Some(id),
            preco_por: 10000,
            message_id: Some(id),
            dt_envio: hora(9, 0),
            dt_edicao: None,
        });
    }
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    assert_eq!(
        rodar_em(&f, &tg, &r, hora(23, 0), None).unwrap().editadas,
        20
    );
    assert_eq!(
        rodar_em(&f, &tg, &r, hora(23, 5), None).unwrap().editadas,
        5
    );
    assert_eq!(
        rodar_em(&f, &tg, &r, hora(23, 10), None).unwrap().editadas,
        0
    );
}

/// Edição recusada com 400 (post apagado) → marcada, não repetida.
#[test]
fn edicao_recusada_nao_repete() {
    let f = fonte(1);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap();
    f.expirar(1);
    tg.roteirizar([Err(ErroCanal::Recusada {
        status: 400,
        descricao: "message to edit not found".into(),
    })]);
    let rel = rodar_em(&f, &tg, &r, hora(23, 0), None).unwrap();
    assert_eq!((rel.editadas, rel.edicoes_descartadas), (0, 1));
    assert!(f.envios()[0].dt_edicao.is_some());
}

/// LIM-01: 429 → código 0, só o já confirmado fica gravado, `retry_after` relatado.
#[test]
fn limite_429_encerra_com_sucesso() {
    let f = fonte(2);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Ok(()), Err(ErroCanal::Limite(37))]);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap();
    assert_eq!(rel.retry_after, Some(37));
    assert_eq!(rel.enviados, 1);
    let envios = f.envios();
    assert_eq!(envios.len(), 1);
    assert!(envios[0].message_id.is_some());
    // O estado guarda o fim da espera.
    let e = EstadoEnvio::depois(&rel, hora(10, 0), EstadoEnvio::default());
    assert_eq!(e.pausa_ate, Some(hora(10, 0) + 37));
}

/// LIM-02: durante a pausa, 0 chamadas e código 0; depois dela, volta a enviar.
#[test]
fn pausa_respeitada() {
    let f = fonte(2);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let pausa = Some(hora(10, 0) + 400);
    let rel = rodar_em(&f, &tg, &r, hora(10, 5), pausa).unwrap();
    assert_eq!(rel.parada, Some(Parada::Pausa));
    assert!(tg.chamadas().is_empty());
    // A pausa sobrevive a execuções puladas e some depois de uma execução normal.
    let e = EstadoEnvio::depois(&rel, hora(10, 5), EstadoEnvio { pausa_ate: pausa });
    assert_eq!(e.pausa_ate, pausa);
    let rel = rodar_em(&f, &tg, &r, hora(10, 10), pausa).unwrap();
    assert_eq!(rel.enviados, 2);
    assert_eq!(EstadoEnvio::depois(&rel, hora(10, 10), e).pausa_ate, None);
}

/// Canal inativo → nada a fazer, sem falha.
#[test]
fn canal_inativo_nao_envia() {
    let f = fonte(2).com_canal(Canal {
        id: 1,
        chat_id: "@x".into(),
        ativo: false,
    });
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap();
    assert_eq!(rel.parada, Some(Parada::CanalInativo));
    assert!(tg.chamadas().is_empty());
}

/// Dois posts antigos (ids 501, 502) de ofertas que expiraram, prontos para edição.
fn duas_expiradas() -> FakeEnvio {
    let f = FakeEnvio::new(Parametros::default(), vec![]);
    for (id_envio, id) in [(1, 501), (2, 502)] {
        let mut l = oferta(id);
        l.oferta.ativo = false;
        f.adicionar(l);
        f.registrar(RegistroEnvio {
            id_envio,
            canal: 1,
            id_oferta: id,
            id_produto: Some(id),
            preco_por: 10000,
            message_id: Some(id),
            dt_envio: hora(9, 0),
            dt_edicao: None,
        });
    }
    f
}

/// LIM-01 nas edições: 429 na segunda edição → código 0, só a primeira com `DT_EDICAO`,
/// `retry_after` relatado e a pausa calculada a partir dele.
#[test]
fn limite_429_na_edicao() {
    let f = duas_expiradas();
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Ok(()), Err(ErroCanal::Limite(30))]);
    let rel = rodar_em(&f, &tg, &r, hora(23, 0), None).unwrap();
    assert_eq!(rel.editadas, 1);
    assert_eq!(rel.retry_after, Some(30));
    let editadas: Vec<i64> = f
        .envios()
        .iter()
        .filter(|e| e.dt_edicao.is_some())
        .map(|e| e.id_oferta)
        .collect();
    assert_eq!(editadas.len(), 1, "{editadas:?}");
    let e = EstadoEnvio::depois(&rel, hora(23, 0), EstadoEnvio::default());
    assert_eq!(e.pausa_ate, Some(hora(23, 0) + 30));
}

/// Erro na edição que não é 400 nem 429 → falha (código 1) sem marcar a edição.
#[test]
fn erro_na_edicao_falha_sem_marcar() {
    let f = duas_expiradas();
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Err(ErroCanal::Timeout(30))]);
    let falha = rodar_em(&f, &tg, &r, hora(23, 0), None).unwrap_err();
    assert_eq!(falha.codigo, Codigo::Falha);
    assert_eq!(falha.fase, "edicao_telegram");
    assert!(f.envios().iter().all(|e| e.dt_edicao.is_none()));
}
