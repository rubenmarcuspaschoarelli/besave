//! CHV-01, CHV-02, CPY-01, CPY-02, ORC-01..03, REU-01..04: imagens de oferta (BSV-13).

use std::cell::Cell;
use std::path::{Path, PathBuf};

use image::ImageEncoder;
use worker::imagens::{
    AVISO_GRANDE, LADO_SMALL, MotivoFalhaImagem, ORCAMENTO_SMALL, ajustar_small, chave_grande,
    chave_placeholder, chave_small, e_webp, origem, publicar_imagens,
};
use worker::modelo::Area;
use worker::publicador::{META_IMAGEM, Meta, Publicador, PublicadorMemoria};

/// Imagem WebP sem perdas com pixels pseudoaleatórios (comprime mal, fica bem maior que o
/// orçamento de 25 600 B mesmo em resoluções pequenas), para exercitar a recodificação.
fn webp_ruido(largura: u32, altura: u32) -> Vec<u8> {
    let mut img = image::RgbaImage::new(largura, altura);
    let mut x: u64 = 0x2545_F491_4F6C_DD1D;
    for pixel in img.pixels_mut() {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        let b = x.to_le_bytes();
        *pixel = image::Rgba([b[0], b[1], b[2], 255]);
    }
    let mut saida = Vec::new();
    image::codecs::webp::WebPEncoder::new_lossless(&mut saida)
        .write_image(
            img.as_raw(),
            largura,
            altura,
            image::ExtendedColorType::Rgba8,
        )
        .unwrap();
    saida
}

/// Pasta temporária isolada por teste (nunca reaproveitada entre execuções).
fn dir_temp(nome: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "besave-worker-teste-imagens-{nome}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn escrever_origem(dir: &Path, id: i64, small: &[u8], grande: &[u8]) {
    let pasta = dir.join(id.to_string());
    std::fs::create_dir_all(&pasta).unwrap();
    std::fs::write(pasta.join(format!("{id}-small.webp")), small).unwrap();
    std::fs::write(pasta.join(format!("{id}.webp")), grande).unwrap();
}

/// Bytes com assinatura WebP válida e `tamanho` bytes no total (preenchidos após o cabeçalho).
fn bytes_webp(tamanho: usize) -> Vec<u8> {
    let mut b = b"RIFF".to_vec();
    b.extend_from_slice(&[0, 0, 0, 0]);
    b.extend_from_slice(b"WEBPVP8 ");
    b.resize(tamanho.max(b.len()), b'A');
    b
}

#[test]
fn chaves_do_bucket() {
    assert_eq!(chave_small(5412), "img/ofertas/5412-small.webp");
    assert_eq!(chave_grande(5412), "img/ofertas/5412.webp");
}

#[test]
fn origem_monta_os_dois_caminhos() {
    let dir = PathBuf::from("robos").join("imagens");
    let (small, grande) = origem(&dir, 5412);
    assert_eq!(
        small,
        dir.join("5412").join("5412-small.webp"),
        "{}",
        small.display()
    );
    assert_eq!(
        grande,
        dir.join("5412").join("5412.webp"),
        "{}",
        grande.display()
    );
}

#[test]
fn assinatura_webp_aceita_riff_webp() {
    let mut bytes = b"RIFF".to_vec();
    bytes.extend_from_slice(&[10, 0, 0, 0]); // tamanho do chunk RIFF, irrelevante aqui
    bytes.extend_from_slice(b"WEBPVP8 ");
    assert!(e_webp(&bytes));
}

#[test]
fn assinatura_webp_rejeita_vazio_riff_sem_webp_e_jpeg() {
    assert!(!e_webp(b""));
    let mut riff_sem_webp = b"RIFF".to_vec();
    riff_sem_webp.extend_from_slice(&[10, 0, 0, 0]);
    riff_sem_webp.extend_from_slice(b"JPEGxxxx");
    assert!(!e_webp(&riff_sem_webp));
    assert!(!e_webp(&[0xFF, 0xD8, 0xFF, 0xE0, 0, 0, 0, 0, 0, 0, 0, 0]));
}

/// `Area::slug` deve cobrir as 10 variantes com o slug de URL do CONTRATO §2.3 (não o valor do
/// enum): usado em `img/placeholder/{slug}.webp`, já referenciado por BSV-20.
#[test]
fn slug_cobre_as_10_variantes_do_contrato() {
    let esperado = [
        "tech",
        "players",
        "meu-lar",
        "elas",
        "eles",
        "cultura",
        "familia",
        "pets",
        "esporte-vida",
        "outros",
    ];
    let obtido: Vec<&str> = Area::TODAS.iter().map(Area::slug).collect();
    assert_eq!(obtido, esperado);
}

/// CPY-01: fixture dentro do orçamento sobe com os bytes idênticos e a `Meta` de `img/**`.
#[test]
fn copia_direta_dentro_do_orcamento() {
    let dir = dir_temp("copia-direta");
    let pequena = bytes_webp(12_000);
    let grande = bytes_webp(90_000);
    escrever_origem(&dir, 5412, &pequena, &grande);

    let bytes_esperados = (pequena.len() + grande.len()) as u64;
    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[5412], &dir, &mut p).unwrap();

    assert_eq!(rel.publicadas, 1);
    // Fix (validation.md, 2ª rodada): `bytes` soma os tamanhos publicados, não fica em 0.
    assert_eq!(rel.bytes, bytes_esperados);
    assert_eq!(p.ler(&chave_small(5412)).unwrap(), Some(pequena));
    assert_eq!(p.ler(&chave_grande(5412)).unwrap(), Some(grande));
    assert_eq!(p.meta(&chave_small(5412)), Some(META_IMAGEM));
    assert_eq!(p.meta(&chave_grande(5412)), Some(META_IMAGEM));
}

/// CPY-02: `.webp` com conteúdo que não é WebP vira falha nomeada, sem panic; o loop continua
/// e publica o próximo id normalmente.
#[test]
fn arquivo_nao_webp_vira_falha_e_o_loop_continua() {
    let dir = dir_temp("nao-webp");
    let jpeg = vec![0xFF, 0xD8, 0xFF, 0xE0, 0, 0, 0, 0, 0, 0, 0, 0];
    escrever_origem(&dir, 5413, &jpeg, &bytes_webp(1_000));
    escrever_origem(&dir, 5414, &bytes_webp(1_000), &bytes_webp(1_000));

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[5413, 5414], &dir, &mut p).unwrap();

    assert_eq!(rel.falhas, vec![(5413, MotivoFalhaImagem::NaoWebp)]);
    assert!(!p.existe(&chave_small(5413)).unwrap());
    assert!(!p.existe(&chave_grande(5413)).unwrap());
    assert_eq!(rel.publicadas, 1);
    assert!(p.existe(&chave_small(5414)).unwrap());
    assert!(p.existe(&chave_grande(5414)).unwrap());
}

/// ORC-01: `ajustar_small` devolve WebP válido, dentro do orçamento e com o lado maior ≤ 320 px.
#[test]
fn ajustar_small_cabe_no_orcamento_e_no_lado_maximo() {
    let origem = webp_ruido(400, 400);
    assert!(
        origem.len() > ORCAMENTO_SMALL,
        "fixture não ficou grande o bastante: {} B",
        origem.len()
    );

    let ajustada = ajustar_small(&origem).unwrap();

    assert!(e_webp(&ajustada));
    assert!(ajustada.len() <= ORCAMENTO_SMALL, "{} B", ajustada.len());
    let decodificada =
        image::load_from_memory_with_format(&ajustada, image::ImageFormat::WebP).unwrap();
    assert!(decodificada.width().max(decodificada.height()) <= LADO_SMALL);
}

/// ORC-02: `-small.webp` acima do orçamento é recodificado e contado em `reprocessadas`.
#[test]
fn small_acima_do_orcamento_e_recodificado_e_contado() {
    let dir = dir_temp("reprocessada");
    let small_grande_demais = webp_ruido(400, 400);
    assert!(small_grande_demais.len() > ORCAMENTO_SMALL);
    escrever_origem(&dir, 6000, &small_grande_demais, &bytes_webp(1_000));

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[6000], &dir, &mut p).unwrap();

    assert_eq!(rel.reprocessadas, 1);
    assert_eq!(rel.publicadas, 1);
    let publicado = p.ler(&chave_small(6000)).unwrap().unwrap();
    assert!(publicado.len() <= ORCAMENTO_SMALL);
    assert_ne!(publicado, small_grande_demais);
    // Fix 5 (validation.md): `maior_small` reflete o tamanho publicado, não fica em 0.
    assert_eq!(rel.maior_small, publicado.len() as u64);
    assert!(rel.maior_small > 0);
}

/// Fix (validation.md, 3ª rodada): `maior_small`/`maior_grande` são o maior valor **entre todos
/// os ids** publicados na execução, não só o último processado — exige `.max()`, não overwrite.
#[test]
fn maior_small_e_maior_grande_refletem_o_maior_entre_varios_ids() {
    let dir = dir_temp("maior-entre-varios");
    // 9100 é o maior nos dois; 9101 (processado depois) é menor nos dois.
    escrever_origem(&dir, 9100, &bytes_webp(3_000), &bytes_webp(5_000));
    escrever_origem(&dir, 9101, &bytes_webp(1_000), &bytes_webp(2_000));

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[9100, 9101], &dir, &mut p).unwrap();

    assert_eq!(rel.publicadas, 2);
    assert_eq!(
        rel.maior_small, 3_000,
        "não pode regredir para o valor do último id processado"
    );
    assert_eq!(
        rel.maior_grande, 5_000,
        "não pode regredir para o valor do último id processado"
    );
}

/// Fix 3 (validation.md, ORC-02 boundary): exatamente `ORCAMENTO_SMALL` não é reprocessado;
/// um byte a mais já é.
#[test]
fn small_no_limite_exato_nao_e_reprocessado_um_byte_a_mais_e() {
    let dir = dir_temp("limite-exato");
    escrever_origem(&dir, 6100, &bytes_webp(ORCAMENTO_SMALL), &bytes_webp(1_000));
    escrever_origem(
        &dir,
        6101,
        &bytes_webp(ORCAMENTO_SMALL + 1),
        &bytes_webp(1_000),
    );

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[6100], &dir, &mut p).unwrap();
    assert_eq!(
        rel.reprocessadas, 0,
        "exatamente no limite não deve recodificar"
    );
    assert_eq!(
        p.ler(&chave_small(6100)).unwrap().unwrap().len(),
        ORCAMENTO_SMALL
    );

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[6101], &dir, &mut p).unwrap();
    assert_eq!(
        rel.reprocessadas, 1,
        "um byte acima do limite já recodifica"
    );
}

/// Fix 1 (validation.md): assinatura inválida em QUALQUER uma das duas chaves marca o id inteiro
/// como `falhas` (unidade atômica — as duas chaves sobem juntas ou nenhuma sobe); mesmo que a
/// small também estivesse acima do orçamento, o id nunca aparece em `reprocessadas`.
#[test]
fn grande_invalida_marca_falha_mesmo_com_small_acima_do_orcamento() {
    let dir = dir_temp("grande-invalida-small-grande");
    let small_grande_demais = webp_ruido(400, 400);
    assert!(small_grande_demais.len() > ORCAMENTO_SMALL);
    let grande_invalida = vec![0xFF, 0xD8, 0xFF, 0xE0, 0, 0, 0, 0, 0, 0, 0, 0];
    escrever_origem(&dir, 6200, &small_grande_demais, &grande_invalida);

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[6200], &dir, &mut p).unwrap();

    assert_eq!(rel.falhas, vec![(6200, MotivoFalhaImagem::NaoWebp)]);
    assert_eq!(
        rel.reprocessadas, 0,
        "id atômico: falha barra o reprocessamento também"
    );
    assert_eq!(rel.publicadas, 0);
    assert!(!p.existe(&chave_small(6200)).unwrap());
    assert!(!p.existe(&chave_grande(6200)).unwrap());
}

/// ORC-03: imagem grande acima de 300 000 B publica sem alteração; `maior_grande` reflete o
/// maior tamanho publicado na execução.
#[test]
fn imagem_grande_acima_do_aviso_publica_sem_alteracao() {
    let dir = dir_temp("grande-acima-do-aviso");
    let grande = bytes_webp(AVISO_GRANDE + 50_000);
    escrever_origem(&dir, 7000, &bytes_webp(1_000), &grande);

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[7000], &dir, &mut p).unwrap();

    assert_eq!(p.ler(&chave_grande(7000)).unwrap(), Some(grande.clone()));
    assert_eq!(rel.maior_grande, grande.len() as u64);
}

/// REU-01: id já publicado (as duas chaves existem) é pulado mesmo com a origem "trocada" —
/// nunca compara conteúdo.
#[test]
fn id_ja_publicado_e_reaproveitado_mesmo_com_origem_trocada() {
    let dir = dir_temp("reaproveita");
    let original_pequena = bytes_webp(1_000);
    let original_grande = bytes_webp(1_000);
    escrever_origem(&dir, 8000, &original_pequena, &original_grande);

    let mut p = PublicadorMemoria::new();
    publicar_imagens(&[8000], &dir, &mut p).unwrap();
    let publicado_antes = p.ler(&chave_small(8000)).unwrap();

    // Origem muda depois da 1ª publicação: a 2ª chamada não deve nem ler o disco de novo.
    escrever_origem(&dir, 8000, &bytes_webp(2_000), &bytes_webp(2_000));
    let rel = publicar_imagens(&[8000], &dir, &mut p).unwrap();

    assert_eq!(rel.reaproveitadas, 1);
    assert_eq!(rel.publicadas, 0);
    assert_eq!(p.ler(&chave_small(8000)).unwrap(), publicado_antes);
}

/// Fix 2 (validation.md, REU-01 conjunction): só uma das duas chaves já existe no destino
/// (ex.: publicação anterior interrompida a meio) — não conta como reaproveitada; as duas
/// chaves saem gravadas ao final.
#[test]
fn apenas_uma_chave_existente_nao_e_reaproveitada() {
    let dir = dir_temp("uma-chave-existente");
    let pequena = bytes_webp(1_000);
    let grande = bytes_webp(1_000);
    escrever_origem(&dir, 8100, &pequena, &grande);

    let mut p = PublicadorMemoria::new();
    p.gravar(&chave_small(8100), &pequena, &META_IMAGEM)
        .unwrap();

    let rel = publicar_imagens(&[8100], &dir, &mut p).unwrap();

    assert_eq!(
        rel.reaproveitadas, 0,
        "só uma chave presente não deve contar como reaproveitada"
    );
    assert_eq!(rel.publicadas, 1);
    assert!(p.existe(&chave_small(8100)).unwrap());
    assert!(p.existe(&chave_grande(8100)).unwrap());
}

/// REU-02: pasta ausente e pasta com só um dos dois arquivos viram `sem_origem`, sem erro.
#[test]
fn sem_pasta_ou_com_um_so_arquivo_conta_sem_origem() {
    let dir = dir_temp("sem-origem");
    // 8100: pasta nunca criada.
    // 8101: pasta criada, só o arquivo grande.
    let pasta_parcial = dir.join("8101");
    std::fs::create_dir_all(&pasta_parcial).unwrap();
    std::fs::write(pasta_parcial.join("8101.webp"), bytes_webp(1_000)).unwrap();

    let mut p = PublicadorMemoria::new();
    let rel = publicar_imagens(&[8100, 8101], &dir, &mut p).unwrap();

    assert_eq!(rel.sem_origem, 2);
    assert_eq!(rel.publicadas, 0);
    assert!(rel.falhas.is_empty());
    for id in [8100, 8101] {
        assert!(!p.existe(&chave_small(id)).unwrap());
        assert!(!p.existe(&chave_grande(id)).unwrap());
    }
}

/// REU-03: os 10 placeholders são publicados na 1ª chamada e reaproveitados na 2ª (mesmo com
/// a lista de ids vazia).
#[test]
fn placeholders_publicados_uma_vez_e_reaproveitados_depois() {
    let dir = dir_temp("placeholders");
    let mut p = PublicadorMemoria::new();

    publicar_imagens(&[], &dir, &mut p).unwrap();
    for area in Area::TODAS {
        assert!(p.existe(&chave_placeholder(area)).unwrap(), "{area:?}");
    }
    let gravacoes_1a_chamada = p.gravacoes().len();
    assert_eq!(gravacoes_1a_chamada, 10);

    publicar_imagens(&[], &dir, &mut p).unwrap();
    assert_eq!(
        p.gravacoes().len(),
        gravacoes_1a_chamada,
        "2ª chamada não deveria regravar nenhum placeholder"
    );
}

/// REU-04: segunda execução completa com os mesmos ids → 0 publicadas, todas reaproveitadas.
#[test]
fn segunda_execucao_completa_nao_publica_nada_de_novo() {
    let dir = dir_temp("segunda-execucao");
    let ids = [9000, 9001, 9002];
    for id in ids {
        escrever_origem(&dir, id, &bytes_webp(1_000), &bytes_webp(1_000));
    }

    let mut p = PublicadorMemoria::new();
    let primeira = publicar_imagens(&ids, &dir, &mut p).unwrap();
    assert_eq!(primeira.publicadas, ids.len() as u64);

    let segunda = publicar_imagens(&ids, &dir, &mut p).unwrap();
    assert_eq!(segunda.publicadas, 0);
    assert_eq!(segunda.reaproveitadas, ids.len() as u64);
}

/// Espiona `PublicadorMemoria` contando chamadas a `existem`/`gravar_lote` (não a `existe`/
/// `gravar` unitários, que o default do trait chama por dentro). `existem` é `&self` no trait,
/// daí o `Cell`; `gravar_lote` é `&mut self`, um `u32` simples basta.
#[derive(Default)]
struct ContadorDeLotes {
    dentro: PublicadorMemoria,
    existem_chamadas: Cell<u32>,
    gravar_lote_chamadas: u32,
}

impl Publicador for ContadorDeLotes {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.dentro.listar(prefixo)
    }
    fn existem(&self, chaves: &[&str]) -> worker::publicador::Result<Vec<bool>> {
        self.existem_chamadas.set(self.existem_chamadas.get() + 1);
        chaves.iter().map(|c| self.dentro.existe(c)).collect()
    }
    fn gravar_lote(&mut self, itens: &[(String, Vec<u8>, Meta)]) -> worker::publicador::Result<()> {
        self.gravar_lote_chamadas += 1;
        for (chave, bytes, meta) in itens {
            self.dentro.gravar(chave, bytes, meta)?;
        }
        Ok(())
    }
}

/// Revisão do dono (BSV-13): 5000 ids devem gerar poucas dezenas de chamadas de
/// `existem`/`gravar_lote` (blocos de 64 ids), não 20 000 chamadas unitárias de `existe`/
/// `gravar` (2 chaves × 2 operações × 5000).
#[test]
fn cinco_mil_ids_usam_no_maximo_80_chamadas_em_lote() {
    let dir = dir_temp("cinco-mil-lote");
    let ids: Vec<i64> = (1..=5000).collect();
    for &id in &ids {
        escrever_origem(&dir, id, &bytes_webp(1_000), &bytes_webp(1_000));
    }

    let mut p = ContadorDeLotes::default();
    let rel = publicar_imagens(&ids, &dir, &mut p).unwrap();

    assert_eq!(rel.publicadas, 5000);
    assert!(
        p.existem_chamadas.get() <= 80,
        "esperava <= 80 chamadas de existem (blocos de 64), teve {}",
        p.existem_chamadas.get()
    );
    assert!(
        p.gravar_lote_chamadas <= 80,
        "esperava <= 80 chamadas de gravar_lote, teve {}",
        p.gravar_lote_chamadas
    );
}

/// Desempenho: 5000 ids contra `PublicadorMemoria` (sem rede) em até 5 s — critério de aceite do
/// ticket. `#[ignore]`: instável sob carga no CI, roda localmente com `cargo test -- --ignored`.
#[test]
#[ignore = "desempenho; rodar localmente com cargo test -- --ignored"]
fn cinco_mil_ids_em_ate_5_segundos() {
    let dir = dir_temp("cinco-mil-desempenho");
    let ids: Vec<i64> = (1..=5000).collect();
    for &id in &ids {
        escrever_origem(&dir, id, &bytes_webp(1_000), &bytes_webp(1_000));
    }

    let mut p = PublicadorMemoria::new();
    let inicio = std::time::Instant::now();
    let rel = publicar_imagens(&ids, &dir, &mut p).unwrap();
    let tempo = inicio.elapsed();

    assert_eq!(rel.publicadas, 5000);
    assert!(tempo <= std::time::Duration::from_secs(5), "{tempo:?}");
}

/// Grava as duas chaves de cada id e os 10 placeholders direto no destino (sem `publicar_imagens`):
/// o destino "já tem tudo", como no 2º ciclo real.
fn destino_com_tudo(ids: &[i64]) -> PublicadorMemoria {
    let mut p = PublicadorMemoria::new();
    for &id in ids {
        p.gravar(&chave_small(id), b"s", &META_IMAGEM).unwrap();
        p.gravar(&chave_grande(id), b"g", &META_IMAGEM).unwrap();
    }
    for area in Area::TODAS {
        p.gravar(&chave_placeholder(area), b"p", &META_IMAGEM)
            .unwrap();
    }
    p
}

/// LST-01 (BSV-13b): 5000 ids já publicados → nenhuma checagem por chave, poucas listagens,
/// nada publicado e tudo reaproveitado.
#[test]
fn cinco_mil_ids_existentes_decididos_so_por_listagem() {
    let dir = dir_temp("lst-cinco-mil");
    let ids: Vec<i64> = (1..=5000).collect();
    let mut p = destino_com_tudo(&ids);
    let gravacoes_antes = p.gravacoes().len();

    let rel = publicar_imagens(&ids, &dir, &mut p).unwrap();

    assert_eq!(p.existe_chamadas(), 0, "existe chamado por imagens");
    assert_eq!(p.existem_chamadas(), 0, "existem chamado por imagens");
    assert!(
        p.listar_chamadas() <= 10,
        "esperava <= 10 listagens, teve {}",
        p.listar_chamadas()
    );
    assert_eq!(rel.publicadas, 0);
    assert_eq!(rel.reaproveitadas, 5000);
    assert_eq!(
        p.gravacoes().len(),
        gravacoes_antes,
        "nada deveria ser gravado"
    );
}

/// LST-02 + LST-03 (BSV-13b): id sem chave nenhuma e id com só uma das duas chaves (cada uma das
/// duas possibilidades) → publicados, com as duas chaves gravadas nesta execução.
#[test]
fn id_novo_e_id_com_uma_so_chave_gravam_as_duas() {
    let dir = dir_temp("lst-novo-e-parcial");
    for id in [7001, 7002, 7003] {
        escrever_origem(&dir, id, &bytes_webp(1_000), &bytes_webp(2_000));
    }
    let mut p = destino_com_tudo(&[]);
    p.gravar(&chave_small(7002), b"s", &META_IMAGEM).unwrap();
    p.gravar(&chave_grande(7003), b"g", &META_IMAGEM).unwrap();
    let antes = p.gravacoes().len();

    let rel = publicar_imagens(&[7001, 7002, 7003], &dir, &mut p).unwrap();

    assert_eq!(rel.publicadas, 3);
    assert_eq!(rel.reaproveitadas, 0);
    let novas: Vec<&str> = p.gravacoes()[antes..].iter().map(String::as_str).collect();
    for id in [7001, 7002, 7003] {
        assert!(
            novas.contains(&chave_small(id).as_str()),
            "{id} small: {novas:?}"
        );
        assert!(
            novas.contains(&chave_grande(id).as_str()),
            "{id} grande: {novas:?}"
        );
        assert_eq!(p.ler(&chave_small(id)).unwrap().unwrap().len(), 1_000);
        assert_eq!(p.ler(&chave_grande(id)).unwrap().unwrap().len(), 2_000);
    }
}

/// LST-04 (BSV-13b): placeholder listado não é regravado; o ausente é gravado.
#[test]
fn placeholder_existente_nao_e_reenviado_e_ausente_e_enviado() {
    let dir = dir_temp("lst-placeholder");
    let mut p = PublicadorMemoria::new();
    let ausente = Area::Pets;
    for area in Area::TODAS.into_iter().filter(|a| *a != ausente) {
        p.gravar(&chave_placeholder(area), b"p", &META_IMAGEM)
            .unwrap();
    }
    let antes = p.gravacoes().len();

    publicar_imagens(&[], &dir, &mut p).unwrap();

    assert_eq!(
        &p.gravacoes()[antes..],
        [chave_placeholder(ausente)],
        "só o placeholder ausente deveria subir"
    );
    assert_eq!(p.existe_chamadas() + p.existem_chamadas(), 0);
}

/// LST-06 (BSV-13b): chaves fora de `{id}.webp`/`{id}-small.webp` são contadas, não valem como
/// imagem de nenhum id e não são removidas.
#[test]
fn chaves_estranhas_contadas_ignoradas_e_mantidas() {
    let dir = dir_temp("lst-estranhas");
    escrever_origem(&dir, 5412, &bytes_webp(1_000), &bytes_webp(1_000));
    let estranhas = [
        "img/ofertas/5412_small.webp",
        "img/ofertas/5412.jpg",
        "img/ofertas/abc.webp",
        "img/ofertas/5412/5412.webp",
    ];
    let mut p = destino_com_tudo(&[]);
    for c in estranhas {
        p.gravar(c, b"x", &META_IMAGEM).unwrap();
    }
    // Só a grande "de verdade": a `_small` estranha não pode completar o par.
    p.gravar(&chave_grande(5412), b"g", &META_IMAGEM).unwrap();

    let rel = publicar_imagens(&[5412], &dir, &mut p).unwrap();

    assert_eq!(rel.chaves_estranhas, estranhas.len() as u64);
    assert_eq!(rel.publicadas, 1);
    assert_eq!(rel.reaproveitadas, 0);
    assert!(p.remocoes().is_empty());
    for c in estranhas {
        assert!(p.existe(c).unwrap(), "{c} foi removida");
    }
}
