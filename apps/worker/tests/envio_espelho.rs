//! BSV-62 ESP-01..05: espelho do post confirmado no Telegram na fila do WhatsApp, com Oracle,
//! Telegram e relógio falsos (como os testes da BSV-40).

mod comum;

use comum::{linha_canal, mapeamento};

use worker::avisos::modelo::LinhaAviso;
use worker::envio::binario::{espelho_do_env, texto_simulacao};
use worker::envio::canal::{ErroCanal, FakeCanal, RelogioFake};
use worker::envio::fonte::{FakeEnvio, FilaWhatsapp, FonteEnvio, LigacaoAviso, RegistroEnvio};
use worker::envio::foto::OrigemFoto;
use worker::envio::frases::Frases;
use worker::envio::legenda::legenda_whatsapp;
use worker::envio::modelo::{LinhaCanal, Parametros, para_canal};
use worker::envio::oracle::SQL_ENFILEIRAR_WHATSAPP;
use worker::envio::rodada::{Contexto, RelatorioEnvio, rodar, simular};
use worker::envio::site::Imagens;
use worker::execucao::Falha;
use worker::imagens::ErroImagem;
use worker::modelo::Area;

/// 2026-09-24 00:00 em Brasília (03:00Z).
const DIA0: i64 = 1_790_218_800;

fn hora(h: i64, m: i64) -> i64 {
    DIA0 + h * 3600 + m * 60
}

/// Oferta com 50% de desconto, área Meu Lar e página no ar.
fn oferta(id: i64) -> LinhaCanal {
    let mut l = linha_canal(id, Some(200.0), 100.0);
    l.oferta.dt_oferta = Some(hora(7, 0));
    l.oferta.area = Some("MEU LAR".into());
    l.dt_publicacao_site = Some(hora(7, 0));
    l
}

fn fonte(n: i64) -> FakeEnvio {
    FakeEnvio::new(Parametros::default(), (1..=n).map(oferta).collect())
}

fn foto_rapida(_: &Imagens, id: i64, area: Area) -> Result<(Vec<u8>, OrigemFoto), ErroImagem> {
    Ok((vec![0xFF, 0xD8, id as u8], OrigemFoto::Placeholder(area)))
}

fn frases() -> Frases {
    Frases::embutidas().unwrap()
}

fn rodar_em(
    f: &FakeEnvio,
    tg: &FakeCanal,
    r: &RelogioFake,
    t: i64,
    espelho: Option<i64>,
) -> Result<RelatorioEnvio, Falha> {
    r.definir(t);
    let m = mapeamento();
    rodar(&Contexto {
        fonte: f,
        telegram: tg,
        relogio: r,
        m: &m,
        imagens: Imagens::pasta(None),
        avisos: Imagens::pasta(None),
        foto: foto_rapida,
        frases: &frases(),
        espelho_whatsapp: espelho,
        canal: 1,
        pausa_ate: None,
    })
}

/// ESP-01: Telegram confirma → 1 linha por post, com a legenda do WhatsApp, o `ID_ENVIO` do
/// Telegram, o slug da área e a hora da fila.
#[test]
fn post_confirmado_vai_para_a_fila() {
    let f = fonte(2);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap();
    assert_eq!(rel.enviados, 2);
    assert_eq!(rel.espelhados, 2);
    assert_eq!(rel.espelho_falhas, 0);
    let envios = f.envios();
    let fila = f.fila_whatsapp();
    assert_eq!(fila.len(), 2, "{fila:?}");
    let m = mapeamento();
    for l in &fila {
        let e = envios.iter().find(|e| e.id_oferta == l.id_oferta).unwrap();
        assert!(e.message_id.is_some(), "só post confirmado entra");
        let o = para_canal(&oferta(l.id_oferta), &m).unwrap();
        assert_eq!(
            l,
            &FilaWhatsapp {
                canal: 2,
                id_oferta: o.id,
                id_envio_telegram: e.id_envio,
                legenda: legenda_whatsapp(&o, false, &Parametros::default(), &frases()),
                area_slug: "meu-lar".into(),
                dt_fila: l.dt_fila,
            }
        );
        assert!(l.dt_fila >= hora(10, 0) && l.dt_fila <= hora(10, 1));
        assert!(
            l.legenda
                .contains(&format!("https://besave.io/{}?utm_source=whatsapp", o.id))
        );
    }
    assert!(
        rel.linha(0).contains("espelhados=2 espelho_falhas=0"),
        "{}",
        rel.linha(0)
    );
}

/// ESP-01: a linha nasce `P` (o INSERT do Oracle grava o status e a sequence).
#[test]
fn insert_do_oracle_grava_pendente() {
    let sql: String = SQL_ENFILEIRAR_WHATSAPP
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    assert_eq!(
        sql,
        "INSERT INTO ENVIO_WHATSAPP (ID_ENVIO_WA, ID_CANAL, ID_OFERTA, ID_ENVIO_TELEGRAM, \
         DS_LEGENDA, DS_AREA_SLUG, ST_ENVIO, DT_FILA) VALUES (SQ_ENVIO_WHATSAPP.NEXTVAL, :1, :2, \
         :3, :4, :5, 'P', DATE '1970-01-01' + :6 / 86400)"
    );
}

/// ESP-02: Telegram falha → nenhuma linha na fila.
#[test]
fn falha_do_telegram_nao_enfileira() {
    let f = fonte(1);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Err(ErroCanal::Recusada {
        status: 400,
        descricao: "Bad Request".into(),
    })]);
    assert!(rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).is_err());
    assert!(f.fila_whatsapp().is_empty());
    // 429 também não enfileira.
    let tg = FakeCanal::new(&r);
    tg.roteirizar([Err(ErroCanal::Limite(30))]);
    let rel = rodar_em(&f, &tg, &r, hora(10, 5), Some(2)).unwrap();
    assert_eq!(rel.retry_after, Some(30));
    assert!(f.fila_whatsapp().is_empty());
}

/// ESP-01: a linha só entra depois do `confirmar`. Confirmação falhou → execução falha e a fila
/// fica vazia.
#[test]
fn sem_confirmacao_nao_enfileira() {
    let f = fonte(1);
    f.falhar_confirmacao(true);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let falha = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap_err();
    assert_eq!(falha.fase, "confirmacao_oracle");
    assert!(f.fila_whatsapp().is_empty(), "{:?}", f.fila_whatsapp());
}

/// ESP-01: o "caiu" do post do Telegram vai também na legenda da fila.
#[test]
fn caiu_vai_para_a_fila() {
    let f = fonte(1);
    // Mesmo produto (id_produto 1) enviado há 1 h a R$ 200,00: hoje R$ 100,00 é queda de 50%.
    f.registrar(RegistroEnvio {
        id_envio: 10,
        canal: 1,
        id_oferta: 99,
        id_produto: Some(1),
        preco_por: 20000,
        message_id: Some(500),
        dt_envio: DIA0 - 3600,
        dt_edicao: None,
    });
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap();
    assert_eq!(rel.enviados, 1);
    let fila = f.fila_whatsapp();
    assert_eq!(fila.len(), 1, "{fila:?}");
    let o = para_canal(&oferta(1), &mapeamento()).unwrap();
    assert_eq!(
        fila[0].legenda,
        legenda_whatsapp(&o, true, &Parametros::default(), &frases())
    );
    assert!(
        fila[0].legenda.contains("\n📉 *Caiu mais o preço!!!*\n"),
        "{}",
        fila[0].legenda
    );
    let posts = tg.chamadas();
    assert!(posts[0].legenda.contains("📉 <b>Caiu mais o preço!!!</b>"));
}

/// ESP-02: sem a variável → nenhuma linha (comportamento de antes).
#[test]
fn sem_variavel_nao_enfileira() {
    let f = fonte(2);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), None).unwrap();
    assert_eq!(rel.enviados, 2);
    assert_eq!(rel.espelhados, 0);
    assert!(f.fila_whatsapp().is_empty());
}

/// ESP-02: valor da variável. Ausente, vazia ou inválida → sem espelho.
#[test]
fn variavel_do_espelho() {
    assert_eq!(espelho_do_env(None), None);
    assert_eq!(espelho_do_env(Some("")), None);
    assert_eq!(espelho_do_env(Some("  ")), None);
    assert_eq!(espelho_do_env(Some("2")), Some(2));
    assert_eq!(espelho_do_env(Some(" 2 ")), Some(2));
    assert_eq!(espelho_do_env(Some("whatsapp")), None);
}

/// ESP-03: falha ao inserir → a execução termina bem (código 0), o post do Telegram fica
/// confirmado e o lote segue.
#[test]
fn falha_na_fila_nao_desfaz_o_telegram() {
    let f = fonte(2);
    f.falhar_fila(true);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap();
    assert_eq!(rel.enviados, 2, "o lote seguiu");
    assert_eq!(rel.espelho_falhas, 2);
    assert_eq!(rel.espelhados, 0);
    let envios = f.envios();
    assert_eq!(envios.len(), 2);
    assert!(envios.iter().all(|e| e.message_id.is_some()), "{envios:?}");
    assert!(f.fila_whatsapp().is_empty());
}

/// ESP-04: a mesma oferta duas vezes → 1 linha, sem erro.
#[test]
fn duplicata_ignorada() {
    let f = fonte(0);
    let l = FilaWhatsapp {
        canal: 2,
        id_oferta: 7,
        id_envio_telegram: 1,
        legenda: "x".into(),
        area_slug: "tech".into(),
        dt_fila: DIA0,
    };
    assert!(f.enfileirar_whatsapp(&l).unwrap());
    assert!(!f.enfileirar_whatsapp(&l).unwrap());
    assert_eq!(f.fila_whatsapp().len(), 1);

    // Pela execução: a oferta já na fila não gera erro nem segunda linha.
    let f = fonte(1);
    f.enfileirar_whatsapp(&FilaWhatsapp { id_oferta: 1, ..l })
        .unwrap();
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap();
    assert_eq!(rel.enviados, 1);
    assert_eq!((rel.espelhados, rel.espelho_falhas), (0, 0));
    assert_eq!(f.fila_whatsapp().len(), 1);
}

/// ESP-05: aviso e "Oferta encerrada" não entram na fila.
#[test]
fn aviso_e_encerrada_nao_espelham() {
    let f = fonte(0);
    f.ligar_aviso(LigacaoAviso {
        canal: 1,
        aviso: LinhaAviso {
            id: 1,
            titulo: "Aviso 1".into(),
            texto: "Os links deste canal são de afiliado.".into(),
            ativo: true,
            dt_inicio: DIA0 - 86_400,
            dt_publicacao_site: Some(DIA0 - 3600),
            ..Default::default()
        },
        intervalo_min: 120,
        ativo: true,
    });
    f.adicionar(oferta(9));
    f.registrar(RegistroEnvio {
        id_envio: 50,
        canal: 1,
        id_oferta: 9,
        id_produto: Some(9),
        preco_por: 10000,
        message_id: Some(777),
        dt_envio: hora(8, 0),
        dt_edicao: None,
    });
    f.expirar(9);
    let r = RelogioFake::em(DIA0);
    let tg = FakeCanal::new(&r);
    let rel = rodar_em(&f, &tg, &r, hora(10, 0), Some(2)).unwrap();
    assert_eq!(rel.aviso, Some(1));
    assert_eq!(rel.editadas, 1);
    assert_eq!(rel.enviados, 0);
    assert!(f.fila_whatsapp().is_empty(), "{:?}", f.fila_whatsapp());
}

/// `--sim` com o espelho: a prévia mostra a legenda do WhatsApp e nada vai para a fila.
#[test]
fn simulacao_mostra_a_legenda_do_whatsapp() {
    let f = fonte(1);
    let r = RelogioFake::em(hora(10, 0));
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    let ctx = |espelho| Contexto {
        fonte: &f,
        telegram: &tg,
        relogio: &r,
        m: &m,
        imagens: Imagens::pasta(None),
        avisos: Imagens::pasta(None),
        foto: foto_rapida,
        frases: &FRASES,
        espelho_whatsapp: espelho,
        canal: 1,
        pausa_ate: None,
    };
    let sim = simular(&ctx(Some(2))).unwrap();
    let o = para_canal(&oferta(1), &m).unwrap();
    let wa = legenda_whatsapp(&o, false, &Parametros::default(), &FRASES);
    assert_eq!(
        sim.previas[0].legenda_whatsapp.as_deref(),
        Some(wa.as_str())
    );
    assert!(texto_simulacao(&sim, &[]).contains(&format!("na fila do WhatsApp\n{wa}")));
    assert!(f.fila_whatsapp().is_empty());
    assert_eq!(
        simular(&ctx(None)).unwrap().previas[0].legenda_whatsapp,
        None
    );
}

static FRASES: std::sync::LazyLock<Frases> = std::sync::LazyLock::new(frases);
