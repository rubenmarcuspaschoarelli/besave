//! IMG-01..04, IDE-01..02, REC-01..06, FAL-01..03, EXP-01..04, ORC-01, REL-01: imagem de oferta
//! reenviada por hash, não por existência de chave (BSV-45). Derivados do critério de aceite.

mod comum;

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use comum::{AGORA, linha, mapeamento};
use worker::conversao::LinhaOferta;
use worker::execucao::linha_relatorio;
use worker::expurgo::{CHAVE_EXPURGO, ConfigExpurgo};
use worker::fonte::FakeFonte;
use worker::geracao::{Relatorio, gerar};
use worker::imagens::{
    CHAVE_INDICE, ConfigImagens, RelatorioImagens, chave_grande, chave_placeholder, chave_small,
    publicar_imagens,
};
use worker::modelo::Area;
use worker::paginas::hash16;
use worker::publicador::{
    ErroPublicador, META_ESTADO, META_IMAGEM, Meta, Publicador, PublicadorMemoria, Result,
};
use worker::redirects::RedirectsMemoria;
use worker::site::{ConfigSite, ErroConfigSite};

const HORA: i64 = 3600;
/// 2026-09-25T05:30:00Z = 02:30 em Brasília: dentro da janela padrão do expurgo.
const NA_JANELA: i64 = AGORA + 16 * HORA + 50 * 60;

// ---- infraestrutura de teste ----

/// `PublicadorMemoria` que anota os prefixos listados e pode falhar o `gravar_lote` que contém
/// uma chave.
struct Espiao {
    dentro: PublicadorMemoria,
    listados: RefCell<Vec<String>>,
    falhar_com: Option<String>,
}

impl Espiao {
    fn new() -> Self {
        Self {
            dentro: PublicadorMemoria::new(),
            listados: RefCell::new(vec![]),
            falhar_com: None,
        }
    }

    fn listagens_de_ofertas(&self) -> usize {
        self.listados
            .borrow()
            .iter()
            .filter(|p| p.as_str() == "img/ofertas/")
            .count()
    }

    fn zerar_listagens(&self) {
        self.listados.borrow_mut().clear();
    }

    /// Chaves de imagem de oferta gravadas desde a criação.
    fn imagens_gravadas(&self) -> Vec<String> {
        self.dentro
            .gravacoes()
            .iter()
            .filter(|c| c.starts_with("img/ofertas/"))
            .cloned()
            .collect()
    }

    fn gravacoes_do_indice(&self) -> usize {
        self.dentro
            .gravacoes()
            .iter()
            .filter(|c| c.as_str() == CHAVE_INDICE)
            .count()
    }

    fn indice(&self) -> BTreeMap<String, String> {
        let bytes = self.dentro.ler(CHAVE_INDICE).unwrap().expect("índice");
        serde_json::from_slice(&bytes).unwrap()
    }
}

impl Publicador for Espiao {
    fn existe(&self, chave: &str) -> Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> Result<()> {
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> Result<()> {
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> Result<Vec<String>> {
        self.listados.borrow_mut().push(prefixo.to_owned());
        self.dentro.listar(prefixo)
    }
    fn remover_lote(&mut self, chaves: &[String]) -> Result<()> {
        self.dentro.remover_lote(chaves)
    }
    fn gravar_lote(&mut self, itens: &[(String, Vec<u8>, Meta)]) -> Result<()> {
        if let Some(f) = &self.falhar_com
            && itens.iter().any(|(c, _, _)| c == f)
        {
            return Err(ErroPublicador::Aws {
                operacao: "PutObject",
                chave: f.clone(),
                fonte: "falha injetada".into(),
            });
        }
        for (c, b, m) in itens {
            self.gravar(c, b, m)?;
        }
        Ok(())
    }
}

fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-worker-teste-imagens-hash-{nome}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// WebP "de mentira" (só a assinatura RIFF/WEBP) com um byte de assinatura de conteúdo.
fn webp(marca: u8, tamanho: usize) -> Vec<u8> {
    let mut b = b"RIFF".to_vec();
    b.extend_from_slice(&[0, 0, 0, 0]);
    b.extend_from_slice(b"WEBPVP8 ");
    b.resize(tamanho.max(b.len()), marca);
    b
}

fn escrever(dir: &Path, id: i64, marca: u8) {
    let pasta = dir.join(id.to_string());
    std::fs::create_dir_all(&pasta).unwrap();
    std::fs::write(pasta.join(format!("{id}-small.webp")), webp(marca, 200)).unwrap();
    std::fs::write(pasta.join(format!("{id}.webp")), webp(marca, 400)).unwrap();
}

fn hash_da_origem(dir: &Path, id: i64) -> String {
    let pasta = dir.join(id.to_string());
    let mut bytes = std::fs::read(pasta.join(format!("{id}.webp"))).unwrap();
    bytes.extend(std::fs::read(pasta.join(format!("{id}-small.webp"))).unwrap());
    hash16(&bytes)
}

fn ciclo(
    ids: &[i64],
    dir: &Path,
    p: &mut dyn Publicador,
    cfg: &ConfigImagens,
    agora: i64,
) -> RelatorioImagens {
    publicar_imagens(ids, dir, p, cfg, agora).unwrap()
}

fn padrao() -> ConfigImagens {
    ConfigImagens::default()
}

fn chaves_do_id(id: i64) -> [String; 2] {
    [chave_small(id), chave_grande(id)]
}

// ---- IMG: a troca de arquivo sobe ----

/// IMG-01: o defeito de 19/10 — mesmo id, arquivo trocado no espelho.
#[test]
fn arquivo_trocado_com_o_mesmo_id_sobe_de_novo_sem_apagar_nada() {
    let dir = dir_temp("troca");
    escrever(&dir, 5412, b'A');
    let mut p = Espiao::new();
    ciclo(&[5412], &dir, &mut p, &padrao(), AGORA);
    let antes = p.imagens_gravadas().len();
    assert_eq!(antes, 2);

    escrever(&dir, 5412, b'B');
    let rel = ciclo(&[5412], &dir, &mut p, &padrao(), AGORA + 300);

    assert_eq!(rel.reenviadas, 1);
    assert_eq!(rel.publicadas, 1);
    let gravadas = p.imagens_gravadas();
    assert_eq!(gravadas.len(), antes + 2, "{gravadas:?}");
    assert_eq!(
        p.ler(&chave_grande(5412)).unwrap(),
        Some(webp(b'B', 400)),
        "o bucket tem a imagem nova"
    );
    assert!(p.dentro.remocoes().is_empty(), "nenhuma chave apagada");
    assert_eq!(p.indice()["5412"], hash_da_origem(&dir, 5412));
}

/// IMG-01 (discriminação): trocar só o `-small` também conta como troca.
#[test]
fn trocar_so_o_small_tambem_sobe() {
    let dir = dir_temp("troca-small");
    escrever(&dir, 7, b'A');
    let mut p = Espiao::new();
    ciclo(&[7], &dir, &mut p, &padrao(), AGORA);
    std::fs::write(dir.join("7").join("7-small.webp"), webp(b'Z', 200)).unwrap();
    let rel = ciclo(&[7], &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(rel.reenviadas, 1);
    assert_eq!(p.ler(&chave_small(7)).unwrap(), Some(webp(b'Z', 200)));
}

/// IMG-02: id novo sobe, é "publicada" e não "reenviada", e entra no índice.
#[test]
fn id_novo_sobe_e_entra_no_indice() {
    let dir = dir_temp("novo");
    escrever(&dir, 1, b'A');
    escrever(&dir, 2, b'B');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    let rel = ciclo(&[1, 2], &dir, &mut p, &padrao(), AGORA + 300);

    assert_eq!(rel.publicadas, 1);
    assert_eq!(rel.reenviadas, 0);
    assert_eq!(rel.reaproveitadas, 1);
    let indice = p.indice();
    assert_eq!(indice["1"], hash_da_origem(&dir, 1));
    assert_eq!(indice["2"], hash_da_origem(&dir, 2));
    assert_ne!(indice["1"], indice["2"]);
}

/// IMG-03: formato do índice — objeto plano id → hash16, headers de estado, nenhuma URL.
#[test]
fn indice_e_objeto_plano_id_para_hash16_sem_url() {
    let dir = dir_temp("formato");
    escrever(&dir, 5412, b'A');
    let mut p = Espiao::new();
    ciclo(&[5412], &dir, &mut p, &padrao(), AGORA);

    assert_eq!(p.dentro.meta(CHAVE_INDICE), Some(META_ESTADO));
    assert_eq!(CHAVE_INDICE, "_estado/imagens.json");
    let bruto = String::from_utf8(p.dentro.ler(CHAVE_INDICE).unwrap().unwrap()).unwrap();
    assert!(!bruto.contains("http"), "{bruto}");
    let h = &p.indice()["5412"];
    assert_eq!(h.len(), 16);
    assert!(h.bytes().all(|b| b.is_ascii_hexdigit()), "{h}");
    // Hash da concatenação `{id}.webp` ++ `{id}-small.webp`.
    assert_eq!(*h, hash_da_origem(&dir, 5412));
}

/// IMG-04: o índice só é gravado depois dos uploads do ciclo.
#[test]
fn indice_e_gravado_depois_das_imagens() {
    let dir = dir_temp("ordem");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    let g = p.dentro.gravacoes();
    let pos_indice = g.iter().position(|c| c == CHAVE_INDICE).unwrap();
    let ultima_imagem = g
        .iter()
        .rposition(|c| c.starts_with("img/ofertas/"))
        .unwrap();
    assert!(ultima_imagem < pos_indice, "{g:?}");
}

// ---- IDE: ciclo sem mudança ----

/// IDE-01 + IMG-04: 2º ciclo sem mudança.
#[test]
fn segundo_ciclo_sem_mudanca_nao_sobe_nao_lista_e_nao_regrava_o_indice() {
    let dir = dir_temp("inalterado");
    for id in [1, 2, 3] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    ciclo(&[1, 2, 3], &dir, &mut p, &padrao(), AGORA);
    assert_eq!(p.listagens_de_ofertas(), 1, "a 1ª reconstrói o índice");
    let (imagens, indices) = (p.imagens_gravadas().len(), p.gravacoes_do_indice());
    p.zerar_listagens();

    let rel = ciclo(&[1, 2, 3], &dir, &mut p, &padrao(), AGORA + 300);

    assert_eq!(rel.publicadas, 0);
    assert_eq!(rel.reaproveitadas, 3);
    assert_eq!(p.imagens_gravadas().len(), imagens, "0 uploads");
    assert_eq!(p.listagens_de_ofertas(), 0, "0 listagens de img/ofertas/");
    assert_eq!(p.gravacoes_do_indice(), indices, "índice não regravado");
}

/// IDE-02: placeholders — ausente publica, presente não republica; listados todo ciclo.
#[test]
fn placeholders_ausente_publica_presente_nao_republica() {
    let dir = dir_temp("placeholders");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    let ph = |p: &Espiao| {
        p.dentro
            .gravacoes()
            .iter()
            .filter(|c| c.starts_with("img/placeholder/"))
            .count()
    };
    assert_eq!(ph(&p), 10);
    assert_eq!(
        p.dentro.meta(&chave_placeholder(Area::Tech)),
        Some(META_IMAGEM)
    );

    ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(ph(&p), 10, "presentes: nada republicado");
    assert!(
        p.listados
            .borrow()
            .iter()
            .filter(|x| x.as_str() == "img/placeholder/")
            .count()
            >= 2,
        "placeholders são listados todo ciclo"
    );

    p.remover(&chave_placeholder(Area::Elas)).unwrap();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 600);
    assert_eq!(ph(&p), 11, "só o ausente voltou");
}

// ---- REC: reconstrução e reconciliação ----

/// REC-01: índice ausente com o par já no bucket → 1 listagem, 0 uploads, índice construído.
#[test]
fn indice_ausente_lista_reconstroi_e_nao_sobe_o_que_ja_esta_no_bucket() {
    let dir = dir_temp("ausente");
    for id in [1, 2] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    for id in [1, 2] {
        for c in chaves_do_id(id) {
            p.gravar(&c, b"qualquer", &META_IMAGEM).unwrap();
        }
    }
    let antes = p.imagens_gravadas().len();

    let rel = ciclo(&[1, 2], &dir, &mut p, &padrao(), AGORA);

    assert_eq!(p.listagens_de_ofertas(), 1);
    assert_eq!(rel.publicadas, 0);
    assert_eq!(p.imagens_gravadas().len(), antes, "0 uploads de oferta");
    assert_eq!(p.indice()["1"], hash_da_origem(&dir, 1));
    assert_eq!(p.indice()["2"], hash_da_origem(&dir, 2));

    p.zerar_listagens();
    ciclo(&[1, 2], &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(p.listagens_de_ofertas(), 0, "o ciclo seguinte já não lista");
}

/// REC-01: na reconstrução, par incompleto no bucket sobe.
#[test]
fn reconstrucao_envia_o_id_cujo_par_nao_esta_inteiro_no_bucket() {
    let dir = dir_temp("par-incompleto");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    p.gravar(&chave_small(1), b"x", &META_IMAGEM).unwrap();
    let rel = ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    assert_eq!(rel.publicadas, 1);
    assert_eq!(p.ler(&chave_grande(1)).unwrap(), Some(webp(b'A', 400)));
}

/// REC-02: índice inválido de três jeitos → reconstrói sem erro e o seguinte já não lista.
#[test]
fn indice_invalido_reconstroi_sem_erro() {
    for (nome, conteudo) in [
        ("json", &b"{nao e json"[..]),
        ("lista", &b"[1,2,3]"[..]),
        ("hash-curto", &br#"{"1":"abc"}"#[..]),
        ("hash-maiusculo", &br#"{"1":"ABCDEF0123456789"}"#[..]),
        ("valor-nao-string", &br#"{"1":5}"#[..]),
    ] {
        let dir = dir_temp(&format!("invalido-{nome}"));
        escrever(&dir, 1, b'A');
        let mut p = Espiao::new();
        for c in chaves_do_id(1) {
            p.gravar(&c, b"x", &META_IMAGEM).unwrap();
        }
        p.gravar(CHAVE_INDICE, conteudo, &META_ESTADO).unwrap();

        let rel = ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
        assert_eq!(p.listagens_de_ofertas(), 1, "{nome}");
        assert_eq!(rel.publicadas, 0, "{nome}: o bucket já tinha o par");
        assert_eq!(p.indice()["1"], hash_da_origem(&dir, 1), "{nome}");

        p.zerar_listagens();
        ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 300);
        assert_eq!(p.listagens_de_ofertas(), 0, "{nome}: já reconstruído");
    }
}

/// REC-03: `BESAVE_IMAGENS_RELISTAR=1` lista mesmo com índice válido.
#[test]
fn relistar_forcado_lista_com_indice_valido() {
    let dir = dir_temp("forcado");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    p.zerar_listagens();
    let forcado = ConfigImagens {
        relistar: true,
        ..padrao()
    };
    ciclo(&[1], &dir, &mut p, &forcado, AGORA + 300);
    assert_eq!(p.listagens_de_ofertas(), 1);
}

/// REC-04: `HORAS=0` lista todo ciclo; padrão não lista antes de 24 h e lista depois.
#[test]
fn intervalo_zero_lista_todo_ciclo_e_o_padrao_so_depois_de_24h() {
    let dir = dir_temp("intervalo");
    escrever(&dir, 1, b'A');

    let zero = ConfigImagens {
        relistar_horas: 0,
        ..padrao()
    };
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &zero, AGORA);
    p.zerar_listagens();
    ciclo(&[1], &dir, &mut p, &zero, AGORA + 60);
    assert_eq!(p.listagens_de_ofertas(), 1, "HORAS=0: lista todo ciclo");

    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    p.zerar_listagens();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 24 * HORA - 1);
    assert_eq!(p.listagens_de_ofertas(), 0, "1 s antes de 24 h");
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 24 * HORA);
    assert_eq!(p.listagens_de_ofertas(), 1, "em 24 h");
    p.zerar_listagens();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 24 * HORA + 300);
    assert_eq!(
        p.listagens_de_ofertas(),
        0,
        "a marca andou para o novo horário"
    );
}

/// REC-05: chave apagada à mão com o índice intacto volta só depois da janela (as duas metades).
#[test]
fn chave_apagada_a_mao_nao_volta_antes_da_janela_e_volta_depois() {
    let dir = dir_temp("apagada");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    p.remover(&chave_grande(1)).unwrap();

    let rel = ciclo(&[1], &dir, &mut p, &padrao(), AGORA + HORA);
    assert_eq!(rel.publicadas, 0);
    assert_eq!(p.ler(&chave_grande(1)).unwrap(), None, "antes da janela");

    let rel = ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 24 * HORA);
    assert_eq!(rel.publicadas, 1);
    assert_eq!(rel.reenviadas, 0, "restauração, não troca de imagem");
    assert_eq!(
        p.ler(&chave_grande(1)).unwrap(),
        Some(webp(b'A', 400)),
        "depois da janela"
    );
}

/// REC-06: variáveis inválidas são recusadas; válidas são lidas.
#[test]
fn config_das_variaveis_de_imagens() {
    let de = |pares: &'static [(&'static str, &'static str)]| {
        ConfigSite::de(move |k| {
            pares
                .iter()
                .find(|(n, _)| *n == k)
                .map(|(_, v)| (*v).to_owned())
        })
    };
    let c = de(&[]).unwrap().imagens;
    assert!(!c.relistar);
    assert_eq!(c.relistar_horas, 24);

    let c = de(&[
        ("BESAVE_IMAGENS_RELISTAR", "1"),
        ("BESAVE_IMAGENS_RELISTAR_HORAS", "0"),
    ])
    .unwrap()
    .imagens;
    assert!(c.relistar);
    assert_eq!(c.relistar_horas, 0);

    for (var, valor) in [
        ("BESAVE_IMAGENS_RELISTAR", "talvez"),
        ("BESAVE_IMAGENS_RELISTAR_HORAS", "-1"),
        ("BESAVE_IMAGENS_RELISTAR_HORAS", "muitas"),
    ] {
        let e = ConfigSite::de(|k| (k == var).then(|| valor.to_owned())).unwrap_err();
        let ErroConfigSite::Invalida(nome, _) = e;
        assert_eq!(nome, var);
    }
}

// ---- FAL: o que falha não entra no índice ----

/// FAL-01: `sem_origem` não grava hash; o ciclo seguinte tenta o mesmo id.
#[test]
fn sem_origem_nao_entra_no_indice_e_o_ciclo_seguinte_tenta_de_novo() {
    let dir = dir_temp("sem-origem");
    let mut p = Espiao::new();
    let rel = ciclo(&[9], &dir, &mut p, &padrao(), AGORA);
    assert_eq!(rel.sem_origem, 1);
    assert!(!p.indice().contains_key("9"));

    escrever(&dir, 9, b'A');
    let rel = ciclo(&[9], &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(rel.sem_origem, 0);
    assert_eq!(rel.publicadas, 1);
    assert_eq!(p.indice()["9"], hash_da_origem(&dir, 9));
}

/// FAL-02: falha de envio num bloco — os ids dele ficam fora do índice, os blocos anteriores
/// entram, e o ciclo seguinte reenvia só os que faltam.
#[test]
fn falha_de_envio_nao_grava_hash_do_bloco_e_o_proximo_ciclo_repete() {
    let dir = dir_temp("falha-envio");
    let ids: Vec<i64> = (1..=70).collect();
    for &id in &ids {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    p.falhar_com = Some(chave_small(70));

    let erro = publicar_imagens(&ids, &dir, &mut p, &padrao(), AGORA);
    assert!(erro.is_err());

    let indice = p.indice();
    assert!(indice.contains_key("1"), "bloco anterior ficou no índice");
    assert!(indice.contains_key("64"));
    assert!(
        !indice.contains_key("65"),
        "bloco que falhou fora do índice"
    );
    assert!(!indice.contains_key("70"));

    p.falhar_com = None;
    let antes = p.imagens_gravadas().len();
    let rel = ciclo(&ids, &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(rel.publicadas, 6, "ids 65..=70");
    assert_eq!(p.imagens_gravadas().len(), antes + 12);
    assert_eq!(p.indice().len() - 1, 70, "70 ids (+ a marca de listagem)");
}

/// FAL-03: origem que não é WebP não entra no índice; se já estava, mantém o hash anterior.
#[test]
fn origem_invalida_fica_fora_do_indice_e_mantem_o_hash_anterior() {
    let dir = dir_temp("nao-webp");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    let hash_antigo = p.indice()["1"].clone();

    std::fs::write(dir.join("1").join("1.webp"), b"isto nao e webp").unwrap();
    std::fs::create_dir_all(dir.join("2")).unwrap();
    std::fs::write(dir.join("2").join("2.webp"), b"jpeg").unwrap();
    std::fs::write(dir.join("2").join("2-small.webp"), b"jpeg").unwrap();

    let rel = ciclo(&[1, 2], &dir, &mut p, &padrao(), AGORA + 300);
    assert_eq!(rel.falhas.len(), 2);
    assert_eq!(p.indice()["1"], hash_antigo);
    assert!(!p.indice().contains_key("2"));
    assert_eq!(p.ler(&chave_grande(1)).unwrap(), Some(webp(b'A', 400)));
}

// ---- EXP: expurgo pela fila (BSV-47) ----

fn site() -> ConfigSite {
    ConfigSite {
        expurgo: ConfigExpurgo::default(),
        ..ConfigSite::default()
    }
}

fn rodar(
    ids: &[i64],
    dir: &Path,
    p: &mut dyn Publicador,
    kvs: &mut RedirectsMemoria,
    agora: i64,
) -> Relatorio {
    let linhas: Vec<LinhaOferta> = ids
        .iter()
        .map(|&id| LinhaOferta {
            dt_publicacao_site: Some(AGORA - 1800),
            ..linha(id)
        })
        .collect();
    gerar(
        &FakeFonte::new(linhas, vec![], agora),
        &mapeamento(),
        p,
        kvs,
        dir,
        &site(),
        agora,
    )
    .unwrap()
}

fn tem(p: &Espiao, id: i64) -> [bool; 2] {
    chaves_do_id(id).map(|c| p.dentro.chaves().contains(&c))
}

/// EXP-01 + EXP-02: o id que saiu do conjunto fica no índice (e no bucket) até a janela; na
/// janela, saem as 2 chaves **e** o id do índice gravado.
#[test]
fn id_que_saiu_continua_no_indice_ate_a_fila_apagar() {
    let dir = dir_temp("exp-fila");
    for id in [1, 2, 3] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&[1, 2, 3], &dir, &mut p, &mut kvs, AGORA);
    assert!(p.indice().contains_key("3"));

    // Fora da janela (AGORA = 2026-09-25T10:00Z = 07:00 em Brasília): sai do conjunto, não do bucket.
    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA + 300);
    assert_eq!(r.expurgo.enfileirados, 1);
    assert_eq!(r.expurgo.removidos, 0);
    assert!(p.indice().contains_key("3"), "EXP-01: ainda no índice");
    assert_eq!(tem(&p, 3), [true, true]);

    // Na janela: a fila apaga.
    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, NA_JANELA);
    assert_eq!(r.expurgo.removidos, 1);
    assert_eq!(tem(&p, 3), [false, false], "EXP-02: 2 chaves removidas");
    assert!(!p.indice().contains_key("3"), "EXP-02: fora do índice");
    assert!(p.indice().contains_key("1") && p.indice().contains_key("2"));
}

/// EXP-03: o mesmo id volta depois do expurgo → sobe de novo.
#[test]
fn id_que_volta_depois_do_expurgo_sobe_de_novo() {
    let dir = dir_temp("exp-reentrada");
    for id in [1, 2] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA);
    rodar(&[1], &dir, &mut p, &mut kvs, NA_JANELA);
    assert_eq!(tem(&p, 2), [false, false]);

    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, NA_JANELA + 86_400 + 300);
    assert_eq!(r.imagens.publicadas, 1);
    assert_eq!(tem(&p, 2), [true, true]);
    assert!(p.indice().contains_key("2"));
}

/// EXP-04: reativado antes da janela → sai da fila, continua no índice, não é reenviado.
#[test]
fn id_reativado_antes_da_janela_nao_e_reenviado() {
    let dir = dir_temp("exp-reativado");
    for id in [1, 2] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA);
    rodar(&[1], &dir, &mut p, &mut kvs, AGORA + 300);
    let antes = p.imagens_gravadas().len();

    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA + 600);

    assert_eq!(r.imagens.publicadas, 0);
    assert_eq!(r.imagens.reaproveitadas, 2);
    assert_eq!(p.imagens_gravadas().len(), antes, "nada reenviado");
    assert!(p.indice().contains_key("2"));
    // E a fila esvaziou: a janela seguinte não apaga o id reativado.
    rodar(&[1, 2], &dir, &mut p, &mut kvs, NA_JANELA);
    assert_eq!(tem(&p, 2), [true, true]);
}

/// REC (BSV-47): índice válido e recente, mas a fila ainda sem `reconciliado` → o ciclo lista
/// `img/ofertas/` e a imagem órfã do bucket entra na fila.
#[test]
fn fila_nao_reconciliada_forca_listagem_e_a_orfa_entra_na_fila() {
    let dir = dir_temp("fila-nao-reconciliada");
    for id in [1, 2] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA);
    // Estado de hoje na produção: índice válido e recente, fila nunca reconciliada, órfã no bucket.
    p.dentro.remover(CHAVE_EXPURGO).unwrap();
    for c in chaves_do_id(99) {
        p.gravar(&c, b"orfa", &META_IMAGEM).unwrap();
    }
    p.zerar_listagens();

    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA + 300);

    assert_eq!(p.listagens_de_ofertas(), 1, "lista para reconciliar");
    assert_eq!(r.expurgo.enfileirados, 1, "a órfã 99 entra na fila");
    let fila = String::from_utf8(p.ler(CHAVE_EXPURGO).unwrap().unwrap()).unwrap();
    assert!(fila.contains("\"99\""), "{fila}");
    assert!(fila.contains("\"reconciliado\":true"), "{fila}");

    p.zerar_listagens();
    rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA + 600);
    assert_eq!(
        p.listagens_de_ofertas(),
        0,
        "reconciliada: o ciclo seguinte não lista"
    );
}

/// REC: chave `_desconhecida` no índice é ignorada; o índice continua válido e não força listagem.
#[test]
fn chave_desconhecida_com_underscore_nao_invalida_o_indice() {
    let dir = dir_temp("chave-desconhecida");
    escrever(&dir, 1, b'A');
    let mut p = Espiao::new();
    ciclo(&[1], &dir, &mut p, &padrao(), AGORA);
    let mut mapa = p.indice();
    mapa.insert("_desconhecida".into(), "qualquer coisa".into());
    p.gravar(
        CHAVE_INDICE,
        &serde_json::to_vec(&mapa).unwrap(),
        &META_ESTADO,
    )
    .unwrap();
    p.zerar_listagens();
    let antes = p.imagens_gravadas().len();

    let rel = ciclo(&[1], &dir, &mut p, &padrao(), AGORA + 300);

    assert_eq!(p.listagens_de_ofertas(), 0, "índice lido como válido");
    assert_eq!(rel.reaproveitadas, 1);
    assert_eq!(rel.publicadas, 0);
    assert_eq!(p.imagens_gravadas().len(), antes);
}

/// GER: ciclo completo sem mudança lista `img/ofertas/` no máximo na 1ª vez.
#[test]
fn gerar_nao_lista_img_ofertas_no_segundo_ciclo() {
    let dir = dir_temp("gerar-sem-lista");
    for id in [1, 2] {
        escrever(&dir, id, b'A');
    }
    let mut p = Espiao::new();
    let mut kvs = RedirectsMemoria::new();
    rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA);
    assert_eq!(p.listagens_de_ofertas(), 1);
    p.zerar_listagens();
    let indices = p.gravacoes_do_indice();

    let r = rodar(&[1, 2], &dir, &mut p, &mut kvs, AGORA + 300);

    assert_eq!(p.listagens_de_ofertas(), 0);
    assert_eq!(r.imagens.publicadas, 0);
    assert_eq!(p.gravacoes_do_indice(), indices);
}

// ---- ORC e REL ----

/// ORC-01: índice de 30.000 ids ≤ 1 MB. Mede o custo por id com ids de 6 dígitos (pior caso
/// próximo do real) numa amostra e projeta para 30 mil: criar 60 mil arquivos custa ~80 s.
#[test]
fn indice_de_30_mil_ids_cabe_em_1_mb() {
    const AMOSTRA: usize = 2_000;
    let dir = dir_temp("orcamento");
    let ids: Vec<i64> = (100_000..100_000 + AMOSTRA as i64).collect();
    for &id in &ids {
        escrever(&dir, id, (id % 251) as u8);
    }
    let mut p = Espiao::new();
    ciclo(&ids, &dir, &mut p, &padrao(), AGORA);
    let bytes = p.dentro.ler(CHAVE_INDICE).unwrap().unwrap().len();
    let por_id = bytes.div_ceil(AMOSTRA);
    assert!(por_id * 30_000 <= 1_000_000, "{por_id} B/id");
    assert!(
        por_id >= 20,
        "{por_id} B/id: a amostra tem mesmo {AMOSTRA} ids"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

/// REL-01: a linha do ciclo agendado traz `t_imagens_listagem` e `imagens_reenviadas`.
#[test]
fn linha_do_ciclo_agendado_traz_listagem_e_reenviadas() {
    let mut rel = Relatorio::default();
    rel.imagens.reenviadas = 3;
    rel.tempos.imagens_listagem = 1234;
    let linha = linha_relatorio(&rel, 10, AGORA);
    let campos: Vec<&str> = linha.split(' ').collect();
    assert!(campos.contains(&"imagens_reenviadas=3"), "{linha}");
    assert!(campos.contains(&"t_imagens_listagem=1234"), "{linha}");
}
