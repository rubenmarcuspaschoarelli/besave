//! CIC-01..06: execuções sucessivas de `gerar` sobre o mesmo `PublicadorMemoria`.

mod comum;

use std::time::{Duration, Instant};

use comum::{AGORA, DIA, dir_imagens_vazio, linha, linhas_fixture, mapeamento};
use worker::conversao::LinhaOferta;
use worker::fonte::FakeFonte;
use worker::geracao::{ErroGeracao, Relatorio, gerar};
use worker::mapeamento::Mapeamento;
use worker::modelo::Manifest;
use worker::publicador::{Publicador, PublicadorMemoria};
use worker::redirects::{Redirects, RedirectsMemoria};
use worker::site::ConfigSite;

fn rodar(
    linhas: &[LinhaOferta],
    p: &mut PublicadorMemoria,
    m: &Mapeamento,
    agora: i64,
) -> Result<Relatorio, ErroGeracao> {
    rodar_com(linhas, p, &mut RedirectsMemoria::new(), m, agora)
}

fn rodar_com(
    linhas: &[LinhaOferta],
    p: &mut PublicadorMemoria,
    kvs: &mut RedirectsMemoria,
    m: &Mapeamento,
    agora: i64,
) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas.to_vec(), vec![], agora),
        m,
        p,
        kvs,
        &dir_imagens_vazio(),
        &ConfigSite::default(),
        agora,
    )
}

fn manifest(p: &PublicadorMemoria) -> Manifest {
    serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap()
}

fn arquivo(m: &Manifest, n: u64) -> String {
    m.chunks.iter().find(|c| c.n == n).unwrap().arquivo.clone()
}

/// Ofertas já no ar: `DT_PUBLICACAO_SITE` gravada (BSV-36). "Sem mudança no Oracle" inclui a coluna;
/// com ela nula, o `dp` acompanharia o relógio de cada execução (o `UPDATE` não roda em `gerar`).
fn no_ar(v: Vec<LinhaOferta>) -> Vec<LinhaOferta> {
    v.into_iter()
        .map(|l| LinhaOferta {
            dt_publicacao_site: Some(AGORA - 1800),
            ..l
        })
        .collect()
}

/// Chunks 1, 5 (fixture) e 7.
fn fonte() -> Vec<LinhaOferta> {
    let mut v = linhas_fixture();
    v.extend([linha(1001), linha(7001)]);
    no_ar(v)
}

/// Chaves gravadas a partir do índice `desde` do histórico.
fn gravadas(p: &PublicadorMemoria, desde: usize) -> Vec<String> {
    p.gravacoes()[desde..].to_vec()
}

#[test]
fn segunda_execucao_sem_mudanca_nao_grava_nem_remove_chunk() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    let r1 = rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    assert_eq!(r1.chunks_escritos, 3);
    let marca = p.gravacoes().len();

    let r2 = rodar(&fonte(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r2.chunks_escritos, 0);
    assert_eq!(r2.chunks_removidos, 0);
    assert_eq!(r2.chunks_reaproveitados, 3);
    assert_eq!(
        gravadas(&p, marca),
        vec!["manifest.prev.json", "manifest.json"]
    );
    assert_eq!(p.listar("data/chunks/").unwrap().len(), 3);
}

#[test]
fn mudanca_no_chunk_5_regrava_so_ele_e_antigo_sai_na_terceira() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    let m1 = manifest(&p);
    let antigo_5 = arquivo(&m1, 5);

    let mut alterada = fonte();
    alterada[1].preco_por = Some(79.90); // 5413
    let marca = p.gravacoes().len();
    let r2 = rodar(&alterada, &mut p, &m, AGORA + 600).unwrap();
    let m2 = manifest(&p);
    let novo_5 = arquivo(&m2, 5);

    assert_ne!(novo_5, antigo_5);
    assert_eq!(r2.chunks_escritos, 1);
    // BSV-21: o preço aparece na página, então só a página de 5413 e o índice acompanham o chunk.
    assert_eq!(
        gravadas(&p, marca),
        vec![
            novo_5.clone(),
            "oferta/5413/index.html".into(),
            "_estado/paginas.json".into(),
            "manifest.prev.json".into(),
            "manifest.json".into()
        ]
    );
    assert_eq!(arquivo(&m2, 1), arquivo(&m1, 1));
    assert_eq!(arquivo(&m2, 7), arquivo(&m1, 7));
    // O manifest anterior ainda aponta para o antigo: fica mais um ciclo.
    assert_eq!(r2.chunks_removidos, 0);
    assert!(p.existe(&antigo_5).unwrap());

    let r3 = rodar(&alterada, &mut p, &m, AGORA + 1200).unwrap();
    assert_eq!(r3.chunks_removidos, 1);
    assert_eq!(r3.chunks_escritos, 0);
    assert!(!p.existe(&antigo_5).unwrap());
    assert!(p.existe(&novo_5).unwrap());
    assert_eq!(p.listar("data/chunks/").unwrap(), {
        let mut v: Vec<String> = m2.chunks.iter().map(|c| c.arquivo.clone()).collect();
        v.sort();
        v
    });
}

#[test]
fn manifest_prev_e_copia_do_anterior() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&fonte(), &mut p, &m, AGORA).unwrap();
    assert!(!p.existe("manifest.prev.json").unwrap());
    let primeiro = p.ler("manifest.json").unwrap().unwrap();

    rodar(&fonte(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(p.ler("manifest.prev.json").unwrap().unwrap(), primeiro);
    assert_ne!(p.ler("manifest.json").unwrap().unwrap(), primeiro);
}

#[test]
fn expurgo_muda_hash_e_faixa_vazia_some() {
    let m = mapeamento();
    let desativada_ha_6_dias = |l: LinhaOferta| LinhaOferta {
        ativo: false,
        dt_desativacao: Some(AGORA - 6 * DIA),
        ..l
    };
    let mut linhas = fonte();
    linhas[2] = desativada_ha_6_dias(linhas[2].clone()); // 5420
    linhas.push(desativada_ha_6_dias(linha(9001))); // sozinha no chunk 9
    let mut p = PublicadorMemoria::new();
    rodar(&linhas, &mut p, &m, AGORA).unwrap();
    let m1 = manifest(&p);
    assert!(m1.chunks.iter().any(|c| c.n == 9));

    // 2 dias depois as duas passam de 7 dias desativadas e saem da fonte.
    rodar(&linhas, &mut p, &m, AGORA + 2 * DIA).unwrap();
    let m2 = manifest(&p);
    let c5 = m2.chunks.iter().find(|c| c.n == 5).unwrap();
    assert_ne!(c5.arquivo, arquivo(&m1, 5));
    assert_eq!(c5.ids, [5412, 5413]);
    assert!(m2.chunks.iter().all(|c| c.n != 9));
}

#[test]
fn manifest_anterior_invalido_falha_sem_gravar() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    p.gravar(
        "manifest.json",
        b"{nao e json",
        &worker::publicador::META_MANIFEST,
    )
    .unwrap();
    let erro = rodar(&fonte(), &mut p, &m, AGORA).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ManifestAnteriorInvalido(_)),
        "{erro:?}"
    );
    assert_eq!(p.gravacoes(), ["manifest.json"]);
}

/// 30 000 cards válidos, 31 faixas de id.
fn trinta_mil() -> Vec<LinhaOferta> {
    (1..=30_000)
        .map(|id| LinhaOferta {
            titulo: Some(format!(
                "Produto {id} linha {} modelo {} com garantia",
                id % 97,
                id % 13
            )),
            preco_por: Some(10.0 + (id % 500) as f64),
            ..linha(id)
        })
        .collect()
}

/// CIC-06, parte funcional: gera, valida e conta; sem limite de tempo (roda no CI).
#[test]
fn trinta_mil_cards_geram_31_chunks() {
    let mut p = PublicadorMemoria::new();
    let rel = rodar(&trinta_mil(), &mut p, &mapeamento(), AGORA).unwrap();
    assert_eq!(rel.validas, 30_000);
    let m = manifest(&p);
    assert_eq!(m.total_ofertas, 30_000);
    assert_eq!(m.chunks.len(), 31);
    assert_eq!(m.chunks.iter().map(|c| c.qtd).sum::<u64>(), 30_000);
}

/// CIC-06, parte de desempenho: instável sob carga no CI, então fica fora do check obrigatório.
/// Rodar localmente com `cargo test -- --ignored`.
#[test]
#[ignore = "desempenho; rodar localmente com cargo test -- --ignored"]
fn trinta_mil_cards_em_ate_30_segundos() {
    let linhas = trinta_mil();
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    let inicio = Instant::now();
    rodar(&linhas, &mut p, &m, AGORA).unwrap();
    let tempo = inicio.elapsed();
    assert!(tempo <= Duration::from_secs(30), "{tempo:?}");
}

#[test]
fn manifest_anterior_json_sem_forma_de_manifest_falha_sem_gravar() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    p.gravar(
        "manifest.json",
        br#"{"versao":1}"#,
        &worker::publicador::META_MANIFEST,
    )
    .unwrap();
    let erro = rodar(&fonte(), &mut p, &m, AGORA).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ManifestAnteriorInvalido(_)),
        "{erro:?}"
    );
    assert_eq!(p.gravacoes(), ["manifest.json"]);
}

/// ORD-05: oferta expurgada perde a chave na KVS; segunda execução sem mudança não escreve.
#[test]
fn expurgo_apaga_a_chave_na_kvs() {
    let m = mapeamento();
    let mut linhas = fonte();
    linhas[2] = LinhaOferta {
        ativo: false,
        dt_desativacao: Some(AGORA - 6 * DIA),
        ..linhas[2].clone()
    }; // 5420
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA).unwrap();
    assert!(kvs.listar().unwrap().contains_key(&5420));

    let r = rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA + 600).unwrap();
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 0));

    let r = rodar_com(&linhas, &mut p, &mut kvs, &m, AGORA + 2 * DIA).unwrap();
    assert_eq!((r.redirects.puts, r.redirects.dels), (0, 1));
    assert_eq!(
        kvs.listar().unwrap().into_keys().collect::<Vec<_>>(),
        [1001, 5412, 5413, 7001]
    );
}

// ---- BSV-21: páginas, CSS, sitemap, robots e índice no ciclo ----

fn texto(p: &PublicadorMemoria, chave: &str) -> String {
    String::from_utf8(
        p.ler(chave)
            .unwrap()
            .unwrap_or_else(|| panic!("sem {chave}")),
    )
    .unwrap()
}

/// Chaves do site (tudo que não é chunk, imagem nem manifest), na ordem gravada.
fn do_site(chaves: &[String]) -> Vec<String> {
    chaves
        .iter()
        .filter(|c| !c.starts_with("data/") && !c.starts_with("img/") && !c.starts_with("manifest"))
        .cloned()
        .collect()
}

/// SIT-01: primeira execução com as 3 ofertas das fixtures. O CSS é do deploy do site (BSV-30).
#[test]
fn primeira_execucao_publica_paginas_sitemap_robots_e_indice() {
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &mapeamento(), AGORA).unwrap();
    assert_eq!(
        do_site(p.gravacoes()),
        [
            "oferta/5412/index.html",
            "oferta/5413/index.html",
            "oferta/5420/index.html",
            "sitemap-1.xml",
            "sitemap.xml",
            "robots.txt",
            "_estado/paginas.json",
            // BSV-12c: índice da KVS, gravado na sincronização (antes do manifest).
            "_estado/redirects.json",
        ]
    );
    assert!(!p.existe("assets/besave.css").unwrap());
    assert_eq!(texto(&p, "robots.txt"), "User-agent: *\nDisallow: /\n");
    let estado: serde_json::Value =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    for id in ["5412", "5413", "5420"] {
        assert_eq!(estado[id].as_str().unwrap().len(), 16, "{estado}");
    }
    assert!(estado.get("_css").is_none(), "{estado}");
}

/// SIT-02: segunda execução sem mudança → só os manifests.
#[test]
fn segunda_execucao_sem_mudanca_nao_sobe_nada_do_site() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&no_ar(linhas_fixture()), &mut p, &m, AGORA).unwrap();
    let marca = p.gravacoes().len();
    let r2 = rodar(&no_ar(linhas_fixture()), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(gravadas(&p, marca), ["manifest.prev.json", "manifest.json"]);
    assert_eq!(r2.site.paginas.publicadas, 0);
    assert_eq!(r2.site.paginas.inalteradas, 3);
    assert!(!r2.site.robots_publicado && !r2.site.indice_gravado);
    assert_eq!(r2.site.sitemaps_publicados, 0);
}

/// SIT-03/SIT-04: ativa → encerrada sai do sitemap no mesmo ciclo e só a página dela sobe.
#[test]
fn oferta_encerrada_sai_do_sitemap_e_so_a_pagina_dela_sobe() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &m, AGORA).unwrap();
    let sitemap = texto(&p, "sitemap-1.xml");
    assert!(
        sitemap
            .contains("<loc>https://besave.com.br/oferta/5412/</loc><lastmod>2026-09-24</lastmod>")
    );
    assert!(sitemap.contains("<loc>https://besave.com.br/oferta/5413/</loc>"));
    assert!(!sitemap.contains("/oferta/5420/"), "encerrada no sitemap");

    let mut linhas = linhas_fixture();
    linhas[1].ativo = false; // 5413
    linhas[1].dt_desativacao = Some(AGORA);
    let marca = p.gravacoes().len();
    rodar(&linhas, &mut p, &m, AGORA + 600).unwrap();
    let novas = gravadas(&p, marca);
    let paginas: Vec<&String> = novas.iter().filter(|c| c.starts_with("oferta/")).collect();
    assert_eq!(paginas, ["oferta/5413/index.html"]);
    assert!(novas.contains(&"sitemap-1.xml".to_owned()), "{novas:?}");
    let sitemap = texto(&p, "sitemap-1.xml");
    assert!(!sitemap.contains("/oferta/5413/"), "{sitemap}");
    assert!(sitemap.contains("/oferta/5412/"), "{sitemap}");
    assert!(texto(&p, "oferta/5413/index.html").contains("noindex"));
}

/// SIT-05: oferta expurgada → página removida, fora do índice e do sitemap.
#[test]
fn oferta_expurgada_sai_da_pagina_do_indice_e_do_sitemap() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &m, AGORA).unwrap();
    assert!(p.existe("oferta/5412/index.html").unwrap());

    let linhas: Vec<LinhaOferta> = linhas_fixture()
        .into_iter()
        .filter(|l| l.id != 5412)
        .collect();
    let r2 = rodar(&linhas, &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r2.site.paginas.removidas, 1);
    assert!(p.remocoes().contains(&"oferta/5412/index.html".to_owned()));
    assert!(!p.existe("oferta/5412/index.html").unwrap());
    let estado: serde_json::Value =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    assert!(estado.get("5412").is_none(), "{estado}");
    assert!(estado.get("5413").is_some(), "{estado}");
    assert!(!texto(&p, "sitemap-1.xml").contains("/oferta/5412/"));
}

/// SIT-07: `sitemap-{n}.xml` que não é mais gerado sai do bucket.
#[test]
fn sitemap_que_nao_e_mais_gerado_e_removido() {
    let mut p = PublicadorMemoria::new();
    // Resto de uma execução anterior com mais de 45 000 ativas.
    p.gravar(
        "sitemap-2.xml",
        b"<urlset/>",
        &worker::publicador::META_SITEMAP,
    )
    .unwrap();
    let r = rodar(&linhas_fixture(), &mut p, &mapeamento(), AGORA).unwrap();
    assert_eq!(r.site.sitemaps_removidos, 1);
    assert_eq!(p.remocoes(), ["sitemap-2.xml"]);
    assert_eq!(
        p.listar("sitemap").unwrap(),
        ["sitemap-1.xml", "sitemap.xml"]
    );
    assert!(!texto(&p, "sitemap.xml").contains("sitemap-2.xml"));
}

/// SIT-11: índice ilegível conta como ausente: tudo sobe de novo e o ciclo termina.
#[test]
fn indice_ilegivel_reenvia_tudo_sem_abortar() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &m, AGORA).unwrap();
    p.gravar(
        "_estado/paginas.json",
        b"{nao e json",
        &worker::publicador::META_ESTADO,
    )
    .unwrap();
    let marca = p.gravacoes().len();
    let r = rodar(&linhas_fixture(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r.site.paginas.publicadas, 3);
    assert!(r.site.robots_publicado);
    assert_eq!(
        do_site(&gravadas(&p, marca)),
        [
            "oferta/5412/index.html",
            "oferta/5413/index.html",
            "oferta/5420/index.html",
            "sitemap-1.xml",
            "sitemap.xml",
            "robots.txt",
            "_estado/paginas.json",
        ]
    );
    let estado: serde_json::Value =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    assert!(estado.get("5412").is_some(), "{estado}");
    assert!(p.existe("manifest.json").unwrap());
}

/// SIT-11 + expurgo sem índice: com `_estado/paginas.json` corrompido, o conjunto anterior vem do
/// bucket (`listar("oferta/")`); a página órfã sai e o índice é reconstruído e regravado.
#[test]
fn indice_corrompido_reconstroi_do_bucket_e_remove_orfa() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &m, AGORA).unwrap();
    p.gravar(
        "oferta/9999/index.html",
        b"<html>orfa</html>",
        &worker::publicador::META_PAGINA,
    )
    .unwrap();
    p.gravar(
        "_estado/paginas.json",
        b"{nao e json",
        &worker::publicador::META_ESTADO,
    )
    .unwrap();
    let marca = p.gravacoes().len();

    let r = rodar(&linhas_fixture(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r.site.paginas.removidas, 1);
    assert_eq!(p.remocoes(), ["oferta/9999/index.html"]);
    assert!(!p.existe("oferta/9999/index.html").unwrap());
    assert_eq!(r.site.paginas.publicadas, 3);
    assert!(r.site.indice_gravado);
    assert!(gravadas(&p, marca).contains(&"_estado/paginas.json".to_owned()));
    let estado: serde_json::Value =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    assert!(estado.get("9999").is_none(), "{estado}");
    for id in ["5412", "5413", "5420"] {
        assert_eq!(estado[id].as_str().unwrap().len(), 16, "{estado}");
    }
}

/// O caminho de reconstrução é só para índice ausente/ilegível: com índice válido, uma página no
/// bucket que não está no índice não é tocada (nenhuma listagem de `oferta/` por execução).
#[test]
fn indice_valido_nao_lista_nem_remove_pagina_fora_dele() {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &m, AGORA).unwrap();
    p.gravar(
        "oferta/9999/index.html",
        b"<html>fora do indice</html>",
        &worker::publicador::META_PAGINA,
    )
    .unwrap();
    let r = rodar(&linhas_fixture(), &mut p, &m, AGORA + 600).unwrap();
    assert_eq!(r.site.paginas.removidas, 0);
    assert!(p.remocoes().is_empty());
    assert!(p.existe("oferta/9999/index.html").unwrap());
}

fn rodar_site(
    linhas: &[LinhaOferta],
    p: &mut PublicadorMemoria,
    site: &ConfigSite,
    agora: i64,
) -> Relatorio {
    gerar(
        &FakeFonte::new(linhas.to_vec(), vec![], agora),
        &mapeamento(),
        p,
        &mut RedirectsMemoria::new(),
        &dir_imagens_vazio(),
        site,
        agora,
    )
    .unwrap()
}

/// SIT-08/SIT-09 na virada de DNS: `BESAVE_INDEXAVEL` e a base mudam → robots, sitemaps e índice
/// sobem de novo com o conteúdo novo; páginas não mudam.
#[test]
fn virada_para_indexavel_regrava_robots_e_sitemaps() {
    let mut p = PublicadorMemoria::new();
    rodar_site(&linhas_fixture(), &mut p, &ConfigSite::default(), AGORA);
    assert_eq!(texto(&p, "robots.txt"), "User-agent: *\nDisallow: /\n");
    let marca = p.gravacoes().len();
    let novo = ConfigSite {
        base: "https://www.besave.com.br".into(),
        indexavel: true,
    };
    let r = rodar_site(&linhas_fixture(), &mut p, &novo, AGORA + 600);
    assert_eq!(
        do_site(&gravadas(&p, marca)),
        [
            "sitemap-1.xml",
            "sitemap.xml",
            "robots.txt",
            "_estado/paginas.json"
        ]
    );
    assert!(r.site.robots_publicado);
    assert_eq!(
        texto(&p, "robots.txt"),
        "User-agent: *\nAllow: /\n\nSitemap: https://www.besave.com.br/sitemap.xml\n"
    );
    assert!(
        texto(&p, "sitemap-1.xml").contains("<loc>https://www.besave.com.br/oferta/5412/</loc>")
    );
}

/// BSV-30 (WRK-02): índice antigo com `_css` não faz o worker publicar CSS; a chave some do índice.
#[test]
fn indice_antigo_com_css_nao_publica_css() {
    let mut p = PublicadorMemoria::new();
    rodar(&linhas_fixture(), &mut p, &mapeamento(), AGORA).unwrap();
    let mut estado: serde_json::Map<String, serde_json::Value> =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    estado.insert("_css".into(), "0000000000000000".into());
    p.gravar(
        "_estado/paginas.json",
        &serde_json::to_vec(&estado).unwrap(),
        &worker::publicador::META_ESTADO,
    )
    .unwrap();
    let marca = p.gravacoes().len();
    let r = rodar(&linhas_fixture(), &mut p, &mapeamento(), AGORA + 600).unwrap();
    assert_eq!(r.site.paginas.publicadas, 0);
    assert_eq!(do_site(&gravadas(&p, marca)), ["_estado/paginas.json"]);
    assert!(!p.existe("assets/besave.css").unwrap());
    let novo: serde_json::Value =
        serde_json::from_slice(&p.ler("_estado/paginas.json").unwrap().unwrap()).unwrap();
    assert!(novo.get("_css").is_none(), "{novo}");
    assert_eq!(novo["5412"].as_str().unwrap().len(), 16);
}
