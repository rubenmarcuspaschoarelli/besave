//! BSV-41 ENV-01..04, ENV-08..13, ENV-15..16: aviso nas execuções do envio, com Oracle, Telegram e
//! relógio falsos.

mod comum;

use std::cell::RefCell;
use std::path::{Path, PathBuf};

use comum::{linha_canal, mapeamento};
use image::codecs::jpeg::JpegEncoder;
use image::{ImageEncoder, ImageFormat, Rgb, RgbImage};
use worker::avisos::modelo::LinhaAviso;
use worker::envio::aviso::legenda_aviso;
use worker::envio::binario::texto_simulacao;
use worker::envio::canal::{CanalTelegram, Chamada, ErroCanal, FakeCanal, RelogioFake};
use worker::envio::fonte::{AvisoCanal, FakeEnvio, LigacaoAviso, RegistroAviso};
use worker::envio::foto::OrigemFoto;
use worker::envio::http::{ConfigCanal, pedido_mensagem};
use worker::envio::modelo::{LinhaCanal, Parametros};
use worker::envio::rodada::{Contexto, RelatorioEnvio, rodar, simular};
use worker::execucao::Falha;
use worker::imagens::ErroImagem;
use worker::modelo::Area;

/// 2026-09-24 00:00 em Brasília (03:00Z).
const DIA0: i64 = 1_790_218_800;

fn hora(h: i64, m: i64) -> i64 {
    DIA0 + h * 3600 + m * 60
}

/// Oferta com 50% de desconto e página no ar (vale o dia inteiro).
fn oferta(id: i64) -> LinhaCanal {
    let mut l = linha_canal(id, Some(200.0), 100.0);
    l.oferta.dt_oferta = Some(hora(7, 0));
    l.dt_publicacao_site = Some(hora(7, 0));
    l
}

fn linha_aviso(id: i64) -> LinhaAviso {
    LinhaAviso {
        id,
        titulo: format!("Aviso {id}"),
        texto: "Os links deste canal são de afiliado.".into(),
        ativo: true,
        dt_inicio: DIA0 - 86_400,
        dt_publicacao_site: Some(DIA0 - 3600),
        ..Default::default()
    }
}

fn ligar(f: &FakeEnvio, a: LinhaAviso) {
    f.ligar_aviso(LigacaoAviso {
        canal: 1,
        aviso: a,
        intervalo_min: 120,
        ativo: true,
    });
}

/// `n` ofertas e o aviso 1 (sem imagem, intervalo 120) ligado ao canal 1.
fn fonte(n: i64) -> FakeEnvio {
    let f = FakeEnvio::new(Parametros::default(), (1..=n).map(oferta).collect());
    ligar(&f, linha_aviso(1));
    f
}

fn foto_rapida(_: Option<&Path>, id: i64, area: Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem> {
    Ok((vec![0xFF, 0xD8, id as u8], OrigemFoto::Placeholder(area)))
}

fn contexto<'a>(
    f: &'a FakeEnvio,
    tg: &'a dyn CanalTelegram,
    r: &'a RelogioFake,
    m: &'a worker::mapeamento::Mapeamento,
    dir_avisos: Option<&'a Path>,
) -> Contexto<'a> {
    Contexto {
        fonte: f,
        telegram: tg,
        relogio: r,
        m,
        dir_imagens: None,
        dir_avisos,
        foto: foto_rapida,
        canal: 1,
        pausa_ate: None,
    }
}

fn rodar_em(
    f: &FakeEnvio,
    tg: &dyn CanalTelegram,
    r: &RelogioFake,
    t: i64,
) -> Result<RelatorioEnvio, Falha> {
    r.definir(t);
    let m = mapeamento();
    rodar(&contexto(f, tg, r, &m, None))
}

fn de(tg: &FakeCanal, metodo: &str) -> Vec<Chamada> {
    tg.chamadas()
        .into_iter()
        .filter(|c| c.metodo == metodo)
        .collect()
}

/// ENV-01..03: intervalo 120 → enviado às 08:00, não às 09:55, de novo às 10:00.
#[test]
fn intervalo_120_minutos() {
    let f = fonte(0);
    let r = RelogioFake::em(hora(8, 0));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(8, 0)).unwrap();
    assert_eq!(rel.aviso, Some(1));
    assert_eq!(de(&tg, "sendMessage").len(), 1);
    for t in [hora(8, 5), hora(9, 0), hora(9, 55)] {
        let rel = rodar_em(&f, &tg, &r, t).unwrap();
        assert_eq!(rel.aviso, None);
    }
    assert_eq!(de(&tg, "sendMessage").len(), 1);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert_eq!(rel.aviso, Some(1));
    assert_eq!(de(&tg, "sendMessage").len(), 2);
    let envios = f.envios_aviso();
    assert_eq!(envios.len(), 2);
    assert_eq!(envios[0].dt_envio, hora(8, 0));
    assert_eq!(envios[1].dt_envio, hora(10, 0));
}

/// ENV-04: fora de `[08:00, 22:00)` nenhum aviso, mesmo nunca enviado.
#[test]
fn fora_da_janela_nao_envia() {
    let f = fonte(0);
    let r = RelogioFake::em(hora(7, 55));
    let tg = FakeCanal::new(&r);
    for t in [hora(7, 55), hora(22, 0), hora(23, 30), hora(3, 0)] {
        let rel = rodar_em(&f, &tg, &r, t).unwrap();
        assert_eq!(rel.aviso, None);
    }
    assert!(tg.chamadas().is_empty());
    assert!(f.envios_aviso().is_empty());
}

/// ENV-05 (na execução): dois vencidos → só o mais atrasado, um por execução.
#[test]
fn dois_vencidos_so_o_mais_atrasado() {
    let f = fonte(0);
    ligar(&f, linha_aviso(2));
    f.registrar_aviso(RegistroAviso {
        id_envio: 1,
        aviso: 1,
        canal: 1,
        message_id: Some(5),
        dt_envio: hora(6, 0),
    });
    f.registrar_aviso(RegistroAviso {
        id_envio: 2,
        aviso: 2,
        canal: 1,
        message_id: Some(6),
        dt_envio: hora(5, 0),
    });
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert_eq!(rel.aviso, Some(2));
    assert_eq!(de(&tg, "sendMessage").len(), 1);
    assert!(de(&tg, "sendMessage")[0].legenda.contains("Aviso 2"));
}

/// ENV-06: `DT_PUBLICACAO_SITE` nula → não envia.
#[test]
fn sem_data_de_publicacao_nao_envia() {
    let f = FakeEnvio::new(Parametros::default(), vec![]);
    ligar(
        &f,
        LinhaAviso {
            dt_publicacao_site: None,
            ..linha_aviso(1)
        },
    );
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert_eq!(rel.aviso, None);
    assert!(tg.chamadas().is_empty());
}

/// ENV-08: o aviso não reduz o lote de ofertas nem conta em `enviados_hoje`.
#[test]
fn aviso_nao_reduz_a_cota() {
    let com = fonte(10);
    let sem = FakeEnvio::new(Parametros::default(), (1..=10).map(oferta).collect());
    let r = RelogioFake::em(hora(10, 0));
    let (tg_com, tg_sem) = (FakeCanal::new(&r), FakeCanal::new(&r));
    let a = rodar_em(&com, &tg_com, &r, hora(10, 0)).unwrap();
    let b = rodar_em(&sem, &tg_sem, &r, hora(10, 0)).unwrap();
    assert_eq!(a.aviso, Some(1));
    assert_eq!(a.devido, b.devido);
    assert_eq!(a.enviados, b.enviados);
    assert_eq!(a.enviados, Parametros::default().qt_por_execucao);
    assert_eq!(
        de(&tg_com, "sendPhoto").len(),
        de(&tg_sem, "sendPhoto").len()
    );
    // Execução seguinte: `enviados_hoje` conta só ofertas.
    let a2 = rodar_em(&com, &tg_com, &r, hora(10, 5)).unwrap();
    let b2 = rodar_em(&sem, &tg_sem, &r, hora(10, 5)).unwrap();
    assert_eq!(a2.enviados_hoje, b2.enviados_hoje);
    assert_eq!(
        a2.enviados_hoje,
        u64::from(Parametros::default().qt_por_execucao)
    );
}

/// ENV-08 no teto: 178 de 180 enviados hoje, 21:55 (esperado = 180) → o lote de 2 sai mesmo com o aviso enviado
/// antes dele (se o aviso contasse, sobraria 1 < L e o lote seria 0).
#[test]
fn aviso_nao_conta_perto_do_teto() {
    let f = fonte(10);
    for i in 0..178 {
        f.registrar(worker::envio::fonte::RegistroEnvio {
            id_envio: i + 1,
            canal: 1,
            id_oferta: 5000 + i,
            id_produto: Some(5000 + i),
            preco_por: 100,
            message_id: Some(i + 1),
            dt_envio: hora(8, 0) + i * 60,
            dt_edicao: None,
        });
    }
    let r = RelogioFake::em(hora(21, 55));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(21, 55)).unwrap();
    assert_eq!(rel.aviso, Some(1));
    assert_eq!(rel.enviados_hoje, 178);
    assert_eq!(rel.devido, 2);
    assert_eq!(rel.enviados, 2);
    assert_eq!(de(&tg, "sendPhoto").len(), 2);
    assert_eq!(de(&tg, "sendMessage").len(), 1);
}

/// Telegram que, a cada envio, guarda o `ENVIO_AVISO` do fake naquele instante.
struct Espiao<'a> {
    f: &'a FakeEnvio,
    visto: RefCell<Vec<Vec<RegistroAviso>>>,
}

impl CanalTelegram for Espiao<'_> {
    fn enviar_foto(&self, _: &str, _: &[u8], _: &str, _: bool) -> Result<i64, ErroCanal> {
        Ok(70)
    }
    fn editar_legenda(&self, _: &str, _: i64, _: &str) -> Result<(), ErroCanal> {
        Ok(())
    }
    fn enviar_mensagem(&self, _: &str, _: &str, _: bool) -> Result<i64, ErroCanal> {
        self.visto.borrow_mut().push(self.f.envios_aviso());
        Ok(88)
    }
}

/// ENV-09: no instante do envio a linha já existe, sem `message_id`; depois, com ele.
#[test]
fn linha_reservada_antes_do_envio() {
    let f = fonte(0);
    let r = RelogioFake::em(hora(10, 0));
    let espiao = Espiao {
        f: &f,
        visto: RefCell::new(Vec::new()),
    };
    rodar_em(&f, &espiao, &r, hora(10, 0)).unwrap();
    let visto = espiao.visto.borrow();
    assert_eq!(visto.len(), 1);
    assert_eq!(visto[0].len(), 1);
    assert_eq!(visto[0][0].aviso, 1);
    assert_eq!(visto[0][0].message_id, None);
    assert_eq!(f.envios_aviso()[0].message_id, Some(88));
}

/// ENV-10: Telegram recusa o aviso → linha apagada, WARN no relatório e o lote segue.
#[test]
fn falha_no_aviso_nao_impede_o_lote() {
    for erro in [
        ErroCanal::Recusada {
            status: 400,
            descricao: "Bad Request".into(),
        },
        ErroCanal::Http(502),
        ErroCanal::Timeout(30),
    ] {
        let f = fonte(10);
        let r = RelogioFake::em(hora(10, 0));
        let tg = FakeCanal::new(&r);
        tg.roteirizar([Err(erro.clone())]);
        let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
        assert!(f.envios_aviso().is_empty(), "{erro:?}");
        assert!(rel.aviso_falhou, "{erro:?}");
        assert_eq!(rel.aviso, None);
        assert_eq!(rel.enviados, 2, "{erro:?}");
        assert_eq!(de(&tg, "sendPhoto").len(), 2);
        assert!(
            rel.linha(0).contains("aviso=- aviso_falhou=1"),
            "{}",
            rel.linha(0)
        );
    }
}

/// Falha do Oracle ao ler os avisos → lote segue.
#[test]
fn falha_ao_ler_avisos_nao_impede_o_lote() {
    let f = fonte(10);
    f.falhar_avisos(true);
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert!(rel.aviso_falhou);
    assert_eq!(rel.enviados, 2);
}

/// ENV-11: 429 no aviso → linha apagada, execução encerrada sem lote.
#[test]
fn limite_no_aviso_encerra_a_execucao() {
    let f = fonte(10);
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Err(ErroCanal::Limite(30))]);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert_eq!(rel.retry_after, Some(30));
    assert_eq!(rel.enviados, 0);
    assert!(de(&tg, "sendPhoto").is_empty());
    assert!(f.envios_aviso().is_empty());
    assert!(f.envios().is_empty());
}

/// ENV-12: sem imagem → `sendMessage` com a legenda do aviso; `message_id` confirmado.
#[test]
fn sem_imagem_vai_send_message() {
    let f = fonte(0);
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    let msgs = de(&tg, "sendMessage");
    assert_eq!(msgs.len(), 1);
    assert_eq!(msgs[0].chat_id, "@besaveofertas");
    let esperado = legenda_aviso(&AvisoCanal {
        aviso: linha_aviso(1),
        intervalo_min: 120,
        ativo: true,
        ultimo_envio: None,
    });
    assert_eq!(msgs[0].legenda, esperado);
    assert!(de(&tg, "sendPhoto").is_empty());
    assert_eq!(f.envios_aviso()[0].message_id, Some(msgs[0].message_id));
}

/// `sendMessage` real: JSON com `text`, HTML e prévia do link ligada.
#[test]
fn pedido_send_message() {
    let cfg =
        ConfigCanal::de(|k| (k == "TELEGRAM_CANAL_BOT_TOKEN").then(|| "1:tok".into())).unwrap();
    let req = pedido_mensagem(&cfg, "@besaveofertas", "<b>Oi</b>", true).unwrap();
    assert_eq!(req.uri().path(), "/bot1:tok/sendMessage");
    let v: serde_json::Value = serde_json::from_slice(req.body()).unwrap();
    assert_eq!(v["chat_id"], "@besaveofertas");
    assert_eq!(v["text"], "<b>Oi</b>");
    assert_eq!(v["parse_mode"], "HTML");
    assert_eq!(v["disable_notification"], true);
    assert_eq!(v["link_preview_options"]["is_disabled"], false);
    assert!(v.get("disable_web_page_preview").is_none());
}

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-envio-aviso-{nome}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn jpg(dir: &Path, nome: &str) {
    let img = RgbImage::from_pixel(300, 100, Rgb([0, 0, 220]));
    let mut bytes = Vec::new();
    JpegEncoder::new(&mut bytes)
        .write_image(img.as_raw(), 300, 100, image::ExtendedColorType::Rgb8)
        .unwrap();
    std::fs::write(dir.join(nome), bytes).unwrap();
}

/// ENV-13: com imagem `.jpg` → `sendPhoto` com JPEG 800×800 e a legenda do aviso.
#[test]
fn com_imagem_vai_send_photo() {
    let dir = dir_temp("foto");
    jpg(&dir, "aviso.jpg");
    let f = FakeEnvio::new(Parametros::default(), vec![]);
    ligar(
        &f,
        LinhaAviso {
            imagem: Some("aviso.jpg".into()),
            ..linha_aviso(1)
        },
    );
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    let rel = rodar(&contexto(&f, &tg, &r, &m, Some(&dir))).unwrap();
    assert_eq!(rel.aviso, Some(1));
    let fotos = de(&tg, "sendPhoto");
    assert_eq!(fotos.len(), 1);
    assert!(de(&tg, "sendMessage").is_empty());
    assert!(fotos[0].legenda.starts_with("<b>Aviso 1</b>\n"));
    let img = image::load_from_memory_with_format(&fotos[0].jpeg, ImageFormat::Jpeg).unwrap();
    assert_eq!((img.width(), img.height()), (800, 800));
}

/// ENV-14 (na execução): `.png` → aviso ignorado, nada enviado.
#[test]
fn imagem_png_nao_envia() {
    let f = FakeEnvio::new(Parametros::default(), vec![]);
    ligar(
        &f,
        LinhaAviso {
            imagem: Some("aviso.png".into()),
            ..linha_aviso(1)
        },
    );
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    assert_eq!(rel.aviso, None);
    assert!(tg.chamadas().is_empty());
}

/// ENV-15: silencioso segue o horário de som (09:00–21:00).
#[test]
fn silencioso_do_canal() {
    let f = fonte(0);
    let r = RelogioFake::em(hora(8, 0));
    let tg = FakeCanal::new(&r);
    rodar_em(&f, &tg, &r, hora(8, 0)).unwrap();
    rodar_em(&f, &tg, &r, hora(10, 0)).unwrap();
    let msgs = de(&tg, "sendMessage");
    assert_eq!(msgs.len(), 2);
    assert!(msgs[0].silencioso);
    assert!(!msgs[1].silencioso);
}

/// ENV-16: `--sim` mostra o aviso devido, sem Telegram e sem escrita.
#[test]
fn simulacao_mostra_o_aviso() {
    let f = fonte(3);
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    let sim = simular(&contexto(&f, &tg, &r, &m, None)).unwrap();
    assert!(tg.chamadas().is_empty());
    assert!(f.envios_aviso().is_empty());
    let a = sim.aviso.clone().unwrap();
    assert_eq!(a.id, 1);
    assert!(a.legenda.contains("/avisos/1/?utm_source=telegram"));
    assert_eq!(a.jpeg, None);
    let t = texto_simulacao(&sim, &[]);
    assert!(
        t.contains("aviso 1 (sendMessage, na janela: vai agora)"),
        "{t}"
    );
    assert!(t.contains(&a.legenda), "{t}");

    // Fora da janela: mostra, avisando que não vai agora.
    r.definir(hora(23, 0));
    let sim = simular(&contexto(&f, &tg, &r, &m, None)).unwrap();
    let t = texto_simulacao(&sim, &[]);
    assert!(t.contains("fora da janela: não vai agora"), "{t}");
}
