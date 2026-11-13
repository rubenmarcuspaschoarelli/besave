//! BSV-61 IMG-01..03, AVI-01, PRE-01..03, CFG-01: fotos do envio pelo site, com HTTP e disco falsos.

mod comum;

use std::cell::RefCell;
use std::path::{Path, PathBuf};

use comum::mapeamento;
use image::codecs::jpeg::JpegEncoder;
use image::codecs::webp::WebPEncoder;
use image::{ImageEncoder, ImageFormat, Rgba, RgbaImage};
use worker::avisos::modelo::LinhaAviso;
use worker::envio::aviso::foto_aviso_de;
use worker::envio::canal::{FakeCanal, RelogioFake};
use worker::envio::fonte::{FakeEnvio, LigacaoAviso};
use worker::envio::foto::{OrigemFoto, foto, foto_de};
use worker::envio::modelo::Parametros;
use worker::envio::rodada::{Contexto, rodar};
use worker::envio::site::{
    BaixarHttps, ErroBaixa, ErroBase, Imagens, LerDisco, MAX_BYTES, TIMEOUT, base, base_do_env, url,
};
use worker::modelo::Area;

const OFERTAS: &str = "https://besave.com.br/img/ofertas/";
const AVISOS: &str = "https://besave.com.br/img/avisos/";

/// Responde sempre o mesmo e guarda as URLs pedidas.
struct FakeHttp {
    resposta: Result<(u16, Vec<u8>), ErroBaixa>,
    urls: RefCell<Vec<String>>,
}

impl FakeHttp {
    fn new(resposta: Result<(u16, Vec<u8>), ErroBaixa>) -> Self {
        Self {
            resposta,
            urls: RefCell::default(),
        }
    }
    fn ok(corpo: Vec<u8>) -> Self {
        Self::new(Ok((200, corpo)))
    }
    fn urls(&self) -> Vec<String> {
        self.urls.borrow().clone()
    }
}

impl BaixarHttps for FakeHttp {
    fn baixar(&self, url: &str) -> Result<(u16, Vec<u8>), ErroBaixa> {
        self.urls.borrow_mut().push(url.to_owned());
        self.resposta.clone()
    }
}

/// Conta leituras e devolve sempre o mesmo conteúdo.
struct FakeDisco {
    conteudo: Vec<u8>,
    lidos: RefCell<Vec<PathBuf>>,
}

impl FakeDisco {
    fn new(conteudo: Vec<u8>) -> Self {
        Self {
            conteudo,
            lidos: RefCell::default(),
        }
    }
    fn leituras(&self) -> usize {
        self.lidos.borrow().len()
    }
}

impl LerDisco for FakeDisco {
    fn ler(&self, caminho: &Path) -> std::io::Result<Vec<u8>> {
        self.lidos.borrow_mut().push(caminho.to_owned());
        Ok(self.conteudo.clone())
    }
}

/// WebP sólido vermelho `w × h`.
fn webp(w: u32, h: u32) -> Vec<u8> {
    let img = RgbaImage::from_pixel(w, h, Rgba([220, 0, 0, 255]));
    let mut b = Vec::new();
    WebPEncoder::new_lossless(&mut b)
        .write_image(img.as_raw(), w, h, image::ExtendedColorType::Rgba8)
        .unwrap();
    b
}

fn jpg() -> Vec<u8> {
    let img = image::RgbImage::from_pixel(300, 100, image::Rgb([0, 0, 220]));
    let mut b = Vec::new();
    JpegEncoder::new_with_quality(&mut b, 90)
        .write_image(img.as_raw(), 300, 100, image::ExtendedColorType::Rgb8)
        .unwrap();
    b
}

/// WebP válido completado com zeros até `n` bytes (o decodificador ignora o que vem depois).
fn webp_com(n: usize) -> Vec<u8> {
    let mut b = webp(40, 20);
    b.resize(n, 0);
    b
}

fn decodificar(jpeg: &[u8]) -> image::RgbImage {
    image::load_from_memory_with_format(jpeg, ImageFormat::Jpeg)
        .unwrap()
        .to_rgb8()
}

fn vermelho(p: &image::Rgb<u8>) -> bool {
    p.0[0] >= 180 && p.0[1] <= 50 && p.0[2] <= 50
}

fn com_url<'a>(base: &'a str, http: &'a FakeHttp, disco: &'a FakeDisco) -> Imagens<'a> {
    Imagens {
        url: Some(base),
        dir: None,
        http,
        disco,
    }
}

/// IMG-01: `200` com WebP → foto da oferta 800×800 (não o placeholder), origem = URL inteira.
#[test]
fn oferta_200_webp_vira_foto() {
    let http = FakeHttp::ok(webp(400, 200));
    let disco = FakeDisco::new(vec![]);
    let (jpeg, origem) = foto_de(&com_url(OFERTAS, &http, &disco), 7, Area::Tech).unwrap();
    assert_eq!(
        origem,
        OrigemFoto::Site("https://besave.com.br/img/ofertas/7.webp".into())
    );
    assert_eq!(http.urls(), ["https://besave.com.br/img/ofertas/7.webp"]);
    let img = decodificar(&jpeg);
    assert_eq!(img.dimensions(), (800, 800));
    assert!(
        vermelho(img.get_pixel(400, 400)),
        "{:?}",
        img.get_pixel(400, 400)
    );
    assert_ne!(jpeg, foto(None, 7, Area::Tech).unwrap().0);
}

/// IMG-02: 404, 500, 301, timeout, conexão, corpo não-imagem e corpo > 5 MB → placeholder da área.
#[test]
fn oferta_falhas_viram_placeholder() {
    let placeholder = foto(None, 7, Area::Pets).unwrap().0;
    let casos = [
        Ok((404, webp(10, 10))),
        Ok((500, vec![])),
        Ok((301, webp(10, 10))),
        Ok((204, webp(10, 10))),
        Ok((206, webp(10, 10))),
        Err(ErroBaixa::Timeout(15)),
        Err(ErroBaixa::Conexao("recusada".into())),
        Err(ErroBaixa::Grande),
        Ok((200, b"<html>nao e imagem</html>".to_vec())),
        Ok((200, vec![])),
        Ok((200, webp_com(MAX_BYTES + 1))),
    ];
    for (i, r) in casos.into_iter().enumerate() {
        let http = FakeHttp::new(r);
        let disco = FakeDisco::new(webp(10, 10));
        let (jpeg, origem) = foto_de(&com_url(OFERTAS, &http, &disco), 7, Area::Pets).unwrap();
        assert_eq!(origem, OrigemFoto::Placeholder(Area::Pets), "caso {i}");
        assert_eq!(jpeg, placeholder, "caso {i}");
        assert_eq!(http.urls().len(), 1, "caso {i}");
    }
}

/// IMG-02 (fronteira): corpo de exatamente 5 MB é aceito; 5 MB + 1, não.
#[test]
fn limite_de_5_mb_inclusivo() {
    assert_eq!(MAX_BYTES, 5 * 1024 * 1024);
    assert_eq!(TIMEOUT, std::time::Duration::from_secs(15));
    let disco = FakeDisco::new(vec![]);
    let http = FakeHttp::ok(webp_com(MAX_BYTES));
    let (_, origem) = foto_de(&com_url(OFERTAS, &http, &disco), 3, Area::Elas).unwrap();
    assert_eq!(
        origem,
        OrigemFoto::Site("https://besave.com.br/img/ofertas/3.webp".into())
    );
    let http = FakeHttp::ok(webp_com(MAX_BYTES + 1));
    let (_, origem) = foto_de(&com_url(OFERTAS, &http, &disco), 3, Area::Elas).unwrap();
    assert_eq!(origem, OrigemFoto::Placeholder(Area::Elas));
}

/// IMG-03: base com e sem `/` no fim → a mesma URL final, comparada inteira.
#[test]
fn base_com_e_sem_barra() {
    let disco = FakeDisco::new(vec![]);
    let mut urls = Vec::new();
    for b in [
        "https://besave.com.br/img/ofertas/",
        "https://besave.com.br/img/ofertas",
    ] {
        let http = FakeHttp::ok(webp(10, 10));
        foto_de(&com_url(b, &http, &disco), 5412, Area::Tech).unwrap();
        urls.extend(http.urls());
    }
    assert_eq!(
        urls,
        [
            "https://besave.com.br/img/ofertas/5412.webp",
            "https://besave.com.br/img/ofertas/5412.webp"
        ]
    );
    assert_eq!(
        url("https://besave.com.br/img/avisos", "3.jpg"),
        "https://besave.com.br/img/avisos/3.jpg"
    );
    assert_eq!(
        url("https://besave.com.br/img/avisos/", "3.jpg"),
        "https://besave.com.br/img/avisos/3.jpg"
    );
}

/// AVI-01: `DS_IMAGEM = promo.jpg` → `GET {base}{id}.jpg`; `.WEBP` → `.webp`; foto 800×800.
#[test]
fn aviso_pela_url() {
    let disco = FakeDisco::new(vec![]);
    let http = FakeHttp::ok(jpg());
    let j = foto_aviso_de(&com_url(AVISOS, &http, &disco), 3, Some(" promo.jpg ")).unwrap();
    assert_eq!(http.urls(), ["https://besave.com.br/img/avisos/3.jpg"]);
    assert_eq!(decodificar(&j).dimensions(), (800, 800));

    let http = FakeHttp::ok(webp(50, 50));
    assert!(foto_aviso_de(&com_url(AVISOS, &http, &disco), 4, Some("Banner.WEBP")).is_some());
    assert_eq!(http.urls(), ["https://besave.com.br/img/avisos/4.webp"]);
}

/// AVI-01: falha (404, timeout, não-imagem, > 5 MB) → sem foto; sem `DS_IMAGEM` → nem pede.
#[test]
fn aviso_falha_sem_foto() {
    let disco = FakeDisco::new(jpg());
    for r in [
        Ok((404, jpg())),
        Ok((204, jpg())),
        Ok((206, jpg())),
        Err(ErroBaixa::Timeout(15)),
        Ok((200, b"lixo".to_vec())),
        Ok((200, webp_com(MAX_BYTES + 1))),
    ] {
        let http = FakeHttp::new(r);
        assert_eq!(
            foto_aviso_de(&com_url(AVISOS, &http, &disco), 3, Some("x.jpg")),
            None
        );
        assert_eq!(http.urls().len(), 1);
    }
    let http = FakeHttp::ok(jpg());
    assert_eq!(
        foto_aviso_de(&com_url(AVISOS, &http, &disco), 3, None),
        None
    );
    assert_eq!(
        foto_aviso_de(&com_url(AVISOS, &http, &disco), 3, Some("  ")),
        None
    );
    assert!(http.urls().is_empty());
    assert_eq!(disco.leituras(), 0);
}

/// PRE-02: URL e pasta → só a URL (pasta: 0 leituras). PRE-01: só pasta → só o disco.
/// PRE-03: nenhuma → placeholder, nada lido.
#[test]
fn precedencia_oferta() {
    let dir = Path::new("/srv/besave/imagens/ofertas/img");
    let http = FakeHttp::ok(webp(10, 10));
    let disco = FakeDisco::new(webp(10, 10));
    let ambos = Imagens {
        url: Some(OFERTAS),
        dir: Some(dir),
        http: &http,
        disco: &disco,
    };
    let (_, origem) = foto_de(&ambos, 9, Area::Tech).unwrap();
    assert_eq!(
        origem,
        OrigemFoto::Site("https://besave.com.br/img/ofertas/9.webp".into())
    );
    assert_eq!(http.urls().len(), 1);
    assert_eq!(disco.leituras(), 0);

    // URL falhando com a pasta definida: placeholder, a pasta continua sem ser lida.
    let falha = FakeHttp::new(Ok((404, vec![])));
    let (_, origem) = foto_de(
        &Imagens {
            http: &falha,
            ..ambos
        },
        9,
        Area::Tech,
    )
    .unwrap();
    assert_eq!(origem, OrigemFoto::Placeholder(Area::Tech));
    assert_eq!(disco.leituras(), 0);

    let http = FakeHttp::ok(webp(10, 10));
    let so_pasta = Imagens {
        url: None,
        dir: Some(dir),
        http: &http,
        disco: &disco,
    };
    let (_, origem) = foto_de(&so_pasta, 9, Area::Tech).unwrap();
    assert_eq!(origem, OrigemFoto::Oferta(dir.join("9").join("9.webp")));
    assert_eq!(disco.leituras(), 1);
    assert!(http.urls().is_empty());

    let disco = FakeDisco::new(webp(10, 10));
    let nenhuma = Imagens {
        url: None,
        dir: None,
        http: &http,
        disco: &disco,
    };
    let (_, origem) = foto_de(&nenhuma, 9, Area::Tech).unwrap();
    assert_eq!(origem, OrigemFoto::Placeholder(Area::Tech));
    assert_eq!(disco.leituras(), 0);
    assert!(http.urls().is_empty());
}

/// PRE-01..03 no aviso.
#[test]
fn precedencia_aviso() {
    let dir = Path::new("/srv/besave/imagens/avisos");
    let http = FakeHttp::ok(jpg());
    let disco = FakeDisco::new(jpg());
    let ambos = Imagens {
        url: Some(AVISOS),
        dir: Some(dir),
        http: &http,
        disco: &disco,
    };
    assert!(foto_aviso_de(&ambos, 2, Some("a.jpg")).is_some());
    assert_eq!(http.urls(), ["https://besave.com.br/img/avisos/2.jpg"]);
    assert_eq!(disco.leituras(), 0);

    let so_pasta = Imagens { url: None, ..ambos };
    assert!(foto_aviso_de(&so_pasta, 2, Some("a.jpg")).is_some());
    assert_eq!(*disco.lidos.borrow(), [dir.join("a.jpg")]);
    assert_eq!(http.urls().len(), 1);

    let nenhuma = Imagens {
        url: None,
        dir: None,
        ..ambos
    };
    assert_eq!(foto_aviso_de(&nenhuma, 2, Some("a.jpg")), None);
    assert_eq!(disco.leituras(), 1);
    assert_eq!(http.urls().len(), 1);
}

/// AVI-01 na execução: URL do aviso falha (com a pasta definida) → `sendMessage`, sem foto, e a
/// pasta não é lida. Oferta com URL boa → `sendPhoto` com a foto do site.
#[test]
fn execucao_com_urls() {
    let mut l = comum::linha_canal(11, Some(200.0), 100.0);
    // 2026-09-24 07:00 em Brasília; a execução é às 10:00.
    let dia0 = 1_790_218_800;
    l.oferta.dt_oferta = Some(dia0 + 7 * 3600);
    l.dt_publicacao_site = Some(dia0 + 7 * 3600);
    let f = FakeEnvio::new(Parametros::default(), vec![l]);
    f.ligar_aviso(LigacaoAviso {
        canal: 1,
        aviso: LinhaAviso {
            id: 1,
            titulo: "Aviso 1".into(),
            texto: "Texto.".into(),
            imagem: Some("aviso.jpg".into()),
            ativo: true,
            dt_inicio: dia0 - 86_400,
            dt_publicacao_site: Some(dia0 - 3600),
            ..Default::default()
        },
        intervalo_min: 120,
        ativo: true,
    });
    let r = RelogioFake::em(dia0 + 10 * 3600);
    let tg = FakeCanal::new(&r);
    let m = mapeamento();
    let http_ofertas = FakeHttp::ok(webp(400, 200));
    let http_avisos = FakeHttp::new(Ok((404, vec![])));
    let disco = FakeDisco::new(jpg());
    let dir = Path::new("/srv/besave/imagens");
    let rel = rodar(&Contexto {
        fonte: &f,
        telegram: &tg,
        relogio: &r,
        m: &m,
        imagens: Imagens {
            url: Some(OFERTAS),
            dir: Some(dir),
            http: &http_ofertas,
            disco: &disco,
        },
        avisos: Imagens {
            url: Some(AVISOS),
            dir: Some(dir),
            http: &http_avisos,
            disco: &disco,
        },
        foto: foto_de,
        canal: 1,
        pausa_ate: None,
    })
    .unwrap();
    assert_eq!(rel.aviso, Some(1));
    assert_eq!(rel.enviados, 1);
    let chamadas = tg.chamadas();
    let metodos: Vec<_> = chamadas.iter().map(|c| c.metodo).collect();
    assert_eq!(metodos, ["sendMessage", "sendPhoto"]);
    assert_eq!(
        http_avisos.urls(),
        ["https://besave.com.br/img/avisos/1.jpg"]
    );
    assert_eq!(
        http_ofertas.urls(),
        ["https://besave.com.br/img/ofertas/11.webp"]
    );
    assert_eq!(disco.leituras(), 0);
    let img = decodificar(&chamadas[1].jpeg);
    assert_eq!(img.dimensions(), (800, 800));
    assert!(vermelho(img.get_pixel(400, 400)));
}

/// CFG-01: só `https://host…`, sem query, fragmento, usuário ou espaço; vazia/ausente = sem URL.
#[test]
fn base_validada() {
    const V: &str = "BESAVE_IMAGENS_URL";
    for (entrada, saida) in [
        (
            "https://besave.com.br/img/ofertas/",
            "https://besave.com.br/img/ofertas/",
        ),
        (
            " https://besave.com.br/img/ofertas ",
            "https://besave.com.br/img/ofertas/",
        ),
        ("https://cdn.exemplo.com", "https://cdn.exemplo.com/"),
    ] {
        assert_eq!(base(V, entrada).as_deref(), Ok(saida), "{entrada}");
    }
    for entrada in [
        "http://besave.com.br/img/ofertas/",
        "HTTPS://besave.com.br/",
        "ftp://besave.com.br/",
        "besave.com.br/img/ofertas/",
        "https://",
        "https:///img/ofertas/",
        "https://besave.com.br/img/?v=1",
        "https://besave.com.br/img/#x",
        "https://user@besave.com.br/img/",
        "https://besave.com.br/img ofertas/",
        "https://besave.com.br\\img\\",
    ] {
        let e: ErroBase = base(V, entrada).unwrap_err();
        assert_eq!(e.var, V, "{entrada}");
    }
    assert_eq!(base_do_env(V, |_| None), Ok(None));
    assert_eq!(base_do_env(V, |_| Some("  ".into())), Ok(None));
    assert_eq!(
        base_do_env(V, |k| (k == V).then(|| "https://a.b/c".to_owned())),
        Ok(Some("https://a.b/c/".to_owned()))
    );
    assert!(base_do_env(V, |_| Some("http://a.b/".into())).is_err());
}
